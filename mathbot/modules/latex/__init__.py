import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import io
import core.settings
import aiohttp
import asyncio
import re
import imageutil
import core.help
import discord
import json
import struct
import time
import collections
from queuedict import QueueDict
from open_relative import *
from discord.ext.commands import command, Cog, Context
from utils import is_private, MessageEditGuard
from contextlib import suppress
from enum import IntEnum

from discord import Message
from discord.ext.commands.hybrid import hybrid_command

core.help.load_from_file('./help/latex.md')

DELETE_EMOJI = '🗑'

class LatexCodes(IntEnum):
	ok = 0
	errTex = 1
	errGs = 2

with open_relative('replacements.json', encoding = 'utf-8') as _f:
	TEX_REPLACEMENTS = json.load(_f)


# Error messages

LATEX_TIMEOUT_MESSAGE = 'The renderer took too long to respond.'

PERMS_FAILURE = '''\
I don't have permission to upload images here :frowning:
The owner of this server should be able to fix this issue.
'''

DELETE_PERMS_FAILURE = '''\
The bot has been set up to delete `=tex` command inputs.
It requires the **manage messages** permission in order to do this.
'''


class RenderingError(Exception):
	def __init__(self, log):
		self.log = log

	def __str__(self):
		return f'RenderingError@{id(self)}'

	def __repr__(self):
		return f'RenderingError@{id(self)}'

class LatexPool:
	def __init__(self, bot):
		self.bot = bot
		self.pool = collections.deque()
		for _ in range(self.bot.parameters.get('latex pool')):
			self.add_conn()
		self.bot.loop.create_task(self.refresh())

	def add_conn(self):
		self.pool.append(self.bot.loop.create_task(self.connect()))

	async def refresh(self):
		while self.pool:
			await asyncio.sleep(60)
			_, writer = await self.get_conn()
			writer.close()
			await writer.wait_closed()

	async def connect(self):
		reader, writer = await asyncio.open_connection(
			self.bot.parameters.get('latex hostname'),
			self.bot.parameters.get('latex port'),
		)
		writer.write(b'\\begin{document}\n')
		await writer.drain()
		return reader, writer

	async def get_conn(self):
		self.add_conn()
		return await self.pool.popleft()

class MessagePretendingToBeAContext:

	def __init__(self, message: Message):
		self.message = message

	def __getattr__(self, name):
		if hasattr(self.message, name):
			return getattr(self.message, name)
		if hasattr(self.message.channel, name):
			return getattr(self.message.channel, name)
		return TypeError(f'MessagePretendingToBeAContext doesnt have a {name}')


