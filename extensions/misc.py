import asyncio
import typing
from base64 import b64decode
import re
import string
from builtins import filter

import aiohttp
import urllib.parse

import discord
from discord.ext import commands

import logging

logger = logging.getLogger("Referee")


class Misc(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="explain")
    async def lmgtfy(self, ctx: commands.Context, *, query: str):
        query = query.split("<")[0].strip()
        url_query = urllib.parse.quote_plus(query)
        payload = {"short_url": {"url": f"http://lmgtfy.com/?q={url_query}"}}
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
            await ctx.send(embed=discord.Embed(description=f"[{query}]({resp['short_url']})", color=discord.Colour.dark_gold()))

    @commands.command(name="b64")
    async def b64decode(self, ctx: commands.Context, *, query: typing.Optional[str]):

        async def get_b64_strings(text: str) -> typing.Dict[str, str]:
            enc = filter(lambda x: len(x) % 4 == 0, re.findall(r"[a-zA-Z0-9+/]+={0,2}", text))
            solved = {}
            for code in enc:
                try:
                    solved[code] = b64decode(code).decode()
                except Exception as ex:
                    logger.error(ex)
            return solved

        if not query:
            embed = discord.Embed(description=f"No valid base64 encoded messages found", color=discord.Colour.dark_gold())
            async for m in ctx.channel.history(limit=10, reverse=True):
                results = await get_b64_strings(m.content)
                for c, d in results.items():
                    if not all(x in string.printable for x in set(d)):
                        continue
                    sub = await get_b64_strings(d)
                    levels = 1
                    while sub:
                        sub = await get_b64_strings(d)
                        if sub:
                            d = sub.get(d)
                            levels += 1
                    embed = discord.Embed(description=f"{c}: **{d}**" + (f" | encoded {levels} times" if levels > 1 else ""), color=discord.Colour.dark_gold())
        else:
            try:
                answer = b64decode(query).decode()
                embed = discord.Embed(description=f"{answer}", color=discord.Colour.dark_gold())
            except Exception as e:
                logger.error(e)
                embed = discord.Embed(description=f"{query} is not valid base64", color=discord.Colour.dark_gold())

        await ctx.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Misc(bot))
