import asyncio

import discord
from discord.ext import commands

from config.config import Bouncer as bouncer_config

import logging
import os

from utils import emoji
from Referee import is_aight

logger = logging.getLogger("Referee")

CHECK_BUTTON_FILE_NAME = "extensions/checkmsgID.dat"  # TODO: whatever this is supposed to be


class Bouncer(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            with open(CHECK_BUTTON_FILE_NAME, "r") as file:
                self.check_message_id = int(file.read())
        except Exception as e:
            logger.warning("Could not read check_message_id")
            self.check_message_id = None
        self.guild: discord.Guild = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Called by API everytime a member joins the bots guild
        """
        await member.add_roles(await self.get_newbie_role())
        logger.info(f"Adding newbie role to {member.name}#{member.discriminator}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """
        Called by the API when a new channel is created
        """
        await self.hide_channel(channel, await self.get_newbie_role())

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        Called by the API whenever a user reacts to a message
        :param payload:
        :return:
        """
        if self.check_message_id == payload.message_id:
            guild: discord.Guild = self.bot.get_guild(payload.guild_id)
            member: discord.Member = guild.get_member(payload.user_id)
            if await self.get_newbie_role(guild=guild) in member.roles:
                await member.remove_roles(await self.get_newbie_role(guild=guild))
                logger.info(f"Removed newbie role from {member.name}#{member.discriminator}")
                await self.bot.http.remove_reaction(payload.message_id, payload.channel_id, payload.emoji, payload.user_id)
                await self.welcome(member)

    @staticmethod
    async def welcome(member: discord.Member):
        embed = discord.Embed()
        embed.set_footer(icon_url=member.guild.icon_url, text=member.guild.name)
        embed.add_field(name=f"Welcome to {member.guild.name}!", value=bouncer_config.welcome_message, inline=True)
        await member.send(embed=embed)

    async def get_newbie_role(self):
        """
        Gets the role meant to keep new users in the first channel.
        If the rule doesn't exist, it creates it.
        """
        newbie_role = discord.utils.get(self.guild.roles, name=bouncer_config.newbie_role_name)
        if newbie_role is None:
            newbie_role = await self.guild.create_role(
                reason="Bouncer", name=bouncer_config.newbie_role_name, color=discord.Colour.dark_orange()
            )
        return newbie_role

    async def create_accept_button(self, channel: discord.TextChannel):
        """
        Sends the message to which users are supposed to react
        """
        embed = discord.Embed(title=bouncer_config.accept_text)
        msg: discord.Message = await channel.send(embed=embed)
        await msg.add_reaction(emoji=emoji.white_check_mark)
        with open(CHECK_BUTTON_FILE_NAME, "w") as file:
            file.write(str(msg.id))

    async def delete_accept_button(self, channel: discord.TextChannel):
        """
        Deletes the message created by :meth:`create_accept_button`
        """
        await self.bot.http.delete_message(channel_id=channel.id, message_id=self.check_message_id)
        os.remove(CHECK_BUTTON_FILE_NAME)

    async def hide_channel(self, channel: discord.abc.GuildChannel, role: discord.Role):
        """
        Hides a channel from a role by setting permissions
        :return:
        """
        if isinstance(channel, discord.TextChannel):
            await channel.set_permissions(role, read_messages=False)
        else:
            await channel.set_permissions(role, connect=False)

    async def unhide_channel(self, channel: discord.abc.GuildChannel, role: discord.Role):
        """
        Reverses :meth:`hide_channel` for a specific role and channel
        """
        if isinstance(channel, discord.TextChannel):
            if channel.id != bouncer_config.first_channel_id:
                await channel.set_permissions(role, overwrite=None)
        else:
            await channel.set_permissions(role, overwrite=None)

    @commands.group(invoke_without_command=True)
    @is_aight()
    async def bouncer(self, ctx: commands.Context):
        """
        Enable or disable the bouncer
        """
        embed = discord.Embed(title="Bouncer")
        embed.add_field(name="Usage", value=
                        f"**{ctx.prefix}{ctx.invoked_with} enable**: Lock all channels except "
                        f"{ctx.guild.get_channel(bouncer_config.first_channel_id).mention} for new members\n"
                        f"**{ctx.prefix}{ctx.invoked_with} disable**: Unlock channels\n"
                        )
        await ctx.send(embed=embed, delete_after=30)

    @bouncer.command(name="enable")
    @is_aight()
    async def enable(self, ctx: commands.Context):
        """
        Enable the bouncer
        """
        newbie_role = await self.get_newbie_role()

        await self.create_accept_button(ctx.guild.get_channel(bouncer_config.first_channel_id))

        for channel in ctx.guild.channels:
            if channel.id != bouncer_config.first_channel_id:
                await self.hide_channel(channel, newbie_role)

        embed = discord.Embed(title="Bouncer enabled")
        await ctx.send(embed=embed, delete_after=5)
        await ctx.message.delete()

    @bouncer.command(name="disable")
    @is_aight()
    async def disable(self, ctx: commands.Context):
        """
        Disable the bouncer
        """
        newbie_role = await self.get_newbie_role()

        for channel in ctx.guild.channels:
            await self.unhide_channel(channel, newbie_role)

        await self.delete_accept_button(ctx.guild.get_channel(bouncer_config.first_channel_id))

        await newbie_role.delete()

        embed = discord.Embed(title="Bouncer disabled")
        await ctx.send(embed=embed, delete_after=5)
        await ctx.message.delete()

    @commands.command(name="welcome_me", hidden=True)
    async def welcome_me(self, ctx: commands.Context):
        await self.welcome(ctx.author)
        await ctx.message.delete()


def setup(bot: commands.Bot):
    bot.add_cog(Bouncer(bot))
