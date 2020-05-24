import logging

import discord
from discord.ext import commands

from db_classes.PGReputationDB import PGReputationDB
from config import reputation_config

from utils import emoji

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
                if len(members) > reputation_config.max_mentions:
                    await message.channel.send(
                        f"Maximum number of simultaneous thanks is {reputation_config.max_mentions}. Try again with less mentions.",
                        delete_after=30
                    )
                elif not members:
                    await message.channel.send(
                        f"Say \"Thanks @HelpfulUser @OtherHelpfulUser @AnotherHelpfulUser\" to award up to {reputation_config.max_mentions} people with a reputation point!",
                        delete_after=30
                    )
                else:
                    logger.debug("Attempting to get last_given_diff")
                    try:
                        last_given_diff = await self.db.get_time_between_lg_now(message.author.id)
                        if last_given_diff:
                            if last_given_diff <= reputation_config.RepDelay:
                                await message.add_reaction(emoji.hourglass)
                                logger.debug("Cooldown active, returning")
                                return
                    except Exception as e:
                        logger.error(e)
                    logger.debug("Time okay, iterating members")
                    for member in members:
                        if member.bot:
                            logger.debug(f"Thanking {member} canceled: User is bot")
                            await message.add_reaction(emoji.robot)
                        elif member == message.author and not reputation_config.Debug:
                            logger.debug(f"Thanking {member} canceled: User thanking themselves")
                            await message.add_reaction(self.self_thank_emoji)
                        else:
                            logger.debug("Attempting to thank")
                            try:
                                await self.db.thank(message.author.id, member.id, message.channel.id)
                            except Exception as e:
                                logger.error(e)
                            await message.add_reaction(emoji.thumbs_up)
                await message.delete(delay=30)


    @commands.command(name="rep", aliases=["get_rep"])
    async def get_rep(self, ctx: commands.Context, member: discord.Member = None):
        if not member:
            member = ctx.author
        embed = discord.Embed(title="Reputation", color=discord.Color.dark_gold())
        embed.add_field(name=f"{member.name}'s reputation:",
                        value=str(await self.db.get_user_rep(member.id)),
                        inline=True)
        await ctx.send(embed=embed)


    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx: commands.Context):
        embed = discord.Embed(title="Leaderboard", color=discord.Color.dark_gold())
        i = 0
        embed.add_field(name="Highest Reputations Scores:", value="".join(
            "{}: {}#{}: {}\n".format(
                str(i := i + 1).zfill(len(str(reputation_config.Leader_Limit))), self.bot.get_user(x['user_id']).name,
                self.bot.get_user(x['user_id']).discriminator, x['current_rep']
            )
            for x in await self.db.get_leaderboard()))
        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
