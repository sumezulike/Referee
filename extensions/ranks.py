import asyncio
from typing import List, Union, Dict
import discord
from discord.ext import commands

from config import ranks_config
from db_classes.PGRanksDB import PGRanksDB
from models.ranks_models import Rank
from utils import emoji


class Ranks(commands.Cog):

    class Role(commands.RoleConverter):
        """
        This class is only to be used as a converter for command arguments
        """
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
        self.on_cooldown: List[int] = []
        self.latest_reactions: Dict[int: int] = {}
        self.ranks_cache: List[Rank] = []

    @commands.Cog.listener()
    async def on_ready(self):
        """
                On_ready eventhandler, gets called by api
        """
        self.bot.loop.create_task(self.bg_clear_cooldowns())
        await self.update_ranks_cache()

    async def update_ranks_cache(self):
        """
        Update the cache from the db
        """
        self.ranks_cache = self.db.get_all_ranks()

    async def bg_clear_cooldowns(self):
        """
        Background task to reset cooldown
        """
        while not self.bot.is_closed():
            self.on_cooldown = []
            await asyncio.sleep(ranks_config.cooldown_time)

    async def process_cooldown(self, user_id: int):
        """
        Controls whether the user has violated the rate-limit and places them on cooldown
        :param user_id: ID of the user that added
        """
        self.latest_reactions[user_id] = self.latest_reactions.get(user_id, 1) + 1
        if self.latest_reactions.get(user_id) > ranks_config.cooldown_count:
            self.on_cooldown.append(user_id)

    @staticmethod
    async def warn_limit_exceeded(member: discord.Member, role: discord.Role):
        """
        Notifies a user per DM that they have too many roles
        :param member: The user that has exceeded the role limit
        :param role: The :class:`Role` the user was trying to add
        """
        embed = discord.Embed(title=f"You can not have more than **{ranks_config.rank_count_limit}** ranks.\n"
                                    f"Remove a rank first to add **{role.name}**.")
        await member.send(embed=embed)

    @staticmethod
    async def notify_role_added(member: discord.Member, role: discord.Role):
        """
        Notifies a user per DM that they added a role
        :param member: The user that has added a role
        :param role: The :class:`Role` the user has added
        """
        embed = discord.Embed(title=f"**{role.name}** was added to your roles")
        await member.send(embed=embed)

    @staticmethod
    async def notify_role_removed(member: discord.Member, role: discord.Role):
        """
        Notifies a user per DM that they removed a role
        :param member: The user that has removed a role
        :param role: The :class:`Role` the user has removed
        """
        embed = discord.Embed(title=f"**{role.name}** was removed from your roles")
        await member.send(embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """
        Called by api whenever a reaction is added.
        :param payload: A :class:`discord.RawReactionActionEvent`
        """
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
                                ro.id in [ra.role_id for ra in self.ranks_cache]]) >= ranks_config.rank_count_limit:
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
    async def add_rank(self, ctx: commands.Context, ranks: commands.Greedy[Union[Role, str]]):
        """
        This command creates one or more new ranks and the rank selection messages that can then be used by Members.
        If the given rank is an existing role, the role will be used, otherwise a role will be created.
        Usage: ref!add_rank rankName1 [rankName2 rankName3 ...]

        :param ctx: Context object for the specific invoked ćommand, passed by api
        :param ranks: A list of one or more roles or strings
        """
        for rank in ranks:
            if isinstance(rank, str):
                rank_name = rank
                new_role = await ctx.guild.create_role(name=rank_name, mentionable=True,
                                                       color=discord.Color.dark_grey())
                await self.create_rank_message(name=rank_name, role=new_role)

            elif isinstance(rank, discord.Role):
                if not self.db.get_rank(role_id=rank.id):
                    await self.create_rank_message(name=rank.name, role=rank)
                else:
                    await ctx.send(f"Rank {rank.name} already exists", delete_after=5)
        await ctx.message.delete()
        await self.update_ranks_cache()

    @commands.command(aliases=["delete_ranks", "remove_rank", "remove_ranks"])
    @commands.has_permissions(kick_members=True)
    async def delete_rank(self, ctx: commands.Context, roles: commands.Greedy[Role]):
        """
        This command deletes one or more ranks and the ranks selection messages.
        The invoking user will be prompted before deleting the role which belongs to the rank.
        Usage: ref!delete_rank roleName1 [roleName2 roleName3 ...]

        :param ctx: Context object for the specific invoked ćommand, passed by api
        :param roles: A list of one or more roles
        """
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
        await self.update_ranks_cache()

    async def quick_embed_query(self, ctx: commands.Context, question: str, reraise_timeout: bool = True) -> bool:
        """
        Sends a yes/no query to a context
        :param ctx: The :class:`commands.Context` to which the query should be sent
        :param question: The content of the query
        :param reraise_timeout: Whether an exception should be raised on timeout, defaults to False
        :return: bool answer
        """
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