class LatexModule(Cog):

	def __init__(self, bot):
		self.bot = bot
		self.pool = LatexPool(bot)

	@hybrid_command(aliases=['latex', 'rtex', 'texw', 'wtex'])
	@core.settings.command_allowed('c-tex')
	async def tex(self, context, *, latex=''):
		await self.handle(context.message, latex, math_mode=False)

	@hybrid_command(aliases=['ptex'])
	@core.settings.command_allowed('c-tex')
	async def texp(self, context, *, latex=''):
		await self.handle(context.message, latex, math_mode=True)

	@Cog.listener()
	async def on_message_discarded(self, message: Message):
		if not message.author.bot and message.content.count('$$') >= 2 and not message.content.startswith('=='):
			if is_private(message.channel) or (await self.bot.settings.resolve_message('c-tex', message) and await self.bot.settings.resolve_message('f-inline-tex', message)):
				latex = extract_inline_tex(message.clean_content)
				if latex != '':
					await self.handle(MessagePretendingToBeAContext(message), latex, math_mode=True)

	async def handle(self, message, source, math_mode):
		if source == '':
			await context.reply('Type `=help tex` for information on how to use this command.')
		else:
			print('latex render', message.author.id, source)
			colour_back, colour_text = await self.get_colours(message.author)
			latex = f'\\pagecolor[HTML]{{{colour_back}}}\\definecolor{{text}}{{HTML}}{{{colour_text}}}\\color{{text}}\\ctikzset{{color=text}}{process_latex(source, math_mode)}\n\\end{{document}}\n'
			await self.render_and_reply(message, latex)

	async def render_and_reply(self, message, latex):
		with MessageEditGuard(message, message.channel, self.bot) as guard:
			async with message.channel.typing():
				sent_message = None
				try:
					render_result = await self.generate_image(latex)
				except asyncio.TimeoutError:
					sent_message = await guard.reply(context, LATEX_TIMEOUT_MESSAGE)
				except RenderingError as e:
					err = e.log is not None and re.search(r'^\*?!.*?^!', e.log + '\n!', re.MULTILINE + re.DOTALL)
					if err:
						m = err[0].strip("!\n")
					else:
						m = e.log
					sent_message = await guard.send(f'Rendering failed. Check your code. You may edit your existing message.\n\n**Error Log:**\n```\n{m[:1800]}\n```')
				else:
					sent_message = await guard.send(file=discord.File(render_result, 'latex.png'))
					if await self.bot.settings.resolve_message('f-tex-delete', message):
						try:
							await context.message.delete()
						except discord.errors.NotFound:
							pass
						except discord.errors.Forbidden:
							await guard.reply(context, 'Failed to delete source message automatically - either grant the bot "Manage Messages" permissions or disable `f-tex-delete`')

				if sent_message and await self.bot.settings.resolve_message('f-tex-trashcan', context.message):
					with suppress(discord.errors.NotFound):
						await sent_message.add_reaction(DELETE_EMOJI)

	@Cog.listener()
	async def on_reaction_add(self, reaction, user):
		if not user.bot and reaction.emoji == DELETE_EMOJI:
			blame = await self.bot.keystore.get_json('blame', str(reaction.message.id))
			if blame is not None and blame['id'] == user.id:
				await reaction.message.delete()

	async def get_colours(self, user):
		colour_setting = await self.bot.keystore.get('p-tex-colour', str(user.id)) or 'light'
		if colour_setting == 'light':
			return 'ffffff', '202020'
		elif colour_setting == 'dark':
			return '36393F', 'f0f0f0'
		# Fallback in case of other weird things
		return 'ffffff', '202020'

	async def generate_image(self, latex, tries=0):
		if tries > self.bot.parameters.get('latex pool'):
			raise Exception('too many latex tries')
		writer = None
		try:
			reader, writer = await self.pool.get_conn()
			writer.write(latex.encode())
			await writer.drain()
			body = await asyncio.wait_for(reader.read(), timeout=5)
			if body == b'':
				raise Exception('empty body')
		except asyncio.TimeoutError:
			raise
		except:
			return await self.generate_image(latex, tries + 1)
		finally:
			if writer is not None:
				writer.close()
		code, = struct.unpack('!I', body[-4:])
		if code == LatexCodes.errTex:
			raise RenderingError(body[:-4].decode())
		if code != LatexCodes.ok:
			raise Exception('latex render: {body}')
		return io.BytesIO(body[:-4])

def extract_inline_tex(content):
	parts = iter(content.split('$$'))
	latex = ''
	try:
		while True:
			word = next(parts)
			if word != '':
				latex += word.replace('#', '\\#') \
						     .replace('$', '\\$') \
						     .replace('%', '\\%')
				latex += ' '
			word = next(parts)
			if word != '':
				latex += '$\\displaystyle {}$ '.format(word.strip('`'))
	except StopIteration:
		pass
	return latex.rstrip()


BLOCKFORMAT_REGEX = re.compile('^```(?:tex\n)?((?:.|\n)*)```$')

def process_latex(latex, math_mode):
	latex = latex.strip(' \n')
	blockformat = re.match(BLOCKFORMAT_REGEX, latex)
	if blockformat:
		latex = blockformat[1].strip(' \n')
	for key, value in TEX_REPLACEMENTS.items():
		if key in latex:
			latex = latex.replace(key, value)
	if not math_mode:
		latex = f'\\( \\displaystyle {latex} \\)'
	return latex


def setup(bot):
	return bot.add_cog(LatexModule(bot))
