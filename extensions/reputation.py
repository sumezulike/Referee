import asyncio
import logging
import re
from datetime import datetime, date, timedelta

import discord
from discord.ext import commands
from typing import Optional

from config.config import Reputation as reputation_config, Timeouts
from db_classes.PGReputationDB import PGReputationDB
from extensions.reputation_graphics import *
from models.reputation_models import Thank
from utils import emoji

logger = logging.getLogger("Referee")

from Referee import can_kick, can_ban


class Reputation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGReputationDB()
        self.guild = None


    @commands.Cog.listener()
    async def on_ready(self):
        self.guild: discord.Guild = self.bot.guilds[0]
        self.self_thank_emoji = discord.utils.get(self.guild.emojis, name="cmonBruh") or emoji.x
        await self.check_thanked_roles()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild:
            # this has to be in on_message, since it's not technically a command
            # in the sense that it starts with our prefix
            if message.author.bot:
                return

            if await self.is_thank_message(message):
                await self.handle_thank_message(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if after.guild:
            # this has to be in on_message, since it's not technically a command
            # in the sense that it starts with our prefix
            if after.author.bot:
                return
            if before.content == after.content:
                return
            if before.mentions.map(lambda m: m.id) == after.mentions.map(lambda m: m.id):
                return

            if await self.is_thank_message(after):
                await self.handle_thank_message(after)

    async def handle_thank_message(self, message: discord.Message):
        mentioned_members = message.mentions
        logger.info(
            f"Received thanks from {message.author} to {', '.join(str(m) for m in mentioned_members)}: {message.content}")

        if await self.is_on_cooldown(source_user_id=message.author.id):
            if mentioned_members:
                await message.add_reaction(emoji.hourglass)
            logger.debug("General cooldown active, returning")
            return

        if len(mentioned_members) > reputation_config.max_mentions:
            logger.debug("Sending 'Too many mentions'")
            await message.channel.send(
                f"Maximum number of thanks is {reputation_config.max_mentions}. Try again with less mentions.",
                delete_after=Timeouts.short
            )
        elif not mentioned_members:
            logger.debug("Sending usage hint")
            await message.channel.send(
                f"Say \"Thanks @HelpfulUser\" or use the reply feature to award someone with a point on the support scoreboard!",
                delete_after=Timeouts.short
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
                        member_rep = await self.db.get_user_rep(member.id)
                        if member_rep == 1:
                            await self.notify_user_of_thank(member, message.author)

                        await self.check_thanked_roles(member)

                try:
                    reaction, user = await self.bot.wait_for('reaction_add', timeout=Timeouts.short,
                                                             check=check)
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

    async def notify_user_of_thank(self, member: discord.Member, source_member: discord.Member):
        thankHelp = f"You were just awarded with a reputation point by {source_member.display_name}, probably for helping them with something. **Good job!**\n" \
                    f"We count **'Thank you'** messages as a fun way to track helpfulness and community engagement.\n\n" \
 \
                    f"Every message containing a thank with a mention will be recorded, I'll react with {emoji.thumbs_up} to confirm that.\n" \
                    f"I will offer a {emoji.trashcan} reaction to take it back, just in case it was a mistake.\n\n" \
 \
                    f"To check your score  *(Spoiler: It's 1)*  use `r!rep`\n\n" \
 \
                    f"For an overview over the top 10, use `r!rep scoreboard`, `r!rep scoreboard all` for the whole list and `r!rep scoreboard me` to focus on you\n\n" \
 \
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

        text = message.content.lower()

        for word in ignore_list:
            text = text.replace(word, "")

        text = "\n".join(line for line in text.split("\n") if not line.startswith("> "))

        if re.findall(r"\bthx\b", text) and message.mentions:  # Thx @Trapture
            logger.debug("Is thank: thx mentions")
            return True

        if "thank" in text:
            if message.mentions:  # I thank thee @Trapture
                logger.debug("Is thank: mentions")
                return True
            elif text.startswith("thank"):  # Thanks bro
                logger.debug("Is thank: startswith")
                return True
            elif any(s.strip().startswith("thank") for s in re.split("\\W+", text)):  # Alright, thanks a lot
                logger.debug("Is thank: punctuation startswith")
                return True
            elif any(s.strip().endswith("thanks") for s in re.split("\\W+", text)):  # Ah thanks. Cool.
                logger.debug("Is thank: punctuation endswith thanks")
                return True
            elif "thank you" in text and text[text.find("thank you") - 1] == " ":  # Not "thank you"
                logger.debug("Is thank: thank you")
                return True
            else:
                return False
        else:
            return False


    async def check_thanked_roles(self, member=None):
        if not member:
            logger.debug("Checking all members for thank autorole")
        thanked_role = self.guild.get_role(reputation_config.thanked_role)
        for member in self.guild.members if not member else [member]:
            if thanked_role not in member.roles:
                member_rep = await self.db.get_user_rep(member.id)
                if member_rep >= reputation_config.thanked_role_threshold:
                    await member.add_roles(thanked_role, reason="Reached enough thanks")
                    logger.info(f"Added {thanked_role.name} to {member.name} with {member_rep} points")


    @commands.command(hidden=True)
    @can_kick()
    async def test_notify(self, ctx: commands.Context):
        await self.notify_user_of_thank(ctx.author, ctx.author)


    @commands.group(name="rep", aliases=["ep", "score", "thanks"])
    async def get_rep(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        """
        Displays a users current reputation score
        :param member: Any user, omit to query own score
        """
        if ctx.invoked_subcommand is None:
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


    @get_rep.command(name="history", aliases=["stats", "hist", "herstory"])
    async def thank_stats(self, ctx: commands.Context, member: Optional[discord.Member] = None):

        def display_name(u_id):  # TODO: put this where it belongs
            if not self.guild.get_member(u_id):
                return str(u_id)
            else:
                return self.guild.get_member(u_id).display_name


        if not member:
            member = ctx.author

        if member.bot:
            embed = discord.Embed(title=f"Thanking history of {member.display_name}", color=discord.Color.dark_gold())
            embed.add_field(name=f"Received: 0", value=f"{member.display_name}, the thankless hero of {self.guild.name}")
            await ctx.send(embed=embed)
            return


        thanks_received = await self.db.get_thanks(target_user_id=member.id)
        thanks_given = await self.db.get_thanks(source_user_id=member.id)
        embed = discord.Embed(title=f"Thanking history of {member.display_name}", color=discord.Color.dark_gold())
        thankers = dict()
        for t in thanks_received:
            date_str = t.timestamp.strftime('%d %b %Y')
            thankers[t.source_user_id] = thankers.get(t.source_user_id, []) + [date_str]

        thankees = dict()
        for t in thanks_given:
            date_str = t.timestamp.strftime('%d %b %Y')
            thankees[t.target_user_id] = thankees.get(t.target_user_id, []) + [date_str]

        received = "\n".join(
            f"{display_name(u_id)}{'(' + str(len(dates)) + ')' if len(dates) > 1 else ''}" for u_id, dates in
            sorted(thankers.items(), key=lambda x: len(x[1]), reverse=True))
        given = "\n".join(
            f"{display_name(u_id)}{'(' + str(len(dates)) + ')' if len(dates) > 1 else ''}" for u_id, dates in
            sorted(thankees.items(), key=lambda x: len(x[1]), reverse=True))

        embed.add_field(name=f"Received: {len(thanks_received)}", value=received if received else "Help some folks out!", inline=True)
        embed.add_field(name=f"Given: {len(thanks_given)}", value=given if given else "Say thanks every once in a while!", inline=True)
        await ctx.send(embed=embed)


    @get_rep.command(name="graph")
    @can_ban()
    async def thanks_graph(self, ctx: commands.Context):
        wait_msg = await ctx.send(f"This is going to take a while {emoji.rolling_eyes}")
        try:
            async with ctx.typing():
                filename = await generate_graph(self.guild, await self.db.get_thanks())

            await ctx.send(f"There you go {ctx.author.mention}", file=discord.File(filename))
        except Exception as e:
            await ctx.send(f"Nope, graph machine broke. {self.guild.get_member(238359385888260096).mention}!!!")
            raise e
        finally:
            await wait_msg.delete()


    @commands.command(name="scoreboard", hidden=True)
    async def old_leaderboard(self, ctx: commands.Context, *, args: Optional[str] = ""):
        if args:
            await ctx.send(f"You're probably looking for this: ```r!ep scores {args}```", delete_after=Timeouts.mid)
        else:
            await self.leaderboard(ctx)

    @get_rep.group(name="scoreboard", aliases=["leaderboard", "scores"])
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
                img = await draw_scoreboard(leaderboard=leaderboard[:reputation_config.leaderboard_max_length],
                                            guild=self.guild)
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
            img = await draw_scoreboard(leaderboard=leaderboard, guild=self.guild)
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
            img = await draw_scoreboard(leaderboard=leaderboard, guild=self.guild)
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
            img = await draw_scoreboard(leaderboard=leaderboard, guild=self.guild)
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
            img = await draw_scoreboard(leaderboard=leaderboard[a:b], highlight={"member_id": ctx.author.id},
                                        guild=self.guild)
            await ctx.send(file=discord.File(img, filename="scoreboard.png"))


def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
