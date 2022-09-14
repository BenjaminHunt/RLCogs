import discord

import asyncio

from discord.ui import ActionRow, Button, ButtonStyle
from redbot.core import Config, commands, checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

from datetime import datetime, timedelta
from pytz import timezone, all_timezones_set

defaults = {'TimeZone': 'America/New_York'}


WHITE_X_REACT = "\U0000274E"

class TestCog(commands.Cog):
    """Test misc commands for anything!"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.time_zones = {}

        self.task = asyncio.create_task(self.pre_load_data())
        inter_client = InteractionClient(bot)

    @commands.command()
    async def test(self, ctx):
        button = Button(
            label="button!",
            style=ButtonStyle('primary'), # (discord.ButtonStyle.primary)
            emoji=WHITE_X_REACT
        )
        
        # ar = ActionRow(button)
        v = discord.ui.View(children=[button])
        await ctx.reply("hello!", view=v)
