import abc
from distutils.command.config import config

from .bc_config import bcConfig
from accountManager import AccountManager

from dislash import InteractionClient, ActionRow, Button, ButtonStyle
from datetime import date, datetime, timedelta, timezone
import tempfile
import discord
import asyncio
import requests
import random
import urllib.parse
import traceback

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"Emoji": None, "MatchDates": [], "MatchDay": 1,
            "TeamRoles": [], "ReplayGroups": {}, "Schedule": {}, 
            "TeamNameChanges": {}, "TimeZone": None}

global_defaults = {"BCTokens": {}}
verify_timeout = 30 # seconds
temp_team_name_timeout = 60 # seconds

class BCMatchGroups(commands.Cog):
    """Allows members of a franchise to create ballchasing groups"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567893, force_registration=True)
        self.config.register_global(**global_defaults)
        self.config.register_guild(**defaults)
        self.account_manager_cog: AccountManager = bot.get_cog("AccountManager")
        self.task = asyncio.create_task(self.auto_update_match_day())
        self.auto_update_md = True

    def cog_unload(self):
        """Clean up when cog shuts down."""
        self.auto_update_match_day = False
        if self.task:
            self.task.cancel()

# Admin Commands - Season Configuration
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setMatchDates(self, ctx, *dates):
        """Sets the dates where games will be played.

        Date format: MM/DD/YY(YY)
        Example:
        [p]setMatchDates 5/1/21 6/2/21 6/7/21 6/9/2021
        """
        century = datetime.now().strftime("%Y")[:2]
        all_dates = []
        for date in dates:
            try:
                mm, dd, yy = date.split('/')
                if len(yy) == 2:
                    yy = century + yy
                all_dates.append(datetime(int(yy), int(mm), int(dd)))
            except:
                await ctx.send("Traceback:\n```\n{}\n```".format(traceback.print_exc()))
                return await ctx.send(":x: **{}** is not represented in a valid date format. Use `{}help setMatchDates` for more information.".format(date, ctx.prefix))

        all_dates.sort()
        all_str_dates = [
            "{dt.month}/{dt.day}/{dt.year}".format(dt=date) for date in all_dates]
        await self._save_match_dates(ctx.guild, all_str_dates)
        await ctx.send(":white_check_mark: Saved {} match dates.".format(len(all_dates)))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearMatchDates(self, ctx):
        """Clears all match dates registered with the bot.
        """
        await self._save_match_dates(ctx.guild, [])
        await ctx.send("Done")

    @commands.command(aliases=['matches', 'getMatchDays'])
    @commands.guild_only()
    @checks.admin_or_permissions()
    async def getMatchDates(self, ctx):
        match_day = await self._get_match_day(ctx.guild)
        dates = await self._get_match_dates(ctx.guild)
        dates_str = ""
        for i in range(len(dates)):
            if str(i+1) == str(match_day):
                dates_str += "\n**({}) {}**".format(i+1, dates[i])
            else:
                dates_str += "\n({}) {}".format(i+1, dates[i])
        if dates_str:
            await ctx.send("__All Match Dates:__{}".format(dates_str))
        else:
            await ctx.send(":x: No match dates registered.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def setMatchDay(self, ctx, match_day):
        await self.config.guild(ctx.guild).MatchDay.set(match_day)
        await ctx.send("Done")

    @commands.command(aliases=['umd'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def updateMatchDay(self, ctx):
        await self._update_match_day(ctx.guild, channel=ctx.channel, force_set=True)
        await ctx.send("Done")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def nextMatchDay(self, ctx):
        match_day = await self.config.guild(ctx.guild).MatchDay()
        match_day = int(match_day) + 1
        await self.config.guild(ctx.guild).MatchDay.set(match_day)
        await ctx.send(":white_check_mark: It is now **match day {}**.".format(match_day))

    @commands.command(aliases=['md', 'gmd'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def getMatchDay(self, ctx):
        match_day = await self.config.guild(ctx.guild).MatchDay()
        await ctx.send("Match Day {}.".format(match_day))

    @commands.command(aliases=['endseason'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def endSeason(self, ctx):
        prompt = "Are you sure you want to clear all data for this season?"
        if_not_prompt = "No changes have been made to the current season."
        if await self._react_prompt(ctx, prompt, if_not_prompt):
            await self._save_top_level_groups(ctx.guild, {})
            await self._save_match_day(ctx.guild, 0)
            await self._save_match_dates(ctx.guild, [])
            await ctx.send("Done")

# Admin Settings - Team Mgmt
    @commands.command(aliases=['addTeams', 'addFranchiseTeams'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def addTeamRoles(self, ctx, *roleList):
        """Registers each role with the bot as a franchise team role"""
        team_roles = [role.id for role in await self._get_team_roles(ctx.guild)]
        found = []
        failed = []
        message_components = []
        for role_name in roleList:
            try:
                role = await commands.RoleConverter().convert(ctx, role_name)
                if role.id in team_roles or role in found:
                    failed.append(role)
                else:
                    found.append(role)
                    team_roles.append(role.id)
            except:
                failed.append(role_name)

        await self._save_team_roles(ctx.guild, team_roles)

        if failed:
            message_components.append(":x: **{}** roles failed: {}".format(
                len(failed), ', '.join(role_name for role_name in failed)))

        if found:
            message_components.append(":white_check_mark: Added **{}** team roles: {}".format(
                len(found), ', '.join(role_name.mention for role_name in found)))

        if message_components:
            return await ctx.send('\n'.join(message_components))

        await ctx.send(":x: No roles provided.")

    @commands.command(aliases=['removeTeam', 'removeFranchiseTeam', 'rmteam'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def removeTeamRole(self, ctx, *, team_name):
        """Removes a specified role from the list of team roles."""
        team_role = await self._match_team_role(ctx.guild, team_name=team_name)
        team_role_ids = [role.id for role in await self._get_team_roles(ctx.guild)]

        if team_role.id in team_role_ids:
            team_role_ids.remove(team_role.id)
            await self._save_team_roles(ctx.guild, team_role_ids)
            await ctx.send("Done")
        else:
            await ctx.send(":x: {} is not a valid team identifier.".format(team_name))

    @commands.command(aliases=['clearFranchiseTeams', 'clearTeams'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def clearTeamRoles(self, ctx):
        prompt = "Are you sure you want to clear **{}** Team Roles?".format(len(await self._get_team_roles(ctx.guild)))
        if await self._react_prompt(ctx, prompt, "Teams not cleared."):
            await self._save_team_roles(ctx.guild, [])
            await ctx.send("Done")

# Admin Commands - Misc
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def transferGroupOwner(self, ctx, team_name, new_owner: discord.Member):
        pass

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearRosters(self, ctx):
        """Removes all team roles from members within the guild server."""
        if not await self._react_prompt(ctx, "Are you sure you wish to clear all rosters?", "No roster changes made."):
            return
        removed = 0
        team_roles = await self._get_team_roles(ctx.guild)
        for role in team_roles:
            for member in role.members:
                await member.remove_roles(role)
                removed += 1
        await ctx.send("Removed team roles for {} players.".format(removed))

# Ballchasing Group Setup Commands
    @commands.command(aliases=['setTopLevelGroup'])
    @commands.guild_only()
    async def setSeasonGroup(self, ctx, group_code, *, team_role: discord.Role = None):
        member = ctx.message.author

        # validate auth token
        auth_token = await self._get_member_bc_token(member)
        if not auth_token:
            return await ctx.send(":x: {} you must first register your auth token before setting your team's ballchasing group. To do so, use `{}setMyBCAuthToken`.".format(
                member.mention, ctx.prefix
            ))

        # normalize ballchasing group full links
        bc_group_url = 'ballchasing.com/group/'
        if bc_group_url in group_code:
            group_code = group_code[group_code.index(
                bc_group_url)+len(bc_group_url):]

        # match team role
        if not team_role:
            team_role = await self._match_team_role(ctx.guild, member, team_role)
            if not team_role:
                return await ctx.send(":x: Team role could not be found.")

        # validate group, enable sharing
        payload = {
            'shared': True,
            'team_identification': 'by-player-clusters',
            'player_identification': 'by-id'
        }
        r = await self._bc_patch_request(auth_token, '/groups/{}'.format(group_code), json=payload)

        if r.status_code in [200, 204]:
            # save group
            await self._save_season_group(ctx.guild, team_role, member, group_code)
            message = ":white_check_mark: Done.\n"
            message += "You may view the {} replay group here:\nhttps://ballchasing.com/group/{}".format(
                team_role.mention,
                group_code
            )
        else:
            message = ":x: **{}** is not a valid group code.".format(
                group_code)
        await ctx.send(message)

# Score Reporting
    
    @commands.command(aliases=['ttnc', 'tempTeamNameChange'])
    @commands.guild_only()
    async def temporaryTeamNameChange(self, ctx, *, temporary_team_name):
        team_role = (await self._get_member_team_roles(ctx.guild, ctx.message.author))[0]
        og_team_name = self._get_team_name(team_role)
        tier = self._get_team_tier(team_role)
        await self._save_temp_team_name_change(ctx.guild, team_role, og_team_name)
        await ctx.send(f"The **{og_team_name}** ({tier}) will be renamed as the **{temporary_team_name}** for {temp_team_name_timeout} seconds.")
        await self._set_team_role_name(team_role, temporary_team_name)
        asyncio.create_task(self._process_team_name_reset(ctx.guild, team_role))
        
    @commands.command(aliases=['fbcr', 'fbcreport', 'bcrfor'])
    @commands.guild_only()
    async def forcebcreport(self, ctx, franchise_team, opposing_team, match_day: int=None, match_type:str=bcConfig.REGULAR_SEASON_MT):
        """Finds match games from recent public uploads for a specified franchise team, and adds them to the correct Ballchasing subgroup
        """
        match_type = match_type.title()
        if match_type not in bcConfig.VALID_MATCH_TYPES:
            return await ctx.send(":x: **{}** is not a valid match type. Please choose from the following: \n\t {}".format(
                match_type,
                ', '.join(bcConfig.VALID_MATCH_TYPES)
            ))
        team_role = await self._match_team_role(ctx.guild, team_name=franchise_team)
        team_name = self._get_team_name(team_role)
        await self._process_bcreport(ctx, team_name, opposing_team, match_day, match_type=match_type)

    @commands.command(aliases=['bcr', 'bcpull', 'played', 'gg'])
    @commands.guild_only()
    async def bcReport(self, ctx, opposing_team, match_day=None):
        """Finds match games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """
        try:
            team_role = (await self._get_member_team_roles(ctx.guild, ctx.message.author))[0]
        except:
            return await ctx.send(":x: You are not rostered to a team in this server.")
        team_name = self._get_team_name(team_role)
        match_type = bcConfig.REGULAR_SEASON_MT
        await self._process_bcreport(ctx, team_name, opposing_team, match_day, match_type)

    @commands.command(aliases=['bcrps', 'postSeasonGame', 'psg', 'reportPlayoffMatch', 'rpm'])
    @commands.guild_only()
    async def bcReportPostSeason(self, ctx, opposing_team, match_day=None):
        """Finds match games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """
        try:
            team_role = (await self._get_member_team_roles(ctx.guild, ctx.message.author))[0]
        except:
            return await ctx.send(":x: You are not rostered to a team in this server.")
        team_name = self._get_team_name(team_role)
        await self._process_bcreport(ctx, team_name, opposing_team, match_day, bcConfig.POSTSEASON_MT)

    @commands.command(aliases=['rs', 'scrimmed', 'bcScrim', 'bcscrim', 'scrim'])
    @commands.guild_only()
    async def reportScrim(self, ctx, *, opposing_team):
        """Finds scrim games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """
        opposing_team = opposing_team.replace('"', '')
        team_role = await self._match_team_role(ctx.guild, member=ctx.author)
        team_name = self._get_team_name(team_role)
        await self._process_bcreport(ctx, team_name, opposing_team, match_type=bcConfig.SCRIM_MT)

    # Broke
    @commands.command(aliases=['bcrg', 'removeGroup', 'deleteGroup', 'delgroup'])
    @commands.guild_only()
    async def bcRemoveGroup(self, ctx, opposing_team, match_day=None, match_type=bcConfig.REGULAR_SEASON_MT):
        """Finds match games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """
        try:
            team_role = (await self._get_member_team_roles(ctx.guild, ctx.message.author))[0]
        except:
            return await ctx.send(":x: You are not rostered to a team in this server.")
        team_name = self._get_team_name(team_role)
        if not match_day:
            match_day = await self._get_match_day(ctx.guild)
        match_type = bcConfig.REGULAR_SEASON_MT

        match_date = await self._get_match_date(ctx.guild, match_day)
        match = {
            "home": team_name,
            "away": opposing_team,
            "matchDay": match_day,
            "matchDate": match_date,
            "type": match_type
        }

        # matches_reported = await self._check_if_reported(ctx, auth_token, team_name, match_day, match_type=bcConfig.REGULAR_SEASON_MT)

        # await ctx.send(match_subgroup_id)
        return

        if not match_subgroup_id:
            return await ctx.send("Oops! Something went wrong...")

        group_owner_id = (await self._get_top_level_group(ctx.guild, team_role))[0]
        auth_token = await self._get_member_bc_token(ctx.guild.get_member(group_owner_id))

        r = await self._bc_delete_request(auth_token, '/groups/{}'.format(match_subgroup_id))

        if r.status_code == 204:
            await ctx.send("Done")
        else:
            await ctx.send("I don't think it worked lol. feel free to check -- https://ballchasing.com/group/{}".fomrat(match_subgroup_id))

# General Use
    # region info commands
    @commands.command(aliases=['team'])
    @commands.guild_only()
    async def roster(self, ctx, team_name=None):
        member = ctx.message.author
        if not team_name:
            try:
                team_role = (await self._get_member_team_roles(ctx.guild, member))[0]
            except:
                return await ctx.send(":x: You are not rostered to a team in this server.")
        else:
            team_role = await self._get_team_role(ctx.guild, team_name)

        team_name = self._get_team_name(team_role)
        emoji_url = ctx.guild.icon_url
        players = []
        for player in await self._get_roster(team_role):
            p_str = player.mention
            if self.is_captain(player):
                p_str = "{} (C)".format(p_str)
            players.append(p_str)
        embed = discord.Embed(
            title="{} Roster".format(team_name),
            description='\n'.join(players),
            color=team_role.color
        )
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)

        await ctx.send(embed=embed)

    @commands.command(aliases=['franchiseTeams'])
    @commands.guild_only()
    async def listFranchiseTeams(self, ctx):
        """List all registered teams"""
        member = ctx.message.author
        team_roles = await self._get_team_roles(ctx.guild)
        await ctx.send('Teams: {}'.format(', '.join(role.mention for role in team_roles)))

    @commands.command()
    @commands.guild_only()
    async def rosters(self, ctx):
        emoji_url = ctx.guild.icon_url
        team_roles = await self._get_team_roles(ctx.guild)
        for team_role in team_roles:
            team_name = self._get_team_name(team_role)
            players = []
            for player in await self._get_roster(team_role):
                p_str = player.mention
                if self.is_captain(player):
                    p_str = "{} (C)".format(p_str)
                players.append(p_str)
            embed = discord.Embed(
                title="{} Roster".format(team_name),
                description='\n'.join(players),
                color=team_role.color
            )
            if emoji_url:
                embed.set_thumbnail(url=emoji_url)

            await ctx.send(embed=embed)

    @commands.command(aliases=['seasonGroup', 'myGroup', 'mygroup', 'gsg'])
    @commands.guild_only()
    async def getSeasonGroup(self, ctx, *, team_name=None):
        """Views this season's ballchasing group for your team"""
        member = ctx.message.author

        team_role = await self._match_team_role(ctx.guild, member, team_name)

        if not team_role:
            return await ctx.send(":x: Team not found.")

        group_code = (await self._get_top_level_group(ctx.guild, team_role))[1]
        message = "https://ballchasing.com/group/{}".format(group_code)
        embed = discord.Embed(title="{} Replay Group".format(
            team_role.name), description=message, color=team_role.color)
        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['allgroups', 'groups'])
    @commands.guild_only()
    async def getSeasonGroups(self, ctx):
        team_roles = await self._get_team_roles(ctx.guild)

        embed = discord.Embed(
            title="Franchise Ballchasing Groups", color=discord.Color.green())
        for team_role in team_roles:
            try:
                group_code = (await self._get_top_level_group(ctx.guild, team_role))[1]
                embed.add_field(name=team_role.name, value="https://ballchasing.com/group/{}".format(group_code), inline=False)
            except:
                pass

        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)

        await ctx.send(embed=embed)

    @commands.command(aliases=['getmatch'])
    @commands.guild_only()
    async def getMatch(self, ctx, match_day=None, *, team_name=None):
        """Gets the ballchasing group for a given team and match day.

        Default Team: (Your team)
        Default Match Day: Current
        """
        if match_day == 'last':
            match_day = str(int(await self._get_match_day(ctx.guild)))
            last = True
        else:
            last = False

        if not match_day:
            match_day = await self._get_match_day(ctx.guild)

        member = ctx.message.author
        if not team_name:
            try:
                team_role = (await self._get_member_team_roles(ctx.guild, member))[0]
            except:
                return await ctx.send(":x: You are not rostered to a team in this server.")
        else:
            team_role = await self._get_team_role(ctx.guild, team_name)

        if not team_role:
            return ctx.send(":x: **{}** is not a valid team name or tier".format(team_name))
        team_name = self._get_team_name(team_role)

        embed = discord.Embed(
            title="Match Day {}: {} vs ...".format(match_day, team_name),
            description="_Finding Group for the {} from match day {}..._".format(
                team_name, match_day),
            color=team_role.color
        )
        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        output_msg = await ctx.send(embed=embed)

        auth_token = await self._get_member_bc_token(member)
        if not auth_token:
            group_owner_id = (await self._get_top_level_group(ctx.guild, team_role))[0]
            auth_token = await self._get_member_bc_token(ctx.guild.get_member(group_owner_id))
        matches_reported = await self._check_if_reported(ctx, auth_token, team_name, match_day, match_type=bcConfig.REGULAR_SEASON_MT)

        if not matches_reported:
            if last:
                match_day = int(match_day) - 1
                embed = discord.Embed(
                    title="Match Day {}: {} vs ...".format(
                        match_day, team_name),
                    description="_Finding Group for the {} from match day {}..._".format(
                        team_name, match_day),
                    color=team_role.color
                )
                await output_msg.edit(embed=embed)
                matches_reported = await self._check_if_reported(ctx, auth_token, team_name, match_day, match_type=bcConfig.REGULAR_SEASON_MT)

            if not matches_reported:
                embed.description = ":x: This match was never reported."
                return await output_msg.edit(embed=embed)

        if len(matches_reported) == 1:
            summary, code, opposing_team = matches_reported[0]
            link = "https://ballchasing.com/group/{}".format(code)
            embed.title = "Match Day {}: {} vs {}".format(
                match_day, team_name, opposing_team)
            embed.description = "{}\n\n[Click here to view this group!]({})".format(
                summary, link)
            await output_msg.edit(embed=embed)
        else:
            embed.description = ""
            for match_report in matches_reported:
                summary, code, opposing_team = match_report
                link = "https://ballchasing.com/group/{}".format(code)
                embed.title = "Match Day {}".format(match_day)
                summary = summary.replace('*', '')
                bc_link = "[View Group]({})".format(link)
                embed.add_field(name=summary, value=bc_link, inline=False)

            await output_msg.edit(embed=embed)
    # endregion info commands

    # region performance
    @commands.command(aliases=['mds', 'matchResultSummary', 'mrs'])
    @commands.guild_only()
    async def matchDaySummary(self, ctx, match_day=None, team=None):
        """Returns Franchise performance for the current, or provided match day"""
        asyncio.create_task(self._match_day_summary(ctx, match_day))

    # TODO: add 'franchise' as team name -- use /groups/{id} on regular season to get team record summary
    @commands.command(aliases=['gsp', 'getSeasonResults', 'gsr'])
    @commands.guild_only()
    async def getSeasonPerformance(self, ctx, *, team_name=None):
        """Returns the season performance for the given team (invoker's team by default)"""
        asyncio.create_task(self._get_season_performance(ctx, team_name))
    # endregion performance

    # region action
    @commands.command()
    @commands.guild_only()
    async def copyGroup(self, ctx, team_name, parent_group_code=None):
        """Executes a process to create a copy of a specified team's replay group, and
        saves it to the invoker's ballchasing account. This is a deep copy."""
        asyncio.create_task(self._process_group_copy(
            ctx, team_name, parent_group_code))

    # endregion action
