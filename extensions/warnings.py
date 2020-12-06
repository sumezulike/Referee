import asyncio
import logging
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from Referee import can_kick
from config.config import Warnings as warnings_config
from db_classes.PGWarningDB import PGWarningDB
from models.warnings_models import RefWarning
from utils import emoji

logger = logging.getLogger("Referee")

punishments = {2: 4, 3: 24}


def get_warned_color(color: tuple) -> tuple:
    def is_grey(c):
        return max([abs(c[0] - c[1]), abs(c[1] - c[2]), abs(c[0] - c[2])]) < 25


    new_color = (color[0] // 2, color[1] // 2, color[2] // 2)
    if sum(new_color) / 3 < 100 and is_grey(new_color):
        return warnings_config.default_warned_color
    else:
        return new_color


class Warnings(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGWarningDB()
        self.guild: discord.Guild = None  # initialized in on_ready


    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.bg_check())
        self.guild = self.bot.guilds[0]


    async def bg_check(self):
        """
        Runs every 120 seconds to check whether warnings have expired
        """
        while not self.bot.is_ready():
            await asyncio.sleep(1)

        while not self.bot.is_closed():
            await self.check_all_members()
            await asyncio.sleep(120)  # task runs every second minute


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Called by api whenever a message is received.
        Checks for warnings and clears
        """
        if not message.guild:
            return

        if message.content.startswith("?warn "):
            logger.info(f"Identified warn command: '{message.content}' from "
                        f"{message.author.name}#{message.author.discriminator}")
            if message.author.top_role >= discord.utils.find(lambda m: m.name == 'Support', self.guild.roles):
                ctx = await self.bot.get_context(message)
                member = await discord.ext.commands.MemberConverter().convert(ctx=ctx,
                                                                              argument=message.content.split()[1])
                reason = message.content.split(" ", 2)[2]
                await self.warn(ctx=ctx, member=member, reason=reason)


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Checks on each join to make sure that members can't get rid of the warned role by leaving and rejoining
        """
        await self.check_warnings(member)


    @staticmethod
    def clean_content(message: discord.message) -> str:
        """
        Should be replaced by new discordpy util function
        """
        content = message.clean_content
        content = content.replace("***", "").replace("\\_", "_").replace("\\*", "*").replace("\\\\", "\\")
        return content


    @staticmethod
    def get_warned_roles(member: discord.Member) -> list:
        """
        Filters through a members roles to return only the ones related to warning
        """
        warned_roles = list(filter(lambda r: r.name == warnings_config.warned_role_name, member.roles))
        return warned_roles


    async def acknowledge(self, message: discord.Message):
        """
        Briefly adds an emoji to a message
        """
        await message.add_reaction(emoji.eye)
        await asyncio.sleep(1)
        await message.remove_reaction(emoji.eye, self.bot.user)


    # noinspection PyUnusedLocal
    async def enforce_punishments(self, ctx: commands.Context, member: discord.Member, warning: RefWarning):
        """
        This method checks a users number of active warnings and enacts the punishments

        """
        await self.check_warnings(member)
        num_warnings = len(await self.db.get_active_warnings(member.id))
        if num_warnings in punishments.keys():
            await ctx.channel.send(
                f"{member.display_name} has been warned {num_warnings}"
                f" times in the last {warnings_config.warning_lifetime} hours. "
                f"Automatically muting them for {punishments.get(num_warnings)} hours",
                delete_after=30
            )
            await self.mute(member, punishments.get(num_warnings) * 60 * 60)


    async def check_warnings(self, member: discord.Member):
        """
        This method compares a users roles to the status in the db and marks or unmarks them as warned
        """
        is_warned = bool(self.get_warned_roles(member))

        active_warnings = await self.db.get_active_warnings(member.id)

        if active_warnings:
            if not is_warned:
                await self.assign_warned_role(member)
        elif is_warned:
            await self.remove_warned_roles(member)


    async def check_all_members(self):
        """
        Checks the warnings for all members in a guiöd
        """
        for member in self.guild.members:
            await self.check_warnings(member)


    async def assign_warned_role(self, member: discord.Member):
        """
        Assigns a "warned" role to a member, if possible, and if necessary
        """
        if member.top_role.position > member.guild.me.top_role.position:
            return

        if self.get_warned_roles(member):
            return

        warning_color = discord.Colour.from_rgb(*get_warned_color(member.colour.to_rgb()))
        warned_roles = list(
            filter(lambda r: r.name == warnings_config.warned_role_name and r.colour == warning_color,
                   self.guild.roles))

        if not warned_roles:
            role = await self.guild.create_role(name=warnings_config.warned_role_name,
                                                colour=warning_color)
            await asyncio.sleep(0.5)
        else:
            role = warned_roles[0]

        if role.position <= member.top_role.position:
            await role.edit(position=max(member.top_role.position, 1))

        await member.add_roles(role)


    async def remove_warned_roles(self, member: discord.Member):
        """
        Removes all "warned" roles from a member
        """
        warned_roles = self.get_warned_roles(member)
        await member.remove_roles(*warned_roles)


    @staticmethod
    async def mute(member: discord.Member, mute_time_seconds: int):
        """
        Mutes a member for a certain timespan
        """
        muted_roles = discord.utils.get(member.guild.roles, name="Muted")
        if isinstance(muted_roles, list):
            muted_roles = muted_roles[0]
        await member.add_roles(muted_roles)
        await asyncio.sleep(mute_time_seconds)
        await member.remove_roles(*muted_roles)


    async def warning_str(self, warning: RefWarning, show_expiration: bool = False,
                          show_warned_name: bool = False) -> str:
        """
        Returns information about a warning in a nice format
        """
        warn_str = ""
        if show_warned_name:
            user: discord.User = await self.bot.fetch_user(warning.user_id)
            name = f"{user.name}#{user.discriminator}" if user else f"Not found({warning.user_id})"
            warn_str += f"**User:** {name}\n"
        warn_str += f"**Date:** {warning.date_str}\n"
        if show_expiration:
            warn_str += f"**Expires**: {warning.expiration_str}\n"
        warn_str += f"**Reason:** {warning.reason}\n"
        warn_str += f"**Mod:** {warning.mod_name}\n"
        return warn_str


    @commands.command(name="warn")
    @can_kick()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        """
        Adds a new warning for a member.
        Usage: ref!warn @Member [reason for the warning]

        :param member:
        :param reason:
        """
        warning = RefWarning(
            user_id=member.id,
            reason=reason,
            timestamp=datetime.now(),
            mod_name=f"{ctx.author.display_name}#{ctx.author.discriminator}",
            expiration_time=datetime.now() + timedelta(hours=warnings_config.warning_lifetime))
        await self.db.put_warning(warning)
        await self.enforce_punishments(ctx, member, warning)
        await self.acknowledge(ctx.message)


    @commands.command(name="clear")
    @can_kick()
    async def clear(self, ctx: commands.Context, member: discord.Member):
        """
        Removes all active warnings from a member. The warnings persist in an expired state.
        :param member:
        """
        await self.db.expire_warnings(member.id)
        await self.remove_warned_roles(member)
        await self.acknowledge(ctx.message)


    @commands.command(aliases=["warns", "?"])
    @can_kick()
    async def warnings(self, ctx: commands.Context, member: discord.Member = None):
        """
        Lists all active and expired warnings for a member
        :param member:
        """
        if not member:
            await ctx.send("Usage: `ref!warnings @member`", delete_after=30)
            return

        all_warnings = await self.db.get_warnings(member.id)
        active_warnings = await self.db.get_active_warnings(member.id)
        expired_warnings = list(filter(lambda x: x not in active_warnings, all_warnings))

        if all_warnings:
            title = "{}: {} warnings ({} active)".format(member.display_name, len(all_warnings), len(active_warnings))
        else:
            title = f"No warnings for {member.display_name}#{member.discriminator}"
        embed = discord.Embed(title=title, color=discord.Color.dark_gold())

        if active_warnings:
            active_str = "\n".join(await self.warning_str(w, show_expiration=True) for w in active_warnings)
            embed.add_field(name="Active ({})".format(len(active_warnings)), value=active_str, inline=False)

        if expired_warnings:
            expired_str = "\n".join(await self.warning_str(w) for w in expired_warnings)
            embed.add_field(name="Expired ({})".format(len(all_warnings) - len(active_warnings)), value=expired_str,
                            inline=False)

        await ctx.send(embed=embed)


    @commands.command(aliases=["active", "!"])
    @can_kick()
    async def active_warnings(self, ctx: commands.Context):
        """
        Lists all currently active warnings
        """
        active_warnings = await self.db.get_all_active_warnings()

        title = "Active warnings" if active_warnings else "No active warnings"
        embed = discord.Embed(title=title, color=discord.Color.dark_gold())

        for member_id in active_warnings:
            warnings = await self.db.get_active_warnings(member_id)
            active_str = "\n".join(
                [await self.warning_str(w, show_warned_name=True, show_expiration=True) for w in warnings])
            if active_str:
                embed.add_field(name=ctx.guild.get_member(member_id), value=active_str, inline=False)

        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Warnings(bot))
