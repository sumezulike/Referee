import logging
import re
from typing import Optional, Union

import discord
from discord.ext import commands

from db_classes.PGActivityDB import PGActivityDB
from config import activity_config

import utils

logger = logging.getLogger("Referee")

from Referee import is_aight


class Activity(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGActivityDB()
        self.guild = None


    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        pass

def setup(bot: commands.Bot):
    bot.add_cog(Activity(bot))
