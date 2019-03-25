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
from config.Config import Config

from models.refwarning import RefWarning


conf = Config("config/options.ini")

warning_lifetime = int(conf.warningLifetime)

bot = commands.Bot(command_prefix=conf.commandPrefixes,
                   case_insensitive=True,
                   pm_help=None,
                   description=conf.description,
                   activity=discord.Game(name="ref!ping"))

warning_db = PGWarningRepository()


def main():
    bot.run(conf.token)


@bot.event
async def on_ready():
    bot.remove_command("help")
    bot.loop.create_task(bg_check())
    print("Ready!")


async def bg_check():
    while not bot.is_ready():
        await asyncio.sleep(1)

    while not bot.is_closed():
        for guild in bot.guilds:
            await check_all_warnings(guild)
        await asyncio.sleep(60)  # task runs every minute


@bot.event
async def on_message(message: discord.Message):
    if message_is_warning(message):
        name, reason = get_name_reason(message)

        member: discord.Member = await commands.MemberConverter().convert(await bot.get_context(message), name)

        warning = RefWarning(user_id=str(member.id),
                             reason=reason,
                             timestamp=datetime.now(),
                             expiration_time=datetime.now() + timedelta(hours=warning_lifetime))

        await save_warning(warning)
        await execute_warning(await bot.get_context(message), member, warning)

    # Else, if the message is a clear
    elif message_is_clear(message):

        name = clean_content(message)[:-1].split("for ")[-1]
        member: discord.Member = await commands.MemberConverter().convert(await bot.get_context(message), name)
        await remove_warned_roles(member)

    await bot.process_commands(message)


def clean_content(message: discord.message) -> str:
    content = message.clean_content

    content = content.replace("***", "").replace("\\_", "_").replace("\\*", "*").replace("\\\\", "\\")

    return content


def message_is_warning(message: discord.message) -> bool:
    content = clean_content(message)
    if message.author.id == conf.dynoID:
        if "has been warned" in content:
            return True
    return False


def get_name_reason(message: discord.message) -> tuple:
    content = clean_content(message)
    name, reason = content.split(" has been warned.", 1)
    name = name.split("> ")[1]
    return name, reason


def message_is_clear(message: discord.message):
    content = clean_content(message)
    return "<:dynoSuccess:314691591484866560> Cleared" in content and "warnings for " in content


@bot.event
async def on_member_join(member: discord.Member):
    await check_warnings(member)


async def acknowledge(message: discord.Message):
    await message.add_reaction("👁")


async def execute_warning(ctx: commands.Context, member: discord.Member, warning: RefWarning):
    await check_warnings(member)
    num_warnings = len(warning_db.get_active_warnings(member.id))
    if num_warnings > 1:
        await ctx.channel.send(
            "{} has been warned {} times in the last {} hours".format(
                member.display_name,
                num_warnings,
                warning_lifetime
            )
        )


async def check_warnings(member: discord.Member):
    is_warned = bool(await get_warned_roles(member))

    active_warnings = warning_db.get_active_warnings(str(member.id))

    if active_warnings:
        if not is_warned:
            await assign_warned_role(member)
    elif is_warned:
        await remove_warned_roles(member)


async def check_all_warnings(guild):
    member_ids = warning_db.get_all_warnings().keys()
    for member_id in member_ids:
        await check_warnings(guild.get_member(int(member_id)))


async def assign_warned_role(member: discord.Member):
    if member.top_role.position > member.guild.me.top_role.position:
        return

    if len(await get_warned_roles(member)) >= 2:
        return

    guild: discord.Guild = member.guild
    warning_color = discord.Colour.from_rgb(*get_warned_color(member.colour.to_rgb()))
    warned_roles = filter(lambda r: r.name == conf.warnedRoleName and r.colour == warning_color, guild.roles)

    if not warned_roles:
        role = await guild.create_role(name=conf.warnedRoleName,
                                       colour=warning_color)
        await asyncio.sleep(0.5)
    else:
        role = warned_roles[0]

    if role.position <= member.top_role.position:
        await role.edit(position=max(member.top_role.position, 1))

    await member.add_roles(role)


