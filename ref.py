import configparser
import discord
from discord.ext import commands
import sys
import os
import logging
import logging.handlers
import timeit

CONFIG_FILE = "config/options.ini"
DYNO_ID = 155149108183695360

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


@bot.event
async def on_ready():
    bot.remove_command("help")
    print("Ready!")


def remove_formatting(text: str):
    return text.replace("***", "").replace("\\_", "_").replace("\\*", "*").replace("\\\\", "\\")


@bot.event
async def on_message(message: discord.Message):
    content = remove_formatting(message.content)
    if message.author.id == DYNO_ID:
        if "has been warned" in content:
            print(content)
            name = content.split(" has been warned")[0]
            name = name.split("> ")[1]
            member = await commands.MemberConverter().convert(await bot.get_context(message), name)  # type: discord.Member
            await message.channel.send("Shame on you, {}".format(member.mention))
        await message.add_reaction("👁")
    await bot.process_commands(message)

async def execute_warning(member: discord.Member):

    await assign_warned_role(member)


async def assign_warned_role(member: discord.Member):
    pass

@bot.command()
async def ping(ctx: commands.Context):
    start = timeit.default_timer()
    embed = discord.Embed(title="Pong.")
    msg = await ctx.send(embed=embed)              # type: discord.Message
    await msg.add_reaction("👍")
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
    logger = set_logger()
    bot.run(token)
