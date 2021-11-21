import asyncio
import logging

import aiohttp
import discord
from discord.ext import commands

from datetime import datetime, timedelta

from config.config import Christmas_Competition as config, Timeouts

from Referee import can_kick
from db_classes.PGChristmasDB import PGChristmasDB
from utils import emoji

logger = logging.getLogger("Referee")


class ChristmasCompetition(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = PGChristmasDB()
        self.lb_data = None
        self.last_updated_lb = datetime.fromtimestamp(0)

    @commands.command(name="set_cookie", hidden=True)
    @can_kick()
    async def UpdateAocCookie(self, ctx: commands.Context, cookie: str):
        await self.db.update_cookie(cookie)

    @commands.command(name="test_cookie", hidden=True)
    @can_kick()
    async def TestAocCookie(self, ctx: commands.Context):
        url = 'https://adventofcode.com/' + config.year + '/leaderboard/private/view/' + config.leaderboard_id + '.json'
        cookies = {'session': await self.db.get_cookie()}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url) as resp:
                await ctx.reply(resp.status)

    @commands.command(name="aoc", aliases=["register", "egister"], hidden=True)
    async def Register(self, ctx: commands.Context, name: str):
        if await self.db.get_user(None, ctx.message.author.id) is not None:
            await ctx.message.channel.send("You are already registered.", delete_after=Timeouts.short)
            return

        message = await ctx.reply("Is " + name + " Your AoC name? If so, react with " + emoji.thumbs_up)
        await message.add_reaction(emoji.thumbs_up)
        await message.add_reaction(emoji.trashcan)

        def check(_reaction: discord.Reaction, _user):
            return _reaction.message.id == message.id and _user == ctx.message.author and str(_reaction.emoji) in [
                emoji.trashcan, emoji.thumbs_up]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=Timeouts.mid, check=check)
        except asyncio.TimeoutError:
            await ctx.message.channel.send("AoC name wasn't confirmed, cancelling.", delete_after=Timeouts.short)
        else:
            if reaction.emoji == emoji.thumbs_up:
                await self.db.add_user(name.lower(), ctx.message.author.id)
                await ctx.message.channel.send("AoC name confirmed, saving...", delete_after=Timeouts.short)
        finally:
            await message.delete()

    @commands.command(name="aoc_update", hidden=True)
    async def Update(self, ctx: commands.Context, name: str):
        message = await ctx.reply("Is " + name + " Your AoC name? If so, react with " + emoji.thumbs_up)
        await message.add_reaction(emoji.thumbs_up)
        await message.add_reaction(emoji.trashcan)

        def check(_reaction: discord.Reaction, _user):
            return _reaction.message.id == message.id and _user == ctx.message.author and str(_reaction.emoji) in [
                emoji.trashcan, emoji.thumbs_up]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=Timeouts.mid, check=check)
        except asyncio.TimeoutError:
            await ctx.message.channel.send("AoC name wasn't confirmed, cancelling.", delete_after=Timeouts.short)
        else:
            if reaction.emoji == emoji.thumbs_up:
                await self.db.update_user(name.lower(), ctx.message.author.id)
                await ctx.message.channel.send("AoC name confirmed, saving...", delete_after=Timeouts.short)
        finally:
            await message.delete()


    async def TryUpdateLeaderboardData(self):
        if (datetime.now() - self.last_updated_lb).seconds <= 1000:
            return

        self.last_updated_lb = datetime.now()

        url = 'https://adventofcode.com/' + config.year + '/leaderboard/private/view/' + config.leaderboard_id + '.json'
        cookies = {'session': await self.db.get_cookie()}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url) as resp:
                self.lb_data = await resp.json()

    @commands.command(name="notjoined", hidden=True)
    @can_kick()
    async def NotOnLeaderboard(self, ctx: commands.Context):
        await self.TryUpdateLeaderboardData()
        registered = await self.db.get_all_users()
        in_leaderboard = []
        for member_id in self.lb_data["members"]:
            in_leaderboard += [self.lb_data["members"][member_id]["name"]]

        out = "__**joined via discord, but not in leaderboard**__\n"

        for user in registered:
            if user[0] not in in_leaderboard:
                out += user[0] + " (discord: <@" + str(user[1]) + ">)\n"
        out += "__**joined leaderboard, but not via discord**__\n"
        for user in in_leaderboard:
            if not any(u[0] == user for u in registered):
                out += user + "\n"

        await ctx.reply(out)

    @commands.command(name="whois_discord", hidden=True)
    @can_kick()
    async def AoC_WhoIs(self, ctx: commands.Context, *, subject: discord.Member):
        await ctx.reply(await self.db.get_user(None, subject.id))

    @commands.command(name="whois_aoc", hidden=True)
    @can_kick()
    async def AoC_WhoIs2(self, ctx: commands.Context, subject: str):
        await ctx.reply(await self.db.get_user(subject, None))

def setup(bot: commands.Bot):
    bot.add_cog(ChristmasCompetition(bot))
