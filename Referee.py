import asyncio

import discord
from discord.ext import commands
import timeit
from config import config


bot = commands.Bot(command_prefix=config.commandPrefixes,
                   case_insensitive=True,
                   pm_help=None,
                   activity=discord.Game(name=config.status))


def main():
    """
    Main function, loads extension and starts the bot
    """
    for ext in config.extensions:
        bot.load_extension(f"extensions.{ext}")
        print(f"Loaded {ext}")

    bot.run(config.token)


@bot.event
async def on_ready():
    """
    On_ready eventhandler, gets called by api
    """
    bot.remove_command("help")
    print("Ready!")


@bot.command()
async def ping(ctx: commands.Context):
    """
    Basic command to check whether bot is alive

    :param ctx: Context object for the specific invoked ćommands
    """
    start = timeit.default_timer()
    title = "Pong. "
    embed = discord.Embed(title=title, color=discord.Color.dark_gold())
    msg = await ctx.send(embed=embed)  # type: discord.Message
    zoop = discord.utils.get(ctx.guild.emojis, name="zoop")
    dur = timeit.default_timer() - start
    embed.title += f"  |  {dur:.3}s"
    await msg.edit(embed=embed)
    await msg.add_reaction(zoop)

    def check(reaction, user):
        return user == ctx.author and reaction.emoji == zoop

    try:
        await bot.wait_for("reaction_add", check=check, timeout=120)
    except asyncio.TimeoutError:
        pass
    await msg.delete()
    await ctx.message.delete()


# noinspection PyUnusedLocal
@bot.command(aliases=["game"])
@commands.has_permissions(kick_members=True)
async def status(ctx: commands.Context, *, activity: str):
    """
    Changes the bots current discord activity
    :param ctx: Context object for the specific invoked ćommands
    :param activity: The string that will be displayed as activity
    """
    await bot.change_presence(activity=discord.Game(name=activity))

if __name__ == '__main__':
    main()
