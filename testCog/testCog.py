import abc
import discord
import asyncio
import urllib.parse
import operator

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

from datetime import datetime
from pytz import timezone

defaults = {}

class TestCog(commands.Cog):
    """Test misc commands for anything!"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.players = []
        self.six_mans_cog = bot.get_cog("SixMans")

        
    @commands.guild_only()
    @commands.command(aliases=['time'])
    @checks.admin_or_permissions(manage_guild=True)
    async def getTime(self, ctx, log_channel: discord.TextChannel):
        """I'm not documenting a test lmao"""

        fmt = "%Y-%m-%d %H:%M:%S %Z%z"
        timezonelist = ['UTC', 'America/New_York', 'US/Pacific','Europe/Berlin']
        for zone in timezonelist:
            now_time = datetime.now(timezone(zone))
            await ctx.send(now_time.strftime(fmt))
            
        await ctx.send('--')

        now = datetime.now(timezone('America/New_York'))
        await ctx.send("Boston: {}".format(now))
        utc = now.astimezone(timezone('UTC'))
        await ctx.send("UTC:    {}".format(utc))
        