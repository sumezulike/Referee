import asyncio
from typing import List, Union, Dict, Tuple
import discord
from discord.ext import commands

from config.config import Rolegroups as rolegroups_config
from db_classes.PGRolegroupsDB import PGRolegroupsDB
from models.rolegroups_models import Rolegroup

from utils import emoji
import logging

from Referee import is_aight

logger = logging.getLogger("Referee")

control_emojis = [emoji.plus, emoji.white_check_mark, emoji.x, emoji.pencil]
edit_control_emojis = [emoji.pencil, emoji.rotating_arrows, emoji.trashcan]


class Rolegroups(commands.Cog):
    class Role_T(commands.RoleConverter, discord.Role):
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
            db: PGRolegroupsDB = ctx.bot.cogs["Rolegroups"].db
            rolegroups = await db.get_all_rolegroups()

            id_matches = list(filter(lambda r: str(r.db_id) == argument, rolegroups))
            name_matches = list(filter(lambda r: r.name.lower().startswith(argument.lower()), rolegroups))

            logger.debug(f"Matches: {id_matches}, {name_matches}")

            if id_matches:
                return (id_matches + name_matches)[0]
            elif name_matches:
                if len(name_matches) == 1:
                    return name_matches[0]
                else:
                    raise commands.BadArgument(
                        f"Too many matches found for {argument}: {', '.join(r.name for r in name_matches)}")
            else:
                raise commands.BadArgument(f"No Rolegroups found with {argument}")

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGRolegroupsDB()
        self.on_cooldown: List[int] = []
        self.latest_reactions: Dict[int: int] = {}
        self.editing_mod: discord.Member = None
        self.edit_save_actions = []
        self.edit_cancel_actions = []
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
            await self.stop_editing(rg, save_changes=False)


    async def bg_check(self):
        """
        Runs every 24h to clear reactions that were missed
        """
        while not self.bot.is_ready():
            await asyncio.sleep(1)

        while not self.bot.is_closed():
            logger.info(f"Autoclearing user reactions")
            await self.clear_user_reactions()
            await asyncio.sleep(60 * 60)  # task runs every hour


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
        embed = discord.Embed(
            title=f"You can not have more than **{rolegroups_config.role_count_limit}** roles from {rolegroup.name}. Removing a role by clicking the reaction again.")
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
                logger.debug(f"User {payload.user_id} on cooldown, ignoring")
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
                logger.debug(f"Reaction {payload.emoji} to {rolegroup.name} from {member.name}")
                try:
                    await self.handle_rolegroup_reaction(rolegroup=rolegroup, member=member,
                                                         reaction_emoji=str(payload.emoji))
                except Exception as e:
                    logger.error(e)

            await self.bot.http.remove_reaction(message_id=payload.message_id, channel_id=payload.channel_id,
                                                emoji=payload.emoji, member_id=payload.user_id)


    async def handle_rolegroup_reaction(self, rolegroup: Rolegroup, member: discord.Member, reaction_emoji: str):
        if self.editing_mod:
            rolegroup = self.get_temp_rolegroup(rolegroup)

        role_id = rolegroup.get_role(reaction_emoji)
        if not role_id:
            logger.debug(f"No role_id for emoji {reaction_emoji}")
        role = self.guild.get_role(role_id)
        if role_id and role is None and reaction_emoji not in control_emojis:
            logger.info(f"Forgetting inexistent role with id {role_id}")
            rolegroup.del_role(role_id=role_id)
            if self.editing_mod:
                await self.update_temp_rolegroup(rolegroup)
            else:
                await self.db.update_rolegroup(rolegroup)
            await self.update_rolegroup_message(rolegroup)

        if self.editing_mod and member.id == self.editing_mod.id:
            logger.debug(f"Editing mode: {reaction_emoji}")
            if reaction_emoji == emoji.plus:
                await self.add_new_role_prompt(member, rolegroup)
            elif reaction_emoji == emoji.pencil:
                await self.rename_rolegroup_prompt(member, rolegroup)
            elif reaction_emoji == emoji.white_check_mark:
                await self.stop_editing(rolegroup, save_changes=True)
            elif reaction_emoji == emoji.x:
                await self.stop_editing(rolegroup, save_changes=False)
            else:
                await self.edit_role_prompt(member=member, rolegroup=rolegroup, role=role)
            return

        if not role:
            logger.debug(f"No role with id {role_id}")
            return
        else:
            logger.debug(f"Matched {reaction_emoji} to {role.name}")

        if role not in member.roles:
            if sum(1 for role in member.roles if
                   role.id in rolegroup.roles.values()) >= rolegroups_config.role_count_limit:
                await self.warn_limit_exceeded(member, rolegroup)
                logger.info(f"Stopped {member.name} from adding {role.name}, too many roles")
            else:
                await member.add_roles(role)
                logger.info(f"Added {role.name} to {member.name}")
                await self.notify_role_added(member, role)
        else:
            await member.remove_roles(role)
            logger.info(f"Removed {role.name} from {member.name}")
            await self.notify_role_removed(member, role)


    @commands.group(name="rolegroup", aliases=["rolegroups", "rg"])
    @is_aight()
    async def rolegroup_cmd(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            helpmsg = f"""Usage: 
{self.bot.command_prefix[0]}rolegroup *COMMAND*

Commands:
create *ROLEGROUP_NAME*
destroy *ROLEGROUP_NAME*
edit *ROLEGROUP_NAME*
add *ROLEGROUP_NAME* *ROLENAME*
del *RLEGROUP_NAME* *ROLENAME*
"""
            await self.send_simple_embed(channel=ctx, content=helpmsg, delete_after=30)
            await ctx.message.delete()


    @rolegroup_cmd.command(name="create")
    @is_aight()
    async def create_rolegroup(self, ctx: commands.Context, *, name: str = None):
        def messagecheck(_message):
            return _message.author.id == ctx.author.id and _message.content


        if not name:
            prompt = await self.send_simple_embed(channel=ctx,
                                                  content=f"Send a name for the new rolegroup",
                                                  mentions=ctx.author)
            try:
                message: discord.Message = await self.bot.wait_for("message", check=messagecheck, timeout=30)
            except asyncio.TimeoutError:
                logger.error("creeate rolegroup, name timed out")
                await prompt.delete()
                return
            else:
                name: str = message.content
                await message.delete()
            finally:
                await prompt.delete()

        if list(filter(lambda x: x.name == name, await self.db.get_all_rolegroups())):
            await self.send_simple_embed(channel=ctx, content="A role group with that name already exists",
                                         delete_after=5)
            await ctx.message.delete()
            return
        rolegroup = Rolegroup(name=name)
        msg = await self.create_rolegroup_message(rolegroup=rolegroup)
        rolegroup.message_id = msg.id
        await self.db.add_rolegroup(rolegroup=rolegroup)
        await ctx.message.delete()


    @rolegroup_cmd.command(name="destroy")
    @is_aight()
    async def destroy_rolegroup(self, ctx: commands.Context, *, rolegroup: Rolegroup_T):
        try:
            if rolegroup.roles:
                delete_all = await self.quick_embed_query(ctx=ctx,
                                                          question=f"Also delete all {len(rolegroup.roles)} discord roles?",
                                                          reraise_timeout=True)
            else:
                delete_all = False
        except asyncio.TimeoutError:
            logger.error("destroy rolegroup timed out")
            return
        else:
            if delete_all:
                logger.info(f"Deleting all roles from rolegroup {rolegroup.name}")
                for role_id in rolegroup.roles.values():
                    try:
                        role = self.guild.get_role(role_id)
                        await role.delete(reason=f"Bulk delete by {ctx.author.name}")
                    except Exception as e:
                        logger.error(e)

            try:
                rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
                await rolegroup_msg.delete()
            except Exception as e:
                logger.error(e)
            await self.db.delete_rolegroup(rolegroup.db_id)
        finally:
            await ctx.message.delete()


    @rolegroup_cmd.command(name="edit")
    @is_aight()
    async def edit_rolegroup(self, ctx: commands.Context, *, rolegroup: Rolegroup_T):
        await self.start_editing(rolegroup, ctx.author)
        helpmsg = f"""Use the reactions to edit '{rolegroup.name}'
{emoji.plus}: add a role to the group
{emoji.white_check_mark}: save changes and quit
{emoji.x}: discard changes and quit
Click an existing roles reaction to edit the role
"""
        msg = await self.send_simple_embed(channel=ctx, content=helpmsg)
        self.edit_cancel_actions.append(msg.delete())
        self.edit_save_actions.append(msg.delete())
        await ctx.message.delete()


    @rolegroup_cmd.command(name="add")
    @is_aight()
    async def add_role_to_rolegroup(self, ctx: commands.Context, rolegroup: Rolegroup_T, *, role: Union[Role_T, str]):
        def message_check(_message):
            return _message.author.id == ctx.author.id and _message.content


        if type(role) == str:
            role_name = role
        else:
            role_name = role.name

        prompt = await self.send_simple_embed(channel=ctx, content=f"Send a non-custom emoji for **{role_name}**",
                                              mentions=ctx.author)
        try:
            message: discord.Message = await self.bot.wait_for("message", check=message_check, timeout=30)
        except asyncio.TimeoutError:
            logger.error("add_role timed out")
            return
        else:
            try:
                await message.add_reaction(emoji=message.content)
            except Exception as e:
                logger.error(e)
                await self.send_simple_embed(channel=ctx, content=f"\"{message.content}\" is not a valid emoji",
                                             delete_after=5)
                return
            else:
                role_emoji = message.content
                if role_emoji in control_emojis:
                    await self.send_simple_embed(channel=ctx,
                                                 content=f"{', '.join(control_emojis[:-1])} and {control_emojis[-1]} cannot be assigned to roles",
                                                 delete_after=5)
                    return
            finally:
                await message.delete()
        finally:
            await prompt.delete()
            await ctx.message.delete()

        if type(role) == str:
            logger.info(f"Creating new role {role} for {rolegroup.name}")
            name = role
            role = await self.guild.create_role(name=name, reason=f"Added to {rolegroup.name} by {ctx.author.name}")

        rolegroup.add_role(role_id=role.id, emoji=role_emoji)
        await self.db.update_rolegroup(rolegroup)
        await self.update_rolegroup_message(rolegroup)


    @rolegroup_cmd.command(name="del")
    @is_aight()
    async def del_role_from_rolegroup(self, ctx: commands.Context, rolegroup: Rolegroup_T, *, role: Role_T):
        try:
            delete_role = await self.quick_embed_query(ctx=ctx, question=f"Also delete discord role?",
                                                       reraise_timeout=True)
        except asyncio.TimeoutError:
            logger.error("del_role timed out")
            return
        rolegroup.del_role(role_id=role.id)
        if delete_role:
            await role.delete(reason=f"Deleted by {ctx.author.name}")
        await self.db.update_rolegroup(rolegroup)
        await self.update_rolegroup_message(rolegroup)
        await ctx.message.delete()


    @rolegroup_cmd.command(name="clean")
    @is_aight()
    async def clean_rolegroup_message(self, ctx: commands.Context, rolegroup: Rolegroup_T):
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        for reaction in rolegroup_msg.reactions:
            async for user in reaction.users():
                await self.bot.http.remove_reaction(
                    message_id=rolegroup.message_id,
                    channel_id=rolegroups_config.channel_id,
                    emoji=reaction.emoji,
                    member_id=user.id
                )
        await self.update_rolegroup_message(rolegroup=rolegroup)
        await ctx.message.delete()

    async def quick_embed_query(self, ctx: Union[commands.Context, Tuple[discord.TextChannel, discord.Member]],
                                question: str, reraise_timeout: bool = True) -> bool:
        """
        Sends a yes/no query to a context
        :param ctx: The :class:`commands.Context` to which the query should be sent OOOR a Tuple of Channel and Member
        :param question: The content of the query
        :param reraise_timeout: Whether an exception should be raised on timeout, defaults to True
        :return: bool answer
        """


        def check(_reaction, _user):
            return _user == member and str(_reaction.emoji) in [emoji.x, emoji.white_check_mark]


        if type(ctx) == commands.Context:
            channel = ctx.channel
            member = ctx.author
        else:
            channel = ctx[0]
            member = ctx[1]

        logger.debug(f"Sending query '{question}' for {member.name}")

        msg = await self.send_simple_embed(channel=channel, content=question)
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
            await self.send_simple_embed(channel=channel, content=reaction.emoji, delete_after=2)
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

        msg = await self.send_simple_embed(channel=channel, content=rolegroup.name)
        return msg


    async def update_rolegroup_message(self, rolegroup: Rolegroup):
        logger.debug(f"Updating embed for {rolegroup.name}")
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        for reaction in rolegroup_msg.reactions:
            if reaction.emoji in control_emojis:
                continue
            if not rolegroup.get_role(reaction.emoji):
                await self.bot.http.remove_reaction(
                    message_id=rolegroup.message_id,
                    channel_id=rolegroups_config.channel_id,
                    emoji=reaction.emoji,
                    member_id=self.bot.user.id
                )
        embed_roles_texts = []
        emoji_full_role = [(role_emoji, self.guild.get_role(role_id) or role_id) for role_emoji, role_id in
                           rolegroup.roles.items()]
        for role_emoji, role in sorted(emoji_full_role, key=lambda r: r[1].name.lower()):
            if type(role) != discord.Role:
                logger.info(f"Forgetting role with id {role}")
                rolegroup.del_role(role_id=role)
                if self.editing_mod:
                    await self.update_temp_rolegroup(rolegroup)
                else:
                    await self.db.update_rolegroup(rolegroup)
                await self.update_rolegroup_message(rolegroup)
                continue
            embed_roles_texts.append(f"{role_emoji}  |  **{role.name}**")
            await rolegroup_msg.add_reaction(emoji=role_emoji)

        embed_text = '\n'.join(embed_roles_texts)
        embed = discord.Embed(title=rolegroup.name, color=discord.Color.dark_gold())
        embed.add_field(name="*", value=embed_text)

        await rolegroup_msg.edit(embed=embed)


    async def add_new_role_prompt(self, member: discord.Member, rolegroup: Rolegroup):
        def messagecheck(_message):
            return _message.author.id == member.id and _message.content


        rolegroup = self.get_temp_rolegroup(rolegroup)

        channel: discord.TextChannel = self.guild.get_channel(rolegroups_config.channel_id)
        prompt = await self.send_simple_embed(channel=channel,
                                              content=f"Send the id of an existing role or a name for the new role",
                                              mentions=member)
        try:
            message: discord.Message = await self.bot.wait_for("message", check=messagecheck, timeout=30)
        except asyncio.TimeoutError:
            logger.error("add prompt, id/name timed out")
            await prompt.delete()
            return
        else:
            name: str = message.content
            await message.delete()

        await prompt.delete()
        prompt = await self.send_simple_embed(channel=channel, content=f"Send a non-custom emoji for **{name}**",
                                              mentions=member)
        try:
            message: discord.Message = await self.bot.wait_for("message", check=messagecheck, timeout=30)
        except asyncio.TimeoutError:
            await prompt.delete()
            logger.error("add prompt, emoji timed out")
            return

        else:
            try:
                await message.add_reaction(emoji=message.content)
            except Exception as e:
                logger.error(e)
                await self.send_simple_embed(channel=channel, content=f"\"{message.content}\" is not a valid emoji",
                                             delete_after=5)
                return
            else:
                role_emoji = message.content
                if role_emoji in control_emojis:
                    await self.send_simple_embed(channel=channel,
                                                 content=f"{', '.join(control_emojis[:-1])} and {control_emojis[-1]} cannot be assigned to roles",
                                                 delete_after=5)
                    return
                if len(role_emoji) > 2:
                    await self.send_simple_embed(channel=channel, content=f"{role_emoji} is a custom emoji",
                                                 delete_after=5)
                    return

                if role_emoji in rolegroup.roles.keys():
                    await self.send_simple_embed(channel=channel,
                                                 content=f"{role_emoji} is already assigned to {await self.guild.get_role(rolegroup.get_role(role_emoji)).name}.\nIf you want to rename it, click the {role_emoji} reaction")
                    return

                role = None
                if name.isnumeric():
                    role = self.guild.get_role(int(name))
                if not role:
                    role = await self.guild.create_role(name=name, reason=f"Added to {rolegroup.name} by {member.name}")
                    self.edit_cancel_actions.append(role.delete(reason=f"Cancelled rolegroup editing"))
                    logger.info(f"Created role {role.name}")

                rolegroup.add_role(role_id=role.id, emoji=role_emoji)
                await self.update_temp_rolegroup(rolegroup)
            finally:
                await message.delete()
                await prompt.delete()


    async def edit_role_prompt(self, member: discord.Member, rolegroup: Rolegroup, role: discord.Role):
        def messagecheck(_message):
            return _message.author.id == member.id and _message.content


        def reaction_check(_reaction, _user):
            return _reaction.message == prompt and _user.id == member.id and _reaction.emoji in edit_control_emojis


        rolegroup = self.get_temp_rolegroup(rolegroup)

        channel: discord.TextChannel = self.guild.get_channel(rolegroups_config.channel_id)
        embed = discord.Embed(title=f"{rolegroup.get_emoji(role.id)} {role.name}", color=discord.Color.dark_gold())
        embed.add_field(name=f"Use reactions to edit {role.name}",
                        value=f"{emoji.pencil}: edit name\n{emoji.rotating_arrows}: change emoji\n{emoji.trashcan}: delete")
        prompt = await channel.send(embed=embed)
        for e in edit_control_emojis:
            await prompt.add_reaction(e)
        try:
            reaction, user = await self.bot.wait_for("reaction_add", check=reaction_check, timeout=60)
        except asyncio.TimeoutError:
            logger.error("edit prompt timed out")
            return
        else:
            if reaction.emoji == emoji.pencil:
                sub_prompt = await self.send_simple_embed(channel=channel,
                                                          content=f"Send a new name for {rolegroup.get_emoji(role.id)}")
                try:
                    message = await self.bot.wait_for("message", check=messagecheck, timeout=60)
                except asyncio.TimeoutError:
                    logger.error("edit prompt, new name timed out")
                    return
                else:
                    prev = role.name
                    await role.edit(name=message.content)
                    self.edit_cancel_actions.append(role.edit(name=prev))
                    await message.delete()
                finally:
                    await sub_prompt.delete()
            elif reaction.emoji == emoji.rotating_arrows:
                sub_prompt = await self.send_simple_embed(channel=channel,
                                                          content=f"Send a new non-custom emoji for {role.name}")
                try:
                    message = await self.bot.wait_for("message", check=messagecheck, timeout=60)
                except asyncio.TimeoutError:
                    logger.error("edit prompt, new emoji timed out")
                    return
                else:
                    try:
                        await message.add_reaction(emoji=message.content)
                    except Exception as e:
                        logger.error(e)
                        await self.send_simple_embed(channel=channel,
                                                     content=f"\"{message.content}\" is not a valid emoji",
                                                     delete_after=5)
                        return
                    else:
                        role_emoji = message.content
                        if role_emoji in control_emojis:
                            await self.send_simple_embed(channel=channel,
                                                         content=f"{', '.join(control_emojis[:-1])} and {control_emojis[-1]} cannot be assigned to roles",
                                                         delete_after=5)
                            return
                        if len(role_emoji) > 2:
                            await self.send_simple_embed(channel=channel, content=f"{role_emoji} is a custom emoji",
                                                         delete_after=5)
                            return

                        rolegroup.del_role(role_id=role.id)
                        rolegroup.add_role(role_id=role.id, emoji=role_emoji)
                    finally:
                        await message.delete()
                finally:
                    await sub_prompt.delete()
            elif reaction.emoji == emoji.trashcan:
                try:
                    delete_role = await self.quick_embed_query(ctx=(channel, member),
                                                               question="Also delete discord role?",
                                                               reraise_timeout=True)
                except asyncio.TimeoutError:
                    logger.error("edit prompt, delete role timed out")
                    return
                else:
                    rolegroup.del_role(role.id)
                    if delete_role:
                        self.edit_save_actions.append(role.delete(reason=f"Deleted by {member.name}"))
            await self.update_temp_rolegroup(rolegroup)
        finally:
            await prompt.delete()


    async def rename_rolegroup_prompt(self, member: discord.Member, rolegroup: Rolegroup):
        def messagecheck(_message):
            return _message.author.id == member.id and _message.content


        rolegroup = self.get_temp_rolegroup(rolegroup)

        channel: discord.TextChannel = self.guild.get_channel(rolegroups_config.channel_id)
        prompt = await self.send_simple_embed(channel=channel, content=f"Send a new name for {rolegroup.name}",
                                              mentions=member)
        try:
            message: discord.Message = await self.bot.wait_for("message", check=messagecheck, timeout=30)
        except asyncio.TimeoutError:
            logger.error("rename rolegroup timed out")
            return
        else:
            name: str = message.content
            await message.delete()

            rolegroup.name = name
            await self.update_temp_rolegroup(rolegroup)

        finally:
            await prompt.delete()


    async def start_editing(self, rolegroup: Rolegroup, editor: discord.Member):
        logger.info(f"Started editing")
        await self.load_temp_rolegroups()
        self.editing_mod = editor
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        for e in control_emojis:
            await rolegroup_msg.add_reaction(e)


    async def stop_editing(self, rolegroup: Rolegroup, save_changes: bool):
        rolegroup_msg = await self.get_rolegroup_message(rolegroup=rolegroup)
        for e in control_emojis:
            await rolegroup_msg.remove_reaction(e, member=self.bot.user)
        await self.clear_user_reactions()
        actions = self.edit_save_actions if save_changes else self.edit_cancel_actions[::-1]
        for action in actions:
            try:
                await action
            except Exception as e:
                logger.error(e)

        self.edit_save_actions = []
        self.edit_cancel_actions = []
        self.editing_mod = None

        if save_changes:
            await self.save_temp_rolegroups()
        await self.clear_temp_rolegroups()
        await self.update_rolegroup_message(await self.db.get_rolegroup(rolegroup_id=rolegroup.db_id))
        logger.info(f"Stopped editing. {'Saved' if save_changes else 'Discarded'} changes.")


    async def get_rolegroup_message(self, rolegroup: Rolegroup) -> discord.Message:
        channel = self.guild.get_channel(rolegroups_config.channel_id)
        msg = await channel.fetch_message(rolegroup.message_id)
        return msg


    async def load_temp_rolegroups(self):
        logger.debug(f"Loading temp rolegroups from db")
        self.temp_rolegroups = {r.name: r for r in await self.db.get_all_rolegroups()}


    async def update_temp_rolegroup(self, rolegroup: Rolegroup):
        self.temp_rolegroups[rolegroup.name] = rolegroup
        await self.update_rolegroup_message(rolegroup)


    def get_temp_rolegroup(self, rolegroup: Rolegroup) -> Rolegroup:
        return self.temp_rolegroups.get(rolegroup.name)


    async def save_temp_rolegroups(self):
        logger.debug(f"Saving temp rolegroups to db")
        for name, rg in self.temp_rolegroups.items():
            await self.db.update_rolegroup(rg)


    async def clear_temp_rolegroups(self):
        logger.debug(f"Clearing temp rolegroups")
        self.temp_rolegroups = {}


    @staticmethod
    async def send_simple_embed(channel: Union[discord.TextChannel, commands.Context, discord.User], content: str,
                                delete_after=None,
                                mentions: Union[List[discord.Member], discord.Member] = None) -> discord.Message:
        embed = discord.Embed(title=content, color=discord.Color.dark_gold())
        if mentions:
            if type(mentions) == list:
                embed.description = " ".join(u.mention for u in mentions)
            else:
                embed.description = mentions.mention
        if delete_after:
            msg = await channel.send(embed=embed, delete_after=delete_after)
        else:
            msg = await channel.send(embed=embed)
        return msg


def setup(bot: commands.Bot):
    bot.add_cog(Rolegroups(bot))
