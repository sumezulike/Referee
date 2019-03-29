import asyncio

import discord
from discord.ext import commands

from db_classes.PGModmailDB import PGModmailDB

from models import modmail_models

from utils import emoji

MOD_CHANNEL_ID = 539570743168466958


class ModMail(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGModmailDB()
        self.mod_channel = None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if await self.is_valid_mail(message):
            await self.process_modmail(message)

    @commands.Cog.listener()
    async def on_ready(self):
        self.mod_channel: discord.TextChannel = self.bot.get_channel(MOD_CHANNEL_ID)
        if not self.mod_channel:
            raise RuntimeError("Modchannel is None")

    async def is_valid_mail(self, message):
        return \
            message.guild is None and \
            not message.author.bot and \
            message.content

    async def process_modmail(self, message: discord.Message):
        author_name = f"{message.author.display_name}#{message.author.discriminator}"
        mail = modmail_models.ModMail(author_id=message.author.id, author_name=author_name, timestamp=message.created_at, content=message.content)
        modmail_id = self.db.put_modmail(mail)
        message_id = await self.report(mail)
        self.db.assign_message_id(modmail_id=modmail_id, message_id=message_id)

    async def report(self, mail: modmail_models.ModMail) -> int:
        embed = discord.Embed(title=f"**({mail.modmail_id})** New ModMail by {mail.author_name}", color=discord.Color.dark_gold())
        embed.add_field(name="Message", value=mail.content, inline=False)
        embed.add_field(name=f"Answered: {emoji.x}", value=f"Use `ref!answer {mail.modmail_id} <your answer>` to respond", inline=False)

        msg = await self.mod_channel.send(embed=embed)
        return msg.id

    async def update_modmail_answer(self, modmail_id: int, answer: modmail_models.ModMailAnswer):
        modmail = self.db.get_modmail(modmail_id)
        report_message: discord.Message = (await self.mod_channel.fetch_message(modmail.message_id))
        embed: discord.Embed = report_message.embeds[0]
        name = f"Answered: {emoji.white_check_mark}"
        if emoji.x in embed.fields[1].name:
            embed.set_field_at(1, name=name, value=f"**1. {answer.mod_name}:** \"{answer.content}\"", inline=False)

        else:
            content = embed.fields[1].value
            num_answers = len(content.split("\n"))
            embed.set_field_at(1, name=name, value=f"{content}\n**{num_answers+1}. {answer.mod_name}:** \"{answer.content}\"", inline=False)

        await report_message.edit(embed=embed)

    @commands.command(aliases=["respond", "a", "res", "ans"])
    @commands.has_permissions(kick_members=True)
    async def answer(self, ctx: commands.Context, modmail_id: int, *, message: str):
        modmail = self.db.get_modmail(modmail_id)
        embed = discord.Embed(title="Preview **(Confirm or cancel below)**", color=discord.Color.dark_gold())
        embed.add_field(name=f"Request by {modmail.author_name}", value=modmail.content, inline=False)
        embed.add_field(name=f"Answer by {ctx.author.display_name}", value=message, inline=False)

        preview: discord.Message = await ctx.send(embed=embed)
        await preview.add_reaction(emoji.white_check_mark)
        await preview.add_reaction(emoji.x)

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in [emoji.x, emoji.white_check_mark]

        async def cancel_answer():
            cancel_embed = discord.Embed(title=f"{emoji.x} Cancelled answer to {modmail_id}")
            await ctx.send(embed=cancel_embed, delete_after=30)

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
        except asyncio.TimeoutError:
            await cancel_answer()
        else:
            if str(reaction) == emoji.white_check_mark:
                answer = modmail_models.ModMailAnswer(content=message, mod_id=ctx.author.id, mod_name=ctx.author.display_name, modmail=modmail, timestamp=ctx.message.created_at)
                await self.answer_user(modmail, answer)

                sent_embed = discord.Embed(title=f"{emoji.white_check_mark} Sent answer to {modmail_id}")
                await ctx.send(embed=sent_embed, delete_after=30)
            else:
                await cancel_answer()
        finally:
            await preview.delete()
            await ctx.message.delete()

    async def answer_user(self, modmail: modmail_models.ModMail, answer: modmail_models.ModMailAnswer):
        embed = discord.Embed(name="ModMail", color=discord.Color.dark_gold())
        embed.add_field(name=f"Your request from {modmail.timestamp_str}", value=modmail.content, inline=False)
        embed.add_field(name=f"Answered by {answer.mod_name}", value=answer.content, inline=False)

        user = await self.bot.fetch_user(modmail.author_id)
        await user.send(embed=embed)
        self.db.put_answer(answer)
        await self.update_modmail_answer(modmail_id=modmail.modmail_id, answer=answer)

    @commands.command(aliases=["answers_to", "get_ans", "a?"])
    @commands.has_permissions(kick_members=True)
    async def get_answers(self, ctx: commands.Context, modmail_id: int = None):
        if modmail_id is None:
            await ctx.send(f"Usage: `!get_answers <ID>`", delete_after=30)
            return

        answers = self.db.get_answers(modmail=self.db.get_modmail(modmail_id=modmail_id))
        if not answers:
            await ctx.send(f"No answers to **({modmail_id})**")
        else:
            embed = discord.Embed(name=f"Answers to **({modmail_id})** from {answers[0].modmail.author_name}", color=discord.Color.dark_gold())
            for ans in answers:
                embed.add_field(name=f"{ans.mod_name}, {ans.timestamp_str}", value=f"{ans.content}", inline=False)
            await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(ModMail(bot))
