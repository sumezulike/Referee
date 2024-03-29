import asyncio
import logging
import re
import urllib.parse
from base64 import b64decode, b64encode
from builtins import filter

import aiohttp
import discord
import string
from typing import Union, List, Tuple, Dict, Optional
from discord.ext import commands
from discord.ext.commands import BadArgument

from Referee import can_kick, can_ban
from config.config import Misc as config, Timeouts
from extensions.rolegroups import Role_T
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
        def emoji_check(reaction: discord.Reaction, user):
            return user == message.author and str(
                reaction.emoji) == emoji.trashcan and reaction.message.id == msg.id


        content = message.content.lower()
        if len(content.split()) == 1 and content.endswith(".gif") and not content.startswith("http"):
            await self.provide_gif(message)
        if not any(message.content.startswith(p) for p in self.bot.command_prefix):
            b64_finds = await self.get_b64_strings(message.content)
            if b64_finds and min(map(len, b64_finds.keys())) > 6:
                res = "\n".join(f"'{c}' => **{d}**" for c, d in b64_finds.items())
                embed = discord.Embed(title="Decoded b64:", description=res)
                msg = await message.channel.send(embed=embed)
                await msg.add_reaction(emoji.trashcan)

                try:
                    reaction, _ = await self.bot.wait_for('reaction_add', timeout=Timeouts.long, check=emoji_check)
                except asyncio.TimeoutError:
                    await msg.remove_reaction(emoji.trashcan, self.bot.user)
                else:
                    await msg.delete()
        calc = message.content.replace("\\", "").replace(" ", "").replace("`", "")
        if len(calc) >= 3 and set(calc).issubset(set("0123456789+-*/().")) and "**" not in calc and set(calc) & set(
                "+-*/") and set(calc) & set("0123456789"):
            logger.debug(f"Calculating {calc} for {message.author}")
            try:
                result = eval(calc)
                answer = f"`{calc}` = **{result}**"
                if len(answer) >= 2000:
                    answer = str(result)
            except SyntaxError:
                await message.add_reaction(emoji.x)
                await asyncio.sleep(0.1)
                await message.remove_reaction(emoji.x, self.bot.user)
                return
            except Exception as e:
                result = e.__class__.__name__
                answer = result
            logger.debug(f"Result: {result}")

            embed = discord.Embed(title="Result:", description=answer)
            msg = await message.channel.send(embed=embed)
            await msg.add_reaction(emoji.trashcan)

            try:
                reaction, _ = await self.bot.wait_for('reaction_add', timeout=Timeouts.long, check=emoji_check)
            except asyncio.TimeoutError:
                await msg.remove_reaction(emoji.trashcan, self.bot.user)
            else:
                await msg.delete()


    async def provide_gif(self, message: discord.Message):
        content = message.content.lower()
        logger.debug(f"Fetching gif: {content}")
        query = content.split(".gif")[0]
        url = await self.fetch_gif(query)
        gif_message = await message.channel.send(url)
        await gif_message.add_reaction(emoji.trashcan)


        def check(reaction: discord.Reaction, user):
            return user == message.author and str(
                reaction.emoji) == emoji.trashcan and reaction.message.id == gif_message.id


        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=Timeouts.long, check=check)
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
    @can_kick()
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


    async def get_b64_strings(self, text: str) -> Dict[str, str]:
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
    async def b64decode(self, ctx: commands.Context, *, query: Optional[str]):
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


    @commands.command(name="info", aliases=["whois", "whoisin", "whatis"])
    async def show_info(self, ctx: commands.Context, *, subject: Union[Role_T, discord.Member]):
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

    @commands.command(name="regex_ban", aliases=["ban"])
    @can_ban()
    async def regex_ban(self, ctx: commands.Context, *, regex: str):
        try:
            re.compile(regex)
        except re.error:
            await ctx.send(f"Invalid regex: <https://regexr.com/?expression={regex}>")
            return
        targets: List[discord.Member] = [m for m in self.guild.members if re.fullmatch(regex, m.name)]
        if not targets:
            await ctx.send(f"No matches for `{regex}`")
            return
        embed = discord.Embed(title=f"{len(targets)} matches")
        matches = ""
        for t in targets:
            if len(matches) > 1000:
                embed.add_field(name="---", value=matches)
                matches = ""
            else:
                matches = matches + "\n" + t.display_name
        else:
            embed.add_field(name="---", value=matches)

        await ctx.send(embed=embed)
        if await self.quick_embed_query(ctx, question="Do you want to ban these users?", reraise_timeout=False):
            count = 0
            for m in targets:
                try:
                    await m.ban()
                    count += 1
                except Exception as e:
                    logging.error(e)
            await ctx.send(f"Banned {count}/{len(targets)} users.")
        else:
            await ctx.send("Ban cancelled.")


    async def get_member_info_embed(self, member: discord.Member) -> discord.Embed:
        embed = discord.Embed(
            title=f"**{member.name}#{member.discriminator}** {'(' + member.nick + ')' if member.nick else ''}",
            color=member.color)
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

    async def quick_embed_query(self, ctx: Union[commands.Context, Tuple[discord.TextChannel, discord.Member]],
                                 question: str, reraise_timeout: bool = True) -> bool:
        """
        Sends a yes/no query to a context
        :param ctx: The :class:`commands.Context` to which the query should be sent OOOR a Tuple of Channel and Member
        :param question: The content of the query
        :param reraise_timeout: Whether an exception should be raised on timeout, defaults to True
        :return: bool answer
        """


        def check(_reaction, _user):
            return _user == member and str(_reaction.emoji) in [emoji.x, emoji.white_check_mark]


        if type(ctx) == commands.Context:
            channel = ctx.channel
            member = ctx.author
        else:
            channel = ctx[0]
            member = ctx[1]

        logger.debug(f"Sending query '{question}' for {member.name}")

        msg = await self.send_simple_embed(channel=channel, content=question)
        await msg.add_reaction(emoji.white_check_mark)
        await msg.add_reaction(emoji.x)

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=Timeouts.long, check=check)
        except asyncio.TimeoutError as e:
            await msg.delete()
            if reraise_timeout:
                raise e
            else:
                return False
        else:
            await self.send_simple_embed(channel=channel, content=reaction.emoji, delete_after=2)
            if reaction.emoji == emoji.white_check_mark:
                await msg.delete()
                return True
            else:
                await msg.delete()
                return False

    @staticmethod
    async def send_simple_embed(channel: Union[discord.TextChannel, commands.Context, discord.User], content: str,
                                delete_after=None,
                                mentions: Union[List[discord.Member], discord.Member] = None) -> discord.Message:

        embed = discord.Embed(title=content if len(content) < 256 else emoji.white_check_mark,
                              color=discord.Color.dark_gold())
        if not len(content) < 256:
            embed.add_field(name="*", value=content)
        if mentions:
            if type(mentions) == list:
                embed.description = " ".join(u.mention for u in mentions)
            else:
                embed.description = mentions.mention
        if delete_after:
            msg = await channel.send(embed=embed, delete_after=delete_after)
        else:
            msg = await channel.send(embed=embed)
        return msg

def setup(bot: commands.Bot):
    bot.add_cog(Misc(bot))
