import abc
from .config import config
from datetime import datetime, timedelta, timezone
import tempfile
import discord
import asyncio
import requests
import random
import urllib.parse

# try:
#     import thread
# except ImportError:
#     from pip._internal import main as pip
#     pip(['install', '--user', 'thread'])
#     import thread

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"Emoji": None, "MatchDay": 1, "TeamRoles": [], "ReplayGroups": {}, "Schedule": {}}
global_defaults = {"BCTokens": {}}
verify_timeout = 30

class BCMatchGroups(commands.Cog):
    """Allows members of a franchise to create ballchasing groups"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_global(**global_defaults)
        self.config.register_guild(**defaults)
        self.account_manager_cog = bot.get_cog("AccountManager")
  
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def setMatchDay(self, ctx, match_day):
        await self.config.guild(ctx.guild).MatchDay.set(match_day)
        await ctx.send("Done")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def nextMatchDay(self, ctx):
        match_day = await self.config.guild(ctx.guild).MatchDay()
        match_day = int(match_day) + 1
        await self.config.guild(ctx.guild).MatchDay.set(match_day)
        await ctx.send(":white_check_mark: It is now **match day {}**.".format(match_day))

    @commands.command(aliases=['md'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def getMatchDay(self, ctx):
        match_day = await self.config.guild(ctx.guild).MatchDay()
        await ctx.send("Match Day {}.".format(match_day))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def addTeamRoles(self, ctx, *roleList):
        """Adds the role to every member that can be found from the userList"""
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
            message_components.append(":x: **{}** roles failed: {}".format(len(failed), ', '.join(role_name for role_name in failed)))
        
        if found:
            message_components.append(":white_check_mark: Added **{}** team roles: {}".format(len(found), ', '.join(role_name.mention for role_name in found)))
        
        if message_components:
            return await ctx.send('\n'.join(message_components))
        
        await ctx.send(":x: No roles provided.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    async def clearTeamRoles(self, ctx):
        prompt = "Are you sure you want to clear **{}** Team Roles?".format(len(await self._get_team_roles(ctx.guild)))
        if await self._react_prompt(ctx, prompt, "Teams not cleared."):
            await self._save_team_roles(ctx.guild, [])
            await ctx.send("Done")

    @commands.command(aliases=['setMyBCAuthKey'])
    async def setMyBCAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Ballchasing API requests for the given user.
        """
        member = ctx.message.author
        try:
            try:
                await ctx.message.delete()
            except:
                pass
            await self._save_member_bc_token(member, auth_token)
            await ctx.send(":white_check_mark: {}, your Ballchasing Auth Token has been set.".format(member.name))
        except:
            await ctx.send(":x: Error setting auth token.")
        
    @commands.command(aliases=['setTopLevelGroup'])
    @commands.guild_only()
    async def setSeasonGroup(self, ctx, group_code, *, team_role:discord.Role=None):
        #TODO: derive player/captain, team from owner of ballchasing group upon lookup
        member = ctx.message.author
        if not team_role:
            team_roles = (await self._get_member_team_roles(ctx.guild, member))
            if team_roles:
                team_role = team_roles[0]
            else:
                return await ctx.send(":x: Couldn't find your team")
        await self._save_season_group(ctx.guild, team_role, member, group_code)
        message = ":white_check_mark: Done.\n"
        message += "You may view the {} replay group here:\nhttps://ballchasing.com/group/{}".format(
            team_role.mention,
            group_code
        )
        await ctx.send(message)

    @commands.command(aliases=['seasonGroup', 'myGroup', 'mygroup'])
    @commands.guild_only()
    async def getSeasonGroup(self, ctx, *, team_name=None):
        """Views this season's ballchasing group for your team"""
        member = ctx.message.author
        
        team_roles = await self._get_team_roles(ctx.guild)
        team_role = None
        if team_name:
            for role in team_roles:
                if team_name.lower() in ' '.join(role.name.split()[:-1]).lower() or (len(role.name.split()) > 1 and team_name.lower() == (role.name.split()[-1][1:-1]).lower()):
                    team_role = role
        else:
            for role in team_roles:
                if role in member.roles:
                    team_role = role
        
        if not team_role:
            return await ctx.send(":x: Team not found.")

        group_code = (await self._get_top_level_group(ctx.guild, team_role))[1]
        message = "https://ballchasing.com/group/{}".format(group_code)
        embed = discord.Embed(title="{} Replay Group".format(team_role.name), description=message, color=team_role.color)
        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        await ctx.send(embed=embed)

    @commands.command(aliases=['allgroups', 'groups'])
    @commands.guild_only()
    async def getSeasonGroups(self, ctx):
        ordered_roles = []
        team_roles = await self._get_team_roles(ctx.guild)
        for role in ctx.guild.roles:
            if role in team_roles:
                ordered_roles.append(role)
        ordered_roles.reverse()

        embed = discord.Embed(title="Franchise Ballchasing Groups", color=discord.Color.green())
        for team_role in ordered_roles:
            group_code = (await self._get_top_level_group(ctx.guild, team_role))[1]
            embed.add_field(name=team_role.name, value="https://ballchasing.com/group/{}".format(group_code), inline=False)
        
        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        
        await ctx.send(embed=embed)

    @commands.command(aliases=['bcr', 'bcpull'])
    @commands.guild_only()
    async def bcreport(self, ctx, opposing_team, match_day=None):
        """Finds match games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """
        member = ctx.message.author
        try:
            team_role = (await self._get_member_team_roles(ctx.guild, member))[0]
        except:
            return await ctx.send(":x: You are not rostered to a team in this server.")
        team_name = self._get_team_name(team_role)

        # Get team/tier information
        if not match_day:
            match_day = await self._get_match_day(ctx.guild)
        emoji_url = ctx.guild.icon_url

        opposing_team = opposing_team.title() if opposing_team.upper() != opposing_team else opposing_team
        embed = discord.Embed(
            title="Match Day {}: {} vs {}".format(match_day, team_name, opposing_team),
            description="Searching https://ballchasing.com for publicly uploaded replays of this match...",
            color=team_role.color
        )
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        bc_status_msg = await ctx.send(embed=embed)

        # Find replays from ballchasing
        match = {
            "home": team_name,
            "away": opposing_team,
            "matchDay": match_day,
            "matchDate": datetime.today()
        }

        bc_group_owner = ctx.guild.get_member((await self._get_top_level_group(ctx.guild, team_role))[0])
        auth_token = await self._get_member_bc_token(member)
        if not auth_token:
            auth_token = await self._get_member_bc_token(ctx.guild.get_member(bc_group_owner.id))
        match_reported = await self._check_if_reported(ctx, match['home'], match['matchDay'], auth_token)

        if match_reported:
            summary, code, opposing_team = match_reported
            link = "https://ballchasing.com/group/{}".format(code)
            embed.title = "Match Day {}: {} vs {}".format(match_day, team_name, opposing_team)
            embed.description = "This match has already been reported.\n\n{}\n\nView Here: {}".format(summary, link)
            await bc_status_msg.edit(embed=embed)
            return

        replays_found = await self._find_match_replays(ctx, member, match)

        ## Not found:
        if not replays_found:
            embed.description = ":x: No matching replays found on ballchasing."
            await bc_status_msg.edit(embed=embed)
            return False
        
        ## Found:
        replay_ids, summary, winner = replays_found

        if winner:
            pass
            # TODO: check for team emoji
        
        # Prepare embed edits for score confirmation
        prompt_embed = discord.Embed.from_dict(embed.to_dict())
        prompt_embed.description = "Match summary:\n{}".format(summary)
        prompt_embed.set_thumbnail(url=emoji_url)
        prompt_embed.description += "\n\nPlease react to confirm the score summary for this match."

        success_embed = discord.Embed.from_dict(prompt_embed.to_dict())
        success_embed.description = "Match summary:\n{}".format(summary)
        success_embed.description += "\n\n:signal_strength: Results confirmed. Creating a ballchasing replay group. This may take a few seconds..." # "\U0001F4F6"

        reject_embed = discord.Embed.from_dict(prompt_embed.to_dict())
        reject_embed.description = "Match summary:\n{}".format(summary)
        reject_embed.description += "\n\n:x: Ballchasing upload has been cancelled."
        
        if not await self._embed_react_prompt(ctx, prompt_embed, existing_message=bc_status_msg, success_embed=success_embed, reject_embed=reject_embed):
            return False
        
        # Find or create ballchasing subgroup
        match_subgroup_id = await self._get_replay_destination(ctx, match)
        if not match_subgroup_id:
            return False

        # Download and upload replays
        tmp_replay_files = await self._download_replays(auth_token, replay_ids)
        uploaded_ids = await self._upload_replays(ctx, auth_token, match_subgroup_id, tmp_replay_files)
        # await ctx.send("replays in subgroup: {}".format(", ".join(uploaded_ids)))
        
        renamed = await self._rename_replays(ctx, auth_token, uploaded_ids)

        embed.description = "Match summary:\n{}\n\nView the ballchasing group: https://ballchasing.com/group/{}\n\n:white_check_mark: Done".format(summary, match_subgroup_id)
        # embed.set_thumbnail(url=emoji_url)
        await bc_status_msg.edit(embed=embed)

    @commands.command(aliases=['getmatch'])
    @commands.guild_only()
    async def getMatch(self, ctx, match_day=None, *, team_name=None):
        """Gets the ballchasing group for a given team and match day.
        
        Default Team: (Your team)
        Default Match Day: Current
        """
        if match_day == 'last':
            match_day = str(int(await self._get_match_day(ctx.guild)) - 1)

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

        team_name = self._get_team_name(team_role)
        
        embed = discord.Embed(
            title="Match Day {}: {} vs ...".format(match_day, team_name),
            description="_Finding Group for the {} from match day {}..._".format(team_name, match_day),
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
        match_reported = await self._check_if_reported(ctx, team_name, match_day, auth_token)

        if not match_reported:
            embed.description = ":x: This match was never reported."
            return await output_msg.edit(embed=embed)

        summary, code, opposing_team = match_reported
        link = "https://ballchasing.com/group/{}".format(code)
        embed.title = "Match Day {}: {} vs {}".format(match_day, team_name, opposing_team)
        embed.description = "{}\n\n[Click here to view this group!]({})".format(summary, link)
        await output_msg.edit(embed=embed)

    @commands.command(aliases=['mds', 'matchResultSummary', 'mrs'])
    @commands.guild_only()
    async def matchDaySummary(self, ctx, match_day=None, team=None):
        """Returns Franchise performance for the current, or provided match day"""
        await self._match_day_summary(ctx, match_day)
    
    @commands.command()
    @commands.guild_only()
    async def tmds(self, ctx, match_day=None):
        """Returns Franchise performance for the current, or provided match day"""
        # try:
        #     thread.start_new_thread(await self._match_day_summary, (ctx, match_day))
        # except:
        #     await ctx.send(":x: An error occured while running this command.")
        #     await self._match_day_summary(ctx, match_day)
    
    @commands.command(aliases=['gsp', 'getSeasonResults', 'gsr'])
    @commands.guild_only()
    async def getSeasonPerformance(self, ctx, *, team_name=None):
        """Returns the season performance for the given team (invoker's team by default)"""
        member = ctx.message.author
        team_roles = await self._get_team_roles(ctx.guild)
        team_role = None
        if team_name:
            for role in team_roles:
                if team_name.lower() == role.name.lower() or (team_name.lower() in ' '.join(role.name.split()[:-1]).lower()) or (len(role.name.split()) > 1 and team_name.lower() == (role.name.split()[-1][1:-1]).lower()):
                    team_role = role
        else:
            for role in team_roles:
                if role in member.roles:
                    team_role = role
                    break
        if not team_role:
            return await ctx.send(":x: Team not found.")
        team_name = self._get_team_name(team_role)

        embed = discord.Embed(
            title="{} Season Results".format(team_name),
            description="_Finding season results for the {}..._".format(team_name),
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

        ## Get match history
        match_days = []
        opponents = []
        all_results = []
        total_wins = 0
        total_losses = 0

        num_match_days = int(await self._get_match_day(ctx.guild))
        for match_day in range(1, num_match_days+1):
            results = await self._get_team_results(ctx, team_name, match_day, auth_token)
            wins, losses, opponent = results
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
            else:
                all_results.append("{}-{} T".format(wins, losses))
        
        match_days.append("")
        opponents.append("**Total**")
        wp_str = self._get_wp_str(total_wins, total_losses)
        if wp_str:
            all_results.append("**{}-{} ({})**".format(total_wins, total_losses, wp_str))
        else:
            all_results.append("**{}-{}**".format(total_wins, total_losses))
            

        ## ################

        embed = discord.Embed(
            title="{} Season Results".format(team_name),
            color=team_role.color  # self._get_win_percentage_color(total_wins, total_losses)
        )

        bc_link = "https://ballchasing.com/group/{}".format(group_code)
        # embed.add_field(name="MD", value="{}\n".format("\n".join(match_days)), inline=True)
        embed.add_field(name="Opponent", value="{}\n".format("\n".join(opponents)), inline=True)
        embed.add_field(name="Results", value="{}\n".format("\n".join(all_results)), inline=True)
        embed.add_field(name="Ballchasing Group", value=bc_link, inline=False)
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        
        await output_msg.edit(embed=embed)

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
        
        embed = discord.Embed(
            title="{} Roster".format(team_name),
            description='\n'.join([player.mention for player in await self._get_roster(team_role)]),
            color=team_role.color
        )
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        
        await ctx.send(embed=embed)

    @commands.command(aliases=['teams'])
    @commands.guild_only()
    async def listTeams(self, ctx):
        """List all registered teams"""
        member = ctx.message.author
        team_roles = await self._get_team_roles(ctx.guild)
        await ctx.send('Teams: {}'.format(', '.join(role.mention for role in team_roles)))

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def testwp(self, ctx, wins:int, losses:int):
        """Tests WP embed color"""
        color = self._get_win_percentage_color(wins, losses)
        try:
            wp = (wins)/(wins+losses)
        except:
            wp = "N/A"
        description = "**Wins:** {}\n**Losses:** {}\n**WP:** {}".format(wins, losses, wp)
        embed = discord.Embed(title="WP Color Test", description=description, color=color)

        await ctx.send(embed=embed)
    
# ballchasing functions
    def _bc_get_request(self, auth_token, endpoint, params=[]):
        url = 'https://ballchasing.com/api'
        url += endpoint
        # params = [urllib.parse.quote(p) for p in params]
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        # url = urllib.parse.quote_plus(url)
        return requests.get(url, headers={'Authorization': auth_token})

    def _bc_post_request(self, auth_token, endpoint, params=[], json=None, data=None, files=None):
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.post(url, headers={'Authorization': auth_token}, json=json, data=data, files=files)

    def _bc_patch_request(self, auth_token, endpoint, params=[], json=None, data=None):
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.patch(url, headers={'Authorization': auth_token}, json=json, data=data)

# other functions
    async def _match_day_summary(self, ctx, match_day=None):
        # team_roles = await self._get_team_roles(ctx.guild)
        
        if match_day == 'last':
            match_day = str(int(await self._get_match_day(ctx.guild)) - 1)

        if not match_day:
            match_day = await self._get_match_day(ctx.guild)
        
        embed = discord.Embed(
            title="Franchise Results for Match Day {}".format(match_day),
            description="_Finding franchise results for match day {}..._".format(match_day),
            color=self._get_win_percentage_color(0, 0)
        )
        emoji_url = ctx.guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        output_msg = await ctx.send(embed=embed)

        trs = await self._get_team_roles(ctx.guild)
        team_roles = []
        for role in ctx.guild.roles:
            if role in trs:
                team_roles.append(role)
        team_roles.reverse()

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
                auth_token = await self._get_member_bc_token((await self._get_top_level_group(team_role))[0])
            team_name = self._get_team_name(team_role)
            results = await self._get_team_results(ctx, team_name, match_day, auth_token)
            wins, losses, opponent = results
            total_wins += wins 
            total_losses += losses
            
            teams.append(team_name)
            tiers.append(self._get_team_tier(team_role))
            if wins > losses:
                all_results.append("{}-{} W".format(wins, losses))
            elif losses > wins:
                all_results.append("{}-{} L".format(wins, losses))
            else:
                all_results.append("{}-{} T".format(wins, losses))
        
        teams.append("**Franchise**")
        tiers.append("-")
        wp_str = self._get_wp_str(total_wins, total_losses)
        if wp_str:
            all_results.append("**{}-{} ({})**".format(total_wins, total_losses, wp_str))
        else:
            all_results.append("**{}-{}**".format(total_wins, total_losses))

        embed = discord.Embed(
            title="Franchise Results for Match Day {}".format(match_day),
            color=self._get_win_percentage_color(total_wins, total_losses)
        )

        embed.add_field(name="Team", value="{}\n".format("\n".join(teams)), inline=True)
        try:
            embed.add_field(name="Tier", value="{}\n".format("\n".join(tiers)), inline=True)
        except:
            pass
        embed.add_field(name="Results", value="{}\n".format("\n".join(all_results)), inline=True)
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        
        await output_msg.edit(embed=embed)
    
    # TODO: reduce duplicate code with _check_if_reported
    async def _get_team_results(self, ctx, franchise_team, match_day, auth_token):
        guild = ctx.guild
        team_role = await self._get_team_role(guild, franchise_team)
        top_level_group_info = await self._get_top_level_group(guild, team_role)

        r = self._bc_get_request(auth_token, '/groups', params=['group={}'.format(top_level_group_info[1])])
        data = r.json()

        opposing_team = ''
        if 'list' not in data:
            return 0, 0, opposing_team

        match_group_code = ''
        for group in data['list']:
            if '{}'.format(match_day).zfill(2) in group['name']:
                match_group_code = group['id']
                opposing_team = group['name'].split(' vs ')[-1]
                break 

        if not match_group_code:
            return 0, 0, opposing_team

        r = self._bc_get_request(auth_token, '/replays', params=['group={}'.format(match_group_code)])
        data = r.json()
        if 'list' not in data:
            return 0, 0, opposing_team
        
        if not data['list']:
            return 0, 0, opposing_team

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
            return franchise_wins, franchise_losses, opposing_team
        return 0, 0, opposing_team
    
    async def _check_if_blue(self, replay, team_role):
        franchise_team = self._get_team_name(team_role)
        try:
            is_blue = franchise_team.lower() in replay['blue']['name'].lower()
            return is_blue
        except:
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

    async def _check_if_reported(self, ctx, franchise_team, match_day, auth_token):
        guild = ctx.guild
        team_role = await self._get_team_role(guild, franchise_team)
        top_level_group_info = await self._get_top_level_group(guild, team_role)

        r = self._bc_get_request(auth_token, '/groups', params=['group={}'.format(top_level_group_info[1])])
        data = r.json()
        if 'list' not in data:
            return None

        match_group_code = ''
        opposing_team = ''
        for group in data['list']:
            if '{}'.format(match_day).zfill(2) in group['name']:
                match_group_code = group['id']
                opposing_team = group['name'].split(' vs ')[-1]
                break 

        if not match_group_code:
            return None

        r = self._bc_get_request(auth_token, '/replays', params=['group={}'.format(match_group_code)])
        data = r.json()
        if 'list' not in data:
            return None
        
        if not data['list']:
            return None

        franchise_wins = 0
        franchise_losses = 0
        for replay in data['list']:
            is_blue = franchise_team.lower() in replay['blue']['name'].lower()
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
            summary = "**{}** {} - {} **{}**".format(franchise_team, franchise_wins, franchise_losses, opposing_team)
            return summary, match_group_code, opposing_team
        
        return None
     
    async def _find_match_replays(self, ctx, member, match, team_players=None):
        if not team_players:
            team_role = await self._get_team_role(ctx.guild, match['home'])
            team_players = await self._get_roster(team_role)
        # search for appearances in private matches
        endpoint = "/replays"

        zone_adj = '-04:00'
        # date_string = match['matchDate']
        # match_date = datetime.strptime(date_string, '%B %d, %Y').strftime('%Y-%m-%d')
        match_date = match['matchDate']
        start_match_date_rfc3339 = "{}T00:00:00{}".format(match_date - timedelta(days=1), zone_adj)
        end_match_date_rfc3339 = "{}T23:59:59{}".format(match_date, zone_adj)

        params = [
            # 'uploader={}'.format(uploader),
            'playlist=private',
            # 'replay-date-after={}'.format(start_match_date_rfc3339),  # Filters by matches played on this day
            # 'replay-date-before={}'.format(end_match_date_rfc3339),
            'count={}'.format(config.search_count),
            'sort-by={}'.format(config.sort_by),
            'sort-dir={}'.format(config.sort_dir)
        ]

        auth_token = await self._get_member_bc_token(member)

        # Search invoker's replay uploads first
        if member in team_players:
            team_players.remove(member)
            team_players.insert(0, member)
        
        # Search all players in game for replays until match is found
        for player in team_players:
            for steam_id in await self._get_steam_ids(player.id):
                uploaded_by_param='uploader={}'.format(steam_id)
                params.append(uploaded_by_param)
                # await ctx.send('&'.join(params))

                r = self._bc_get_request(auth_token, endpoint, params=params)
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
                            
                            home_goals = replay[home]['goals'] if 'goals' in replay[home] else 0
                            away_goals = replay[away]['goals'] if 'goals' in replay[away] else 0
                            if home_goals > away_goals:
                                home_wins += 1
                            else:
                                away_wins += 1

                    series_summary = "**{home_team}** {home_wins} - {away_wins} **{away_team}**".format(
                        home_team = match['home'],
                        home_wins = home_wins,
                        away_wins = away_wins,
                        away_team = match['away']
                    )
                    winner = None
                    if home_wins > away_wins:
                        winner = match['home']
                    elif home_wins < away_wins:
                        winner = match['away']

                    if replay_ids:
                        return replay_ids, series_summary, winner
        return None
    
    async def _get_roster(self, team_role:discord.Role):
        return team_role.members

    async def _get_all_accounts(self, discord_id):
        discord_id = str(discord_id)
        account_register = await self.account_manager_cog.get_account_register()
        if discord_id in account_register:
            return account_register[discord_id]
        return None

    async def _get_steam_id_from_token(self, auth_token):
        r = self._bc_get_request(auth_token, '')
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
    
    async def _get_member_team_roles(self, guild, member):
        team_roles = await self.config.guild(guild).TeamRoles()
        player_team_roles = []
        for role in member.roles:
            if role.id in team_roles:
                player_team_roles.append(role)
        return player_team_roles
    
    def _get_team_name(self, role):
        if role.name[-1] == ')' and ' (' in role.name:
            return ' '.join((role.name).split()[:-1])
        return role.name
    
    def _get_team_tier(self, role):
        if role.name[-1] == ')' and ' (' in role.name:
            opi = role.name.index('(')+1
            cpi = role.name.index(')')
        return None

    def is_match_replay(self, match, replay_data):
        home_team = match['home']       # match cog
        away_team = match['away']       # match cog

        if not self._is_full_replay(replay_data):
            return False

        replay_teams = self.get_replay_teams(replay_data)

        home_team_found = replay_teams['blue']['name'].lower() in home_team.lower() or replay_teams['orange']['name'].lower() in home_team.lower()
        away_team_found = replay_teams['blue']['name'].lower() in away_team.lower() or replay_teams['orange']['name'].lower() in away_team.lower()

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
    
    async def _get_replay_destination(self, ctx, match):
        team_role = await self._get_team_role(ctx.guild, match['home'])
        top_level_group_info = await self._get_top_level_group(ctx.guild, team_role)
        
        bc_group_owner = ctx.guild.get_member(top_level_group_info[0])
        top_group_code = top_level_group_info[1]
        
        # <top level group>/MD <Match Day> vs <Opposing Team>
        ordered_subgroups = [
            "MD {} vs {}".format(str(match['matchDay']).zfill(2), match['away'].title())
        ]

        auth_token = await self._get_member_bc_token(bc_group_owner)
        bc_group_owner_steam = await self._get_steam_id_from_token(auth_token)
        
        endpoint = '/groups'
        params = [
            # 'creator={}'.format(bc_group_owner_steam),
            'group={}'.format(top_group_code)
        ]

        r = self._bc_get_request(auth_token, endpoint, params=params)
        data = r.json()

        debug = False
        if match['home'] == 'Ocelots':
            pass 
            # debug = True

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

                r = self._bc_get_request(auth_token, endpoint, params)
                data = r.json()

            # ## Creating next sub-group
            else:
                payload = {
                    'name': next_group_name,
                    'parent': current_subgroup_id,
                    'player_identification': config.player_identification,
                    'team_identification': config.team_identification
                }
                r = self._bc_post_request(auth_token, endpoint, json=payload)
                data = r.json()
                try:
                    next_subgroup_id = data['id']
                except:
                    await ctx.send(":x: Error creating Ballchasing group: {}".format(next_group_name))
                    # await ctx.send(data)
                    return False
            
        return next_subgroup_id

    async def _download_replays(self, auth_token, replay_ids):
        tmp_replay_files = []
        this_game = 1
        for replay_id in replay_ids[::-1]:
            endpoint = "/replays/{}/file".format(replay_id)
            r = self._bc_get_request(auth_token, endpoint)
            
            # replay_filename = "Game {}.replay".format(this_game)
            replay_filename = "{}.replay".format(replay_id)
            
            tf = tempfile.NamedTemporaryFile()
            tf.name += ".replay"
            tf.write(r.content)
            tmp_replay_files.append(tf)
            this_game += 1

        return tmp_replay_files
    
    async def _upload_replays(self, ctx, auth_token, subgroup_id, files_to_upload):
        endpoint = "/v2/upload"
        params = [
            'visibility={}'.format(config.visibility),
            'group={}'.format(subgroup_id)
        ]

        replay_ids_in_group = []
        for replay_file in files_to_upload:
            replay_file.seek(0)
            files = {'file': replay_file}

            r = self._bc_post_request(auth_token, endpoint, params=params, files=files)
        
            status_code = r.status_code
            data = r.json()

            try:
                if status_code == 201:
                    replay_ids_in_group.append(data['id'])
                elif status_code == 409:
                    payload = {
                        'group': subgroup_id
                    }
                    r = self._bc_patch_request(auth_token, '/replays/{}'.format(data['id']), json=payload)
                    if r.status_code == 204:
                        replay_ids_in_group.append(data['id'])
                    else:
                        await ctx.send(":x: {} error: {}".format(r.status_code, r.json()['error']))
            except:
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
            r = self._bc_patch_request(auth_token, endpoint, json=payload)
            status_code = r.status_code

            if status_code == 204:
                renamed.append(replay_id)            
            else:
                await ctx.send(":x: {} error.".format(status_code))

            game_number += 1
        return renamed
    
    async def _get_team_role(self, guild, team_name):
        team_roles = await self._get_team_roles(guild)
        for role in team_roles:
            if team_name in role.name:
                return role
        return None
    
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

    def _get_win_percentage_color(self, wins:int, losses:int):
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
            #sub_wp = ((wp-50)/50)*100
            wp_adj = (wp-0.5)/0.5
            green_scale = 255
            red_scale = 255 - round(255*wp_adj)
            return discord.Color.from_rgb(red_scale, green_scale, blue_scale)

# json dict
    async def _get_match_day(self, guild):
        return await self.config.guild(guild).MatchDay()
    
    async def _save_match_day(self, guild, match_day):
        await self.config.guild(guild).MatchDay.set(match_day)

    async def _get_team_roles(self, guild):
        team_role_ids = await self.config.guild(guild).TeamRoles()
        return [guild.get_role(role_id) for role_id in team_role_ids]
    
    async def _save_season_group(self, guild, team_role, captain, group_code):
        groups = await self.config.guild(guild).ReplayGroups()
        groups[str(team_role.id)] = [captain.id, group_code]
        await self._save_top_level_groups(guild, groups)

    async def _get_top_level_group(self, guild, team_role):
        try:
            return (await self.config.guild(guild).ReplayGroups())[str(team_role.id)]
        except:
            return None 
        
    async def _save_top_level_groups(self, guild, groups):
        await self.config.guild(guild).ReplayGroups.set(groups)
    
    async def _save_team_roles(self, guild, roles):
        await self.config.guild(guild).TeamRoles.set(roles)

    async def _get_member_bc_token(self, member: discord.Member):
        try:
            return (await self.config.BCTokens())[str(member.id)]
        except:
            try:
                return (await self.config.BCTokens())[member.id]
            except:
                return None
    
    async def _save_member_bc_token(self, member: discord.Member, token):
        tokens = await self.config.BCTokens()
        tokens[str(member.id)] = token
        await self.config.BCTokens.set(tokens)
    