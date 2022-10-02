from discord.ext.commands import command, Cog, Context

class Reboot(Cog):
	def __init__(self, bot):
		self.bot = bot

	@command()
	async def sync_commands_global(self, ctx: Context):
		if ctx.author.id == self.bot.parameters.get('admin_id'):
			await ctx.send('Syncing global commands')
			async with ctx.typing():
				print('Syncing global commands...')
				await ctx.bot.tree.sync()
				print('Done')
				await ctx.send('Done')

def setup(bot):
	return bot.add_cog(Reboot(bot))
