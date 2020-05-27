import logging
import io

import discord
from discord.ext import commands

from db_classes.PGReputationDB import PGReputationDB
from config import reputation_config
from models.reputation_models import Thank

from utils import emoji

from datetime import datetime, date, timedelta

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("Referee")


class Reputation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGReputationDB()
        self.guild = None


    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]
        self.self_thank_emoji = discord.utils.get(self.guild.emojis, name="cmonBruh")


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild:
            # this has to be in on_message, since it's not technically a command
            # in the sense that it starts with our prefix
            if is_thank_message(message):
                members = message.mentions
                logger.info(f"Recieved thanks from {message.author} to {', '.join(str(m) for m in members)}")
                if await self.is_on_cooldown(source_user_id=message.author.id):
                    if members:
                        await message.add_reaction(emoji.hourglass)
                    logger.debug("General cooldown active, returning")
                    return

                if len(members) > reputation_config.max_mentions:
                    await message.channel.send(
                        f"Maximum number of thanks is {reputation_config.max_mentions} per hour. Try again with less mentions.",
                        delete_after=10
                    )
                elif not members:
                    await message.channel.send(
                        f"Say \"Thanks @HelpfulUser\" to award up to {reputation_config.max_mentions} people per hour with a point on the support scoreboard!",
                        delete_after=10
                    )
                else:
                    for member in members:
                        if member.bot:
                            logger.debug(f"Thanking {member} canceled: User is bot")
                            await message.add_reaction(emoji.robot)
                        elif member == message.author:
                            logger.debug(f"Thanking {member} canceled: User thanking themselves")
                            await message.add_reaction(self.self_thank_emoji)
                        elif await self.is_on_cooldown(source_user_id=message.author.id, target_user_id=member.id):
                            logger.debug(f"Thanking {member} cancelled: Cooldown active")
                            await message.add_reaction(emoji.hourglass)
                        else:
                            new_thank = Thank(
                                source_user_id=message.author.id,
                                target_user_id=member.id,
                                channel_id=message.channel.id,
                                message_id=message.id,
                                timestamp=datetime.now()
                            )
                            await self.db.add_thank(new_thank)
                            await message.add_reaction(emoji.thumbs_up)


    async def is_on_cooldown(self, source_user_id, target_user_id=None):
        thanks = await self.db.get_thanks(since=datetime.now()-timedelta(hours=1))
        if len(thanks) >= reputation_config.max_mentions:
            return True
        if target_user_id:
            if target_user_id in [t.target_user_id for t in thanks]:
                return True
        return False

    @commands.command(name="rep", aliases=["get_rep", "score", "thanks"])
    async def get_rep(self, ctx: commands.Context, member: discord.Member = None):
        if not member:
            member = ctx.author
        leaderboard = await self.db.get_leaderboard()

        ranks = {score: i + 1 for i, score in
                 enumerate(sorted(set(x["current_rep"] for x in leaderboard), reverse=True))}

        rep = await self.db.get_user_rep(member.id)
        embed = discord.Embed(title="Support Score", color=discord.Color.dark_gold())
        embed.add_field(name=f"{member.name}:",
                        value=f"{rep} (Rank #{ranks.get(rep, len(ranks) + 1)})",
                        inline=True)
        await ctx.send(embed=embed)


    @commands.group(name="leaderboard", aliases=["scoreboard"])
    async def leaderboard(self, ctx: commands.Context):
        await ctx.trigger_typing()
        if ctx.invoked_subcommand is None:
            leaderboard = await self.db.get_leaderboard()

            img = await self.draw_scoreboard(leaderboard)
            await ctx.send(file=discord.File(img, filename="scoreboard.png"))


    @leaderboard.command()
    async def month(self, ctx: commands.Context, month_number: int = date.today().month):

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

        leaderboard = await self.db.get_leaderboard()

        if ctx.author.id not in (user_ids:=[m["user_id"] for m in leaderboard]):
            embed = discord.Embed(title=f"You are not on the scoreboard yet. Start helping others out to collect points!", color=discord.Color.dark_gold())
            await ctx.send(embed=embed, delete_after=10)
        else:
            position = user_ids.index(ctx.author.id)
            a, b = (position - 2, position + 2)
            while b >= len(leaderboard):
                a, b = a - 1, b - 1
            while a < 0:
                a, b = a + 1, b + 1
            img = await self.draw_scoreboard(leaderboard[a:b])
            await ctx.send(file=discord.File(img, filename="scoreboard.png"))


    async def draw_scoreboard(self, leaderboard: list):
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

        for i, row in enumerate(leaderboard):
            rank, member_id, score = row["rank"], row["user_id"], row["score"]
            member = self.bot.get_user(member_id)

            row_y = i * row_height + (reputation_config.fontsize // 2)
            line_y = row_y + int(reputation_config.fontsize * 1.2)

            row_color = reputation_config.font_colors.get(rank, reputation_config.default_fontcolor)

            w, h = text_draw.textsize(f"{rank}", font=fnt)
            text_draw.text((rank_x - w, row_y), f"{rank}", font=fnt,
                           fill=(255, 255, 255, 50))

            text_draw.text((name_x, row_y), f"{member.display_name}", font=fnt,
                           fill=row_color)

            w, h = text_draw.textsize(f"{score}", font=fnt)
            text_draw.text((point_x - w, row_y), f"{score}", font=fnt,
                           fill=row_color)

            text_draw.line([line_x, line_y,
                            line_x + int(max_line_width * score / leaderboard[0][2]), line_y],
                           fill=row_color, width=2)

        out = Image.alpha_composite(Image.alpha_composite(bg, text), pics)
        tmp_img = io.BytesIO()
        out.save(tmp_img, format="png")
        tmp_img.seek(0)
        return tmp_img


def is_thank_message(message: discord.Message) -> bool:
    text = message.content.lower()
    if "add_thank" in text or "thx" in text:
        if message.mentions:
            return True
        elif text.startswith("add_thank") or text.startswith("thx"):
            return True
        elif any(s.strip().startswith("add_thank") or s.strip().startswith("thx") for s in text.replace(",", ".").split(".")):
            return True
        else:
            return False




def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
