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
        self.config = Config.get_conf(
            self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.time_zones = {}

        self.task = asyncio.create_task(self.pre_load_data())
        inter_client = InteractionClient(bot)

    # Reference: https://github.com/EQUENOS/dislash.py

    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def resetAllNames(self, ctx):
        """Clears all member nicknames where bot has permissions"""
        update_count = 0
        for member in ctx.guild.members:
            try:
                if member.nick:
                    await member.edit(nick=None)
                    update_count += 1
            except:
                pass
        await ctx.send("Cleared nicknames for **{}** members".format(update_count))
    
    @commands.command()
    async def test(self, ctx, num:int):
        if num == 1:
            s = ":x:"
        elif num == 2:
            s = ":white_check_mark:"
        else:
            s = "\U0000274C"
        e = discord.PartialEmoji(name=s)
        await ctx.send(e)

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
            content="This message has no buttons!", components=[row_of_buttons]
        )
        
        on_click = msg.create_click_listener(timeout=60)

        @on_click.matching_id("red")
        async def on_test_button(inter):
            # This function only works if the author presses the button
            # Becase otherwise the previous decorator cancels this one
            await inter.reply("You've clicked the red button!")

        @on_click.matching_id("green")
        async def on_test_button(inter):
            # This function only works if the author presses the button
            # Becase otherwise the previous decorator cancels this one
            await inter.message.edit(components=[])
            await inter.reply("You've clicked the green button!")

        @on_click.timeout
        async def on_timeout():
            await msg.edit(content=msg.content.replace("has", "had"), components=[])

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

    # Ban/Unban
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def ban(self, ctx, user: discord.User, *, reason=None):
        await ctx.guild.ban(user, reason=reason, delete_message_days=0)
        await ctx.send("Done.")
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unban(self, ctx, user: discord.User, *, reason=None):
        await ctx.guild.unban(user, reason=reason)
        await ctx.send("Done.")
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def kick(self, ctx, user: discord.User, *, reason=None):
        await user.kick(reason=reason)
        await ctx.send("Done.")
    
    @commands.guild_only()
    @commands.command(aliases=['kickall'])
    @checks.admin_or_permissions(manage_guild=True)
    async def kickAll(self, ctx, *users):
        kicked = []
        failed = []

        if not users:
            return await ctx.send(":x: No users have been given to be kicked.")

        for user in users:
            try:
                member = await commands.MemberConverter().convert(ctx, user)
                if member in ctx.guild.members:
                    await member.kick(reason="kickall command")
                    kicked.append(member)
            except:
                failed.append(user)

        response = ""
        if kicked:
            response = f":white_check_mark: {len(kicked)} members have been kicked."
        if failed:
            response += f"\n:x: {len(failed)} members could not be kicked: {', '.join(failed)}"
        else:
            response += "\n\nDone."

        await ctx.send(response)
    
    @commands.guild_only()
    @commands.command()
    async def hackjoin(self, ctx, member_or_voice):
        try:
            await ctx.message.delete()
        except:
            pass 
        member = ctx.message.author

        if not (type(member_or_voice) == discord.VoiceChannel or type(member_or_voice) == discord.Member):
            return

        if type(member_or_voice) == discord.Member:
            if not member_or_voice.voice:
                return
            voice_channel = member_or_voice.voice
        else:
            voice_channel = member_or_voice

        try:
            if not member.voice:
                return
            await member.move_to(voice_channel)
        except:
            pass
    
    @commands.guild_only()
    @commands.command()
    async def hackpull(self, ctx, pull_member: discord.Member):
        try:
            await ctx.message.delete()
            if not pull_member.voice or not ctx.author.voice:
                return
            await pull_member.move_to(ctx.author.voice)
        except:
            pass

    @commands.guild_only()
    @commands.command()
    async def mypfp(self, ctx, member=None):
        if not member:
            member = ctx.author

        await ctx.send(f"My pfp link: {member.avatar_url}")

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
