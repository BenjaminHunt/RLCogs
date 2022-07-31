import discord
import asyncio

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

from datetime import datetime, timedelta
from pytz import timezone, all_timezones_set

import requests

defaults = {'TimeZone': 'America/New_York'}
WHITE_X_REACT = "\U0000274E"                # :negative_squared_cross_mark:
WHITE_CHECK_REACT = "\U00002705"            # :white_check_mark:

class DMMonty(commands.Cog):
    """We love Monty!"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.time_zones = {}
        self.dm_compliments = {}
        self.task = asyncio.create_task(self.pre_load_data())


    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setTimeZone(self, ctx, time_zone):
        """Sets timezone for the guild. Valid time zone codes are listed in the "TZ database name" column of
         the following wikipedia page: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"""

        if time_zone not in all_timezones_set:
            wiki = 'https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'

            msg = (':x: **{}** is not a valid time zone code. Please select a time zone from the "TZ database name" column '
                   'from this wikipedia page: {}').format(time_zone, wiki)

            return await ctx.send(msg)

        await self._save_time_zone(ctx.guild, time_zone)
        await ctx.send("Done")

    @commands.guild_only()
    @commands.command(aliases=['dc'])
    @checks.admin_or_permissions(manage_guild=True)
    async def dailyCompliment(self, ctx, member: discord.Member):
        compliment = self.get_compliment()
        try:
            self.dm_compliments[member] = True
            await self.auto_dm_compliments(member)
            await ctx.message.add_reaction(WHITE_CHECK_REACT)
        except:
            await ctx.reply("I tried and failed :(")
    
    @commands.guild_only()
    @commands.command(aliases=['sdc'])
    @checks.admin_or_permissions(manage_guild=True)
    async def stopDailyCompliments(self, ctx, member: discord.Member):
        compliment = self.get_compliment()
        try:
            self.dm_compliments[member] = False
            await ctx.reply(compliment)
            await ctx.message.add_reaction(WHITE_CHECK_REACT)
        except:
            await ctx.reply("I tried and failed :(")
    

    @commands.guild_only()
    @commands.command(aliases=['cs'])
    @checks.admin_or_permissions(manage_guild=True)
    async def compliments(self, ctx, quantity=5, interval_sec=10):
        for i in range(quantity):
            await ctx.reply(self.get_compliment())
            await asyncio.sleep(interval_sec)
    
    @commands.guild_only()
    @commands.command(aliases=['c'])
    @checks.admin_or_permissions(manage_guild=True)
    async def compliment(self, ctx, member: discord.Member):
        compliment = self.get_compliment()
        try:
            await member.send(compliment)
            await ctx.message.add_reaction(WHITE_CHECK_REACT)
        except:
            await ctx.reply("I tried and failed :(")

    # helper functions
    async def pre_load_data(self):
        """Loop task to preload guild data"""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            self.time_zones[guild] = (await self._get_time_zone(guild))

    async def auto_dm_compliments(self, member: discord.Member):
        """Loop task to auto-update match day"""
        await self.bot.wait_until_ready()
        # self.bot.get_cog("bcMatchGroups") == self:
        dm = self.dm_compliments.get(member)
        while dm:
            member.send(self.get_compliment())
            update_time = self.schedule_next_update()
            await asyncio.sleep(update_time)
        del self.dm_compliments[member]

    def schedule_next_update(self):
        # wait_time = 3600  # one hour
        today = datetime.date(datetime.now())
        tomorrow = today + timedelta(days=1)
        tomorrow_dt = datetime.combine(tomorrow, datetime.min.time())
        tomorrow_dt.hour = 12 # send at noon
        wait_time = (tomorrow_dt - datetime.now()).seconds + 30
        return wait_time

    # secondary helpers
    def get_compliment(self):
        return requests.get("https://complimentr.com/api").json().get("compliment")

    # db

    async def _save_time_zone(self, guild, time_zone):
        await self.config.guild(guild).TimeZone.set(time_zone)
        self.time_zones[guild] = time_zone

    async def _get_time_zone(self, guild):
        return await self.config.guild(guild).TimeZone()
