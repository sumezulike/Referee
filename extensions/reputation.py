import re

import discord
from discord.ext import commands

from db_classes.PGReputationDB import PGReputationDB
from config import reputation_config

from utils import emoji


class Reputation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.regex = re.compile(r'^thank(?:s| you) <@!?([0-9]+)>,?(?: <@!?([0-9]+)>,?(?: <@!?([0-9]+)>)?)?')
        self.db = PGReputationDB()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild:
            # this has to be in on_message, since it's not technically a command
            # in the sense that it starts with our prefix
            if (m := re.match(self.regex, message.content.lower())) is not None:
                userids = m.groups()
                last_given_diff = await self.db.get_time_between_lg_now(message.author.id)
                if last_given_diff >= reputation_config.RepDelay:
                    await message.add_reaction(emoji.hourglass)
                    return
                for userid in userids:
                    if userid is None:
                        continue
                    userid = int(userid)
                    if self.bot.get_user(userid).bot:
                        continue
                    if (not reputation_config.Debug) and (userid == message.author.id):
                        continue
                    await self.db.thank(message.author.id, userid, message.channel.id)
                await message.add_reaction(emoji.thumbs_up)

    @commands.command(name="get_rep")
    async def get_rep(self, ctx: commands.Context):
        embed = discord.Embed(title="Reputation", color=discord.Color.dark_gold())
        embed.add_field(name=f"{ctx.message.author.name}'s reputation:",
                        value=str(await self.db.get_user_rep(ctx.message
                                                             .author.id)),
                        inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard")
    async def leaderboard(self, ctx: commands.Context):
        embed = discord.Embed(title="Leaderboard", color=discord.Color.dark_gold())
        i = 0
        embed.add_field(name="Highest Reputations Scores:", value="".join(
            "{}: {}#{}: {}\n".format(
                str(i := i + 1).zfill(len(str(reputation_config.LB_Limit))), self.bot.get_user(x['user_id']).name,
                self.bot.get_user(x['user_id']).discriminator, x['current_rep']
            )
            for x in await self.db.get_leaderboard()))
        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
