import configparser
import discord
from discord.ext import commands
import sys
import os
import logging
import logging.handlers
import timeit


CONFIG_FILE = "config/options.ini"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
prefix = config["Chat"].get("CommandPrefix")
auto_delete = config["Chat"].getboolean("DeleteMessages")
debug_level = config["Chat"].get("DebugLevel")

token = config["Credentials"].get("Token")
description = config["Credentials"].get("Description")

bot = commands.Bot(command_prefix=prefix,
                   case_insensitive=True,
                   pm_help=None,
                   description=description,
                   activity=discord.Game(name="ref!help"))


async def get_oauth_url():
    try:
        data = await bot.application_info()
    except Exception as e:
        return "Couldn't retrieve invite link. Error: {}".format(e)
    return discord.utils.oauth_url(data.id)


@bot.event
async def on_ready():
    url = await get_oauth_url()
    print(url)


@bot.command()
async def ping(ctx: commands.Context):
    start = timeit.default_timer()
    embed = discord.Embed(title="Pong.")
    msg = await ctx.send(embed=embed)  # type: discord.Message
    time = timeit.default_timer() - start
    embed.title += f"  |  {time:.3}s"
    await msg.edit(embed=embed)


def set_logger():

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


if __name__ == '__main__':
    set_logger()
    bot.run(token)
