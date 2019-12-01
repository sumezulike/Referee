import asyncio
import discord
from discord.ext import commands
import timeit
import os

from db_classes.PGHistoryDB import PGHistoryDB
from models.history_models import HistoryMessage
import logging

logger = logging.getLogger("Referee")

REPORT_FILEPATH = "history.csv"

class History(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGHistoryDB()
        self.guild: discord.Guild = None  # initialized in on_ready

    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Called by api whenever a message is received.
        """
        await self.process_message(message)


    async def process_message(self, message: discord.Message):
        if not message.guild:
            return
        if not message.type == discord.MessageType.default:
            return
        if not message.content:
            return

        msg = HistoryMessage(user_id=message.author.id,
                             channel_id=message.channel.id,
                             timestamp=message.created_at,
                             content=message.clean_content)

        await self.db.put_message(msg)


    @commands.command(name="rebase")
    @commands.has_permissions(kick_members=True)
    async def rebase(self, ctx: commands.Context):
        """
        Pulls the entire servers history. RIP.
        """
        if ctx.author.id != 238359385888260096:
            logger.warning(f"{ctx.author} tried to rebase")
            await ctx.send("Ehh. Please discuss this with <@238359385888260096>")
            return
        await ctx.send("This is going to take a while Q_Q", delete_after=30)
        start_time = timeit.default_timer()

        logger.info("Attempting to rebase history")
        for channel in (c for c in ctx.guild.channels if type(c) == discord.TextChannel):  # type: discord.TextChannel

            channel_start_time = timeit.default_timer()
            async for message in channel.history(oldest_first=True, limit=None):
                await self.process_message(message)
            dur = timeit.default_timer() - channel_start_time
            logger.info(f"{channel.name} pulled in {int(dur)}s")

        dur = timeit.default_timer() - start_time
        logger.info(f"Rebase done in {int(dur)}s")
        await ctx.send(f"Rebase done in {int(dur)}s")


    @commands.command(aliases=["history"])
    @commands.has_permissions(kick_members=True)
    async def gethistory(self, ctx: commands.Context, member: discord.Member):
        def clean(s: str):
            return s.replace('"', '""')

        messages = await self.db.get_messages(member.id)
        with open(REPORT_FILEPATH, "w") as file:
            file.write(f"# Post history of {member.display_name}#{member.discriminator}\n")
            file.write("message, timestamp, channel_id\n")
            file.write("\n".join("\"{}\", {}, {}".format(clean(m.content), m.timestamp, m.channel_id) for m in messages))

        await ctx.author.send(file=discord.File(REPORT_FILEPATH))

        os.remove(REPORT_FILEPATH)

def setup(bot: commands.Bot):
    bot.add_cog(History(bot))
