import asyncio

import aiohttp
import urllib.parse

import discord
from discord.ext import commands

import logging
from utils import emoji

logger = logging.getLogger("Referee")


class Bouncer(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="explain")
    async def lmgtfy(self, ctx: commands.Context, *, query: str):
        query = urllib.parse.quote_plus(query)
        payload = {"short_url": {"url": f"http://lmgtfy.com/?q={query}"}}
        headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:66.0) Gecko/20100101 Firefox/66.0",
                   "Accept": "application/json, text/plain, */*",
                   "Accept-Language": "en-US,en;q=0.5",
                   "Accept-Encoding": "gzip, deflate",
                   "Referer": "https://lmgtfy.com/",
                   "Content-Type": "application/json;charset=utf-8",
                   "Origin": "https://lmgtfy.com",
                   "Connection": "close"
                   }

        async with aiohttp.ClientSession(headers=headers) as session:
            short = await session.post("https://api.lmgtfy.com/short_urls", json=payload)
            resp = await short.json()
            print(resp)
            await ctx.send(embed=discord.Embed(title=f"<{resp['short_url']}>", color=discord.Colour.dark_gold()))


def setup(bot: commands.Bot):
    bot.add_cog(Bouncer(bot))
