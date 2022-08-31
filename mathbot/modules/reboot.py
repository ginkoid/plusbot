from discord.ext.commands import command, Cog, Context
import subprocess
import modules.reporter

class Reboot(Cog):

	@command()
	async def sync_commands_global(self, ctx: Context):
		# TODO: Make this userid set in parameters.json
		if ctx.author.id == 133804143721578505:
			await ctx.send('Syncing global commands')
			async with ctx.typing():
				print('Syncing global commands...')
				await ctx.bot.tree.sync()
				print('Done')
				await ctx.send('Done')

def setup(bot):
	return bot.add_cog(Reboot())
