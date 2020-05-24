import re

import discord
from discord.ext import commands

from db_classes.PGReputationDB import PGReputationDB

class Reputation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.regex = re.compile(r'^thank(?:s| you),? <@!([0-9]+)>!?$')
        self.db = PGReputationDB()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.guild:
            # this has to be in on_message, since it's not technically a command
            # in the sense that it starts with our prefix
            if (m := re.match(self.regex, message.content.lower())) is not None:
                userid = m.group(1)
                last_given = await self.db.get_last_given(int(userid))
                await self.db.update_last_given(int(userid))
                await message.channel.send("previous lastgiven: " + str(last_given) + ", new last_given: " + str(await self.db.get_last_given(int(userid))))

    @commands.command(name="get_rep")
    async def get_rep(self, ctx: commands.Context):
        await ctx.send(await self.db.get_user_rep(ctx.message.author.id))


def setup(bot: commands.Bot):
    bot.add_cog(Reputation(bot))