# ballchasing functions
    # references:
    # https://stackoverflow.com/questions/22190403/how-could-i-use-requests-in-asyncio
    # https://stackoverflow.com/questions/53368203/passing-args-kwargs-to-run-in-executor/53369236

    async def _bc_delete_request(self, auth_token, endpoint, params=[]):
        url = 'https://ballchasing.com/api'
        url += endpoint
        # params = [urllib.parse.quote(p) for p in params]
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)

        # url = urllib.parse.quote_plus(url)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, lambda: requests.delete(
            url, headers={'Authorization': auth_token}))
        response = await future
        return response

    async def _bc_get_request(self, auth_token, endpoint, params=[]):
        url = 'https://ballchasing.com/api'
        url += endpoint
        # params = [urllib.parse.quote(p) for p in params]
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)

        # url = urllib.parse.quote_plus(url)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, lambda: requests.get(
            url, headers={'Authorization': auth_token}))
        response = await future
        return response

    async def _bc_post_request(self, auth_token, endpoint, params=[], json=None, data=None, files=None):
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)

        # return requests.post(url, headers={'Authorization': auth_token}, json=json, data=data, files=files)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, lambda: requests.post(
            url, headers={'Authorization': auth_token}, json=json, data=data, files=files))
        response = await future
        return response

    async def _bc_patch_request(self, auth_token, endpoint, params=[], json=None, data=None):
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)

        # return requests.patch(url, headers={'Authorization': auth_token}, json=json, data=data)
        loop = asyncio.get_event_loop()
        future = loop.run_in_executor(None, lambda: requests.patch(
            url, headers={'Authorization': auth_token}, json=json, data=data))
        response = await future
        return response

