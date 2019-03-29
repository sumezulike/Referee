import asyncio

import discord
from discord.ext import commands
import timeit
from config.Config import config


bot = commands.Bot(command_prefix=config.commandPrefixes,
                   case_insensitive=True,
                   pm_help=None,
                   activity=discord.Game(name="ref!ping"))


def main():

    for ext in config.extensions:
        bot.load_extension(f"extensions.{ext}")
        print(f"Loaded {ext}")

    bot.run(config.token)


@bot.event
async def on_ready():
    bot.remove_command("help")
    print("Ready!")


@bot.command()
async def ping(ctx: commands.Context):
    start = timeit.default_timer()
    title = "Pong. "
    embed = discord.Embed(title=title, color=discord.Color.dark_gold())
    msg = await ctx.send(embed=embed)  # type: discord.Message
    zoop = discord.utils.get(ctx.guild.emojis, name="zoop")
    await msg.add_reaction(zoop)
    dur = timeit.default_timer() - start
    embed.title += f"  |  {dur:.3}s"
    await msg.edit(embed=embed)

    def check(reaction, user):
        return user == ctx.author and reaction.emoji == zoop

    try:
        reaction, user = await bot.wait_for("reaction_added", check=check, timeout=120)
    except asyncio.TimeoutError:
        pass
    await ctx.message.delete()




@bot.command(aliases=["game"])
@commands.has_permissions(kick_members=True)
async def status(ctx: commands.Context, *, status: str):
    await bot.change_presence(activity=discord.Game(name=status))

if __name__ == '__main__':
    main()
