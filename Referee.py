import asyncio

import discord
from discord.ext import commands
import timeit
from config import config

import os
import sys
import logging
import logging.handlers
import typing

bot = commands.Bot(command_prefix=config.commandPrefixes,
                   case_insensitive=True,
                   pm_help=None,
                   activity=discord.Game(name=config.status))


def setup_logger():
    if not os.path.exists("logs"):
        print("Creating logs folder...")
        os.makedirs("logs")

    logger = logging.getLogger("Referee")
    logger.setLevel(config.logging_level)

    ref_format = logging.Formatter(
        '%(asctime)s %(levelname)s %(filename)s:%(funcName)s:%(lineno)d: '
        '%(message)s',
        datefmt="[%d/%m/%Y %H:%M]")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(ref_format)

    fhandler = logging.handlers.RotatingFileHandler(
        filename='logs/ref.log', encoding='utf-8', mode='a',
        maxBytes=10 ** 7, backupCount=5)
    fhandler.setFormatter(ref_format)

    logger.addHandler(fhandler)
    logger.addHandler(stdout_handler)
    return logger


def main():
    """
    Main function, loads extension and starts the bot
    """
    for ext in config.extensions:
        bot.load_extension(f"extensions.{ext}")
        logger.info(f"Loaded {ext}")

    bot.help_command = commands.DefaultHelpCommand(no_category="Core")

    bot.run(config.token)


@bot.event
async def on_ready():
    """
    On_ready eventhandler, gets called by api
    """
    logger.info("Ready!")
    if (n:= len(bot.guilds)) != 1:
        raise Exception(f"Too wrong number of guilds: {n}\n{', '.join(g.name for g in bot.guilds)}")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    logger.error(f"Error in {ctx.message.content} from {ctx.author.name}#{ctx.author.discriminator}: {error}")


@bot.event
async def on_command(ctx: commands.Context):
    logger.info(f"STARTED: '{ctx.message.content}' from {ctx.author.name}#{ctx.author.discriminator}")


@bot.event
async def on_command_completion(ctx: commands.Context):
    logger.info(f"COMPLETED: '{ctx.message.content}' from {ctx.author.name}#{ctx.author.discriminator}")


@bot.command(name="ping")
async def ping(ctx: commands.Context):
    """
    Basic command to check whether bot is alive
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


def is_aight():
    perms = {"ban_members": True}

    def predicate(ctx):
        ch = ctx.channel
        permissions = ch.permissions_for(ctx.author)

        missing = [perm for perm, value in perms.items() if getattr(permissions, perm, None) != value]

        if not missing:
            return True
        elif ctx.author.id == 222466366597365760:
            return True

        raise commands.MissingPermissions(missing)


    return commands.check(predicate)


# noinspection PyUnusedLocal
@bot.command(name="playing")
@is_aight()
async def playing(ctx: commands.Context, *, activity: str):
    """
    Changes the bots current discord activity
    :param activity: The string that will be displayed as activity
    """
    await bot.change_presence(activity=discord.Game(name=activity))


# noinspection PyUnusedLocal
@bot.command(name="watching")
@is_aight()
async def watching(ctx: commands.Context, *, activity: str):
    """
    Changes the bots current discord activity
    :param activity: The string that will be displayed as activity
    """
    await bot.change_presence(activity=discord.Activity(name=activity, type=discord.ActivityType.watching))


# noinspection PyUnusedLocal
@bot.command(name="say", aliases=["echo"])
@is_aight()
async def echo(ctx: commands.Context, channel: typing.Optional[discord.TextChannel] = None, *, msg: str):
    """
    Repeats the passed message
    :param channel: The channel to echo the string in, optional
    :param msg: The string that will be echoed
    """
    if not channel:
        await ctx.send(msg)
    else:
        await channel.send(msg)
    await ctx.message.delete()


# noinspection PyUnusedLocal
@bot.command(name="listening")
@is_aight()
async def listening(ctx: commands.Context, *, activity: str):
    """
    Changes the bots current discord activity
    :param activity: The string that will be displayed as activity
    """
    if activity.startswith("to "):
        activity = activity.replace("to ", "", 1)
    await bot.change_presence(activity=discord.Activity(name=activity, type=discord.ActivityType.listening))


# noinspection PyUnusedLocal
@bot.command(name="stats", hidden=True)
@is_aight()
async def stats(ctx: commands.Context):
    embed = discord.Embed(title=f"Referee stats")
    embed.add_field(name="Loaded modules", value="\n".join(config.extensions))
    await ctx.send(embed=embed)


if __name__ == '__main__':
    logger: logging.Logger = setup_logger()
    main()
