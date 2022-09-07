import discord

import asyncio

from redbot.core import Config, commands, checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

from datetime import datetime, timedelta
from pytz import timezone, all_timezones_set

defaults = {}


WHITE_X_REACT = "\U0000274E"

class NullyUtil(commands.Cog):
    """NullyUtil commands for anything!"""
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
        