async def remove_warned_roles(member: discord.Member):
    warned_roles = await get_warned_roles(member)
    await member.remove_roles(*warned_roles)


async def get_warned_roles(member: discord.Member) -> list:
    warned_roles = [r for r in member.roles if r.name == conf.warnedRoleName]
    return warned_roles


async def save_warning(warning: RefWarning):
    warning_db.put_warning(warning)


async def mute(member: discord.Member, mute_time: int = 30 * 60):
    muted_roles = filter(lambda x: x.name == "Muted", member.guild.roles)
    await member.add_roles(*muted_roles)
    await asyncio.sleep(mute_time)
    await member.remove_roles(*muted_roles)


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


def get_warned_color(color: tuple) -> tuple:
    def is_grey(c):
        return max([abs(c[0] - c[1]), abs(c[1] - c[2]), abs(c[0] - c[2])]) < 25

    new_color = (color[0] // 2, color[1] // 2, color[2] // 2)
    default_warned_color = (120, 100, 100)
    if sum(new_color) / 3 < 100 and is_grey(new_color):
        return default_warned_color
    else:
        return new_color


@bot.command()
async def ping(ctx: commands.Context):
    start = timeit.default_timer()
    embed = discord.Embed(title="Pong.")
    msg = await ctx.send(embed=embed)  # type: discord.Message
    await acknowledge(msg)
    dur = timeit.default_timer() - start
    embed.title += f"  |  {dur:.3}s"
    await msg.edit(embed=embed)


@bot.command()
@commands.has_permissions(kick_members=True)
async def warn(ctx: commands.Context, member: discord.Member, *reason):
    await execute_warning(
        ctx, member,
        RefWarning(
            member.id,
            reason=reason,
            timestamp=datetime.now(),
            expiration_time=datetime.now() + timedelta(hours=warning_lifetime)
        )
    )
    await acknowledge(ctx.message)


@bot.command()
@commands.has_permissions(kick_members=True)
async def clear(ctx: commands.Context, member: discord.Member):
    warning_db.expire_warnings(member.id)
    await remove_warned_roles(member)
    await acknowledge(ctx.message)


@bot.command()
@commands.has_permissions(kick_members=True)
async def warnings(ctx: commands.Context, member: discord.Member):

    all_warnings = warning_db.get_warnings(member.id)
    active_warnings = warning_db.get_active_warnings(member.id)

    title = "{}: {} warnings ({}) active".format(member.display_name, len(all_warnings), len(active_warnings))
    embed = discord.Embed(title=title)

    active_str = "".join("{} - {}\n Reason: {}".format(w.timestamp, w.expiration_time, w.reason) for w in active_warnings)
    embed.add_field(name="Active ({})".format(len(active_warnings)), value=active_str)

    expired_str = "".join("{} Reason: {}".format(w.timestamp, w.reason) for w in filter(lambda x: x.is_expired(), all_warnings))
    embed.add_field(name="Expired ({})".format(len(all_warnings)-len(active_warnings)), value=expired_str)

    await ctx.send(embed=embed)


@bot.command(aliases=["active"])
@commands.has_permissions(kick_members=True)
async def active_warnings(ctx: commands.Context):

    title = "Active warnings"
    embed = discord.Embed(title=title)

    active_warnings = warning_db.get_all_active_warnings()

    for member_id in active_warnings:
        warnings = warning_db.get_active_warnings(member_id)
        active_str = "".join("{} - {}\n Reason: {}".format(w.timestamp, w.expiration_time, w.reason) for w in warnings)
        embed.add_field(name=ctx.guild.get_member(member_id), value=active_str)

    await ctx.send(embed=embed)


if __name__ == '__main__':
    try:
        main()
    finally:
        warning_db.close()
