import asyncio
import discord
from discord.ext import commands
import sys
import os
import logging
import logging.handlers
import timeit
from datetime import datetime, timedelta

from PGWarningRepository import PGWarningRepository
from config.Config import config

from models.refwarning import RefWarning

bot = commands.Bot(command_prefix=config.commandPrefixes,
                   case_insensitive=True,
                   pm_help=None,
                   activity=discord.Game(name="ref!ping"))


def main():

    # get extensions

    for ext in config.extensions:
        bot.load_extension(f"extensions.{ext}")
        print(f"Loaded {ext}")

    bot.run(config.token)


@bot.event
async def on_ready():
    bot.remove_command("help")
    bot.loop.create_task(bg_check())
    print("Ready!")

def set_logger() -> logging.Logger:
    if not os.path.exists("logs"):
        print("Creating logs folder...")
        os.makedirs("logs")

    logger = logging.getLogger("referee")
    logger.setLevel(logging.INFO)

    ref_format = logging.Formatter(
        '%(asctime)s %(levelname)s %(funcName)s %(lineno)d: '
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

    dpy_logger = logging.getLogger("discord")

    handler = logging.FileHandler(
        filename='logs/discord.log', encoding='utf-8', mode='a')
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(module)s %(funcName)s %(lineno)d: '
        '%(message)s',
        datefmt="[%d/%m/%Y %H:%M]"))
    dpy_logger.addHandler(handler)

    return logger


@commands.command()
async def ping(ctx: commands.Context):
    start = timeit.default_timer()
    title = "Pong. "
    embed = discord.Embed(title=title, color=discord.Color.dark_gold())
    msg = await ctx.send(embed=embed)  # type: discord.Message
    await msg.add_reaction(discord.utils.get(ctx.guild.emojis, name="zoop"))
    dur = timeit.default_timer() - start
    embed.title += f"  |  {dur:.3}s"
    await msg.edit(embed=embed)

if __name__ == '__main__':
    main()
