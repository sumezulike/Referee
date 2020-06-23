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
from Referee import is_aight
from utils import emoji

logger = logging.getLogger("Referee")


class Misc(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild: discord.Guild = None


    @commands.Cog.listener()
    async def on_ready(self):
        """
        On_ready eventhandler, gets called by api
        """
        self.guild: discord.Guild = self.bot.guilds[0]

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        content = message.content.lower()
        if len(content.split()) == 1 and content.endswith(".gif"):
            logger.debug(f"Fetching gif: {content}")
            query = content.split(".gif")[0]
            url = await self.fetch_gif(query)
            gif_message = await message.channel.send(url)
            await gif_message.add_reaction(emoji.trashcan)

            def check(reaction: discord.Reaction, user):
                return user == message.author and str(reaction.emoji) == emoji.trashcan and reaction.message.id == gif_message.id

            try:
                reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            except asyncio.TimeoutError:
                await gif_message.remove_reaction(emoji.trashcan, self.bot.user)
            else:
                await gif_message.delete()

    async def fetch_gif(self, query):
        query = query.replace("_", "-")
        url_query = urllib.parse.quote_plus(query)
        params = {"sort": "relevant"}
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
            async with await session.get(f"https://giphy.com/search/{url_query}", params=params) as resp:
                body = await resp.text()
                match = re.search(r"Giphy\.renderSearch.+?url\": \"(.*?)\"", body, flags=re.DOTALL)
                if match:
                    url = match[1]
                    return url
                else:
                    logger.debug(f"No match")

    @commands.command(name="explain")
    async def lmgtfy(self, ctx: commands.Context, *, query: str):
        """
        Search for a term on lmgtfy.com
        :param query: The search query
        """
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
            await ctx.send(
                embed=discord.Embed(description=f"[{query}]({resp['short_url']})", color=discord.Colour.dark_gold()))


    @commands.command(name="b64")
    async def b64decode(self, ctx: commands.Context, *, query: typing.Optional[str]):
        """
        Decode a base64 encoded string
        :param query: A base64 encoded string. Omit to have Referee find one in the previous messages
        """

        async def get_b64_strings(text: str) -> typing.Dict[str, str]:
            enc = filter(lambda x: len(x) % 4 == 0, re.findall(r"[a-zA-Z0-9+/]+={0,2}", text))
            solved = {}
            for code in enc:
                try:
                    dec = b64decode(code).decode()
                    if all(x in string.printable for x in set(dec)):
                        solved[code] = dec
                except Exception as ex:
                    logger.error(ex)
            return solved


        if not query:
            found_hits = {}
            async for m in ctx.channel.history(limit=20, reverse=True):
                results = await get_b64_strings(m.content)
                for c, d in results.items():
                    sub = await get_b64_strings(d)
                    levels = 1
                    while sub:
                        sub = await get_b64_strings(d)
                        if sub:
                            d = sub.get(d)
                            levels += 1
                    found_hits[c] = (d, levels)
            if found_hits:
                embed = discord.Embed(description="\n\n".join(
                    [f"*{c}* - **{d[0]}**" + (f" | encoded {d[1]} times" if d[1] > 1 else "") for c, d in
                     found_hits.items()]), color=discord.Colour.dark_gold())
            else:
                embed = discord.Embed(description="No valid base64 found", color=discord.Colour.dark_gold())
            await ctx.send(embed=embed)
        else:
            try:
                answer = b64decode(query).decode()
                embed = discord.Embed(description=f"{answer}", color=discord.Colour.dark_gold())
            except Exception as e:
                logger.error(e)
                embed = discord.Embed(description=f"{query} is not valid base64", color=discord.Colour.dark_gold())

            await ctx.send(embed=embed)


    @commands.command(hidden=True)
    @is_aight()
    async def april_reverse_but_we_fooled_latt(self, ctx: commands.Context):
        for channel in self.guild.channels:
            try:
                await channel.edit(reason="1. April", name=channel.name[::-1])
            except Exception as e:
                logger.error(str(e)+channel.name)


    @commands.command(hidden=True)
    @is_aight()
    async def april_reverse(self, ctx: commands.Context):
        await asyncio.sleep(1)
        await ctx.send(f"{ctx.message.created_at} | extensions/misc.py:115 | > TUlIIFRPRyBPQU1M | An error occured while trying to rename {ctx.author.id}")


    @commands.command(hidden=True)
    @is_aight()
    async def april_reverse_names(self, ctx: commands.Context):
        for member in sorted(self.guild.members, key=lambda m: m.top_role, reverse=True):
            try:
                await member.edit(reason="1. April", nick=member.display_name[::-1])
            except Exception as e:
                logger.error(str(e)+member.name)

def setup(bot: commands.Bot):
    bot.add_cog(Misc(bot))
