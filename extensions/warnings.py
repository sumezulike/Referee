from datetime import datetime, timedelta

import discord
from discord.ext import commands

from db_classes.PGWarningDB import PGWarningDB
from config.Config import Config, config

import asyncio

from models.refwarning import RefWarning

from utils import emoji

NO_REASON = "None"

conf = Config("config/options.ini")

warning_lifetime = int(conf.warningLifetime)


class Warnings(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.warning_db = PGWarningDB()

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.bg_check())

    async def bg_check(self):
        while not self.bot.is_ready():
            await asyncio.sleep(1)

        while not self.bot.is_closed():
            for guild in self.bot.guilds:
                # await check_all_warnings(guild)
                await self.check_all_members(guild)
            await asyncio.sleep(120)  # task runs every second minute

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.message_is_warning(message):
            name, reason = self.get_name_reason(message)

            member: discord.Member = await commands.MemberConverter().convert(await self.bot.get_context(message), name)

            warning = RefWarning(user_id=str(member.id),
                                 reason=reason,
                                 timestamp=datetime.now(),
                                 expiration_time=datetime.now() + timedelta(hours=warning_lifetime))

            await self.save_warning(warning)
            await self.execute_warning(await self.bot.get_context(message), member, warning)

        # Else, if the message is a clear
        elif self.message_is_clear(message):

            name = self.clean_content(message)[:-1].split("for ")[-1]
            member: discord.Member = await commands.MemberConverter().convert(await self.bot.get_context(message), name)

            self.warning_db.expire_warnings(member.id)
            await self.remove_warned_roles(member)


    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.check_warnings(member)

    @staticmethod
    def clean_content(message: discord.message) -> str:
        content = message.clean_content

        content = content.replace("***", "").replace("\\_", "_").replace("\\*", "*").replace("\\\\", "\\")

        return content

    def message_is_warning(self, message: discord.message) -> bool:
        content = self.clean_content(message)
        if message.author.id == int(config.dynoID):
            if "has been warned" in content:
                return True
        return False

    def get_name_reason(self, message: discord.message) -> tuple:
        content = self.clean_content(message)
        name, reason = content.split(" has been warned.", 1)
        name = name.split("> ")[1]
        reason = reason.replace(", ", "", 1)
        return name, reason

    def message_is_clear(self, message: discord.message):
        content = self.clean_content(message)
        return "<:dynoSuccess:314691591484866560> Cleared" in content and "warnings for " in content

    async def acknowledge(self, message: discord.Message):
        await message.add_reaction(emoji.eye)

    async def execute_warning(self, ctx: commands.Context, member: discord.Member, warning: RefWarning):
        await self.check_warnings(member)
        num_warnings = len(self.warning_db.get_active_warnings(member.id))
        if num_warnings > 1:
            await ctx.channel.send(
                f"{member.display_name} has been warned {num_warnings} times in the last {warning_lifetime} hours",
                delete_after=60
            )

    async def check_warnings(self, member: discord.Member):
        is_warned = bool(await self.get_warned_roles(member))

        active_warnings = self.warning_db.get_active_warnings(str(member.id))

        if active_warnings:
            if not is_warned:
                await self.assign_warned_role(member)
        elif is_warned:
            await self.remove_warned_roles(member)

    async def check_all_warnings(self, guild: discord.Guild):
        member_ids = self.warning_db.get_all_warnings().keys()
        for member_id in member_ids:
            await self.check_warnings(guild.get_member(int(member_id)))

    async def check_all_members(self, guild: discord.Guild):
        for member in guild.members:
            await self.check_warnings(member)

    async def assign_warned_role(self, member: discord.Member):
        if member.top_role.position > member.guild.me.top_role.position:
            return

        if len(await self.get_warned_roles(member)) >= 1:
            return

        guild: discord.Guild = member.guild
        warning_color = discord.Colour.from_rgb(*self.get_warned_color(member.colour.to_rgb()))
        warned_roles = list(
            filter(lambda r: r.name == config.warnedRoleName and r.colour == warning_color, guild.roles))

        if not warned_roles:
            role = await guild.create_role(name=config.warnedRoleName,
                                           colour=warning_color)
            await asyncio.sleep(0.5)
        else:
            role = warned_roles[0]

        if role.position <= member.top_role.position:
            await role.edit(position=max(member.top_role.position, 1))

        await member.add_roles(role)

    async def remove_warned_roles(self, member: discord.Member):
        warned_roles = await self.get_warned_roles(member)
        await member.remove_roles(*warned_roles)

    async def get_warned_roles(self, member: discord.Member) -> list:
        warned_roles = [r for r in member.roles if r.name == config.warnedRoleName]
        return warned_roles

    async def save_warning(self, warning: RefWarning):
        self.warning_db.put_warning(warning)

    async def mute(self, member: discord.Member, mute_time: int = 30 * 60):
        muted_roles = list(filter(lambda x: x.name == "Muted", member.guild.roles))
        await member.add_roles(*muted_roles)
        await asyncio.sleep(mute_time)
        await member.remove_roles(*muted_roles)

    def get_warned_color(self, color: tuple) -> tuple:
        def is_grey(c):
            return max([abs(c[0] - c[1]), abs(c[1] - c[2]), abs(c[0] - c[2])]) < 25

        new_color = (color[0] // 2, color[1] // 2, color[2] // 2)
        default_warned_color = (120, 100, 100)
        if sum(new_color) / 3 < 100 and is_grey(new_color):
            return default_warned_color
        else:
            return new_color

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *reason):
        await self.execute_warning(
            ctx, member,
            RefWarning(
                member.id,
                reason=reason,
                timestamp=datetime.now(),
                expiration_time=datetime.now() + timedelta(hours=warning_lifetime)
            )
        )
        await self.acknowledge(ctx.message)

    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def clear(self, ctx: commands.Context, member: discord.Member):
        self.warning_db.expire_warnings(member.id)
        await self.remove_warned_roles(member)
        await self.acknowledge(ctx.message)


    @commands.command(aliases=["warns", "warning", "?"])
    @commands.has_permissions(kick_members=True)
    async def warnings(self, ctx: commands.Context, member: discord.Member = None):

        if not member:
            await ctx.send("Usage: `ref!warnings @member`", delete_after=30)
            return

        all_warnings = self.warning_db.get_warnings(member.id)
        active_warnings = self.warning_db.get_active_warnings(member.id)

        title = "{}: {} warnings ({} active)".format(member.display_name, len(all_warnings), len(active_warnings))
        embed = discord.Embed(title=title, color=discord.Color.dark_gold())

        active_str = "\n".join(
            "**\\*{} - {}\\***\n  Reason: {}".format(w.timestamp_str, w.expiration_str, w.reason or NO_REASON) for w in
            active_warnings)
        if active_str:
            embed.add_field(name="Active ({})".format(len(active_warnings)), value=active_str, inline=False)

        expired_str = "\n".join("**\\*{}\\***\n  Reason: {}".format(w.timestamp_str, w.reason or NO_REASON) for w in
                                list(filter(lambda x: x.is_expired(), all_warnings)))
        if expired_str:
            embed.add_field(name="Expired ({})".format(len(all_warnings) - len(active_warnings)), value=expired_str,
                            inline=False)

        if not any((expired_str, active_str)):
            embed.add_field(name="No warnings", value="noice",
                            inline=False)

        await ctx.send(embed=embed)


    @commands.command(aliases=["active", "!"])
    @commands.has_permissions(kick_members=True)
    async def active_warnings(self, ctx: commands.Context):

        active_warnings = self.warning_db.get_all_active_warnings()

        title = "Active warnings" if active_warnings else "No active warnings"
        embed = discord.Embed(title=title, color=discord.Color.dark_gold())

        for member_id in active_warnings:
            warnings = self.warning_db.get_active_warnings(member_id)
            active_str = "\n".join(
                "**\\*{} - {}\\***\n  Reason: {}".format(w.timestamp_str, w.expiration_str, w.reason or NO_REASON) for w
                in warnings)
            if active_str:
                embed.add_field(name=ctx.guild.get_member(int(member_id)), value=active_str, inline=False)

        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Warnings(bot))
