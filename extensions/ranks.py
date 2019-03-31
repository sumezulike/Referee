import asyncio
from typing import List
import discord
from discord.ext import commands

from config import ranks_config
from db_classes.PGRanksDB import PGRanksDB
from models.ranks_models import Rank
from utils import emoji


class Ranks(commands.Cog):
    class Role(commands.RoleConverter):

        async def convert(self, ctx: commands.Context, argument) -> discord.Role:
            try:
                role = await super().convert(ctx, argument)
                return role
            except commands.BadArgument:
                existing_roles = list(filter(lambda r: r.name.lower() == argument.lower(), ctx.guild.roles))
                if existing_roles:
                    return existing_roles[0]
                else:
                    raise commands.BadArgument

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGRanksDB()
        self.on_cooldown = []
        self.latest_reactions = {}
        self.ranks: List[Rank] = []

    @commands.Cog.listener()
    async def on_ready(self):
        self.bot.loop.create_task(self.clear_cooldowns())
        await self.update_self_ranks()

    async def update_self_ranks(self):
        self.ranks = self.db.get_all_ranks()

    async def clear_cooldowns(self):
        while not self.bot.is_closed():
            self.on_cooldown = []
            await asyncio.sleep(ranks_config.cooldown_time)

    async def process_cooldown(self, user_id: int):
        self.latest_reactions[user_id] = self.latest_reactions.get(user_id, 1)
        if self.latest_reactions.get(user_id) > ranks_config.cooldown_count:
            self.on_cooldown.append(user_id)

    @staticmethod
    async def warn_limit_exceeded(member: discord.Member, role: discord.Role):
        embed = discord.Embed(title=f"You can not have more than **{ranks_config.rank_count_limit}** ranks.\n"
                                    f"Remove a rank first to add **{role.name}**.")
        await member.send(embed=embed)

    @staticmethod
    async def notify_role_added(member: discord.Member, role: discord.Role):
        embed = discord.Embed(title=f"**{role.name}** was added to your roles")
        await member.send(embed=embed)

    @staticmethod
    async def notify_role_removed(member: discord.Member, role: discord.Role):
        embed = discord.Embed(title=f"**{role.name}** was removed from your roles")
        await member.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.channel_id == ranks_config.ranks_channel_id and payload.user_id != self.bot.user.id:
            if payload.user_id in self.on_cooldown:
                return
            await self.process_cooldown(payload.user_id)
            guild: discord.Guild = self.bot.get_guild(payload.guild_id)
            member: discord.Member = guild.get_member(payload.user_id)

            rank = self.db.get_rank(message_id=payload.message_id)

            if rank:
                role = guild.get_role(rank.role_id)

                if str(payload.emoji) == emoji.white_check_mark:
                    if role not in member.roles:
                        if len([ro.id for ro in member.roles if
                                ro.id in [ra.role_id for ra in self.ranks]]) >= ranks_config.rank_count_limit:
                            await self.warn_limit_exceeded(member, role)
                        else:
                            await member.add_roles(role)
                            await self.notify_role_added(member, role)
                elif str(payload.emoji) == emoji.x:
                    if role in member.roles:
                        await member.remove_roles(role)
                        await self.notify_role_removed(member, role)

            await self.bot.http.remove_reaction(payload.message_id, payload.channel_id, payload.emoji, payload.user_id)

    @commands.command(aliases=["create_rank", "add_ranks", "create_ranks"])
    @commands.has_permissions(kick_members=True)
    async def add_rank(self, ctx: commands.Context, ranks: commands.Greedy[Role]):
        for rank in ranks:
            if isinstance(rank, str):
                rank_name = rank
                new_role = await ctx.guild.create_role(name=rank_name.capitalize(), mentionable=True,
                                                       color=discord.Color.dark_grey())
                await self.create_rank_message(name=rank_name, role=new_role)

            elif isinstance(rank, discord.Role):
                if not self.db.get_rank(role_id=rank.id):
                    await self.create_rank_message(name=rank.name, role=rank)
                else:
                    await ctx.send(f"Rank {rank.name} already exists", delete_after=5)
        await ctx.message.delete()
        await self.update_self_ranks()

    @commands.command(aliases=["delete_ranks", "remove_rank", "remove_ranks"])
    @commands.has_permissions(kick_members=True)
    async def delete_rank(self, ctx: commands.Context, roles: commands.Greedy[Role]):
        for role in roles:
            rank = self.db.get_rank(role_id=role.id)
            delete_role = await self.quick_embed_query(ctx=ctx,
                                                       question=f"Also delete role {role.name}?",
                                                       reraise_timeout=False
                                                       )
            if delete_role:
                await self.bot.http.delete_role(ctx.guild.id, rank.role_id)
            self.db.delete_rank(role_id=rank.role_id)
            await self.bot.http.delete_message(ranks_config.ranks_channel_id, rank.message_id)
        await ctx.message.delete()
        await self.update_self_ranks()

    async def quick_embed_query(self, ctx: commands.Context, question: str, reraise_timeout: bool = True) -> bool:
        def check(_reaction, _user):
            return _user == ctx.author and str(_reaction.emoji) in [emoji.x, emoji.white_check_mark]

        embed = discord.Embed(title=question, color=discord.Color.dark_gold())

        msg = await ctx.send(embed=embed)
        await msg.add_reaction(emoji.white_check_mark)
        await msg.add_reaction(emoji.x)

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
        except asyncio.TimeoutError as e:
            await msg.delete()
            if reraise_timeout:
                raise e
            else:
                return False
        else:
            await ctx.send(embed=discord.Embed(title=reaction.emoji), delete_after=5)
            if reaction.emoji == emoji.white_check_mark:
                await msg.delete()
                return True
            else:
                await msg.delete()
                return False

    async def create_rank_message(self, name: str, role: discord.Role):
        """
        This function sends the "Button" to the ranks channel and enters it to the db
        :param name: Name of the new rank
        :param role: The existing discord tole to be linked with the rank
        """
        channel = role.guild.get_channel(ranks_config.ranks_channel_id)
        msg = await channel.send(f"Get: **{role.name}**")

        rank = Rank(name=name, role_id=role.id, message_id=msg.id)
        self.db.add_rank(rank=rank)
        await msg.add_reaction(emoji.white_check_mark)
        await msg.add_reaction(emoji.x)


def setup(bot: commands.Bot):
    bot.add_cog(Ranks(bot))