# other functions
    # big helpers

    async def _process_group_copy(self, ctx, team_name, parent_code=None, status_msg=None):
        member = ctx.message.author

        # Get origin replay group
        initial_update = "Embed: Matching to team replay group..."
        if status_msg:
            await status_msg.edit(content=initial_update)
        else:
            status_msg = await ctx.send(initial_update)
        team_role = await self._match_team_role(ctx.guild, member, team_name)
        if not team_role:
            return await ctx.send(":x: Team not found.")
        team_name = self._get_team_name(team_role)

        top_level_group = (await self._get_top_level_group(ctx.guild, team_role))[1]

        await ctx.send('top group: {}'.format(top_level_group))
        # Verify Group Can be Copied to Destination
        await status_msg.edit(content="Embed: Verifying valid destination...")
        auth_token = await self._get_member_bc_token(member)
        if not auth_token:
            await status_msg.edit(content="Embed: :x: Member has not registered a ballchasing auth token.")
            return

        # Initiate copy process
        # status_msg = await status_msg.edit(content="Embed: Preparing to copy groups...")

        await ctx.send("A")
        # TODO: make top_level_group IN parent_code instead of them being topographically equal
        if parent_code:
            r = await self._bc_get_request(auth_token, '/groups{}'.format(parent_code))
            if r.status_code != 200:
                return await status_msg.edit(content=":x: **{}** is not a valid ballchasing group code.".format(parent_code))
        else:
            r = await self._bc_get_request(auth_token, '/groups/{}'.format(top_level_group))
            if r.status_code != 200:
                return await status_msg.edit(content=":x: Error copying season group.")
            data = r.json()
            payload = {
                "name": "Copy of {}".format(data['name']),
                "player_identification": data["by-id"],
                "team_identification": data["by-distinct-players"]
            }
            r = await self._bc_post_request(auth_token, '/groups', data=payload)
            if r.status_code == 201:
                data = r.json()
                parent_code = data['id']
            else:
                return await status_msg.edit(content=":x: Error copying season group.")

        await ctx.send("B")
        # Perform Copy
        await self._perform_recursive_copy(auth_token, top_level_group, parent_code)

    async def _perform_recursive_copy(self, ctx, auth_token, parent_origin, parent_mirror, wait_time=0):
        if wait_time:
            await asyncio.sleep(wait_time)

        copy_params = ['group={}'.format(parent_origin)]
        mirror_params = ['group={}'.format(parent_mirror)]

        # Step 1: Copy all subgroups in current group
        # Get existing subgroups
        r = await self._bc_get_request(auth_token, '/groups', params=copy_params)
        r_mirror = await self._bc_get_request(auth_token, '/groups', params=mirror_params)

        if r.status_code != 200 or r_mirror.status_code != 200:
            return

        # prepare all subgroup copies
        data = r.json()
        mirror_data = r_mirror.json()
        if data['list']:
            subgroup_id_payloads = {}
            for subgroup in data['list']:
                sub_payload = {
                    'name': subgroup['name'],
                    'player_identification': subgroup['player_identification'],
                    'team_identification': subgroup['team_identification'],
                    'parent': parent_mirror
                }
                subgroup_id_payloads.append({subgroup['id']: sub_payload})

        # Create subgroup copies
        for subgroup_id, subgroup_payload in subgroup_id_payloads.items():
            group_exists = False
            if mirror_data['count'] > 0:
                for mirror_subgroup in mirror_data['list']:
                    if subgroup_payload['name'] == mirror_subgroup['name']:
                        group_exists = True
                        break

            # If not, create it
            if not group_exists:
                r = await self._bc_post_request(auth_token, '/groups', data=subgroup_payload)
                if r.status_code == 201:
                    data = r.json()
                    mirror_subgroup_id = data['id']

            # Perform recursive copy
            await self._perform_recursive_copy(ctx, auth_token, subgroup_id, mirror_subgroup_id, wait_time=10)

        # Step 2: Copy all replays in current group
        # TODO: patch if original uploader is creating a copy
        # Get existing replays
        r = await self._bc_get_request(auth_token, '/replays', params=copy_params)
        if r.status_code != 200:
            return

        data = r.json()
        if data['count']:
            replay_ids = []
            for replay in data['list']:
                replay_ids.append(replay['id'])  # fix

            # Copy over replays
            tmp_replay_files = await self._download_replays(auth_token, replay_ids)
            uploaded_ids = await self._upload_replays(auth_token, parent_mirror, tmp_replay_files, ctx=ctx)

    async def _get_season_performance(self, ctx, team_name):
        member = ctx.message.author
        team_role = await self._match_team_role(ctx.guild, member, team_name)
        if not team_role:
            return await ctx.send(":x: Team not found.")
        team_name = self._get_team_name(team_role)

        embed = discord.Embed(
            title="{} Season Results".format(team_name),
            description="_Finding season results for the {}..._".format(
                team_name),
            color=team_role.color  # self._get_win_percentage_color(0, 0)
        )
        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        output_msg = await ctx.send(embed=embed)

        member_id, group_code = (await self._get_top_level_group(ctx.guild, team_role))
        auth_token = await self._get_member_bc_token(member)
        if not auth_token:
            auth_token = await self._get_member_bc_token(ctx.guild.get_member(member_id))

        # Get match history
        match_days = []
        opponents = []
        all_results = []
        total_wins = 0
        total_losses = 0

        num_match_days = int(await self._get_match_day(ctx.guild))
        for match_day in range(1, num_match_days+1):
            results = await self._get_team_results(ctx, team_name, match_day, auth_token)
            for result in results:
                wins, losses, opponent = result
                total_wins += wins
                total_losses += losses
                if match_day == num_match_days and not opponent:
                    break

                match_days.append(str(match_day))
                opponents.append("MD {} vs {}".format(match_day, opponent))
                if wins > losses:
                    all_results.append("{}-{} W".format(wins, losses))
                elif losses > wins:
                    all_results.append("{}-{} L".format(wins, losses))
                elif wins == 0 and losses == 0:
                    all_results.append("(Not Reported)")
                else:
                    all_results.append("{}-{} T".format(wins, losses))

        match_days.append("")
        opponents.append("**Total**")
        wp_str = self._get_wp_str(total_wins, total_losses)
        if wp_str:
            all_results.append(
                "**{}-{} ({})**".format(total_wins, total_losses, wp_str))
        else:
            all_results.append("**{}-{}**".format(total_wins, total_losses))

        ## ################

        embed = discord.Embed(
            title="{} Season Results".format(team_name),
            # self._get_win_percentage_color(total_wins, total_losses)
            color=team_role.color
        )

        bc_link = "[Click here to see all groups!](https://ballchasing.com/group/{})".format(
            group_code)
        # embed.add_field(name="MD", value="{}\n".format("\n".join(match_days)), inline=True)
        embed.add_field(name="Opponent", value="{}\n".format(
            "\n".join(opponents)), inline=True)
        embed.add_field(name="Results", value="{}\n".format(
            "\n".join(all_results)), inline=True)
        embed.add_field(name="Ballchasing Group", value=bc_link, inline=False)
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)

        await output_msg.edit(embed=embed)

    async def _process_bcreport(self, ctx, team_name, opposing_team, match_day=None, match_type=bcConfig.REGULAR_SEASON_MT):
        member = ctx.message.author
        team_role = await self._get_team_role(ctx.guild, team_name)

        if not team_role:
            return await ctx.send(":x: **{}** is not a valid team name.".format(team_name))

        # Get team/tier information
        if not match_day:
            match_day = await self._get_match_day(ctx.guild)
        emoji_url = ctx.guild.icon_url

        opposing_team = opposing_team.title() if opposing_team.upper() != opposing_team else opposing_team

        if match_type == bcConfig.REGULAR_SEASON_MT:
            series_title = "Match Day {}: {} vs {}".format(match_day, team_name, opposing_team)
        elif match_type == bcConfig.SCRIM_MT:
            series_title = "{} Scrim vs {}".format(
                datetime.now().strftime("%m/%d"), opposing_team)
        elif match_type == bcConfig.POSTSEASON_MT:
            series_title = "Playoff Match Day {}: {} vs {}".format(
                match_day, team_name, opposing_team)

        embed = discord.Embed(
            title=series_title,
            description="Searching https://ballchasing.com for publicly uploaded replays of this match...",
            color=team_role.color
        )
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        bc_status_msg = await ctx.send(embed=embed)

        # get match date
        all_matches = await self._get_match_dates(ctx.guild)
        now = datetime.now()
        diff = 1
        today = "{dt.month}/{dt.day}/{dt.year}".format(dt=now)

        # await ctx.send("num matches: {}".format(len(all_matches)))
        # await ctx.send("md: {} ({})".format(match_day, type(match_day)))
        # TODO: figure out why this needs to be parsed as an int (only when passed by command)
        if type(match_day) == str:
            match_day = int(match_day)

        if today in all_matches and len(all_matches) >= match_day:
            match_date = all_matches[match_day - diff]
        else:
            match_date = None

        if match_type == bcConfig.SCRIM_MT:
            match_date = today

        # Find replays from ballchasing
        match = {
            "home": team_name,
            "away": opposing_team,
            "matchDay": match_day,
            "matchDate": match_date,
            "type": match_type
        }

        bc_group_owner = ctx.guild.get_member((await self._get_top_level_group(ctx.guild, team_role))[0])
        auth_token = await self._get_member_bc_token(member)
        owner_auth_token = await self._get_member_bc_token(ctx.guild.get_member(bc_group_owner.id))
        if not auth_token:
            auth_token = owner_auth_token
        matches_reported = await self._check_if_reported(ctx, auth_token, match['home'], match['matchDay'], match['type'])

        if match_type == bcConfig.REGULAR_SEASON_MT and matches_reported:
            summary, code, reported_opposing_team = matches_reported[0]
            link = "https://ballchasing.com/group/{}".format(code)
            embed.title = "Match Day {}: {} vs {}".format(
                match_day, team_name, opposing_team)
            if opposing_team == reported_opposing_team:
                embed.description = "This match has already been reported.\n\n{}\n\nView Here: {}".format(
                    summary, link)
                await bc_status_msg.edit(embed=embed)
                return

        if match_type == "Scrim":
            search_count = 30
        else:
            search_count = 20

        replays_found = await self._find_match_replays(ctx, auth_token, member, match, search_count=search_count)

        # Not found:
        if not replays_found:
            embed.description = ":x: No matching replays found on ballchasing."
            await bc_status_msg.edit(embed=embed)
            return None
            # replay_ids, summary, winner = None, None, None
        else:
            # Found:
            replay_ids, summary, winner = replays_found
        # await ctx.send("replays found: {}".format(replays_found))

        if winner:
            pass
            # TODO: check for franchise team emoji

        # Prepare embed edits for score confirmation
        prompt_embed = discord.Embed.from_dict(embed.to_dict())
        prompt_embed.title = embed.title
        prompt_embed.description = "Match summary:\n{}".format(summary)
        prompt_embed.set_thumbnail(url=emoji_url)
        prompt_embed.description += "\n\nPlease react to confirm the score summary for this match."

        success_embed = discord.Embed.from_dict(prompt_embed.to_dict())
        success_embed.description = "Match summary:\n{}".format(summary)
        success_embed.description += "\n\n:signal_strength: Results confirmed. Creating a ballchasing replay group. This may take a few seconds..."  # "\U0001F4F6"

        reject_embed = discord.Embed.from_dict(prompt_embed.to_dict())
        reject_embed.description = "Match summary:\n{}".format(summary)
        reject_embed.description += "\n\n:x: Ballchasing upload has been cancelled."

        USE_BUTTONS = False
        ## HERE #############################################################################################

        if USE_BUTTONS:
            none_found = True if not replays_found else False
            maybe_new_replays = await self.prompt_with_buttons(ctx, bc_status_msg, embed, prompt_embed, success_embed, reject_embed, auth_token, member, match, none_found=none_found)

            if maybe_new_replays:
                if type(maybe_new_replays) == bool:
                    pass
                else:
                    replay_ids, summary, winner = maybe_new_replays
            else:
                return False

        #####################################################################################################
        else:
            if not await self._embed_react_prompt(ctx, prompt_embed, existing_message=bc_status_msg, success_embed=success_embed, reject_embed=reject_embed):
                return False

        # TODO: Add find_replay_date and convert_time_zone
        # if match_type == "Scrim":
        #     matchDate = self.find_replay_date(time_zone="America/New_York")

        # Find or create ballchasing subgroup
        match_subgroup_id = await self._get_replay_destination(ctx, match, match_type)
        if not match_subgroup_id:
            return False

        # Download and upload replays
        tmp_replay_files = await self._download_replays(auth_token, replay_ids)
        uploaded_ids = await self._upload_replays(owner_auth_token, match_subgroup_id, tmp_replay_files, ctx=ctx)
        # await ctx.send("replays in subgroup: {}".format(", ".join(uploaded_ids)))

        renamed = await self._rename_replays(ctx, owner_auth_token, uploaded_ids)

        embed.description = "Match summary:\n{}\n\n[View the ballchasing group!](https://ballchasing.com/group/{})\n\n:white_check_mark: Done".format(
            summary, match_subgroup_id)
        # embed.set_thumbnail(url=emoji_url)
        await bc_status_msg.edit(embed=embed)

    # standard -- maybe rework so each guild gets a scheduled update based on their time zone
    async def auto_update_match_day(self):
        """Loop task to auto-update match day"""
        await self.bot.wait_until_ready()
        # self.bot.get_cog("bcMatchGroups") == self:
        while self.auto_update_md:
            for guild in self.bot.guilds:
                await self._update_match_day(guild, force_set=True)
                update_time = self._schedule_next_update()
            await asyncio.sleep(update_time)
        
    async def _process_team_name_reset(self, guild, team_role):
        """Schedules task to reset team name"""
        await self.bot.wait_until_ready()
        await asyncio.sleep(temp_team_name_timeout)
        og_team_name = await self._get_original_team_name(guild, team_role)
        await self._set_team_role_name(team_role, og_team_name)
        await self._save_temp_team_name_change(guild, team_role, None)

    async def prompt_with_buttons(self, ctx, bc_status_msg, search_embed, prompt_embed, success_embed, reject_embed, auth_token, member, match, with_retry=True, none_found=False):

        ## HERE #############################################################################################

        # Wait for someone to click on them
        def check(inter):
            return inter.message.id == bc_status_msg.id

        # ok_button = Button(style=ButtonStyle.green, emoji=discord.PartialEmoji(name=":white_check_mark:"), label="Create Group", custom_id="create")
        # retry_button = Button(style=ButtonStyle.blurple, emoji=discord.PartialEmoji(name=":grey_exclamation:"), label="Search Again", custom_id="retry")
        # cancel_button = Button(style=ButtonStyle.red, emoji=discord.PartialEmoji(name=":x:"), label="Cancel", custom_id="cancel")


        ok_button = Button(style=ButtonStyle.green, label="Create Group", custom_id="create")
        retry_button = Button(style=ButtonStyle.blurple, label="Search Again", custom_id="retry")
        cancel_button = Button(style=ButtonStyle.red, label="Cancel", custom_id="cancel")

        # row_of_buttons = ActionRow(ok_button, retry_button, cancel_button) # if with_retry else ActionRow(ok_button, cancel_button)
        row_of_buttons = ActionRow()

        if not none_found:
            row_of_buttons.add_button(style=ButtonStyle.green, label="Create Group", custom_id="create")
        if not with_retry:
            row_of_buttons.add_button(style=ButtonStyle.blurple, label="Search Again", custom_id="retry")
        row_of_buttons.add_button(style=ButtonStyle.red, label="Cancel", custom_id="cancel")

        # Send a message with buttons
        await bc_status_msg.edit(embed=prompt_embed, components=[row_of_buttons])

        timeout = 20
        inter = await ctx.wait_for_button_click(check, timeout)

        # Send what you received
        button_text = inter.clicked_button.label
        await inter.reply(f"Button: {button_text}")

        if inter.clicked_button.custom_id == "create":
            await inter.message.edit(embed=success_embed, components=[])
            return True
        elif inter.clicked_button.custom_id == "retry":
            await bc_status_msg.edit(embed=search_embed, components=[])

            replays_found = await self._find_match_replays(ctx, auth_token, member, match, deep_search=True)

            if not replays_found:
                return None

            summary = replays_found[1]
            prompt_embed.description = "Match summary:\n{}".format(summary)

            await bc_status_msg.edit(embed=prompt_embed)
            new_replays = await self.prompt_with_buttons(ctx, bc_status_msg, search_embed, prompt_embed, success_embed, reject_embed, None, None, None, False)
            if new_replays:
                return new_replays
            return None

        elif inter.clicked_button.custom_id == "cancel":
            if none_found:
                await inter.message.edit(embed=reject_embed, components=[])
            else:
                await inter.message.edit(components=[])
            return None
        else:
            await inter.message.edit(components=[])

        ## HERE #############################################################################################

    def _schedule_next_update(self):
        # wait_time = 3600  # one hour
        today = datetime.date(datetime.now())
        tomorrow = today + timedelta(days=1)
        tomorrow_dt = datetime.combine(tomorrow, datetime.min.time())
        wait_time = (tomorrow_dt - datetime.now()).seconds + 30
        return wait_time

    async def _match_day_summary(self, ctx, match_day=None):
        # team_roles = await self._get_team_roles(ctx.guild)
        if match_day == 'last':
            match_day = str(int(await self._get_match_day(ctx.guild)) - 1)
            last = True
        else:
            last = False

        if not match_day:
            match_day = await self._get_match_day(ctx.guild)

        embed = discord.Embed(
            title="Franchise Results for Match Day {}".format(match_day),
            description="_Finding franchise results for match day {}..._".format(
                match_day),
            color=self._get_win_percentage_color(0, 0)
        )
        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        output_msg = await ctx.send(embed=embed)
        team_roles = await self._get_team_roles(ctx.guild)

        teams = []
        tiers = []
        all_results = []
        total_wins = 0
        total_losses = 0
        auth_token = await self._get_member_bc_token(ctx.message.author)

        use_invoker_auth_token = True
        if not auth_token:
            use_invoker_auth_token = False

        for team_role in team_roles:
            if not use_invoker_auth_token:
                owner = team_role.guild.get_member((await self._get_top_level_group(team_role.guild, team_role))[0])
                auth_token = await self._get_member_bc_token(owner)
            team_name = self._get_team_name(team_role)
            results = await self._get_team_results(ctx, team_name, match_day, auth_token)
            team_scores = []

            for result in results:
                wins, losses, opponent = result
                total_wins += wins
                total_losses += losses

                if wins > losses:
                    team_scores.append("{}-{} W".format(wins, losses))
                elif losses > wins:
                    team_scores.append("{}-{} L".format(wins, losses))
                elif wins == 0 and losses == 0:
                    team_scores.append("(Not Reported)")
                else:
                    team_scores.append("{}-{} T".format(wins, losses))

            teams.append(team_name)
            tiers.append(self._get_team_tier(team_role))
            all_results.append(', '.join(team_scores))
        teams.append("**Franchise**")
        tiers.append("-")
        wp_str = self._get_wp_str(total_wins, total_losses)
        if wp_str:
            all_results.append(
                "**{}-{} ({})**".format(total_wins, total_losses, wp_str))
        else:
            all_results.append("**{}-{}**".format(total_wins, total_losses))

        embed = discord.Embed(
            title="Franchise Results for Match Day {}".format(match_day),
            color=self._get_win_percentage_color(total_wins, total_losses)
        )

        embed.add_field(name="Team", value="{}\n".format(
            "\n".join(teams)), inline=True)
        try:
            embed.add_field(name="Tier", value="{}\n".format(
                "\n".join(tiers)), inline=True)
        except:
            pass
        embed.add_field(name="Results", value="{}\n".format(
            "\n".join(all_results)), inline=True)
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)

        await output_msg.edit(embed=embed)

    async def _get_team_results(self, ctx, franchise_team, match_day, auth_token, match_type=bcConfig.REGULAR_SEASON_MT):
        guild = ctx.guild
        team_role = await self._get_team_role(guild, franchise_team)
        top_level_group_info = await self._get_top_level_group(guild, team_role)

        # Get match_type subgroup from top-level-group
        r = await self._bc_get_request(auth_token, '/groups', params=['group={}'.format(top_level_group_info[1])])

        data = r.json()

        opposing_team = ''
        if 'list' not in data:
            return [0, 0, opposing_team]

        match_type_group_code = None
        for sub_group in data['list']:
            if sub_group['name'] == match_type:
                match_type_group_code = sub_group['id']
                break

        if not match_type_group_code:
            return [0, 0, opposing_team]

        # Get match replay group from match_type subgroup
        r = await self._bc_get_request(auth_token, '/groups', params=['group={}'.format(match_type_group_code)])

        data = r.json()

        opposing_team = ''
        if 'list' not in data:
            return [0, 0, opposing_team]

        # Get match summary from replays in group
        results = []
        for match_group in data['list']:
            match_group_code = ''
            if '{}'.format(match_day).zfill(2) in match_group['name']:
                match_group_code = match_group['id']
                opposing_team = match_group['name'].split(' vs ')[-1]

            if not match_group_code:
                continue

            r = await self._bc_get_request(auth_token, '/replays', params=['group={}'.format(match_group_code)])
            data = r.json()
            if 'list' not in data:
                continue

            if not data['list']:
                continue

            franchise_wins = 0
            franchise_losses = 0
            for replay in data['list']:
                is_blue = await self._check_if_blue(replay, team_role)

                blue_goals = replay['blue']['goals'] if 'goals' in replay['blue'] else 0
                orange_goals = replay['orange']['goals'] if 'goals' in replay['orange'] else 0

                if is_blue:
                    if blue_goals > orange_goals:
                        franchise_wins += 1
                    else:
                        franchise_losses += 1
                else:
                    if blue_goals > orange_goals:
                        franchise_losses += 1
                    else:
                        franchise_wins += 1

            if franchise_wins or franchise_losses:
                results.append(
                    (franchise_wins, franchise_losses, opposing_team))

        if results:
            return results
        return [(0, 0, '')]

    async def _check_if_blue(self, replay, team_role):
        franchise_team = self._get_team_name(team_role)
        try:
            is_blue = franchise_team.lower() in replay['blue']['name'].lower()
            is_orange = franchise_team.lower(
            ) in replay['orange']['name'].lower()

            if is_blue ^ is_orange:  # ^ is xor
                return is_blue
        except:
            pass

        blue_players = await self._get_replay_player_ids(replay, 'blue')
        orange_players = await self._get_replay_player_ids(replay, 'orange')

        franchise_roster = self._get_players_from_team_role(team_role)
        for player in franchise_roster:
            accounts = await self._get_all_accounts(player.id)
            if accounts:
                for account in accounts:
                    if account in blue_players:
                        return True
                    elif account in orange_players:
                        return False
        return random.choice([True, False])

    async def _get_replay_player_ids(self, replay_data, color):
        players = []
        for player in replay_data[color]['players']:
            players.append([player['id']['platform'], player['id']['id']])
        return players

    async def _check_if_reported(self, ctx, auth_token, franchise_team, match_day, match_type=bcConfig.REGULAR_SEASON_MT):
        guild = ctx.guild
        team_role = await self._get_team_role(guild, franchise_team)
        top_level_group_info = await self._get_top_level_group(guild, team_role)

        r = await self._bc_get_request(auth_token, '/groups', params=['group={}'.format(top_level_group_info[1])])
        data = r.json()
        if 'list' not in data:
            return None

        match_type_group = None
        for group in data['list']:
            if group['name'] == match_type:
                match_type_group = group['id']
                break

        if not match_type_group:
            return None

        r = await self._bc_get_request(auth_token, '/groups', params=['group={}'.format(match_type_group)])
        data = r.json()
        if 'list' not in data:
            return None

        result_summaries = []
        for group in data['list']:
            match_group_code = ''
            opposing_team = ''
            if '{}'.format(match_day).zfill(2) in group['name']:
                match_group_code = group['id']
                opposing_team = group['name'].split(' vs ')[-1]

            if not match_group_code:
                continue

            r = await self._bc_get_request(auth_token, '/replays', params=['group={}'.format(match_group_code)])
            data = r.json()
            # result_data = self._get_reported_match_data(ctx, data)
            if 'list' not in data:
                continue

            if not data['list']:
                continue

            franchise_wins = 0
            franchise_losses = 0
            for replay in data['list']:
                is_blue = await self._check_if_blue(replay, team_role)
                blue_goals = replay['blue']['goals'] if 'goals' in replay['blue'] else 0
                orange_goals = replay['orange']['goals'] if 'goals' in replay['orange'] else 0

                if is_blue:
                    if blue_goals > orange_goals:
                        franchise_wins += 1
                    else:
                        franchise_losses += 1
                else:
                    if blue_goals > orange_goals:
                        franchise_losses += 1
                    else:
                        franchise_wins += 1

            if franchise_wins or franchise_losses:
                summary = "**{}** {} - {} **{}**".format(
                    franchise_team, franchise_wins, franchise_losses, opposing_team)
                result_summaries.append(
                    (summary, match_group_code, opposing_team))

        return result_summaries

    # TODO: Use this to reduce dup code between _check_if_reported and _get_team_results
    async def _get_reported_match_data(self, ctx, response_data, team):
        pass

    async def _find_match_replays(self, ctx, auth_token, member, match, team_players=None, search_count=None, sort_by=None, deep_search=False):

        # TODO: allow opposing_team to be None => ask in helper function

        if not auth_token:
            return None

        if not team_players:
            team_role = await self._get_team_role(ctx.guild, match['home'])
            team_players = await self._get_roster(team_role)
        # search for appearances in private matches
        endpoint = "/replays"

        zone_adj = '-04:00'
        # date_string = match['matchDate']
        # match_date = datetime.strptime(date_string, '%B %d, %Y').strftime('%Y-%m-%d')
        match_date = match['matchDate']

        if not sort_by:
            sort_by = bcConfig.sort_by

        params = [
            # 'uploader={}'.format(uploader),
            'playlist=private',
            'sort-by={}'.format(bcConfig.sort_by),
            'sort-dir={}'.format(bcConfig.sort_dir)
        ]

        # if match_date:
        #     # Filters by matches played on this day
        #     start_match_date_rfc3339 = "{}T00:00:00{}".format(
        #         match_date, zone_adj)
        #     end_match_date_rfc3339 = "{}T23:59:59{}".format(
        #         match_date, zone_adj)
        #     params.append(
        #         'replay-date-after={}'.format(start_match_date_rfc3339))
        #     params.append(
        #         'replay-date-before={}'.format(end_match_date_rfc3339))

        if search_count:
            params.append('count={}'.format(search_count))
        else:
            params.append('count={}'.format(bcConfig.search_count))

        # Search invoker's replay uploads first
        if member in team_players:
            team_players.remove(member)
            team_players.insert(0, member)
        else:
            team_players.append(member)

        # Search all players in game for replays until match is found
        return_replay_ids = []
        return_series_summary = None
        return_winner = None
        for player in team_players:
            for steam_id in await self._get_steam_ids(player.id):
                # TODO: compare results to format, maybe add "skipped replays" field?
                uploaded_by_param = 'uploader={}'.format(steam_id)
                params.append(uploaded_by_param)

                r = await self._bc_get_request(auth_token, endpoint, params=params)
                
                if bcConfig.DEBUG and ctx.guild.id == 675121792741801994:
                    channel = ctx.guild.get_channel(741758967260250213)
                    await channel.send(params)

                data = r.json()
                params.remove(uploaded_by_param)

                # checks for correct replays
                home_wins = 0
                away_wins = 0
                replay_ids = []
                if 'list' in data:
                    for replay in data['list']:
                        if self.is_match_replay(match, replay):
                            replay_ids.append(replay['id'])
                            if replay['blue']['name'].lower() in match['home'].lower():
                                home = 'blue'
                                away = 'orange'
                            else:
                                home = 'orange'
                                away = 'blue'

                            # if not match['matchDate']:
                            #     mm, dd, yyyy = replay['date'][0:10].split('-')
                            #     match_date = datetime(
                            #         int(yyyy), int(mm), int(dd))
                            #     match_date_str = "{dt.month}/{dt.day}/{dt.year}".format(
                            #         dt=match_date)
                            #     match.update({'matchDate': match_date_str})

                            home_goals = replay[home]['goals'] if 'goals' in replay[home] else 0
                            away_goals = replay[away]['goals'] if 'goals' in replay[away] else 0
                            if home_goals > away_goals:
                                home_wins += 1
                            else:
                                away_wins += 1

                    series_summary = "**{home_team}** {home_wins} - {away_wins} **{away_team}**".format(
                        home_team=match['home'],
                        home_wins=home_wins,
                        away_wins=away_wins,
                        away_team=match['away']
                    )
                    winner = None
                    if home_wins > away_wins:
                        winner = match['home']
                    elif home_wins < away_wins:
                        winner = match['away']

                    if len(replay_ids) > len(return_replay_ids):
                        return_replay_ids = replay_ids.copy()
                    
                    if return_replay_ids and not deep_search:
                        return return_replay_ids, series_summary, winner
        
        if return_replay_ids:
            return return_replay_ids, return_series_summary, return_winner

        return None

    async def _discover_match_opponent(self, ctx, match_data):
        pass

    async def _update_match_day(self, guild, channel=None, force_set=False):
        all_matches = await self._get_match_dates(guild)
        match_day = await self._get_match_day(guild)
        if match_day == None or not all_matches:
            return
        now = datetime.now()
        diff = 1
        today = "{dt.month}/{dt.day}/{dt.year}".format(dt=now)
        # await channel.send(today)
        # await channel.send([str("{}".format(match)) for match in all_matches])
        if today not in all_matches and force_set:
            all_dates = []
            for match in all_matches:
                mm, dd, yy = match.split('/')
                all_dates.append(datetime(int(yy), int(mm), int(dd)))

            this_date = datetime(now.year, now.month, now.day)
            if this_date not in all_dates:
                all_dates.append(this_date)
                diff = 0
            all_dates.sort()
            all_matches = [
                "{dt.month}/{dt.day}/{dt.year}".format(dt=date) for date in all_dates]

        new_match_day = all_matches.index(today) + diff
        if str(match_day) != str(new_match_day):
            await self._save_match_day(guild, new_match_day)
            if str(guild.id) == str(675121792741801994):
                if guild.system_channel and not channel:
                    channel = guild.system_channel
                    await channel.send("New match day: {}".format(new_match_day))

    def is_captain(self, member: discord.Member):
        for role in member.roles:
            if role.name.lower() == "captain":
                return True

    async def _get_roster(self, team_role: discord.Role):
        return team_role.members

    async def _get_all_accounts(self, discord_id):
        discord_id = str(discord_id)
        account_register = await self.account_manager_cog.get_account_register()
        if discord_id in account_register:
            return account_register[discord_id]
        return []

    async def _get_steam_id_from_token(self, auth_token):
        r = await self._bc_get_request(auth_token, '')
        if r.status_code == 200:
            return r.json()['steam_id']
        return None

    async def _get_steam_ids(self, discord_id):
        discord_id = str(discord_id)
        steam_accounts = []
        account_register = await self.account_manager_cog.get_account_register()
        if discord_id in account_register:
            for account in account_register[discord_id]:
                if account[0] == 'steam':
                    steam_accounts.append(account[1])
        return steam_accounts

    # maybe outdated?
    async def _get_member_team_roles(self, guild, member):
        team_roles = await self.config.guild(guild).TeamRoles()
        player_team_roles = []
        for role in member.roles:
            if role.id in team_roles:
                player_team_roles.append(role)
        return player_team_roles

    async def _match_team_role(self, guild, member=None, team_name=None):
        """Retreives the role for a specified team. If teaam_name is not provided, matches to the invoker's team."""
        team_roles = await self._get_team_roles(guild)
        # Find from team_name
        if team_name:
            for role in team_roles:
                if team_name.lower() == role.name.lower() or (team_name.lower() in ' '.join(role.name.split()[: -1]).lower()) or (len(role.name.split()) > 1 and team_name.lower() == (role.name.split()[-1][1: -1]).lower()):
                    return role
            return None

        if not member:
            return None

        # Find member's team
        for role in team_roles:
            if role in member.roles:
                return role
        return None

    def _get_team_name(self, role: discord.Role):
        if role.name[-1] == ')' and ' (' in role.name:
            return ' '.join((role.name).split()[:-1])
        return role.name
    
    async def _set_team_role_name(self, team_role: discord.Role, team_name: str):
        tier = self._get_team_tier(team_role)
        new_role_name = f"{team_name} ({tier})" if tier else team_name
        await team_role.edit(name=new_role_name)

    async def _get_team_role(self, guild, team_name_or_player):
        team_roles = await self._get_team_roles(guild)

        if type(team_name_or_player) == discord.Member:
            player = team_name_or_player
            for role in player.roles:
                if role in team_roles:
                    return role

        elif type(team_name_or_player) == str:
            team_name = team_name_or_player
            for role in team_roles:
                if team_name.lower() in role.name.lower():
                    return role
            return None

        return None

    def _get_team_tier(self, role):
        if role.name[-1] == ')' and ' (' in role.name:
            opi = role.name.index(' (')+2
            cpi = role.name.index(')')
            return role.name[opi:cpi]
        return None

    def is_match_replay(self, match, replay_data):
        home_team = match['home']       # match cog
        away_team = match['away']       # match cog

        if not self._is_full_replay(replay_data):
            return False

        replay_teams = self.get_replay_teams(replay_data)

        home_team_found = replay_teams['blue']['name'].lower() in home_team.lower(
        ) or replay_teams['orange']['name'].lower() in home_team.lower()
        away_team_found = replay_teams['blue']['name'].lower() in away_team.lower(
        ) or replay_teams['orange']['name'].lower() in away_team.lower()

        return home_team_found and away_team_found

    def _is_full_replay(self, replay_data):
        if 'duration' in replay_data:
            if replay_data['duration'] < 300:
                return False
        else:
            return False

        blue_goals = replay_data['blue']['goals'] if 'goals' in replay_data['blue'] else 0
        orange_goals = replay_data['orange']['goals'] if 'goals' in replay_data['orange'] else 0
        if blue_goals == orange_goals:
            return False
        for team in ['blue', 'orange']:
            try:
                for player in replay_data[team]['players']:
                    if player['start_time'] == 0:
                        return True
            except:
                return False
        return False

    def get_replay_teams(self, replay):
        try:
            blue_name = replay['blue']['name'].title()
        except:
            blue_name = "Blue"
        try:
            orange_name = replay['orange']['name'].title()
        except:
            orange_name = "Orange"

        blue_players = []
        for player in replay['blue']['players']:
            blue_players.append(player['name'])

        orange_players = []
        for player in replay['orange']['players']:
            orange_players.append(player['name'])

        teams = {
            'blue': {
                'name': blue_name,
                'players': blue_players
            },
            'orange': {
                'name': orange_name,
                'players': orange_players
            }
        }
        return teams

    async def _react_prompt(self, ctx, prompt, if_not_msg=None):
        user = ctx.message.author
        react_msg = await ctx.send(prompt)
        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                return True
            if if_not_msg:
                await ctx.send(if_not_msg)
            return False
        except asyncio.TimeoutError:
            await ctx.send("Sorry {}, you didn't react quick enough. Please try again.".format(user.mention))
            return False

    async def _embed_react_prompt(self, ctx, embed, existing_message=None, success_embed=None, reject_embed=None, clear_after_confirm=True):
        user = ctx.message.author
        if existing_message:
            react_msg = existing_message
            await react_msg.edit(embed=embed)
        else:
            react_msg = await ctx.send(embed=embed)

        start_adding_reactions(react_msg, ReactionPredicate.YES_OR_NO_EMOJIS)
        try:
            pred = ReactionPredicate.yes_or_no(react_msg, user)
            await ctx.bot.wait_for("reaction_add", check=pred, timeout=verify_timeout)
            if pred.result:
                await react_msg.edit(embed=success_embed)
                if clear_after_confirm:
                    await react_msg.clear_reactions()
                return True
            if reject_embed:
                await react_msg.edit(embed=reject_embed)
            return False
        except asyncio.TimeoutError:
            await react_msg.edit(embed=reject_embed)
            await ctx.send("Sorry {}, you didn't react quick enough. Please try again.".format(user.mention))
            return False

    async def _get_replay_destination(self, ctx, match, match_type=bcConfig.REGULAR_SEASON_MT):
        team_role = await self._get_team_role(ctx.guild, match['home'])
        top_level_group_info = await self._get_top_level_group(ctx.guild, team_role)
        bc_group_owner = ctx.guild.get_member(top_level_group_info[0])
        top_group_code = top_level_group_info[1]
        auth_token = await self._get_member_bc_token(bc_group_owner)
        bc_group_owner_steam = await self._get_steam_id_from_token(auth_token)

        # <top level group>/MD <Match Day> vs <Opposing Team>

        if match['type'] == bcConfig.SCRIM_MT:
            today = "{dt.month}/{dt.day}".format(dt=datetime.now())
            match_title = "{} vs {}".format(today, match['away'].title())
        else:
            match_title = "MD {} vs {}".format(
                str(match['matchDay']).zfill(2), match['away'].title())

        ordered_subgroups = [
            match['type'],
            match_title
        ]

        endpoint = '/groups'
        params = [
            # 'creator={}'.format(bc_group_owner_steam),
            'group={}'.format(top_group_code)
        ]

        r = await self._bc_get_request(auth_token, endpoint, params=params)
        data = r.json()

        debug = False
        if debug:
            await ctx.send(len(data['list']))
            await ctx.send(bc_group_owner_steam)
            await ctx.send(top_group_code)
            await ctx.send('{}?{}'.format(endpoint, '&'.join(params)))

        # Dynamically create sub-group
        current_subgroup_id = top_group_code
        next_subgroup_id = None
        for next_group_name in ordered_subgroups:
            if next_subgroup_id:
                current_subgroup_id = next_subgroup_id
            next_subgroup_id = None

            # Check if next subgroup exists
            if 'list' in data:
                for data_subgroup in data['list']:
                    if debug:
                        await ctx.send(data_subgroup)
                    if data_subgroup['name'] == next_group_name:
                        next_subgroup_id = data_subgroup['id']
                        break

            # Prepare & Execute  Next request:
            # ## Next subgroup found: request its contents
            if next_subgroup_id:
                params = [
                    'creator={}'.format(bc_group_owner),
                    'group={}'.format(next_subgroup_id)
                ]

                r = await self._bc_get_request(auth_token, endpoint, params)
                data = r.json()

            # ## Creating next sub-group
            else:
                payload = {
                    'name': next_group_name,
                    'parent': current_subgroup_id,
                    'player_identification': bcConfig.player_identification,
                    'team_identification': bcConfig.team_identification
                }
                r = await self._bc_post_request(auth_token, endpoint, json=payload)
                data = r.json()
                try:
                    next_subgroup_id = data['id']
                except:
                    await ctx.send(":x: Error creating Ballchasing group: {}".format(next_group_name))
                    return False

        return next_subgroup_id

    async def _download_replays(self, auth_token, replay_ids):
        tmp_replay_files = []
        this_game = 1
        for replay_id in replay_ids[::-1]:
            endpoint = "/replays/{}/file".format(replay_id)
            r = await self._bc_get_request(auth_token, endpoint)

            # replay_filename = "Game {}.replay".format(this_game)
            replay_filename = "{}.replay".format(replay_id)

            tf = tempfile.NamedTemporaryFile()
            tf.name += ".replay"
            tf.write(r.content)
            tmp_replay_files.append(tf)
            this_game += 1

        return tmp_replay_files

    async def _upload_replays(self, auth_token, subgroup_id, files_to_upload, ctx=None):
        endpoint = "/v2/upload"
        params = [
            'visibility={}'.format(bcConfig.visibility),
            'group={}'.format(subgroup_id)
        ]

        replay_ids_in_group = []
        for replay_file in files_to_upload:
            replay_file.seek(0)
            files = {'file': replay_file}

            r = await self._bc_post_request(auth_token, endpoint, params=params, files=files)

            status_code = r.status_code
            data = r.json()

            try:
                if status_code == 201:
                    replay_ids_in_group.append(data['id'])
                elif status_code == 409:
                    payload = {
                        'group': subgroup_id
                    }
                    r = await self._bc_patch_request(auth_token, '/replays/{}'.format(data['id']), json=payload)
                    if r.status_code == 204:
                        replay_ids_in_group.append(data['id'])
                    elif ctx:
                        await ctx.send(":x: {} error: {}".format(r.status_code, r.json()['error']))
            except:
                if ctx:
                    await ctx.send(":x: {} error: {}".format(status_code, data['error']))

        return replay_ids_in_group

    async def _rename_replays(self, ctx, auth_token, uploaded_replays_ids):
        renamed = []

        game_number = 1
        for replay_id in uploaded_replays_ids:
            endpoint = '/replays/{}'.format(replay_id)
            payload = {
                'title': 'Game {}'.format(game_number)
            }
            r = await self._bc_patch_request(auth_token, endpoint, json=payload)
            status_code = r.status_code

            if status_code == 204:
                renamed.append(replay_id)
            else:
                await ctx.send(":x: {} error.".format(status_code))

            game_number += 1
        return renamed

    def _find_role_by_name(self, guild, role_name):
        for role in guild.roles:
            if role.name.lower() == role_name.lower():
                return role
        return None

    def _get_players_from_team_role(self, team_role):
        roster = []
        for member in team_role.guild.members:
            if team_role in member.roles:
                roster.append(member)
        return roster

    def _get_wp(self, wins, losses):
        return wins/(wins+losses)

    def _get_wp_str(self, wins, losses, round_to=2):
        if wins + losses:
            return "{}%".format(round(self._get_wp(wins, losses)*100, round_to))
        return ""

    def _get_win_percentage_color(self, wins: int, losses: int):
        if not (wins or losses):
            return discord.Color.default()
        red = (255, 0, 0)
        yellow = (255, 255, 0)
        green = (0, 255, 0)
        wp = self._get_wp(wins, losses)

        if wp == 0:
            return discord.Color.from_rgb(*red)
        if wp == 0.5:
            return discord.Color.from_rgb(*yellow)
        if wp == 1:
            return discord.Color.from_rgb(*green)

        blue_scale = 0
        if wp < 0.5:
            wp_adj = wp/0.5
            red_scale = 255
            green_scale = round(255*wp_adj)
            return discord.Color.from_rgb(red_scale, green_scale, blue_scale)
        else:
            # sub_wp = ((wp-50)/50)*100
            wp_adj = (wp-0.5)/0.5
            green_scale = 255
            red_scale = 255 - round(255*wp_adj)
            return discord.Color.from_rgb(red_scale, green_scale, blue_scale)

    async def _get_match_date(self, guild, match_day=None):
        if not match_day:
            match_day = self._get_match_day(guild)
        match_day = int(match_day)

        all_matches = await self._get_match_dates(guild)

        # if not all_matches:
        #     return None

        now = datetime.now()
        diff = 1
        today = "{dt.month}/{dt.day}/{dt.year}".format(dt=now)

        match_date = today

        if today in all_matches and len(all_matches) >= match_day:
            match_date = all_matches[match_day - diff]

        return match_date

