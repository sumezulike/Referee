import asyncio
import typing
from base64 import b64decode
import re
import string

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
            print(resp)
            await ctx.send(embed=discord.Embed(description=f"[{query}]({resp['short_url']})", color=discord.Colour.dark_gold()))

    @commands.command(name="b64")
    async def b64decode(self, ctx: commands.Context, *, query: typing.Optional[str]):
        if not query:
            embed = discord.Embed(description=f"No valid base64 encoded messsages found", color=discord.Colour.dark_gold())
            async for m in ctx.channel.history(limit=10, reverse=True):
                results = re.findall(r"[a-zA-Z0-9+/]+={0,2}", m.content)
                print(results)
                for r in results:
                    try:
                        answer = b64decode(r).decode()
                        print(answer)
                        if not all(c in string.printable for c in set(answer)):
                            raise RuntimeError("Not printable")
                        embed = discord.Embed(description=f"{r}: **{answer}**", color=discord.Colour.dark_gold())
                    except Exception as e:
                        logger.error(e)
                        continue
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
