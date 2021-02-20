import random
import os
import safe
import PIL
import PIL.Image
import PIL.ImageDraw
import PIL.ImageFont
import io
import core.settings
import urllib
import aiohttp
import asyncio
import traceback
import re
import imageutil
import core.help
import discord
import json
import struct
import time
from queuedict import QueueDict
from open_relative import *
from discord.ext.commands import command, Cog
from utils import is_private, MessageEditGuard
from contextlib import suppress
from enum import IntEnum

core.help.load_from_file('./help/latex.md')

DELETE_EMOJI = '🗑'

class LatexCodes(IntEnum):
	png = 0
	texError = 1

# Load data from external files
def load_template():
	with open_relative('template.tex', encoding = 'utf-8') as f:
		raw = f.read()
	# Remove any comments from the template
	cleaned = re.sub(r'%.*\n', '', raw)
	return cleaned

TEMPLATE = load_template()

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


class LatexModule(Cog):

	def __init__(self, bot):
		self.bot = bot

	@command(aliases=['latex', 'rtex', 'texw', 'wtex'])
	@core.settings.command_allowed('c-tex')
	async def tex(self, context, *, latex=''):
		await self.handle(context.message, latex, math_mode=False)

	@command(aliases=['ptex'])
	@core.settings.command_allowed('c-tex')
	async def texp(self, context, *, latex=''):
		await self.handle(context.message, latex, math_mode=True)

	@Cog.listener()
	async def on_message_discarded(self, message):
		if not message.author.bot and message.content.count('$$') >= 2 and not message.content.startswith('=='):
			if is_private(message.channel) or (await self.bot.settings.resolve_message('c-tex', message) and await self.bot.settings.resolve_message('f-inline-tex', message)):
				latex = extract_inline_tex(message.clean_content)
				if latex != '':
					await self.handle(message, latex, math_mode=True)

	async def handle(self, message, source, math_mode):
		if source == '':
			await message.channel.send('Type `=help tex` for information on how to use this command.')
		else:
			print(json.dumps({
				"author_id": message.author.id,
				"content": source
			}))
			colour_back, colour_text = await self.get_colours(message.author)
			latex = TEMPLATE.replace('#COLOR_BACK',  colour_back) \
			             		.replace('#COLOR_TEXT', colour_text) \
			             		.replace('#CONTENT', process_latex(source, math_mode))
			await self.render_and_reply(
				message,
				latex,
				colour_back
			)

	async def render_and_reply(self, message, latex, colour_back):
		with MessageEditGuard(message, message.channel, self.bot) as guard:
			async with message.channel.typing():
				sent_message = None
				try:
					render_result = await self.generate_image_online(latex)
				except asyncio.TimeoutError:
					sent_message = await guard.send(LATEX_TIMEOUT_MESSAGE)
				except RenderingError as e:
					err = e.log is not None and re.search(r'^!.*?^!', e.log + '\n!', re.MULTILINE + re.DOTALL)
					if err and len(err[0]) < 1000:
						m = err[0].strip("!\n")
						sent_message = await guard.send(f'Rendering failed. Check your code. You may edit your existing message.\n\n**Error Log:**\n```\n{m}\n```')
					else:
						sent_message = await guard.send('Rendering failed. Check your code. You can edit your existing message if needed.')
				else:
					sent_message = await guard.send(file=discord.File(render_result, 'latex.png'))
					if await self.bot.settings.resolve_message('f-tex-delete', message):
						try:
							await message.delete()
						except discord.errors.NotFound:
							pass
						except discord.errors.Forbidden:
							await guard.send('Failed to delete source message automatically - either grant the bot "Manage Messages" permissions or disable `f-tex-delete`')

				if sent_message and await self.bot.settings.resolve_message('f-tex-trashcan', message):
					with suppress(discord.errors.NotFound):
						await sent_message.add_reaction(DELETE_EMOJI)

	@Cog.listener()
	async def on_reaction_add(self, reaction, user):
		if not user.bot:
			if reaction.emoji == DELETE_EMOJI:
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

	async def generate_image_online(self, latex):
		hostname = self.bot.parameters.get('latex hostname')
		port = self.bot.parameters.get('latex port')
		time_render = time.perf_counter()
		reader, writer = await asyncio.open_connection(hostname, port)
		request_body = latex.encode()
		writer.write(struct.pack('<I', len(request_body)))
		writer.write(request_body)
		await writer.drain()
		response = await reader.read()
		writer.close()
		print('Render time', time.perf_counter() - time_render)
		if len(response) == 0:
			raise RenderingError(None)
		code, = struct.unpack('<I', response[:4])
		response_body = response[4:]
		if code == LatexCodes.texError:
			raise RenderingError(response_body.decode())
		if code != LatexCodes.png:
			raise RenderingError(response.decode())
		return io.BytesIO(response_body)

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
	bot.add_cog(LatexModule(bot))
