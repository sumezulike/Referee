import asyncio
import logging

import aiohttp
import discord
from discord.ext import commands

from datetime import datetime, timedelta

import json

from config.config import Christmas_Competition as config, Timeouts

from Referee import can_kick
from db_classes.PGChristmasDB import PGChristmasDB
from utils import emoji

logger = logging.getLogger("Referee")


class ChristmasCompetition(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guild = None
        self.db = PGChristmasDB()
        self.lb_data = None
        self.last_updated_lb = datetime.fromtimestamp(0)

    @commands.Cog.listener()
    async def on_ready(self):
        """
        On_ready eventhandler, gets called by api
        """
        self.guild: discord.Guild = self.bot.guilds[0]

    @commands.command(name="set_cookie", hidden=True)
    @can_kick()
    async def UpdateAocCookie(self, ctx: commands.Context, cookie: str):
        await self.db.update_cookie(cookie)

    @commands.command(name="test_cookie", hidden=True)
    @can_kick()
    async def TestAocCookie(self, ctx: commands.Context):
        # dont replace with not; it can replace None and None != False
        if await self.TryUpdateLeaderboardData() == False:
            await ctx.message.channel.send("Please set a cookie first using r!set_cookie.", delete_after=Timeouts.short)
            return
        await ctx.reply("```json\n" + json.dumps(self.lb_data, indent=4, sort_keys=True) + "```")

    @commands.command(name="aoc", aliases=["register", "egister"], hidden=True)
    async def Register(self, ctx: commands.Context, name: str):
        isUpdate = False

        def check(_reaction: discord.Reaction, _user):
            return _reaction.message.id == message.id and _user == ctx.message.author and str(_reaction.emoji) in [
                emoji.thumbs_down, emoji.thumbs_up]

        if await self.db.get_user(None, ctx.message.author.id) is not None:
            message = await ctx.message.channel.send(
                "You are already registered, do you want to update your AoC name instead?", delete_after=Timeouts.short)
            await message.add_reaction(emoji.thumbs_up)
            await message.add_reaction(emoji.thumbs_down)

            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=Timeouts.mid, check=check)
            except asyncio.TimeoutError:
                pass
            else:
                if reaction.emoji != emoji.thumbs_up:
                    return
                isUpdate = True
            finally:
                await message.delete()

        message = await ctx.reply("Is " + name + " Your AoC name? If so, react with " + emoji.thumbs_up)
        await message.add_reaction(emoji.thumbs_up)
        await message.add_reaction(emoji.thumbs_down)

        def check(_reaction: discord.Reaction, _user):
            return _reaction.message.id == message.id and _user == ctx.message.author and str(_reaction.emoji) in [
                emoji.trashcan, emoji.thumbs_up]

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=Timeouts.mid, check=check)
        except asyncio.TimeoutError:
            await ctx.message.channel.send("AoC name wasn't confirmed, cancelling.", delete_after=Timeouts.short)
        else:
            if reaction.emoji == emoji.thumbs_up:
                if isUpdate:
                    await self.db.update_user(name.lower(), ctx.message.author.id)
                else:
                    await self.db.add_user(name.lower(), ctx.message.author.id)
                await ctx.message.channel.send("AoC name confirmed, saving...", delete_after=Timeouts.short)
        finally:
            await message.delete()

    async def TryUpdateLeaderboardData(self):
        """
        :returns None for rate limit, False for no or invalid cookie, and True for success
        """
        if (datetime.now() - self.last_updated_lb).seconds <= 1000:
            return None
        session = await self.db.get_cookie()
        if session is None:
            return False

        url = 'https://adventofcode.com/' + config.year + '/leaderboard/private/view/' + config.leaderboard_id + '.json'
        cookies = {'session': session}
        async with aiohttp.ClientSession(cookies=cookies) as session:
            async with session.get(url) as resp:
                if not (200 <= resp.status < 300):
                    return False
                self.last_updated_lb = datetime.now()
                self.lb_data = await resp.json()
        return True

    @commands.command(name="notjoined")
    @can_kick()
    async def NotOnLeaderboard(self, ctx: commands.Context):
        # dont replace with not, see Test_cookie for reasoning
        if await self.TryUpdateLeaderboardData() == False:
            await ctx.message.channel.send("Please set a cookie first using r!set_cookie.", delete_after=Timeouts.short)
            return
        registered = await self.db.get_all_users()
        in_leaderboard = []
        for member_id in self.lb_data["members"]:
            in_leaderboard += [self.lb_data["members"][member_id]["name"].lower()]

        out = "__**joined via discord, but not in leaderboard**__\n"

        for user in registered:
            if user[0] not in in_leaderboard:
                out += user[0] + " (discord: <@" + str(user[1]) + ">)\n"
        out += "__**joined leaderboard, but not via discord**__\n"
        for user in in_leaderboard:
            if not any(u[0] == user for u in registered):
                out += user + "\n"

        await ctx.reply(out)

    @commands.command(name="whois_discord")
    @can_kick()
    async def AoC_WhoIs(self, ctx: commands.Context, *, subject: discord.Member):
        await ctx.reply(await self.db.get_user(None, subject.id))

    @commands.command(name="whois_aoc")
    @can_kick()
    async def AoC_WhoIs2(self, ctx: commands.Context, subject: str):
        await ctx.reply(await self.db.get_user(subject.lower(), None))

    @commands.command(name="aoc_lb")
    async def AoC_Leaderboard(self, ctx: commands.Context):
        await self.TryUpdateLeaderboardData()
        sorted_lb = sorted(self.lb_data["members"], key=lambda x: self.lb_data["members"][x]["local_score"],
                           reverse=True)
        out = ""
        embed = discord.Embed(title=f"AoC Leaderboard {config.year}")
        for c in sorted_lb:
            currentMember = self.lb_data["members"][c]
            cm_info = await self.db.get_user(currentMember["name"].lower(), None)
            score = currentMember['local_score']
            if not cm_info:
                out += f"{currentMember['name']} ({str(score)} points)\n"
            else:
                member = self.guild.get_member(cm_info[1])
                out += f"{member.mention} ({cm_info[0]}, {str(score)} points)\n"
            embed.add_field(name="-", value=out)
        await ctx.reply(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(ChristmasCompetition(bot))
