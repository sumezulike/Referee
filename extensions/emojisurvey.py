import asyncio
import datetime
import logging
from builtins import filter
from typing import Union, Tuple, List

import discord
from discord.ext import commands

from db_classes.PGEmojiSurveyDB import PGEmojiSurveyDB

from Referee import can_ban
from Referee import can_kick

from config.config import EmojiSurvey as config, Timeouts

from utils import emoji

logger = logging.getLogger("Referee")


class EmojiSurvey(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild: discord.Guild = None
        self.db = PGEmojiSurveyDB()
        self.survey_channel: discord.TextChannel = None


    @commands.Cog.listener()
    async def on_ready(self):
        """
        On_ready eventhandler, gets called by api
        """
        self.guild: discord.Guild = self.bot.guilds[0]
        self.survey_channel = self.guild.get_channel(config.channel_id)


    @can_ban()
    @commands.group(name="survey")
    async def emoji_survey(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.message.delete()


    @can_ban()
    @emoji_survey.command(name="start", aliases=["create"])
    async def start_survey(self, ctx: commands.Context):
        for custom_emoji in filter(lambda x: not x.animated, self.guild.emojis):
            try:
                msg = await self.survey_channel.send(custom_emoji)
                await asyncio.sleep(0.1)
                await msg.add_reaction(emoji.thumbs_up)
                await asyncio.sleep(0.1)
                await msg.add_reaction(emoji.thumbs_down)
                await asyncio.sleep(0.1)
                await self.db.add_message(message_id=msg.id, emoji=str(custom_emoji))
            except Exception as e:
                logger.error(f"Error creating emoji survey message: {e}")


    @can_kick()
    @emoji_survey.command(name="eval", aliases=["count"])
    async def eval_survey(self, ctx: commands.Context):
        emoji_scores = dict()
        for message_id, custom_emoji in await self.db.get_all():
            msg: discord.Message = await self.survey_channel.fetch_message(message_id)
            upvotes, downvotes = discord.utils.get(msg.reactions, emoji=emoji.thumbs_up).count-1, discord.utils.get(msg.reactions, emoji=emoji.thumbs_down).count-1
            emoji_scores[custom_emoji] = {"upvotes": upvotes,"downvotes": downvotes, "score": upvotes-downvotes}

        positive = {k: v for k, v in emoji_scores.items() if v["score"] >= 0}
        negative = {k: v for k, v in emoji_scores.items() if v["score"]  < 0}

        upvotes_report = "\n".join(f"{e} **{v['score']}** ({v['upvotes']}/{v['downvotes']})" for e, v in sorted(positive.items(), key=lambda x: x[1]["score"], reverse=True))
        downvotes_report = "\n".join(f"{e} **{v['score']}** ({v['upvotes']}/{v['downvotes']})" for e, v in sorted(negative.items(), key=lambda x: x[1]["score"]))

        embed = discord.Embed(title=f"Survey Evaluation - {datetime.datetime.now().strftime('%d %b %Y %H:%M')}")
        if upvotes_report:
            embed.add_field(name="Liked", value=upvotes_report[:1024]) # TODO: Fix message length restiction issue
        if downvotes_report:
            embed.add_field(name="Disliked", value=downvotes_report[:1024])
        await ctx.send(embed=embed)

    @can_ban()
    @emoji_survey.command(name="end", aliases=["stop"])
    async def end_survey(self, ctx: commands.Context):
        delete = await self.quick_embed_query(ctx=ctx, question=f"Are you sure you want delete all survey messages?\nGet the current results with `r!survey count` first", reraise_timeout=False)

        if delete:
            logger.info(f"Deleting the survey")
            for message_id, _ in await self.db.get_all():
                try:
                    await self.db.delete_message(message_id)
                    msg = await self.survey_channel.fetch_message(message_id)
                    await msg.delete()
                except Exception as e:
                    logger.error(f"Error deleting message: {e}")


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
            reaction, user = await self.bot.wait_for('reaction_add', timeout=Timeouts.long, check=check)
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


    @staticmethod
    async def send_simple_embed(channel: Union[discord.TextChannel, commands.Context, discord.User], content: str,
                                delete_after=None,
                                mentions: Union[List[discord.Member], discord.Member] = None) -> discord.Message:

        embed = discord.Embed(title=content if len(content) < 256 else emoji.white_check_mark,
                              color=discord.Color.dark_gold())
        if not len(content) < 256:
            embed.add_field(name="*", value=content)
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
    bot.add_cog(EmojiSurvey(bot))
