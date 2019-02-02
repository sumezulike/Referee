import asyncio
import configparser
import discord
from discord.ext import commands
import sys
import os
import logging
import logging.handlers
import timeit
import time

import models
from WarningRepositorys import WarningRepository, JSONWarningRepository

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

database: WarningRepository = JSONWarningRepository(DATABASE_FILE)
watchlist = []

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


@bot.event
async def on_message(message: discord.Message):
    content = remove_formatting(message.content)
    if message.author.id == DYNO_ID:
        if "has been warned" in content:
            print(content)
            name, reason = content.split(" has been warned.", 1)
            name = name.split("> ")[1]
            member: discord.Member = await commands.MemberConverter().convert(await bot.get_context(message), name)

            warning = models.Warning(user_id=str(member.id),
                                     reason=reason,
                                     expiration_time=time.time() + warning_lifetime)

            await execute_warning(await bot.get_context(message), member, warning)
        elif "<:dynoSuccess:314691591484866560> Cleared" in content and "warnings for " in content:
            name = content[:-1].split("for ")[-1]
            member: discord.Member = await commands.MemberConverter().convert(await bot.get_context(message), name)
            with database as db:
                db.delete_warnings(member.id)
            await remove_warned_roles(member)

    elif message.author.id in watchlist:
        await message.add_reaction("👁")
        watchlist.remove(message.author.id)

    await bot.process_commands(message)


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.status != after.status:
        await check_warnings(after)


@bot.event
async def on_member_join(member: discord.Member):
    await check_warnings(member)
    with database as db:
        if db.get_warnings(member.id):
            await assign_warned_role(member)


async def execute_warning(ctx: commands.Context, member: discord.Member, warning: models.Warning):
    watchlist.append(member.id)
    await log_warning(warning)
    await check_warnings(member)
    num_warnings = await count_warnings(member)
    if num_warnings == 1:
        await assign_warned_role(member)
    elif num_warnings == 2:
        mute_time = 30 * 60
        await ctx.send(f"Second warning in {time_string(warning_lifetime)}:"
                       f" {member.mention} has been muted automatically for {time_string(mute_time)}")
        await mute(member, mute_time)
    elif num_warnings == 3:
        mute_time = 60 * 60 * 12
        await ctx.send(f"Third warning in {time_string(warning_lifetime)}:"
                       f" {member.mention} has been muted automatically for {time_string(mute_time)}")
        await mute(member, mute_time)


async def check_warnings(member: discord.Member):
    with database as db:
        warnings = db.get_warnings(str(member.id))
        if warnings:
            now = time.time()
            invalid = [w for w in warnings if w.expiration_time < now]
            for w in invalid:
                db.delete_warning(w)
            if invalid == warnings:
                await remove_warned_roles(member)


async def assign_warned_role(member: discord.Member):
    if member.top_role.position > member.guild.me.top_role.position:
        return

    if len(await get_warned_roles(member)) >= 2:
        return

    guild: discord.Guild = member.guild
    warning_color = discord.Colour.from_rgb(*get_darker_color(member.colour.to_rgb()))
    warned_roles = [r for r in guild.roles if r.name == warned_role_name and r.colour == warning_color]

    if not warned_roles:
        role = await guild.create_role(name=warned_role_name,
                                       colour=warning_color)
        await asyncio.sleep(0.5)
        await role.edit(position=max(member.top_role.position, 1))
    elif len(warned_roles) == 1:
        role = warned_roles[0]
    else:  # this should NEVER happen
        raise RuntimeError(f"Too many same-colored {warned_role_name} roles")

    await member.add_roles(role)


async def remove_warned_roles(member: discord.Member):
    warned_roles = await get_warned_roles(member)
    await member.remove_roles(*warned_roles)
    if member.id in watchlist:
        watchlist.remove(member.id)


async def get_warned_roles(member: discord.Member) -> list:
    warned_roles = [r for r in member.roles if r.name == warned_role_name]
    return warned_roles


async def count_warnings(member: discord.Member) -> int:
    with database as db:
        return len(db.get_warnings(member.id))

async def log_warning(warning: models.Warning):
    with database as db:
        db.put_warning(warning)


async def mute(member: discord.Member, mutetime: int = 30 * 60):
    muted_role = filter(lambda x: x.name == "Muted", member.guild.roles)
    await member.add_roles(*muted_role)
    await asyncio.sleep(mutetime)
    await member.remove_roles(*muted_role)


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


def get_darker_color(color: tuple) -> tuple:
    if color == (0, 0, 0):
        return 120, 100, 100
    return color[0] // 2, color[1] // 2, color[2] // 2


def remove_formatting(text: str) -> str:
    return text.replace("***", "").replace("\\_", "_").replace("\\*", "*").replace("\\\\", "\\")


def time_string(seconds: int) -> str:
    minutes = seconds // 60
    hours = minutes // 60
    days = hours // 24
    if seconds < 60:
        return f"{seconds}sec"
    elif minutes < 60:
        return f"{minutes}min" + (f"{seconds%60}sec" if seconds % 60 != 0 else "")
    elif hours < 24:
        return f"{hours}h" + (f"{minutes%60}min" if minutes % 60 != 0 else "")
    else:
        return f"{days} days" + (f"{hours%24}h" if hours % 24 != 0 else "")


@bot.command()
async def ping(ctx: commands.Context):
    start = timeit.default_timer()
    embed = discord.Embed(title="Pong.")
    msg = await ctx.send(embed=embed)  # type: discord.Message
    await msg.add_reaction("👍")
    dur = timeit.default_timer() - start
    embed.title += f"  |  {dur:.3}s"
    await msg.edit(embed=embed)


if __name__ == '__main__':
    main()
