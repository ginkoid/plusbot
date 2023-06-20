import core.settings
import re
import core.help
import discord
import json
import urllib.parse
import hmac
import base64
import aiohttp
from open_relative import *
from discord.ext.commands import Cog, Context
from utils import is_private, MessageEditGuard

from discord import Message
from discord.ext.commands.hybrid import hybrid_command

core.help.load_from_file('./help/latex.md')

DELETE_EMOJI = '🗑'

with open_relative('replacements.json', encoding = 'utf-8') as _f:
	TEX_REPLACEMENTS = json.load(_f)

# Error messages

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
		self.hmac_key = base64.urlsafe_b64decode(self.bot.parameters.get('latex hmac_key').encode() + b'==')
		self.session = aiohttp.ClientSession()

	@hybrid_command(aliases=['latex', 'rtex', 'texw', 'wtex'])
	@core.settings.command_allowed('c-tex')
	async def tex(self, context, *, latex=''):
		await self.handle(context, latex, math_mode=False)

	@hybrid_command(aliases=['ptex'])
	@core.settings.command_allowed('c-tex')
	async def texp(self, context, *, latex=''):
		await self.handle(context, latex, math_mode=True)

	@Cog.listener()
	async def on_message_discarded(self, message: Message):
		if not message.author.bot and message.content.count('$$') >= 2 and not message.content.startswith('=='):
			if is_private(message.channel) or (await self.bot.settings.resolve_message('c-tex', message) and await self.bot.settings.resolve_message('f-inline-tex', message)):
				latex = extract_inline_tex(message.clean_content)
				if latex != '':
					await self.handle(MessagePretendingToBeAContext(message), latex, math_mode=True)

	async def handle(self, context: Context, source, math_mode):
		if source == '':
			await context.reply('Type `=help tex` for information on how to use this command.')
		else:
			colour_back, colour_text = await self.get_colours(context.author)
			latex = f'\\pagecolor[HTML]{{{colour_back}}}\\definecolor{{text}}{{HTML}}{{{colour_text}}}\\color{{text}}\\ctikzset{{color=text}}{process_latex(source, math_mode)}'
			await self.render_and_reply(context, latex)

	async def render_and_reply(self, context: Context, latex):
		with MessageEditGuard(context.message, context.message.channel, self.bot) as guard:
			token = base64.urlsafe_b64encode(hmac.digest(self.hmac_key, latex.encode(), 'sha256')).rstrip(b'=').decode()
			url = f'https://tex.flag.sh/render/{urllib.parse.quote(latex)}?token={token}'
			task = self.bot.loop.create_task(guard.reply(context, url))
			try:
				async with self.session.get(url, timeout=10) as response:
					if response.status != 200:
						raise RenderingError(await response.text())
			except RenderingError as e:
				err = e.log is not None and re.search(r'^\*?!.*?^!', e.log + '\n!', re.MULTILINE + re.DOTALL)
				if err:
					m = err[0].strip("!\n")
				else:
					m = e.log
				message = await task
				await message.edit(content=f'Rendering failed. Check your code. You may edit your existing message.\n\n**Error Log:**\n```\n{m[:1800]}\n```')
			else:
				if await self.bot.settings.resolve_message('f-tex-delete', context.message):
					try:
						await context.message.delete()
					except discord.errors.NotFound:
						pass
					except discord.errors.Forbidden:
						await guard.reply(context, 'Failed to delete source message automatically - either grant the bot "Manage Messages" permissions or disable `f-tex-delete`')

	async def get_colours(self, user):
		colour_setting = await self.bot.keystore.get('p-tex-colour', str(user.id)) or 'light'
		if colour_setting == 'light':
			return 'ffffff', '202020'
		elif colour_setting == 'dark':
			return '36393F', 'f0f0f0'
		# Fallback in case of other weird things
		return 'ffffff', '202020'

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
