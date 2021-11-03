import abc
import discord

# from discord_components import Button, Select, SelectOption, ComponentsBot
from dislash import InteractionClient, ActionRow, Button, ButtonStyle

import asyncio
import urllib.parse
import operator

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

from datetime import datetime, timedelta
from pytz import timezone, all_timezones_set

defaults = {'TimeZone': 'America/New_York'}

class TestCog(commands.Cog):
    """Test misc commands for anything!"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.players = []
        self.six_mans_cog = bot.get_cog("SixMans")
        self.time_zones = {}

        self.task = asyncio.create_task(self.pre_load_data())
        self.inter_client = InteractionClient(bot)
    
    
    # Reference: https://github.com/EQUENOS/dislash.py
    @commands.command()
    async def button(self, ctx):
        # Make a row of buttons
        row_of_buttons = ActionRow(
            Button(
                style=ButtonStyle.green,
                label="Green button",
                custom_id="green"
            ),
            Button(
                style=ButtonStyle.red,
                label="Red button",
                custom_id="red"
            )
        )
        # Send a message with buttons
        msg = await ctx.send(
            "This message has buttons!",
            components=[row_of_buttons]
        )
        await ctx.send("done")

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
    @commands.command(aliases=['time'])
    @checks.admin_or_permissions(manage_guild=True)
    async def getTime(self, ctx):
        """I'm not documenting a test lmao"""

        # fmt = "%Y-%m-%d %H:%M:%S %Z%z"
        # timezonelist = ['UTC', 'America/New_York', 'US/Pacific','Europe/Berlin']
        # for zone in timezonelist:
        #     now_time = datetime.now(timezone(zone))
        #     await ctx.send(now_time.strftime(fmt))

        # now = datetime.now(timezone('America/New_York'))
        # await ctx.send("Boston: {}".format(now))
        # utc = now.astimezone(timezone('UTC'))
        # await ctx.send("UTC:    {}".format(utc))
        
        date_str = '10/27/2021'
        zone = self.time_zones[ctx.guild]
        await ctx.send('Date str: {}'.format(date_str))
        await ctx.send('--')

        start = datetime.strptime(date_str, '%m/%d/%Y').astimezone(timezone(zone))
        start_utc = start.astimezone(timezone('UTC'))

        await ctx.send('Match Date: {}\n{}: {}\nUTC: {}'.format(date_str, self.time_zones[ctx.guild], start, start_utc))

        end = start + timedelta(days=1)
        end_utc = start_utc + timedelta(days=1)

        await ctx.send('Match Date: {}\n{}: {}\nUTC: {}'.format(date_str, self.time_zones[ctx.guild], end, end_utc))


    # @inter_client.user_command(name="red")
    # async def press_me(inter):
    #     # User commands are visible in user context menus
    #     # They can be global or per guild, just like slash commands
    #     await inter.respond("Hello there!")

    # @inter_client.message_command(name="green")
    # async def resend(inter):
    #     # Message commands are visible in message context menus
    #     # inter is instance of ContextMenuInteraction
    #     await inter.respond("green")

    async def pre_load_data(self):
        """Loop task to preload guild data"""
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            self.time_zones[guild] = (await self._get_time_zone(guild))

    # db

    async def _save_time_zone(self, guild, time_zone):
        await self.config.guild(guild).TimeZone.set(time_zone)
        self.time_zones[guild] = time_zone

    async def _get_time_zone(self, guild):
        return await self.config.guild(guild).TimeZone()
