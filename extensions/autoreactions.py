import logging
import re
from typing import Optional, Union

import discord
from discord.ext import commands

from db_classes.PGAutoreactDB import PGAutoreactDB
from config import autoreactions_config

import utils

logger = logging.getLogger("Referee")

from Referee import is_aight


class Autoreactions(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGAutoreactDB()
        self.guild = None
        self.autoreactions = []


    @commands.Cog.listener()
    async def on_ready(self):
        self.guild = self.bot.guilds[0]
        self.autoreactions = await self.db.get_autoreactions_list()


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.author.bot:
            await self.react_to(message)


    async def react_to(self, message: discord.Message):
        reactions = [r["emoji"] for r in self.autoreactions
                     if re.findall(r["regex"], message.content) and (
                             message.channel.id == r["channel_id"] or r["channel_id"] is None
                     )]
        logger.debug(f"Reacting to {message.content} in {message.channel} with {reactions}")
        for emoji in reactions:
            emoji = await self.get_emoji(emoji)
            await message.add_reaction(emoji)


    async def get_emoji(self, emoji):
        if len(emoji) > 1:
            emoji = discord.utils.get(self.guild.emojis, id=int(emoji))
        return emoji


    @commands.command(name="react")
    @is_aight()
    async def add_autoreaction(self, ctx: commands.Context, emoji: Union[discord.Emoji, str], regex: Optional[str] = ".*", channel: Optional[discord.TextChannel] = None):
        channel_id = channel.id if channel else None
        if type(emoji) == discord.Emoji:
            emoji = str(emoji.id)
        elif type(emoji) == str:
            if len(emoji) > 1:
                await ctx.send(f"Invalid emoji: {emoji}", delete_after=30)
                return
        try:
            re.compile(regex)
        except re.error:
            await ctx.send(f"Invalid regex: <https://regexr.com/?expression={regex}>")
            return
        await self.db.add_autoreaction(emoji=emoji, channel_id=channel_id, regex=regex)
        self.autoreactions = await self.db.get_autoreactions_list()
        await ctx.message.add_reaction(utils.emoji.thumbs_up)


    @commands.command(name="reactions")
    @is_aight()
    async def list_autoreactions(self, ctx: commands.Context):
        embed = discord.Embed(title="Autoreactions")
        autoreact_strings = [
            f"{r['id']}: {await self.get_emoji(r['emoji'])} - `{r['regex']}` - {self.bot.get_channel(r['channel_id']).mention if r['channel_id'] else 'All channels'}"
            for r in self.autoreactions]
        embed.add_field(name="ID: emoji - regex - channel", value="\n".join(autoreact_strings))
        await ctx.send(embed=embed)


    @commands.command(name="remove_react", aliases=["del_react"])
    @is_aight()
    async def del_autoreaction(self, ctx: commands.Context, autoreaction_id: int):
        await self.db.remove_autoreaction(autoreaction_id=autoreaction_id)
        self.autoreactions = await self.db.get_autoreactions_list()
        await ctx.message.add_reaction(utils.emoji.thumbs_up)


def setup(bot: commands.Bot):
    bot.add_cog(Autoreactions(bot))
