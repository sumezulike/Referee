import asyncio
import logging
import io
from typing import Optional

import discord
from discord.ext import commands

import re

from db_classes.PGReputationDB import PGReputationDB
from config.config import Reputation as reputation_config
from models.reputation_models import Thank

from utils import emoji

from datetime import datetime, date, timedelta

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("Referee")

from Referee import is_aight


class Reputation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGReputationDB()
        self.guild = None
        self.muted = {}


    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]
        self.self_thank_emoji = discord.utils.get(self.guild.emojis, name="cmonBruh") or emoji.x


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild:
            # this has to be in on_message, since it's not technically a command
            # in the sense that it starts with our prefix
            if message.author.bot:
                return

            if await self.is_thank_message(message):
                mentioned_members = message.mentions
                logger.info(
                    f"Recieved thanks from {message.author} to {', '.join(str(m) for m in mentioned_members)}: {message.content}")

                if message.author.id in self.muted:
                    if self.muted.get(message.author.id) > datetime.now():
                        logger.debug(f"Thanking canceled: User is muted")
                        await message.add_reaction(emoji.x)
                        return
                    else:
                        self.muted.pop(message.author.id)

                if await self.is_on_cooldown(source_user_id=message.author.id):
                    if mentioned_members:
                        await message.add_reaction(emoji.hourglass)
                    logger.debug("General cooldown active, returning")
                    return

                if len(mentioned_members) > reputation_config.max_mentions:
                    logger.debug("Sending 'Too many mentions'")
                    await message.channel.send(
                        f"Maximum number of thanks is {reputation_config.max_mentions}. Try again with less mentions.",
                        delete_after=10
                    )
                elif not mentioned_members:
                    logger.debug("Sending usage hint")
                    await message.channel.send(
                        f"Say \"Thanks @HelpfulUser\" to award someone with a point on the support scoreboard!",
                        delete_after=10
                    )
                else:
                    invalid = []
                    error_emojis = []
                    for member in mentioned_members:
                        if member.bot:
                            invalid.append(member)
                            error_emojis.append(emoji.robot)
                            logger.debug(f"Thanking {member} canceled: User is bot")
                        elif member == message.author:
                            invalid.append(member)
                            error_emojis.append(self.self_thank_emoji)
                            logger.debug(f"Thanking {member} canceled: User thanking themselves")
                        elif await self.is_on_cooldown(source_user_id=message.author.id, target_user_id=member.id):
                            invalid.append(member)
                            error_emojis.append(emoji.hourglass)
                            logger.debug(f"Thanking {member} cancelled: Cooldown active")

                    valid = [m for m in mentioned_members if m not in invalid]
                    if not valid:
                        for e in error_emojis:
                            await message.add_reaction(e)
                    else:
                        await message.add_reaction(emoji.thumbs_up)
                        await message.add_reaction(emoji.trashcan)
                        await asyncio.sleep(0.5)
                        trash_reaction = discord.utils.find(lambda x: x.emoji == emoji.trashcan, message.reactions)
                        thumbs_up_reaction = discord.utils.find(lambda x: x.emoji == emoji.thumbs_up,
                                                                message.reactions)

                        def check(_reaction: discord.Reaction, _user):
                            return _reaction.message.id == message.id and _user == message.author and str(
                                _reaction.emoji) in [emoji.trashcan, emoji.thumbs_up]

                        async def save_thanks(members):
                            for member in members:
                                await self.db.add_thank(Thank(
                                    source_user_id=message.author.id,
                                    target_user_id=member.id,
                                    channel_id=message.channel.id,
                                    message_id=message.id,
                                    timestamp=datetime.now())
                                )
                                if await self.db.get_user_rep(member.id) == 1:
                                    await self.notifyUserOfThank(member, message.author)

                        try:
                            reaction, user = await self.bot.wait_for('reaction_add', timeout=10.0, check=check)
                        except asyncio.TimeoutError:
                            logger.debug("Thank confirmed: Timeout")
                            async for user in trash_reaction.users():
                                await message.remove_reaction(emoji.trashcan, user)
                            await save_thanks(valid)

                        else:
                            if reaction.emoji == emoji.trashcan:
                                logger.debug("Thank cancelled")
                                async for user in thumbs_up_reaction.users():
                                    await message.remove_reaction(emoji.thumbs_up, user)
                                await asyncio.sleep(1)
                                async for user in trash_reaction.users():
                                    await message.remove_reaction(emoji.trashcan, user)
                            else:
                                logger.debug("Thank confirmed: Thumbs up")
                                async for user in trash_reaction.users():
                                    await message.remove_reaction(emoji.trashcan, user)
                                await save_thanks(valid)


    async def notifyUserOfThank(self, member: discord.Member, source_member: discord.Member):
        thankHelp = f"You were just awarded with a reputation point by {source_member.display_name}, probably for helping them with something. **Good job!**\n" \
                    f"We count **'Thank you'** messages as a fun way to track helpfulness and community engagement.\n\n" \
                    f"Every message containing a thank with a mention will be recorded, I'll react with {emoji.thumbs_up} to confirm that.\n\n" \
                    f"To check your score *(Spoiler: It's 1)* use `r!rep`\n\n" \
                    f"For an overview over the top 10, use `r!scoreboard`, `r!scoreboard all` for the whole list and `r!scoreboard me` to focus on you\n\n" \
                    f"**Thanks for having a positive impact on the community!**"
        embed = discord.Embed(title="You are appreciated!")
        embed.add_field(name=f"{member.display_name.replace(' ', '_').lower()}.reputation += 1;", value=thankHelp)
        await member.send(embed=embed)


    async def is_on_cooldown(self, source_user_id, target_user_id=None):
        all_thanks = await self.db.get_thanks(since=datetime.now() - timedelta(seconds=reputation_config.cooldown))
        thanks = [t for t in all_thanks if t.source_user_id == source_user_id]
        if len(thanks) >= reputation_config.max_mentions:
            return True
        if target_user_id:
            if target_user_id in [t.target_user_id for t in thanks]:
                return True
        return False


    @staticmethod
    async def is_thank_message(message: discord.Message) -> bool:
        ignore_list = ["thanking", "thanker", "thanked"]
        split_punctuation = "!?:;->"

        text = message.content.lower()

        for word in ignore_list:
            text = text.replace(word, "")

        text = "\n".join(line for line in text.split("\n") if not line.startswith("> "))

        if re.findall(r"\bthx\b", text) and message.mentions:  # Thx @Trapture
            logger.debug("Is thank: thx mentions")
            return True

        if "thank" in text:
            for p in split_punctuation:
                text = text.replace(p, ".")

            if message.mentions:  # I thank thee @Trapture
                logger.debug("Is thank: mentions")
                return True
            elif text.startswith("thank"):  # Thanks bro
                logger.debug("Is thank: startswith")
                return True
            elif any(s.strip().startswith("thank") for s in text.split(".")):  # Alright, thanks a lot
                logger.debug("Is thank: punctuation startswith")
                return True
            elif any(s.strip().endswith("thanks") for s in text.split(".")):  # Ah thanks. Cool.
                logger.debug("Is thank: punctuation endswith thanks")
                return True
            elif "thank you" in text and text[text.find("thank you") - 1] == " ":  # Not "thank you"
                logger.debug("Is thank: thank you")
                return True
            else:  # @Trapture likes to thank people
                return False
        else:
            return False


    @commands.command(hidden=True)
    # @is_aight()
    async def testNotify(self, ctx: commands.Context):
        await self.notifyUserOfThank(ctx.author, ctx.author)


    @commands.command(name="rep", aliases=["ep", "score", "thanks"])
    async def get_rep(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """
        Displays a users current reputation score
        :param member: Any user, omit to query own score
        """
        if not member:
            member = ctx.author
        leaderboard = await self.db.get_leaderboard()

        rank = [m["rank"] for m in leaderboard if m["user_id"] == member.id]
        if rank:
            rank = rank[0]

        rep = await self.db.get_user_rep(member.id)

        if member.bot:
            rep = "Math.Infinity"  # Not python, but it looks better than math.inf
            rank = "0"  # It's an easteregg, it doesn't have to make sense

        embed = discord.Embed(title="Support Score", color=discord.Color.dark_gold())
        embed.add_field(name=f"{member.name}:",
                        value=f"{rep} " + (f"(Rank #{rank})" if rank else ""),
                        inline=True)
        await ctx.send(embed=embed)


    @commands.command(name="thankmute", aliases=["tmute", "nothank", "nothanks"], hidden=True)
    @is_aight()
    async def thankmute(self, ctx: commands.Context, member: discord.Member, duration: str = None):
        """
        This is not neccesary
        :param member:
        :param duration:
        """
        if not duration:
            await ctx.send(f"Usage: {ctx.prefix}thankmute @Member 10m\nPossible time units: s, m, h, d")
            return

        factors = {
            "s": 1,
            "m": 60,
            "h": 60 * 60,
            "d": 60 * 60 * 24
        }
        unit_names = {
            "s": "second",
            "m": "minute",
            "h": "hour",
            "d": "day"
        }
        unit = duration[-1].lower()
        factor = factors.get(unit, 0)

        number = duration[:-1] if factor else duration
        factor = factor or 60

        try:
            seconds = int(number) * factor
        except ValueError:
            await ctx.send(f"Usage: {ctx.prefix}thankmute @Member 10m\nPossible time units: s, m, h, d")
            return
        end_time = datetime.now() + timedelta(seconds=seconds)
        self.muted[member.id] = end_time
        await ctx.message.add_reaction(emoji.white_check_mark)


    @commands.group(name="scoreboard")
    async def leaderboard(self, ctx: commands.Context):
        """
        Displays the reputation scoreboard. Can be invoked with different subcommands
        """
        await ctx.trigger_typing()
        if ctx.invoked_subcommand is None:
            leaderboard = await self.db.get_leaderboard()

            if not leaderboard:
                embed = discord.Embed(title=f"No entries", color=discord.Color.dark_gold())
                await ctx.send(embed=embed)
            else:
                img = await self.draw_scoreboard(leaderboard[:reputation_config.leaderboard_max_length])
                await ctx.send(file=discord.File(img, filename="scoreboard.png"))


    @leaderboard.command()
    async def all(self, ctx: commands.Context):
        """
        Display entire scoreboard, not only first places
        """
        leaderboard = await self.db.get_leaderboard()

        if not leaderboard:
            embed = discord.Embed(title=f"No entries", color=discord.Color.dark_gold())
            await ctx.send(embed=embed)
        else:
            img = await self.draw_scoreboard(leaderboard)
            await ctx.send(file=discord.File(img, filename="scoreboard.png"))


    @leaderboard.command()
    async def month(self, ctx: commands.Context, month_number: int = date.today().month):
        """
        Display scoreboard for a certain month of this year
        :param month_number: 1 (January) - 12 (December)
        """

        month_name = datetime.strptime(str(month_number), "%m").strftime("%B")

        since = date(date.today().year, month_number, 1)
        until = since + timedelta(days=30)

        leaderboard = await self.db.get_leaderboard(since, until)

        if not leaderboard:
            embed = discord.Embed(title=f"No entries for {month_name}", color=discord.Color.dark_gold())
            await ctx.send(embed=embed)
        else:
            img = await self.draw_scoreboard(leaderboard)
            await ctx.send(file=discord.File(img, filename="scoreboard.png"))


    @leaderboard.command()
    async def week(self, ctx: commands.Context):
        """
        Display this weeks scoreboard
        """

        until = date.today() + timedelta(days=1)
        since = until - timedelta(days=8)

        leaderboard = await self.db.get_leaderboard(since, until)

        if not leaderboard:
            embed = discord.Embed(title=f"No entries for the last week", color=discord.Color.dark_gold())
            await ctx.send(embed=embed)
        else:
            img = await self.draw_scoreboard(leaderboard)
            await ctx.send(file=discord.File(img, filename="scoreboard.png"))


    @leaderboard.command()
    async def me(self, ctx: commands.Context):
        """
        Display an excerpt of the scoreboard centered on your position
        :param ctx:
        :return:
        """

        leaderboard = await self.db.get_leaderboard()

        if ctx.author.id not in (user_ids := [m["user_id"] for m in leaderboard]):
            embed = discord.Embed(
                title=f"You are not on the scoreboard yet. Start helping others out to collect points!",
                color=discord.Color.dark_gold())
            await ctx.send(embed=embed, delete_after=10)
        else:
            position = user_ids.index(ctx.author.id)
            a, b = (position - 3, position + 4)
            while b >= len(leaderboard):
                a, b = a - 1, b - 1
            while a < 0:
                a, b = a + 1, b + 1
            img = await self.draw_scoreboard(leaderboard[a:b], highlight={"member_id": ctx.author.id})
            await ctx.send(file=discord.File(img, filename="scoreboard.png"))


    async def draw_scoreboard(self, leaderboard: list, highlight=None):
        width = reputation_config.fontsize * 13
        row_height = reputation_config.fontsize + reputation_config.fontsize // 2
        height = (len(leaderboard) + 1) * row_height

        bg = Image.new("RGBA", (width, height), (255, 255, 255, 0))
        text = Image.new("RGBA", bg.size, (255, 255, 255, 0))

        pics = Image.new("RGBA", bg.size, (255, 255, 255, 0))
        fnt = ImageFont.truetype('coolvetica.ttf', reputation_config.fontsize)
        text_draw = ImageDraw.Draw(text)

        rank_x = reputation_config.fontsize
        name_x = 2 * reputation_config.fontsize
        point_x = width - reputation_config.fontsize

        line_x = name_x
        max_line_width = (point_x - name_x)

        i = 0

        for row in leaderboard:
            rank, member_id, score = row["rank"], row["user_id"], row["score"]
            member = self.guild.get_member(member_id)
            if not member:
                logger.error(f"No member with user_id {member_id}")
                continue

            row_y = i * row_height + (reputation_config.fontsize // 2)
            line_y = row_y + int(reputation_config.fontsize * 1.2)

            row_color = reputation_config.font_colors.get(rank, reputation_config.default_fontcolor)

            if highlight:
                if (highlight.get("member_id", None) == member_id or
                        highlight.get("rank", None) == rank or
                        highlight.get("score", None) == score or
                        highlight.get("row", None) == i):
                    row_color = reputation_config.highlight_color

            w, h = text_draw.textsize(f"{rank}", font=fnt)
            text_draw.text((rank_x - w, row_y), f"{rank}", font=fnt,
                           fill=(255, 255, 255, 50))
            name = member.display_name
            w, h = text_draw.textsize(f"{name}", font=fnt)
            score_w, _ = text_draw.textsize(f"{score}", font=fnt)
            while name_x + w >= point_x - score_w:
                name = name[:-1]
                w, h = text_draw.textsize(f"{name}...", font=fnt)
            text_draw.text((name_x, row_y), f"{name}" if name == member.display_name else f"{name}...", font=fnt,
                           fill=row_color)

            w, h = text_draw.textsize(f"{score}", font=fnt)
            text_draw.text((point_x - w, row_y), f"{score}", font=fnt,
                           fill=row_color)

            text_draw.line([line_x, line_y,
                            line_x + int(max_line_width * score / leaderboard[0]["score"]), line_y],
                           fill=row_color, width=2)

            i += 1

        out = Image.alpha_composite(Image.alpha_composite(bg, text), pics)
        tmp_img = io.BytesIO()
        out.save(tmp_img, format="png")
        tmp_img.seek(0)
        return tmp_img


def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