# json dict
    async def _get_match_dates(self, guild):
        return await self.config.guild(guild).MatchDates()

    async def _save_match_dates(self, guild, match_dates):
        await self.config.guild(guild).MatchDates.set(match_dates)

    async def _get_match_day(self, guild):
        return int(await self.config.guild(guild).MatchDay())

    async def _save_match_day(self, guild, match_day):
        await self.config.guild(guild).MatchDay.set(match_day)

    async def _get_team_roles(self, guild):
        team_role_ids = await self.config.guild(guild).TeamRoles()
        team_roles = [guild.get_role(role_id) for role_id in team_role_ids]
        team_roles.sort(key=lambda tr: tr.position, reverse=True)
        return team_roles

    async def _save_temp_team_name_change(self, guild, team_role: discord.Role, temp_name: str):
        temp_team_names = {}
        if temp_name:
            temp_team_names[str(team_role.id)] = temp_name
        else:
            if str(team_role.id) in temp_team_names:
                del temp_team_names[str(team_role.id)]

        await self.config.guild(guild).TeamNameChanges.set(temp_team_names)
    
    async def _get_original_team_name(self, guild, team_role: discord.Role):
        return (await self.config.guild(guild).TeamNameChanges()).get(str(team_role.id), None)

    async def _save_season_group(self, guild, team_role, captain, group_code):
        groups = await self.config.guild(guild).ReplayGroups()
        groups[str(team_role.id)] = [captain.id, group_code]
        await self._save_top_level_groups(guild, groups)

    async def _get_top_level_group(self, guild, team_role):
        try:
            return (await self.config.guild(guild).ReplayGroups()).get(str(team_role.id), None)
        except:
            return None

    async def _save_top_level_groups(self, guild, groups):
        await self.config.guild(guild).ReplayGroups.set(groups)

    async def _save_team_roles(self, guild, roles):
        await self.config.guild(guild).TeamRoles.set(roles)
    
    async def _get_member_bc_token(self, member: discord.Member):
        return await self.account_manager_cog._get_member_bc_token(member)
