from discord.ext.commands import command, Cog
import discord

TIER_NONE = 0
TIER_CONSTANT = 1
TIER_QUADRATIC = 2
TIER_EXPONENTIAL = 3
TIER_SPECIAL = 4


class InvalidPatronRankError(Exception):
	pass


class PatronageMixin:

	async def patron_tier(self, uid):
		if not isinstance(uid, (str, int)):
			raise TypeError('User ID looks invalid')
		return TIER_SPECIAL

	async def get_patron_listing(self):
		return 'nobody?'


class PatronModule(Cog):

	def __init__(self, bot):
		self.bot = bot

	@command()
	async def check_patronage(self, ctx):
		m = []
		tier = TIER_SPECIAL
		m.append(f'Your patronage tier is {get_tier_name(tier)}')
		if isinstance(ctx.channel, discord.TextChannel):
			m.append(f'The patrongage of this server\'s owner is {get_tier_name(tier)}')
		await ctx.send('\n'.join(m))

def get_tier_name(tier):
	try:
		return {
			TIER_NONE: 'None',
			TIER_CONSTANT: 'Constant',
			TIER_QUADRATIC: 'Quadratic',
			TIER_EXPONENTIAL: 'Exponential',
			TIER_SPECIAL: 'Ackermann'
		}[tier]
	except KeyError:
		raise InvalidPatronRankError

def setup(bot):
	return bot.add_cog(PatronModule(bot))
