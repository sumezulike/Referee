import asyncio
import typing
import discord
from discord.ext import commands

from config import ranks_config
from db_classes.PGRanksDB import PGRanksDB
from models.ranks_models import Rank
from utils import emoji


class Ranks(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGRanksDB()

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id == ranks_config.ranks_channel_id and payload.user_id != self.bot.user.id:
            rank = self.db.get_rank(message_id=payload.message_id)
            guild: discord.Guild = self.bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)

            if rank:
                role = guild.get_role(rank.role_id)

                if str(payload.emoji) == emoji.white_check_mark:
                    await member.add_roles(role)
                elif str(payload.emoji) == emoji.x:
                    await member.remove_roles(role)

                await self.update_rank_message(guild, rank)

            await self.bot.http.remove_reaction(payload.message_id, payload.channel_id, payload.emoji, payload.user_id)

    @commands.command(aliases=["add_role"])
    @commands.has_permissions(kick_members=True)
    async def add_rank(self, ctx: commands.Context, rank: typing.Union[discord.Role, str]):
        if isinstance(rank, str):
            rank_name = rank.replace(" ", "_")
            existing_roles = discord.utils.get(ctx.guild.roles, name=rank_name)
            if not existing_roles:
                new_role = await ctx.guild.create_role(name=rank_name, mentionable=True,
                                                       color=discord.Color.dark_grey())
                await self.create_rank(name=rank_name, role=new_role)
            elif len(existing_roles) > 1:
                if len(existing_roles) > 1:
                    embed = discord.Embed(title=f"{len(existing_roles)} roles named '{rank_name}' found")
                    await ctx.send(embed=embed, delete_after=30)

            elif len(existing_roles) == 1:
                def check(_reaction, _user):
                    return _user == ctx.author and str(_reaction.emoji) in [emoji.x, emoji.white_check_mark]

                old_role = existing_roles[0]

                embed = discord.Embed(title=f"Use existing role {old_role}?", color=discord.Color.dark_gold())

                msg = await ctx.send(embed=embed)
                await msg.add_reaction(emoji.white_check_mark)
                await msg.add_reaction(emoji.x)

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0,
                                                             check=check)  # Wait for a choice by user who invoked command
                except asyncio.TimeoutError:
                    await msg.delete()
                    await ctx.message.add_reaction(emoji.zzz)
                else:
                    if reaction.emoji == emoji.white_check_mark:
                        await self.create_rank(name=rank_name, role=old_role)
                    else:
                        await msg.delete()

        else:
            await self.create_rank(name=rank.name, role=rank)
        await ctx.message.delete()

    @commands.command
    @commands.has_permissions(kick_members=True)
    async def delete(self, ctx: commands.Context, *, rank: typing.Union[discord.Role, str]):
        pass

    async def create_rank(self, name: str, role: discord.Role):
        channel = role.guild.get_channel(ranks_config.ranks_channel_id)
        embed = discord.Embed(title=f"React to this message to add or remove \n***{role.name}***", color=discord.Color.dark_gold())
        embed.set_footer(text=f"-> {len(role.members)}")

        msg = await channel.send(embed=embed)

        rank = Rank(name=name, role_id=role.id, message_id=msg.id)
        self.db.add_rank(rank=rank)
        await msg.add_reaction(emoji.white_check_mark)
        await msg.add_reaction(emoji.x)

    async def update_rank_message(self, guild: discord.Guild, rank: Rank):
        role = guild.get_role(rank.role_id)
        channel: discord.TextChannel = guild.get_channel(ranks_config.ranks_channel_id)
        embed = discord.Embed(title=f"React to this message to add or remove \n***{role.name}***",
                              color=discord.Color.dark_gold())
        embed.set_footer(text=f"-> {len(role.members)}")

        message: discord.Message = await channel.fetch_message(rank.message_id)

        await message.edit(embed=embed)

def setup(bot: commands.Bot):
    bot.add_cog(Ranks(bot))
