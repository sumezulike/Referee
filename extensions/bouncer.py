import asyncio

import discord
from discord.ext import commands

from config import bouncer_config

import logging
import os

from utils import emoji

logger = logging.getLogger("Referee")

CHECK_BUTTON_FILE_NAME = "extensions/checkmsgID.dat"


class Bouncer(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            with open(CHECK_BUTTON_FILE_NAME, "r") as file:
                self.check_message_id = int(file.read())
        except Exception as e:
            logger.warning("Could not read check_message_id")
            self.check_message_id = None

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await member.add_roles(await self.get_newbie_role(member.guild))
        logger.info(f"Adding newbie role to {member.name}#{member.discriminator}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await self.hide_channel(channel, await self.get_newbie_role(channel.guild))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if self.check_message_id == payload.message_id:
            guild: discord.Guild = self.bot.get_guild(payload.guild_id)
            member: discord.Member = guild.get_member(payload.user_id)
            await member.remove_roles(await self.get_newbie_role(guild=guild))
            logger.info(f"Removed newbie role from {member.name}#{member.discriminator}")
            await asyncio.sleep(0.2)
            await member.add_roles(await self.get_portal_role(guild=guild))
            await asyncio.sleep(0.2)
            await member.remove_roles(await self.get_portal_role(guild=guild))
            await self.bot.http.remove_reaction(payload.message_id, payload.channel_id, payload.emoji, payload.user_id)

    async def get_newbie_role(self, guild: discord.Guild):
        newbie_role = discord.utils.get(guild.roles, name=bouncer_config.newbie_role_name)
        if newbie_role is None:
            newbie_role = await guild.create_role(reason="Bouncer", name=bouncer_config.newbie_role_name, color=discord.Colour.dark_orange())
        return newbie_role

    async def get_portal_role(self, guild: discord.Guild):
        portal_role = discord.utils.get(guild.roles, name=bouncer_config.portal_role_name)
        if portal_role is None:
            portal_role = await guild.create_role(reason="Bouncer", name=bouncer_config.portal_role_name)
        return portal_role

    async def create_accept_button(self, channel: discord.TextChannel):
        embed = discord.Embed(title=bouncer_config.accept_text)
        msg: discord.Message = await channel.send(embed=embed)
        await msg.add_reaction(emoji=emoji.white_check_mark)
        with open(CHECK_BUTTON_FILE_NAME, "w") as file:
            file.write(str(msg.id))

    async def delete_accept_button(self, channel: discord.TextChannel):
        await self.bot.http.delete_message(channel_id=channel.id, message_id=self.check_message_id)
        os.remove(CHECK_BUTTON_FILE_NAME)

    async def hide_channel(self, channel: discord.abc.GuildChannel, role: discord.Role):
        if isinstance(channel, discord.TextChannel):
            await channel.set_permissions(role, read_messages=False)
        else:
            await channel.set_permissions(role, connect=False)

    async def unhide_channel(self, channel: discord.abc.GuildChannel, role: discord.Role):
        if isinstance(channel, discord.TextChannel):
            if channel.id != bouncer_config.first_channel_id:
                await channel.set_permissions(role, overwrite=None)
        else:
            await channel.set_permissions(role, overwrite=None)

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(kick_members=True)
    async def bouncer(self, ctx: commands.Context):
        embed = discord.Embed(title="Bouncer")
        embed.add_field(name="Usage", value=
                        f"**{ctx.prefix}{ctx.invoked_with} enable**: Lock all channels except "
                        f"{ctx.guild.get_channel(bouncer_config.first_channel_id).mention} for new members\n"
                        f"**{ctx.prefix}{ctx.invoked_with} disable**: Unlock channels\n"
                        )
        await ctx.send(embed=embed, delete_after=30)

    @bouncer.command(name="enable")
    @commands.has_permissions(kick_members=True)
    async def enable(self, ctx: commands.Context):
        newbie_role = await self.get_newbie_role(ctx.guild)
        portal_role = await self.get_portal_role(ctx.guild)
        await self.create_accept_button(ctx.guild.get_channel(bouncer_config.first_channel_id))
        for channel in ctx.guild.channels:
            if channel.id != bouncer_config.first_channel_id:
                await self.hide_channel(channel, newbie_role)

            if channel.id != bouncer_config.second_channel_id:
                await self.hide_channel(channel, portal_role)

        embed = discord.Embed(title="Bouncer enabled")
        await ctx.send(embed=embed, delete_after=5)
        await ctx.message.delete()

    @bouncer.command(name="disable")
    @commands.has_permissions(kick_members=True)
    async def disable(self, ctx: commands.Context):
        newbie_role = await self.get_newbie_role(ctx.guild)
        portal_role = await self.get_portal_role(ctx.guild)
        for channel in ctx.guild.channels:
            await self.unhide_channel(channel, newbie_role)
            await self.unhide_channel(channel, portal_role)
        await self.delete_accept_button(ctx.guild.get_channel(bouncer_config.first_channel_id))

        await (await self.get_newbie_role(ctx.guild)).delete()
        await (await self.get_portal_role(ctx.guild)).delete()

        embed = discord.Embed(title="Bouncer disabled")
        await ctx.send(embed=embed, delete_after=5)
        await ctx.message.delete()


def setup(bot: commands.Bot):
    bot.add_cog(Bouncer(bot))
