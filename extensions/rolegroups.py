import asyncio
from typing import List, Union, Dict
import discord
from discord.ext import commands

from config.config import Rolegroups as rolegroups_config
from db_classes.PGRolegroupsDB import PGRolegroupsDB
from models.rolegroups_models import Rolegroup

from utils import emoji
import logging

from Referee import is_aight

logger = logging.getLogger("Referee")

control_emojis = [emoji.plus, emoji.white_check_mark, emoji.x]


class Rolegroups(commands.Cog):

    class Role_T(commands.RoleConverter):
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

    class Rolegroup_T(commands.RoleConverter):
        """
        This class is only to be used as a converter for command arguments
        """
        async def convert(self, ctx: commands.Context, argument: str) -> Rolegroup:
            db = ctx.bot.cogs["Rolegroups"].db
            if argument.isnumeric():
                rolegroup = await db.get_rolegroup(message_id=int(argument))
            else:
                rolegroup = await db.get_rolegroup(name=argument)

            if rolegroup:
                return rolegroup
            else:
                raise commands.BadArgument(f"No Rolegroup found with {argument}")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGRolegroupsDB()
        self.on_cooldown: List[int] = []
        self.latest_reactions: Dict[int: int] = {}
        self.editing_mod: discord.Member = None
        self.temp_rolegroups: Dict[str: Rolegroup] = dict()
        self.guild: discord.Guild = None

    @commands.Cog.listener()
    async def on_ready(self):
        """
        On_ready eventhandler, gets called by api
        """

        self.guild: discord.Guild = self.bot.guilds[0]
        logger.info(f"Set guild to {self.guild}")

        self.bot.loop.create_task(self.bg_clear_cooldowns())
        self.bot.loop.create_task(self.bg_check())

        for rg in await self.db.get_all_rolegroups():
            await self.cancel_editing(rg)

    async def bg_check(self):
        """
        Runs every 24h to clear reactions that were missed
        """
        while not self.bot.is_ready():
            await asyncio.sleep(1)

        while not self.bot.is_closed():
            await self.clear_user_reactions()
            await asyncio.sleep(60 * 60 * 24)  # task runs every 24h

    async def clear_user_reactions(self):
        for rolegroup in await self.db.get_all_rolegroups():
            rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
            for reaction in rolegroup_msg.reactions:
                async for user in reaction.users():
                    if not user == self.bot.user:
                        await self.bot.http.remove_reaction(
                            message_id=rolegroup.message_id,
                            channel_id=rolegroups_config.channel_id,
                            emoji=reaction.emoji,
                            member_id=user.id
                        )


    async def bg_clear_cooldowns(self):
        """
        Background task to reset cooldown
        """
        while not self.bot.is_closed():
            self.on_cooldown = []
            self.latest_reactions = {}
            await asyncio.sleep(rolegroups_config.cooldown_time)

    async def process_cooldown(self, user_id: int):
        """
        Controls whether the user has violated the rate-limit and places them on cooldown
        :param user_id: ID of the user that added
        """
        self.latest_reactions[user_id] = self.latest_reactions.get(user_id, 1) + 1
        if self.latest_reactions.get(user_id) > rolegroups_config.cooldown_count:
            logger.info(f"Placed {user_id} on cooldown")
            self.on_cooldown.append(user_id)

    @staticmethod
    async def warn_limit_exceeded(member: discord.Member, rolegroup: Rolegroup):
        """
        Notifies a user per DM that they have too many roles
        :param member: The user that has exceeded the role limit
        :param rolegroup: The :class:`Rolegroup` the user was trying to add a role from
        """
        embed = discord.Embed(title=f"You can not have more than **{rolegroups_config.role_count_limit}** roles from {rolegroup.name}. Removing a role by clicking the reaction again.")
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
        if payload.channel_id == rolegroups_config.channel_id and payload.user_id != self.bot.user.id:

            if payload.user_id in self.on_cooldown:
                await asyncio.sleep(1)
                await self.bot.http.remove_reaction(
                    message_id=payload.message_id,
                    channel_id=payload.channel_id,
                    emoji=payload.emoji,
                    member_id=payload.user_id
                )
                return
            await self.process_cooldown(payload.user_id)
            member: discord.Member = self.guild.get_member(payload.user_id)

            rolegroup: Rolegroup = await self.db.get_rolegroup(message_id=payload.message_id)
            if rolegroup:
                try:
                    await self.handle_rolegroup_reaction(rolegroup=rolegroup, member=member, reaction_emoji=str(payload.emoji))
                except Exception as e:
                    logger.error(e)

            await self.bot.http.remove_reaction(message_id=payload.message_id, channel_id=payload.channel_id, emoji=payload.emoji, member_id=payload.user_id)

    async def handle_rolegroup_reaction(self, rolegroup: Rolegroup, member: discord.Member, reaction_emoji: str):
        if self.editing_mod and member.id == self.editing_mod.id:
            logger.info("Editing mode")
            if reaction_emoji == emoji.plus:
                await self.add_new_role_prompt(member, rolegroup)
            elif reaction_emoji == emoji.white_check_mark:
                await self.stop_editing(rolegroup)
            elif reaction_emoji == emoji.x:
                await self.cancel_editing(rolegroup)
            else:
                role_id = rolegroup.get_role(reaction_emoji)
                role = self.guild.get_role(role_id)
                await self.edit_role_prompt(member=member, rolegroup=rolegroup, role=role)
            return

        role_id = rolegroup.get_role(reaction_emoji)
        role = self.guild.get_role(role_id)

        logger.debug(f"Matched {reaction_emoji} to {role.name}")
        if not role:
            return

        if role not in member.roles:
            if sum(1 for role in member.roles if
                   role.id in rolegroup.roles.values()) >= rolegroups_config.role_count_limit:
                await self.warn_limit_exceeded(member, role)
                logger.info(f"Stopped {member.name} from adding {role.name}, too many roles")
            else:
                await member.add_roles(role)
                logger.info(f"Added {role.name} to {member.name}")
                await self.notify_role_added(member, role)
        else:
            await member.remove_roles(role)
            logger.info(f"Removed {role.name} from {member.name}")
            await self.notify_role_removed(member, role)

    async def update_db(self, rolegroup: Rolegroup):
        await self.db.delete_rolegroup(rolegroup.name)
        await self.db.add_rolegroup(rolegroup)

    @commands.group(name="rolegroup")
    @is_aight()
    async def rolegroup_cmd(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            helpmsg = f"""Usage: ```{self.bot.command_prefix}rolegroup COMMAND
Commands:
create ROLEGROUP_NAME
destroy ROLEGROUP_NAME
edit ROLEGROUP_NAME
add ROLEGROUP_NAME ROLENAME
del RLEGROUP_NAME ROLENAME
```"""
            await ctx.send(helpmsg, delete_after=30)
            await ctx.message.delete(delay=30)

    @rolegroup_cmd.command(name="create")
    @is_aight()
    async def create_rolegroup(self, ctx: commands.Context, name: str):
        rolegroup = Rolegroup(name=name)
        msg = await self.create_rolegroup_message(rolegroup=rolegroup)
        rolegroup.message_id = msg.id
        await self.db.add_rolegroup(rolegroup=rolegroup)
        await ctx.message.delete()

    @rolegroup_cmd.command(name="edit")
    @is_aight()
    async def edit_rolegroup(self, ctx: commands.Context, rolegroup: Rolegroup_T):
        await self.start_editing(rolegroup, ctx.author)
        helpmsg = f"""Use the reactions to edit {rolegroup.name}
{emoji.plus}: add a role to the group
{emoji.white_check_mark}: save changes and quit
{emoji.x}: discard changes and quit
Click an existing roles reaction to edit the role
"""
        await ctx.send(helpmsg, delete_after=30)
        await ctx.message.delete(delay=30)

    @rolegroup_cmd.command(name="add")
    @is_aight()
    async def add_role_to_rolegroup(self, ctx: commands.Context, rolegroup: Rolegroup_T, role: Union[Role_T, str]):
        def messagecheck(_message):
            return _message.author.id == ctx.author.id and _message.content

        if type(role) == str:
            role_name = role
        else:
            role_name = role.name

        prompt = await ctx.send(content=f"{ctx.author.mention} Send a non-custom emoji for **{role_name}**")
        try:
            message: discord.Message = await self.bot.wait_for("message", check=messagecheck, timeout=30)
        except asyncio.TimeoutError:
            return
        else:
            try:
                await message.add_reaction(emoji=message.content)
            except Exception as e:
                logger.error(e)
                await ctx.send(f"\"{message.content}\" is not a valid emoji", delete_after=5)
                return
            else:
                role_emoji = message.content
                if role_emoji in control_emojis:
                    await ctx.send(
                        f"{', '.join(control_emojis[:-1])} and {control_emojis[-1]} cannot be assigned to roles",
                        delete_after=5)
                    return
            finally:
                await message.delete()
        finally:
            await prompt.delete()

        if type(role) == str:
            name = role
            role = await self.guild.create_role(name=name, reason=f"Added to {rolegroup.name} by {ctx.author.name}")

        rolegroup.add_role(role_id=role.id, emoji=role_emoji)
        await self.update_db(rolegroup)
        await self.update_rolegroup_message(rolegroup)

    @rolegroup_cmd.command(name="del")
    @is_aight()
    async def del_role_from_rolegroup(self, ctx: commands.Context, rolegroup: Rolegroup_T, role: Role_T):
        try:
            delete_role = await self.quick_embed_query(ctx=ctx, question=f"Also delete discord role?", reraise_timeout=True)
        except asyncio.TimeoutError:
            return
        rolegroup.del_role(role_id=role.id)
        if delete_role:
            await role.delete(reason=f"Deleted by {ctx.author.name}")
        await self.update_db(rolegroup)
        await self.update_rolegroup_message(rolegroup)
        await ctx.message.delete()

    @rolegroup_cmd.command(name="destroy")
    @is_aight()
    async def destroy_rolegroup(self, ctx: commands.Context, rolegroup: Rolegroup_T):
        try:
            if rolegroup.roles:
                delete_all = await self.quick_embed_query(ctx=ctx, question=f"Also delete all {len(rolegroup.roles)} discord roles?", reraise_timeout=True)
            else:
                delete_all = False
        except asyncio.TimeoutError:
            return
        else:
            if delete_all:
                logger.info(f"Deleting all roles from rolegroup {rolegroup.name}")
                for role_id in rolegroup.roles.values():
                    role = self.guild.get_role(role_id)
                    await role.delete(reason=f"Bulk delete by {ctx.author.name}")

            rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
            await self.db.delete_rolegroup(rolegroup.name)
            await rolegroup_msg.delete()
        await ctx.message.delete()


    @commands.command()
    @is_aight()
    async def clean_reactions(self, ctx: commands.Context):
        """
        Resets the reactions on the rolegroup messages
        """
        await self.clear_user_reactions()
        await ctx.message.delete()


    async def quick_embed_query(self, ctx: commands.Context, question: str, reraise_timeout: bool = True) -> bool:
        """
        Sends a yes/no query to a context
        :param ctx: The :class:`commands.Context` to which the query should be sent
        :param question: The content of the query
        :param reraise_timeout: Whether an exception should be raised on timeout, defaults to True
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

    async def create_rolegroup_message(self, rolegroup: Rolegroup) -> discord.Message:
        """
        This function sends the "Rolegroup" to the ranks channel
        """
        channel = self.guild.get_channel(rolegroups_config.channel_id)

        embed = discord.Embed(title=rolegroup.name)
        msg = await channel.send(embed=embed)
        return msg

    async def update_rolegroup_message(self, rolegroup: Rolegroup):
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        embed = discord.Embed(title=rolegroup.name)
        for role_emoji, role_id in rolegroup.roles.items():
            role = self.guild.get_role(role_id=role_id)
            embed.add_field(name="-", value=f"{role_emoji}: **{role.name}**")
        await rolegroup_msg.edit(embed=embed)
        for role_emoji, role_id in rolegroup.roles.items():
            await rolegroup_msg.add_reaction(emoji=role_emoji)


    async def add_new_role_prompt(self, member: discord.Member, rolegroup: Rolegroup):
        def messagecheck(_message):
            return _message.author.id == member.id and _message.content

        rolegroup = await self.get_temp_rolegroup(rolegroup)
        assert type(rolegroup) == Rolegroup
        assert type(member) == discord.Member

        channel: discord.TextChannel = self.guild.get_channel(rolegroups_config.channel_id)
        prompt = await channel.send(f"{member.mention} Send the id of an existing role or a name for the new role")
        try:
            message: discord.Message = await self.bot.wait_for("message", check=messagecheck, timeout=30)
        except asyncio.TimeoutError:
            await prompt.delete()
            return
        else:
            name: str = message.content
            role = None
            if name.isnumeric():
                role = self.guild.get_role(int(name))
            if not role:
                role = await self.guild.create_role(name=name, reason=f"Added to {rolegroup.name} by {member.name}")
                logger.info(f"Created role {role.name}")
            await message.delete()

        await prompt.delete()
        prompt = await channel.send(content=f"{member.mention} Send a non-custom emoji for **{role.name}**")
        try:
            message: discord.Message = await self.bot.wait_for("message", check=messagecheck, timeout=30)
        except asyncio.TimeoutError:
            await prompt.delete()
            return

        else:
            try:
                await message.add_reaction(emoji=message.content)
            except Exception as e:
                logger.error(e)
                await channel.send(f"\"{message.content}\" is not a valid emoji", delete_after=5)
                return
            else:
                role_emoji = message.content
                if role_emoji in control_emojis:
                    await channel.send(
                        f"{', '.join(control_emojis[:-1])} and {control_emojis[-1]} cannot be assigned to roles",
                        delete_after=5)
                    return

                rolegroup.add_role(role_id=role.id, emoji=role_emoji)
                await self.update_temp_rolegroup(rolegroup)
                await self.update_rolegroup_message(rolegroup)
            finally:
                await message.delete()
                await prompt.delete()


    async def edit_role_prompt(self, member: discord.Member, rolegroup: Rolegroup, role: discord.Role):
        channel: discord.TextChannel = self.guild.get_channel(rolegroups_config.channel_id)
        await channel.send(f"Just delete {role.name} and make a new role bruv", delete_after=5) # TODO

    async def start_editing(self, rolegroup: Rolegroup, editor: discord.Member):
        await self.load_temp_rolegroups()
        self.editing_mod = editor
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        for e in control_emojis:
            await rolegroup_msg.add_reaction(e)

    async def stop_editing(self, rolegroup: Rolegroup):
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        for e in control_emojis:
            await rolegroup_msg.remove_reaction(e, member=self.bot.user)
        await self.clear_user_reactions()
        self.editing_mod = None
        await self.save_temp_rolegroups()

    async def cancel_editing(self, rolegroup: Rolegroup):
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        for e in control_emojis:
            await rolegroup_msg.remove_reaction(e, member=self.bot.user)
        await self.clear_user_reactions()
        self.editing_mod = None
        await self.clear_temp_rolegroups()
        await self.update_rolegroup_message(await self.db.get_rolegroup(message_id=rolegroup.message_id))

    async def get_rolegroup_message(self, rolegroup: Rolegroup) -> discord.Message:
        channel = self.guild.get_channel(rolegroups_config.channel_id)
        msg = await channel.fetch_message(rolegroup.message_id)
        return msg

    async def load_temp_rolegroups(self):
        self.temp_rolegroups = {r.name: r for r in await self.db.get_all_rolegroups()}

    async def update_temp_rolegroup(self, rolegroup: Rolegroup):
        self.temp_rolegroups[rolegroup.name] = rolegroup

    async def get_temp_rolegroup(self, rolegroup: Rolegroup) -> Rolegroup:
        return self.temp_rolegroups.get(rolegroup.name)

    async def save_temp_rolegroups(self):
        for name, rg in self.temp_rolegroups.items():
            await self.update_db(rg)
        self.temp_rolegroups = {}

    async def clear_temp_rolegroups(self):
        self.temp_rolegroups = {}

def setup(bot: commands.Bot):
    bot.add_cog(Rolegroups(bot))
