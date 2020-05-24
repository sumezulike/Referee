import logging

import discord
from discord.ext import commands

from db_classes.PGReputationDB import PGReputationDB
from config import reputation_config

from utils import emoji

from datetime import datetime, date, timedelta

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
            if message.content.lower().startswith("thank"):
                members = message.mentions
                logger.info(f"Recieved thanks from {message.author} to {', '.join(str(m) for m in members)}")
                last_given_diff = await self.db.get_time_between_lg_now(message.author.id)
                if last_given_diff:
                    if last_given_diff <= reputation_config.RepDelay:
                        await message.add_reaction(emoji.hourglass)
                        logger.debug("Cooldown active, returning")
                        return

                if len(members) > reputation_config.max_mentions:
                    await message.channel.send(
                        f"Maximum number of simultaneous thanks is {reputation_config.max_mentions}. Try again with less mentions.",
                        delete_after=10
                    )
                elif not members:
                    await message.channel.send(
                        f"Say \"Thanks @HelpfulUser @OtherHelpfulUser @AnotherHelpfulUser\" to award up to {reputation_config.max_mentions} people with a reputation point!",
                        delete_after=10
                    )
                else:
                    for member in members:
                        if member.bot:
                            logger.debug(f"Thanking {member} canceled: User is bot")
                            await message.add_reaction(emoji.robot)
                        elif member == message.author and not reputation_config.Debug:
                            logger.debug(f"Thanking {member} canceled: User thanking themselves")
                            await message.add_reaction(self.self_thank_emoji)
                        else:
                            await self.db.thank(message.author.id, member.id, message.channel.id)
                            await message.add_reaction(emoji.thumbs_up)


    @commands.command(name="rep", aliases=["get_rep"])
    async def get_rep(self, ctx: commands.Context, member: discord.Member = None):
        if not member:
            member = ctx.author
        leaderboard = await self.db.get_leaderboard()

        ranks = {score: i + 1 for i, score in
                 enumerate(sorted(set(x["current_rep"] for x in leaderboard), reverse=True))}

        rep = await self.db.get_user_rep(member.id)
        embed = discord.Embed(title="Reputation", color=discord.Color.dark_gold())
        embed.add_field(name=f"{member.name}'s reputation:",
                        value=f"{rep} (Rank #{ranks.get(rep, len(ranks) + 1)})",
                        inline=True)
        await ctx.send(embed=embed)


    @commands.group(name="leaderboard")
    async def leaderboard(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            leaderboard = await self.db.get_leaderboard()
            ranks = {score: i + 1 for i, score in
                     enumerate(sorted(set(x["current_rep"] for x in leaderboard), reverse=True))}

            embed = discord.Embed(title="Leaderboard", color=discord.Color.dark_gold())
            embed.add_field(
                name="Highest Reputations Scores:",
                value="\n".join(
                    "{}: {}#{}: {}".format(
                        str(ranks.get(x["current_rep"])).zfill(len(str(reputation_config.Leader_Limit))),
                        self.bot.get_user(x['user_id']).name,
                        self.bot.get_user(x['user_id']).discriminator, x['current_rep']
                    )
                    for x in leaderboard if x["current_rep"] > 0))
            await ctx.send(embed=embed)


    @leaderboard.command()
    async def month(self, ctx: commands.Context, month_number: int = date.today().month):

        month_name = datetime.strptime(str(month_number), "%m").strftime("%B")

        since = date(date.today().year, month_number, 1)
        until = since + timedelta(days=30)

        member_scores = {}
        for res in await self.db.get_thanks_timeframe(since, until):
            member_scores[res["target_user"]] = member_scores.get(res["target_user"], 0) + 1

        leaderboard = sorted(member_scores, key=member_scores.get, reverse=True)
        ranks = {score: i + 1 for i, score in
                 enumerate(sorted(set(member_scores.values()), reverse=True))}

        if not leaderboard:
            embed = discord.Embed(title=f"No entries for {month_name}", color=discord.Color.dark_gold())
        else:
            embed = discord.Embed(title="Leaderboard", color=discord.Color.dark_gold())
            i = 0
            embed.add_field(
                name=f"Highest Reputations Scores for {month_name}:",
                value="\n".join(
                    "{}: {}#{}: {}".format(
                        str(ranks.get(member_scores.get(user_id))).zfill(len(str(reputation_config.Leader_Limit))),
                        self.bot.get_user(user_id).name,
                        self.bot.get_user(user_id).discriminator, member_scores.get(user_id)
                    )
                    for user_id in leaderboard if member_scores.get(user_id) > 0))
        await ctx.send(embed=embed)


    @leaderboard.command()
    async def week(self, ctx: commands.Context):

        until = date.today() + timedelta(days=1)
        since = until - timedelta(days=8)

        member_scores = {}
        for res in await self.db.get_thanks_timeframe(since, until):
            member_scores[res["target_user"]] = member_scores.get(res["target_user"], 0) + 1

        leaderboard = sorted(member_scores, key=member_scores.get, reverse=True)
        ranks = {score: i + 1 for i, score in
                 enumerate(sorted(set(member_scores.values()), reverse=True))}

        embed = discord.Embed(title="Leaderboard", color=discord.Color.dark_gold())
        i = 0
        embed.add_field(
            name=f"Highest Reputations Scores for previous 7 days:",
            value="\n".join(
                "{}: {}#{}: {}".format(
                    str(ranks.get(member_scores.get(user_id))).zfill(len(str(reputation_config.Leader_Limit))),
                    self.bot.get_user(user_id).name,
                    self.bot.get_user(user_id).discriminator, member_scores.get(user_id)
                )
                for user_id in leaderboard if member_scores.get(user_id) > 0))
        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
