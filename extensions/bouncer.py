import discord
from discord.ext import commands

from config import bouncer_config

import logging

from utils import emoji

logger = logging.getLogger("Referee")

CHECK_BUTTON_FILE_NAME = "checkmsgID.dat"


class Bouncer(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            with open(CHECK_BUTTON_FILE_NAME, "w") as file:
                self.check_message_id = int(file.read())
        except:
            self.check_message_id = None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        pass

    async def get_newbie_role(self, guild: discord.Guild):
        newbie_role = discord.utils.get(guild.roles, name=bouncer_config.newbie_role_name)
        if newbie_role is None:
            newbie_role = await guild.create_role(reason="Bouncer", name=bouncer_config.newbie_role_name, color=discord.Colour.dark_orange())

        return newbie_role

    async def create_accept_button(self, channel: discord.TextChannel):
        embed = discord.Embed(title=bouncer_config.accept_text)
        msg: discord.Message = await channel.send(embed=embed)
        await msg.add_reaction(emoji=emoji.white_check_mark)
        with open(CHECK_BUTTON_FILE_NAME, "w") as file:
            file.write(str(msg.id))

    async def delete_accept_button(self, channel: discord.TextChannel):
        msg: discord.Message = await channel.send(embed=embed)
        with open(CHECK_BUTTON_FILE_NAME, "w") as file:
            file.write("")

    async def hide_channel(self, channel: discord.abc.GuildChannel, role: discord.Role):
        if isinstance(channel, discord.TextChannel):
            if channel.id != bouncer_config.first_channel_id:
                await channel.set_permissions(role, read_messages=False)
        else:
            await channel.set_permissions(role, view_channel=False)

    async def unhide_channel(self, channel: discord.abc.GuildChannel, role: discord.Role):
        if isinstance(channel, discord.TextChannel):
            if channel.id != bouncer_config.first_channel_id:
                await channel.set_permissions(role, overwrite=None)
        else:
            await channel.set_permissions(role, overwrite=None)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await self.hide_channel(channel, await self.get_newbie_role(channel.guild))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if self.check_message_id == payload.message_id:
            if str(payload.emoji) == emoji.white_check_mark:
                guild: discord.Guild = await self.bot.get_guild(payload.guild_id)
                member: discord.Member = guild.get_member(payload.user_id)
                await member.remove_roles(await self.get_newbie_role(guild=guild))

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(kick_members=True)
    async def bouncer(self, ctx: commands.Context):
        embed = discord.Embed(title="Bouncer")
        embed.add_field(name="Usage", value=
                        f"**{ctx.prefix}{ctx.invoked_with} arm**: Lock all but "
                        f"{ctx.guild.get_channel(bouncer_config.first_channel_id).mention} for new members\n"
                        f"**{ctx.prefix}{ctx.invoked_with} disarm**: Unlock channels\n"
                        )
        await ctx.send(embed=embed)

    @bouncer.command(name="arm")
    @commands.has_permissions(kick_members=True)
    async def arm(self, ctx: commands.Context):
        newbie_role = await self.get_newbie_role(ctx.guild)
        await self.create_accept_button(ctx.guild.get_channel(bouncer_config.first_channel_id))
        for channel in ctx.guild.channels:
            await self.hide_channel(channel, newbie_role)

    @bouncer.command(name="disarm")
    @commands.has_permissions(kick_members=True)
    async def disarm(self, ctx: commands.Context):
        newbie_role = await self.get_newbie_role(ctx.guild)
        for channel in ctx.guild.channels:
            await self.unhide_channel(channel, newbie_role)


def setup(bot: commands.Bot):
    bot.add_cog(Bouncer(bot))
