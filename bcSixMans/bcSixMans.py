from .config import config
import requests
from datetime import datetime, timezone
import os
import json
import discord
import asyncio

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

import sys
import pprint as pp

defaults =   {"AuthToken": None, "TopLevelGroup": None, "AccountRegister": {}}
verify_timeout = 30

class BCSixMans(commands.Cog):
    """Manages aspects of Ballchasing Integrations with RSC"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.six_mans_cog = bot.get_cog("SixMans")
    

    # TODO: UPDATE TO FIND RECENT GAMES FROM MATCHUP
    @commands.command(aliases=['sr'])
    @commands.guild_only()
    async def scoreReport(self, ctx, winning_team: str):
        """Finds match games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """
        member = ctx.message.author
        game, six_mans_queue = await self.six_mans_cog._get_info(ctx)
        if game is None or six_mans_queue is None or not winning_team.lower() in ['blue', 'orange'] or not await self._get_top_level_group(ctx):
            return False

        replays_found = await self._find_series_replays(ctx, game, winning_team)

        if not replays_found:
            await ctx.send(":x: No matching replays found.")
            return False

        match_subgroup_id = await self._get_replay_destination(ctx, six_mans_queue, game)
        # await ctx.send("Match Subgroup ID: {}".format(match_subgroup_id))

        replay_ids, summary = replays_found
        # await ctx.send("Matching Ballchasing Replay IDs ({}): {}".format(len(replay_ids), ", ".join(replay_ids)))
        
        tmp_replay_files = await self._download_replays(ctx, replay_ids)
        # await ctx.send("Temp replay files to upload ({}): {}".format(len(tmp_replay_files), ", ".join(tmp_replay_files)))
        
        uploaded_ids = await self._upload_replays(ctx, match_subgroup_id, tmp_replay_files)
        # await ctx.send("replays in subgroup: {}".format(", ".join(uploaded_ids)))
        
        renamed = await self._rename_replays(ctx, uploaded_ids)
        # await ctx.send("replays renamed: {}".format(renamed))
        self._delete_temp_files(tmp_replay_files)
        
        message = ':white_check_mark: {}\n\nReplays added to ballchasing subgroup: <https://ballchasing.com/group/{}>'.format(summary, subgroup_id)
        await ctx.send(message)

    @commands.command(aliases=['setAuthKey'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Ballchasing API requests.
        Note: Auth Token must be generated from the Ballchasing group owner
        """
        token_set = await self._save_auth_token(ctx, auth_token)
        if(token_set):
            await ctx.send("Done.")
        else:
            await ctx.send(":x: Error setting auth token.")

    @commands.command(aliases=["sbcg"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setBCGroup(self, ctx, top_level_group):
        """Sets the Top Level Ballchasing Replay group for saving match replays.
        Note: Auth Token must be generated from the Ballchasing group owner
        """
        group_set = await self._save_top_level_group(ctx, top_level_group)
        if(group_set):
            await ctx.send("Done.")
        else:
            await ctx.send(":x: Error setting top level group.")

    @commands.command(aliases=['accountRegister', 'addAccount'])
    @commands.guild_only()
    async def registerAccount(self, ctx, platform, identifier=None):
        """Allows user to register account for ballchasing requests. This may be found by searching your appearances on ballchasing.com

        Examples:
            [p]registerAccount steam 76561199096013422
            [p]registerAccount xbox e4b17b0000000900
            [p]registerAccount ps4 touchetupac2
            [p]registerAccount epic 76edd61bd58841028a8ee27373ae307a
            [p]registerAccount steam
        """

        # Check platform
        if platform.lower() not in ['steam', 'xbox', 'ps4', 'ps5', 'epic']:
            await ctx.send(":x: \"{}\" is an invalid platform".format(platform))
            return False
        
        member = ctx.message.author
        if not identifier:
            if platform.lower() in ['ps4', 'ps5']:
                await ctx.send(":x: Discord does not support linking to **{}** accounts. Auto-detection failed.".format(platform))
                return False

            identifier = await self._auto_link_account(ctx, member, platform)

        # Validate account -- check for public ballchasing appearances
        valid_account = await self._validate_account(ctx, platform, identifier)
        if valid_account:
            username, appearances = valid_account
        else:
            await ctx.send(":x: No ballchasing replays found for user: {identifier} ({platform}) ".format(identifier=identifier, platform=platform))
            return False

        # React to confirm account registration
        prompt = "**{username}** ({platform}) appears in **{count}** ballchasing replays.".format(username=username, platform=platform, count=appearances)
        prompt += "\n\nWould you like to register this account?"
        nvm_message = "Registration cancelled."
        if not await self._react_prompt(ctx, prompt, nvm_message):
            return False
        
        account_register = await self._get_account_register(ctx)
        if member.id in account_register:
            account_register[member.id].append([platform, identifier])
        else:
            account_register[member.id] = [[platform, identifier]]
        
        # Register account
        if await self._save_account_register(ctx, account_register):
            await ctx.send("Done")

    @commands.command(aliases=['rmaccount'])
    @commands.guild_only()
    async def unregisterAccount(self, ctx, platform, identifier=None):
        remove_accs = []
        account_register = await self._get_account_register(ctx)
        if member.id in account_register:
            for account in account_register[member.id]:
                if account[0] == platform:
                    if not identifier or account[1] == identifier:
                        remove_accs.append(account)
        
        if not remove_accs:
            await ctx.send(":x: No matching account has been found.")
            return False
        
        prompt = "React to confirm removal of the following accounts:\n - " + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in remove_accs)
        if not await self._react_prompt(ctx, prompt, "No accounts have been removed."):
            return False
        
        count = 0
        for acc in remove_accs:
            account_register[member.id].remove(acc)
            count += 1
        
        await self._save_account_register(ctx, account_register)
        await ctx.send(":white_check_mark: Removed **{}** accounts.".format(count))

    @commands.command(aliases=['rmaccounts', 'clearaccounts', 'clearAccounts'])
    @commands.guild_only()
    async def unregisterAccounts(self, ctx):
        """Unlinks registered account for ballchasing requests."""
        account_register = await self._get_account_register(ctx)
        if ctx.message.author.id in account_register:
            count = len(account_register[ctx.message.author.id])
            del account_register[ctx.message.author.id]
            await ctx.send(":white_check_mark: Removed **{}** accounts.".format(count))
        else:
            await ctx.send("No account found.")

    @commands.command(aliases=['bcGroup', 'ballchasingGroup', 'bcg'])
    @commands.guild_only()
    async def bcgroup(self, ctx):
        """Get the top-level ballchasing group to see all season match replays."""
        group_code = await self._get_top_level_group(ctx)
        url = "https://ballchasing.com/group/{}".format(group_code)
        await ctx.send("See all season replays in the top level ballchasing group: {}".format())


    async def _bc_get_request(self, ctx, endpoint, params=[], auth_token=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx)
        
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.get(url, headers={'Authorization': auth_token})

    async def _bc_post_request(self, ctx, endpoint, params=[], auth_token=None, json=None, data=None, files=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx)
        
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.post(url, headers={'Authorization': auth_token}, json=json, data=data, files=files)

    async def _bc_patch_request(self, ctx, endpoint, params=[], auth_token=None, json=None, data=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx)

        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.patch(url, headers={'Authorization': auth_token}, json=json, data=data)

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

    async def _auto_link_account(self, member, platform):
        # {"type": "twitch", "id": "92473777", "name": "discordapp"}
        for account in await member.profile().connected_accounts:
                if account['type'] == platform:
                    return account['id']
        return None

    async def _validate_account(self, ctx, platform, identifier):
        auth_token = config.auth_token
        endpoint = '/replays'
        params = [
            'player-id={platform}:{identifier}'.format(platform=platform, identifier=identifier),
            'count=1'
        ]
        r = await self._bc_get_request(ctx, endpoint, params)
        data = r.json()

        appearances = 0
        username = None
        if data['list']:
            for team_color in ['blue', 'orange']:
                for player in data['list'][0][team_color]['players']:
                    if player['id']['platform'] == platform and player['id']['id'] == identifier:
                        username = player['name']
                        appearances = data['count']
                        break
        if username:
            return username, appearances
        return False

    async def _get_steam_id_from_token(self, ctx, auth_token=None):
        if not auth_token:
            auth_token = await self._get_auth_token(ctx)
        r = await self._bc_get_request(ctx, "")
        if r.status_code == 200:
            return r.json()['steam_id']
        return None

    def get_player_id(discord_id):
        arr = config.account_register[discord_id]
        player_id = "{}:{}".format(arr[0], arr[1])
        return player_id

    async def _get_steam_ids(self, ctx, discord_id):
        steam_accounts = []
        account_register = await self._get_account_register(ctx)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                if account[0] == 'steam':
                    steam_accounts.append(account[1])
        return steam_accounts

    def _is_full_replay(self, replay_data):
        if replay_data['duration'] < 300:
            return False
        if replay_data['blue']['goals'] == replay_data['orange']['goals']:
            return False
        for team in ['blue', 'orange']:
            for players in replay_data[team]:
                if player['start_time'] == 0:
                    return True
        return False

    def _get_account_team(self, platform, plat_id, replay_data):
        for team in ['blue', 'orange']:
            for player in replay_data['players']:
                if player['id']['platform'] == platform and player['id']['id'] == plat_id:
                    return team
        return None

    def _is_six_mans_replay(self, ctx, uploader, sm_game, replay_data, use_account=None):
        """searches for the uploader's appearance in the replay under any registered account"""
        if use_account:
            account_register = {uploader.id: [account]}
        else:
            account_register = await self._get_account_register(ctx)
        
        # which team is the uploader supposed to be on
        if uploader in sm_game.blue:
            uploader_team = 'blue'
        elif uploader in sm_game.orange:
            uploader_team = 'orange'
        else:
            return None

        # swap_teams covers the scenario where the teams join incorrectly, assumes group is correct (applies to score summary only)
        swap_teams = False
        for account in account_register[uploader.id]:
            account_replay_team = self._get_account_team(platform, plat_id, replay_data)
            if not account_replay_team:
                break
            if account_team != account_replay_team:
                swap_teams = True

        # don't count incomplete replays
        if not _is_full_replay(replay_data):
            return False

        # determine winner
        if replay_data['blue']['goals'] > replay_data['orange']['goals']:
            winner = 'blue'
        else:
            winner = 'orange'
        
        # swap teams if necessary
        if swap_teams:
            if winner == 'orange':
                winner = 'blue'
            elif winner = 'blue':
                winner = 'orange'

        return winner

    async def _get_replay_destination(self, ctx, queue, game, top_level_group=None, group_owner_discord_id=None):
        
        auth_token = await self._get_auth_token(ctx)

        # needs both to override default -- TODO: Remove non-match params (derive logically)
        if not group_owner_discord_id or not top_level_group:
            bc_group_owner = await self._get_steam_id_from_token(ctx, auth_token)
            top_level_group = await self._get_top_level_group(ctx)

        # /<top level group>/<queue name>/<game id>
        game_id = game.id
        blue_players = game.blue 
        oran_players = game.orange
        queue_name = next(queue.name for queue in self.queues if queue.id == six_mans_queue.id)

        ordered_subgroups = [
            queue_name,
            game_id
        ]

        endpoint = '/groups'
        
        params = [
            # 'player-id={}'.format(bcc_acc_rsc),
            'creator={}'.format(bc_group_owner),
            'group={}'.format(top_level_group)
        ]

        r = await self._bc_get_request(ctx, endpoint, params, auth_token)
        data = r.json()

        # Dynamically create sub-group
        current_subgroup_id = top_level_group
        next_subgroup_id = None
        for next_group_name in ordered_subgroups:
            if next_subgroup_id:
                current_subgroup_id = next_subgroup_id
            next_subgroup_id = None 

            # Check if next subgroup exists
            if 'list' in data:
                for data_subgroup in data['list']:
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

                r = await self._bc_get_request(ctx, endpoint, params, auth_token)
                data = r.json()

            # ## Creating next sub-group
            else:
                payload = {
                    'name': next_group_name,
                    'parent': current_subgroup_id,
                    'player_identification': config.player_identification,
                    'team_identification': config.team_identification
                }
                r = await self._bc_post_request(ctx, endpoint, auth_token=auth_token, json=payload)
                data = r.json()
                
                try:
                    next_subgroup_id = data['id']
                except:
                    await ctx.send(":x: Error creating Ballchasing group: {}".format(next_group_name))
                    return False
            
        return next_subgroup_id

    async def _find_series_replays(self, ctx, game, winner):
        if not uploader:
            # Return empty for now TODO: Check for opponent steam
            await ctx.send(":x: No steam account linked to ballchasing.com")
            return []

        # search for appearances in private matches
        endpoint = "/replays"
        sort = 'replay-date' # 'created
        sort_dir = 'asc'
        count = 7
        queue_pop_time = ctx.channel.created_at.astimezone().isoformat()
        auth_token = await self._get_auth_token(ctx)
        
        players = []
        for player in game.blue:
            players.append(player)
        for player in game.orange:
            players.append(player)

        for player in players:
            for steam_id in await self._get_steam_ids(ctx, player.id):
                if found:
                    break
                params = [
                    'uploader={}'.format(steam_id),
                    'playlist=private',
                    'replay-date-after={}'.format(queue_pop_time),
                    'count={}'.format(count),
                    'sort-by={}'.format(sort),
                    'sort-dir={}'.format(sort_dir)
                ]

                r = await self._bc_get_request(ctx, endpoint, params=params, auth_token=auth_token)
                data = r.json()

                # checks for correct replays
                oran_wins = 0
                blue_wins = 0
                replay_ids = []
                for replay in data['list']:
                    winner = self._is_six_mans_replay(ctx, player, game, replay)
                    if winner == 'blue':
                        blue_wins += 1
                    else:
                        oran_wins += 1

                series_summary = "****Blue** {blue_wins} - {oran_wins} **Orange**".format(
                    blue_wins = blue_wins, oran_wins = oran_wins
                )

                return replay_ids, series_summary

        message = "No replay files could be found on ballchasing. Please use `[p]accountRegister` to make sure "
        message += "auto-uploaded replays can be automatically added to a Six Mans ballchasing replay group."
        await ctx.send(message)
            
        return None

    async def _download_replays(self, ctx, replay_ids):
        auth_token = await self._get_auth_token(ctx)
        tmp_replay_files = []
        this_game = 1
        for replay_id in replay_ids[::-1]:
            endpoint = "/replays/{}/file".format(replay_id)
            r = await self._bc_get_request(ctx, endpoint, auth_token=auth_token)

            if not os.path.exists("temp/"):
                os.mkdir("temp") # Make temp folder
            
            # replay_filename = "Game {}.replay".format(this_game)
            replay_filename = "{}.replay".format(replay_id)
            f = open("temp/{}".format(replay_filename), "wb")
            f.write(r.content)
            f.close()
            tmp_replay_files.append(replay_filename)
            this_game += 1

        return tmp_replay_files

    async def _upload_replays(self, ctx, subgroup_id, files_to_upload):
        endpoint = "/v2/upload"
        params = [
            'visibility={}'.format(config.visibility),
            'group={}'.format(subgroup_id)
        ]
        auth_token = await self._get_auth_token(ctx)

        replay_ids_in_group = []
        for replay_file_name in files_to_upload:
            files = {'file': open("temp/{}".format(replay_file_name), 'rb')}

            r = await self._bc_post_request(ctx, endpoint, params, auth_token=auth_token, files=files)
        
            status_code = r.status_code
            data = r.json()

            try:
                if status_code == 201 or status_code == 409:
                    replay_ids_in_group.append(data['id'])
            except:
                await ctx.send(":x: {} error: {}".format(status_code, data['error']))
        
        return replay_ids_in_group
        
    async def _rename_replays(self, ctx, uploaded_replays_ids):
        auth_token = await self._get_auth_token(ctx)
        renamed = []

        game_number = 1
        for replay_id in uploaded_replays_ids:
            endpoint = '/replays/{}'.format(replay_id)
            payload = {
                'title': 'Game {}'.format(game_number)
            }
            r = await self._bc_patch_request(ctx, endpoint, auth_token=auth_token, json=payload)  # data=json.dumps(payload))
            status_code = r.status_code

            if status_code == 204:
                renamed.append(replay_id)            
            else:
                await ctx.send(":x: {} error.".format(status_code))

            game_number += 1
        return renamed

    def _delete_temp_files(self, files_to_upload):
        for replay_filename in files_to_upload:
            if os.path.exists("temp/{}".format(replay_filename)):
                os.remove("temp/{}".format(replay_filename))
        try:
            os.rmdir("temp") # Remove Temp Folder
        except OSError:
            print("Can't remove populated folder.")
            return False
        except:
            print("Uncaught error in delete_temp_files.")
            return False
        return True

    async def _get_auth_token(self, ctx):
        return await self.config.guild(ctx.guild).AuthToken()
    
    async def _save_auth_token(self, ctx, token):
        await self.config.guild(ctx.guild).AuthToken.set(token)
        return True

    async def _get_top_level_group(self, ctx):
        return await self.config.guild(ctx.guild).TopLevelGroup()
    
    async def _save_top_level_group(self, ctx, group_id):
        await self.config.guild(ctx.guild).TopLevelGroup.set(group_id)
        return True
    
    async def _get_account_register(self, ctx):
        return await self.config.guild(ctx.guild).AccountRegister()
    
    async def _save_account_register(self, ctx, account_register):
        await self.config.guild(ctx.guild).AccountRegister.set(account_register)
        return True
