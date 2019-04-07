import asyncio
import typing

import discord
from discord.ext import commands

from db_classes.PGModMailDB import PGModMailDB
from models import modmail_models
from utils import emoji
from config import modmail_config
import logging

from datetime import datetime

logger = logging.getLogger("Referee")


class ModMail(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGModMailDB()
        self.mod_channel: discord.TextChannel = None  # will be loaded in on_ready
        self.last_messages_times = {}
        self.guild: discord.Guild = self.bot.guilds[0]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Eventlistener for messages, gets called by api
        :param message: The message object that caused the event
        """
        if await self.is_valid_mail(message):
            cooldown = await self.get_cooldown(message.author.id)
            if cooldown <= 0:
                logger.info(f"Recieved valid mail: '{message.content}' from {message.author.name}#{message.author.discriminator}")
                await self.process_modmail(message)
                ok_embed = discord.Embed(title="Forwarded your message to mod team!", color=discord.Color.dark_gold())
                await message.channel.send(embed=ok_embed, delete_after=30)
                await self.reset_cooldown(message.author.id)
            else:
                cooldown_embed = discord.Embed(
                    title=f"Please wait for {cooldown} minutes before submitting another request to the mod team",
                    color=discord.Color.dark_gold()
                )
                await message.channel.send(embed=cooldown_embed, delete_after=30)

    async def get_cooldown(self, user_id: int) -> int:
        """
        Get the users remaining cooldown
        :param user_id:
        :return: The users remaining cooldown in minutes else 0
        """
        if user_id not in self.last_messages_times:
            return 0
        else:
            minutes_passed = (datetime.now() - self.last_messages_times[user_id]).seconds//60
            cooldown = modmail_config.cooldown - minutes_passed
            if cooldown <= 0:
                del self.last_messages_times[user_id]
                return 0
            else:
                return cooldown

    async def reset_cooldown(self, user_id: int):
        """
        Restarts the users cooldown
        :param user_id:
        """
        self.last_messages_times[user_id] = datetime.now()

    @commands.Cog.listener()
    async def on_ready(self):
        """
        On_ready eventhandler, gets called by api
        """
        self.mod_channel: discord.TextChannel = self.bot.get_channel(modmail_config.mod_channel_id)
        if not self.mod_channel:
            logger.error(f"Channel with ID {modmail_config.mod_channel_id} not found")
            raise RuntimeError(f"Channel with ID {modmail_config.mod_channel_id} not found")

    async def is_valid_mail(self, message: discord.Message):
        """
        Checks whether a message should be forwarded to the mods
        :param message: Message object as passed to :meth:`on_message`
        :return: A boolean indicating whether to process this message
        """
        if message.guild is not None:  # Only process private messages
            return False
        if message.author.bot:  # Do not forward messages from bots
            return False
        if not message.content:  # Do not forward empty messages (images, files, ...)
            return False
        if len(message.content.split()) <= 1:
            return False
        if not self.guild.get_member(message.author.id):
            return False
        return True

    async def process_modmail(self, message: discord.Message):
        """
        Executes the steps to report and save this message as a modmail
        :param message: Message object as passed to :meth:`on_message`
        """
        author_name = f"{message.author.display_name}#{message.author.discriminator}"  # Username#1337

        mail = modmail_models.ModMail(author_id=message.author.id, author_name=author_name,
                                      timestamp=message.created_at, content=message.content)

        modmail_id = await self.db.put_modmail(mail)  # Save to database
        logger.info(f"Saved mail to db: '{mail.content}'. db_id: {modmail_id}")
        message_id = await self.report(mail)  # Send to mod_channel
        logger.info(f"Sent mail to mods: '{mail.content}'. msg_id: {message_id}")
        await self.db.assign_message_id(modmail_id=modmail_id,
                                  message_id=message_id)  # Save discord message ID to db for updating

    async def report(self, mail: modmail_models.ModMail) -> int:
        """
        Forwards the mail to the mod_channel
        :param mail: A :class:`ModMail` object containing all neccesary data
        :return: The id of the generated discord message as :class:`int`
        """
        embed = discord.Embed(title=f"**[{mail.modmail_id}]** - *{mail.author_name}*", color=discord.Color.dark_gold())
        embed.add_field(name="Message", value=mail.content, inline=False)
        embed.add_field(name=f"Answered: {emoji.x}",
                        value=f"Use `ref!answer {mail.modmail_id} <your answer>` to respond", inline=False)

        msg = await self.mod_channel.send(embed=embed)
        return msg.id

    async def update_modmail_answer(self, modmail: modmail_models.ModMail, answer: modmail_models.ModMailAnswer):
        """
        Updates the message generated by :meth:`report` to indicate an answer
        :param modmail: The :class:`ModMail` that has been answered
        :param answer: The answer as a :class:`ModMailAnswer`
        """
        report_message: discord.Message = (await self.mod_channel.fetch_message(modmail.message_id))
        embed: discord.Embed = report_message.embeds[0]
        name = f"Answered: {emoji.white_check_mark}"
        if emoji.x in embed.fields[1].name:  # If unanswered yet
            embed.set_field_at(1, name=name, value=f"**1. {answer.mod_name}:** \"{answer.content}\"", inline=False)

        else:
            content = embed.fields[1].value
            num_answers = len(content.split("\n"))
            embed.set_field_at(1, name=name,
                               value=f"{content}\n**{num_answers + 1}. {answer.mod_name}:** \"{answer.content}\"",
                               inline=False)

        logger.info(f"Updated modmail: '{modmail.modmail_id}'. Answer: {answer.content}")
        await report_message.edit(embed=embed)

    async def answer_user(self, modmail: modmail_models.ModMail, answer: modmail_models.ModMailAnswer):
        """
        Generates an embed answer and sends it to the user
        :param modmail: The :class:`ModMail` that has been answered
        :param answer: The answer as a :class:`ModMailAnswer`
        """
        embed = discord.Embed(name="ModMail", color=discord.Color.dark_gold())
        embed.add_field(name=f"Your request from {modmail.timestamp_str}", value=modmail.content, inline=False)

        if modmail_config.anonymize_responses:
            name = f"Answer from mods"
        else:
            name = f"Answer from {answer.mod_name}"

        embed.add_field(name=name, value=answer.content, inline=False)

        user = await self.bot.fetch_user(modmail.author_id)
        await user.send(embed=embed)
        logger.info(f"Sent answer to user: '{modmail.modmail_id}'. Answer: {answer.content}")
        await self.db.put_answer(answer)
        logger.info(f"Saved answer to db: '{modmail.modmail_id}'. Answer: {answer.content}")
        await self.update_modmail_answer(modmail=modmail, answer=answer)

    @commands.command(aliases=["respond", "a", "res", "ans"])
    @commands.has_permissions(kick_members=True)
    async def answer(self, ctx: commands.Context, modmail_id: typing.Optional[int], *, message: str = ""):
        """
        Answers to a users request. Usage: r!answer [id] <your answer>
        """
        if modmail_id:
            modmail = await self.db.get_modmail(int(modmail_id))

        else:  # User omitted id
            modmail = await self.db.get_latest_modmail()
            modmail_id = modmail.modmail_id

        embed = discord.Embed(title="Preview **(Confirm or cancel below)**", color=discord.Color.dark_gold())
        embed.add_field(name=f"Message by {modmail.author_name}", value=modmail.content, inline=False)
        if modmail_config.anonymize_responses:
            name = f"Answer"
        else:
            name = f"Answer by {ctx.author.display_name}"
        embed.add_field(name=name, value=message, inline=False)

        preview: discord.Message = await ctx.send(embed=embed)
        await preview.add_reaction(emoji.white_check_mark)
        await preview.add_reaction(emoji.x)

        def check(_reaction, _user):
            return _user == ctx.author and str(_reaction.emoji) in [emoji.x, emoji.white_check_mark]

        async def send_cancelled_answer():
            """
            Inner helpmethod to signal a cancelled response
            """
            cancel_embed = discord.Embed(title=f"{emoji.x} Cancelled answer to {modmail_id}")
            await ctx.send(embed=cancel_embed, delete_after=30)

        async def send_sent_answer():
            """
            Inner helpmethod to signal a sent response
            """
            sent_embed = discord.Embed(title=f"{emoji.white_check_mark} Sent answer to {modmail_id}")
            await ctx.send(embed=sent_embed, delete_after=30)

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0,
                                                     check=check)  # Wait for a choice by user who invoked command
        except asyncio.TimeoutError:
            await send_cancelled_answer()
        else:
            if str(reaction) == emoji.white_check_mark:  # only path where user gets a response
                answer = modmail_models.ModMailAnswer(content=message, mod_id=ctx.author.id,
                                                      mod_name=ctx.author.display_name, modmail=modmail,
                                                      timestamp=ctx.message.created_at)
                await self.answer_user(modmail, answer)

                await send_sent_answer()

            else:
                await send_cancelled_answer()
        finally:
            await preview.delete()
            await ctx.message.delete()


def setup(bot: commands.Bot):
    bot.add_cog(ModMail(bot))
