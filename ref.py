import asyncio
import configparser
import discord
from discord.ext import commands
import sys
import os
import logging
import logging.handlers
import timeit

import models

CONFIG_FILE = "config/options.ini"
DATABASE_FILE: str = "warnings.json"
DYNO_ID = 155149108183695360

config = configparser.ConfigParser()
config.read(CONFIG_FILE)
prefix = config["Chat"].get("CommandPrefix")
debug_level = config["Chat"].get("DebugLevel")

warned_role_name = config["Warnings"].get("WarnedRoleName")
warning_lifetime = int(config["Warnings"].get("WarningLifetime"))

token = config["Credentials"].get("Token")
description = config["Credentials"].get("Description")

database: models.WarningDB = models.JSONWarningDB(DATABASE_FILE)
watchlist =[]

bot = commands.Bot(command_prefix=prefix,
                   case_insensitive=True,
                   pm_help=None,
                   description=description,
                   activity=discord.Game(name="ref!ping"))


def main():
    bot.run(token)


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
            name, reason = content.split(" has been warned.", 1)
            name = name.split("> ")[1]
            member: discord.Member = await commands.MemberConverter().convert(await bot.get_context(message), name)

            warning = models.WarningObj(user_id=str(member.id), reason=reason)
            await execute_warning(member, warning)

    elif message.author.id in watchlist:
        await message.add_reaction("👁")
        watchlist.remove(message.author.id)

    await bot.process_commands(message)


async def execute_warning(member: discord.Member, warning: models.WarningObj):

    await log_warning(warning)
    await assign_warned_role(member)
    watchlist.append(member.id)


async def assign_warned_role(member: discord.Member):
    guild: discord.Guild = member.guild
    warning_color = discord.Colour.from_rgb(*get_darker_color(member.colour.to_rgb()))
    warned_roles = [r for r in guild.roles if r.name == warned_role_name and r.colour == warning_color]

    if not warned_roles:
        role = await guild.create_role(name=warned_role_name, colour=warning_color)
        await asyncio.sleep(0.5)
        await role.edit(position=max(member.top_role.position, 1))
    elif len(warned_roles) == 1:
        role = warned_roles[0]
    else:  # this should NEVER happen
        raise RuntimeError(f"Too many same-colored {warned_role_name} roles")

    await member.add_roles(role)


async def remove_warned_roles(member: discord.Member):
    pass


async def log_warning(warning: models.WarningObj):
    with database as db:
        db.put_warning(warning)


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


def get_darker_color(color: tuple):
    if color == (0, 0, 0):
        return 120, 100, 100
    return color[0]//2, color[1]//2, color[2]//2


if __name__ == '__main__':
    main()
