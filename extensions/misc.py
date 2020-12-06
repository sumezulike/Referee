import asyncio
import typing
from base64 import b64decode, b64encode
import re
import string
from builtins import filter

import aiohttp
import urllib.parse

import discord
from discord.ext import commands

import logging

from discord.ext.commands import BadArgument

from Referee import is_aight, send_embed_with_delete_option
from config.config import Bot as config
from utils import emoji

from extensions.rolegroups import Role_T

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
        if len(content.split()) == 1 and content.endswith(".gif") and not content.startswith("http"):
            await self.provide_gif(message)
        if not any(message.content.startswith(p) for p in self.bot.command_prefix):
            b64_finds = await self.get_b64_strings(message.content)
            if b64_finds and min(map(len, b64_finds.keys())) > 6:
                res = "\n".join(f"'{c}' => **{d}**" for c, d in b64_finds.items())
                embed = discord.Embed(title="Decoded b64:", description=res)
                await send_embed_with_delete_option(orig_message=message, embed=embed)
        calc = message.content.replace("\\", "").replace(" ", "").replace("`", "")
        if len(calc) >= 3 and set(calc).issubset(set("0123456789+-*/().")) and "**" not in calc and set(calc)&set("+-*/"):
            logger.debug(f"Calculating {calc} for {message.author}")
            try:
                result = eval(calc)
                answer = f"`{calc}` = **{result}**"
                if len(answer) >= 2000:
                    answer = str(result)
            except SyntaxError:
                await message.add_reaction(emoji.x)
                return
            except Exception as e:
                result = e.__class__.__name__
                answer = result
            logger.debug(f"Result: {result}")

            embed = discord.Embed(title="Result:", description=answer)
            await send_embed_with_delete_option(orig_message=message, embed=embed)


    async def provide_gif(self, message: discord.Message):
        content = message.content.lower()
        logger.debug(f"Fetching gif: {content}")
        query = content.split(".gif")[0]
        url = await self.fetch_gif(query)
        embed = discord.Embed()
        embed.set_image(url=url)
        await send_embed_with_delete_option(orig_message=message, embed=embed)

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


    @commands.command(name="google", aliases=["gg"])
    async def google(self, ctx: commands.Context, *, query: str):
        """
        Search for a term on google.com
        :param query: The search query
        """
        query = query.split("<")[0].strip()
        url_query = urllib.parse.quote_plus(query)
        payload = {"long_url": f"https://www.google.com/search?q={url_query}", }
        headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:66.0) Gecko/20100101 Firefox/66.0",
                   "Connection": "close",
                   "Authorization": f"Bearer {config.bitly_token}"
                   }

        async with aiohttp.ClientSession(headers=headers) as session:
            short = await session.post("https://api-ssl.bitly.com/v4/shorten", json=payload)
            resp = await short.json()
            await ctx.send(
                embed=discord.Embed(description=f"[{query}]({resp['link']})", color=discord.Colour.dark_gold()))


    @commands.command()
    @is_aight()
    async def shorten(self, ctx: commands.Context, url: str):
        url = f"http://{url}" if not url.startswith("http") else url
        payload = {"long_url": url}
        logger.debug((url, payload))
        headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:66.0) Gecko/20100101 Firefox/66.0",
                   "Connection": "close",
                   "Authorization": f"Bearer {config.bitly_token}"
                   }

        async with aiohttp.ClientSession(headers=headers) as session:
            short = await session.post("https://api-ssl.bitly.com/v4/shorten", json=payload)
            resp = await short.json()
            logger.debug(resp)
            try:
                await ctx.send(
                    embed=discord.Embed(description=f"{resp['link']}", color=discord.Colour.dark_gold()))
            except KeyError:
                await ctx.send(
                    embed=discord.Embed(description=f"Bit.ly error: {resp['description']}",
                                        color=discord.Colour.dark_gold()), delete_after=15)


    async def get_b64_strings(self, text: str) -> typing.Dict[str, str]:
        enc = filter(lambda x: len(x) % 4 == 0, re.findall(r"[a-zA-Z0-9+/]+={0,2}", text))
        solved = {}
        for code in enc:
            try:
                dec = b64decode(code).decode()
                if all(x in string.printable for x in set(dec)):
                    solved[code] = dec
            except Exception as ex:
                # logger.error(ex)  # this is noisy and not neccesary
                pass
        return solved

    @commands.command(name="b64")
    async def b64decode(self, ctx: commands.Context, *, query: typing.Optional[str]):
        """
        Decode a base64 encoded string, will encode if decoding fails
        :param query: A base64 encoded string. Omit to have Referee find one in the previous messages
        """

        if not query:
            found_hits = {}
            async for m in ctx.channel.history(limit=20, oldest_first=False):
                results = await self.get_b64_strings(m.content)
                for c, d in results.items():
                    sub = await self.get_b64_strings(d)
                    levels = 1
                    while sub:
                        sub = await self.get_b64_strings(d)
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
                embed = discord.Embed(description=f"That is not valid base64", color=discord.Colour.dark_gold())
                embed.add_field(name="In case you wanted to encode:", value=b64encode(query.encode()).decode())

            await ctx.send(embed=embed)


    @commands.command(hidden=True)
    @is_aight()
    async def april_reverse_but_we_fooled_latt(self, ctx: commands.Context):
        for channel in self.guild.channels:
            try:
                await channel.edit(reason="1. April", name=channel.name[::-1])
            except Exception as e:
                logger.error(str(e) + channel.name)


    @commands.command(hidden=True)
    @is_aight()
    async def april_reverse(self, ctx: commands.Context):
        await asyncio.sleep(1)
        await ctx.send(
            f"{ctx.message.created_at} | extensions/misc.py:115 | > TUlIIFRPRyBPQU1M | An error occured while trying to rename {ctx.author.id}")


    @commands.command(hidden=True)
    @is_aight()
    async def april_reverse_names(self, ctx: commands.Context):
        for member in sorted(self.guild.members, key=lambda m: m.top_role, reverse=True):
            try:
                await member.edit(reason="1. April", nick=member.display_name[::-1])
            except Exception as e:
                logger.error(str(e) + member.name)


    @commands.command(name="info", aliases=["whois", "whoisin", "whatis"])
    async def show_info(self, ctx: commands.Context, *, subject: typing.Union[Role_T, discord.Member]):
        """
        :param subject: Role or member so far
        :return:
        """
        if type(subject) == discord.Role:
            embed = await self.get_role_info_embed(subject)
        elif type(subject) == discord.Member:
            embed = await self.get_member_info_embed(subject)
        else:
            raise BadArgument("Unknown subject type")
        await ctx.send(embed=embed)
        await ctx.message.delete()


    async def get_member_info_embed(self, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(title=f"**{member.name}#{member.discriminator}** {'('+member.nick+')' if member.nick else ''}", color=member.color)
        id_text = f"- {member.top_role.name} "
        if member.bot:
            id_text += "(Bot) "
        if member.system:
            id_text += "(System) "
        id_text += f"-"
        embed.add_field(name=member.id, value=id_text, inline=False)
        embed.add_field(name="Joined discord:", value=member.created_at.strftime("%d. %b %Y %H:%M"), inline=False)
        embed.add_field(name="Joined this server:", value=member.joined_at.strftime("%d. %b %Y %H:%M"), inline=False)
        embed.add_field(name="Roles:", value=', '.join(r.name for r in reversed(member.roles[1:])), inline=False)
        embed.set_image(url=member.avatar_url)
        return embed


    async def get_role_info_embed(self, role: discord.Role) -> discord.Embed:
        embed = discord.Embed(
            title=f"**{role.name}** ({len(role.members)} member{'s' if len(role.members) != 1 else ''})",
            color=role.color)
        member_text = ""
        for name in sorted((m.display_name for m in role.members), key=lambda x: x.lower()):
            if len(member_text) + len(name) >= 1024:
                embed.add_field(name="Members" if role.members else "No members", value=member_text or "-")
                member_text = ""
            member_text += f"{name}\n"
        embed.add_field(name="Members" if role.members else "No members", value=member_text or "-")
        return embed


def setup(bot: commands.Bot):
    bot.add_cog(Misc(bot))
