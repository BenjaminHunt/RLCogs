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
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.six_mans_cog = bot.get_cog("SixMans")
    

    @commands.command()
    @commands.guild_only()
    async def g(self, ctx, member: discord.Member=None):
        member = ctx.message.author
        # self.six_mans_cog = self.bot.get_cog("SixMans")
        game = None
        for g in self.six_mans_cog.games:
            if g.textChannel == ctx.channel:
                game = g

        qpt = ctx.channel.created_at.astimezone().isoformat()
        # qpt = qpt[0:19] + qpt[-6:]
        # qpt_cmp = "2021-03-02T01:19:00.272000-05:00"
        qpt_cmp = "2021-03-07T09:54:06.356000+01:00"
        await ctx.send("qpt: `{}`".format(qpt))
        await ctx.send("cmp: `{}`".format(qpt_cmp))
        auth_token = await self._get_auth_token(ctx)
        
        if member:
            accounts = await self._get_steam_ids(ctx, member.id)
            for steam_id in accounts:
                params = [
                    'uploader={}'.format(steam_id),
                    'playlist=private',
                    'replay-date-after={}'.format(qpt_cmp),
                    'count={}'.format(5),
                    # 'sort-by={}'.format(sort),
                    # 'sort-dir={}'.format(sort_dir)
                ]

                r = await self._bc_get_request(ctx, '/replays', params=params, auth_token=auth_token)
                data = r.json()
                if 'list' in data:
                    await ctx.send("{} - {} | Request Code: {} ({} found)".format(member.name, steam_id[-3:], r.status_code, len(data['list'])))
                else:
                    await ctx.send("{} - {} | Request Code: {} => {}".format(member.name, steam_id[-3:], r.status_code, data['error']))
            if not accounts:
               await ctx.send("No accounts found")

    # TODO: automatically run when score reported -- allow to  coexist with the auto-replay-uploader
    @commands.command(aliases=['ggs', 'gg'])
    @commands.guild_only()
    async def gameOver(self, ctx, winning_team: str=None):
        """Finds match games from recent public uploads, and adds them to the correct Ballchasing subgroup
        """
        # Find Six Mans Game, Queue
        member = ctx.message.author
        self.six_mans_cog = self.bot.get_cog("SixMans")
        game = None
        for g in self.six_mans_cog.games:
            await ctx.send(g.id)
            if member in g.blue or member in g.orange or g.textChannel == ctx.message.channel:
                game = g
                await ctx.send("game found: {}".format(game.id))
                break
        
        if len(self.six_mans_cog.games) == 0:
            await ctx.send("no ongoing games")

        if not game:
            await ctx.send("game not found.")
            return False

        six_mans_queue = None
        for q in self.six_mans_cog.queues:
            if game.queueId == q.id:
                six_mans_queue = q
                await ctx.send("queue found: {}".format(six_mans_queue.id))
                break
        
        if not six_mans_queue:
            await ctx.send("queue not found.")
            return False

        if not await self._get_top_level_group(ctx):
            await ctx.send('ballchasing group group not found.')
            return False

        # Find Series replays
        replays_found = await self._find_series_replays(ctx, game, winning_team)

        if not replays_found:
            await ctx.send(":x: No matching replays found.")
            return False

        series_subgroup_id = await self._get_replay_destination(ctx, six_mans_queue, game)
        # await ctx.send("Match Subgroup ID: {}".format(series_subgroup_id))
        if not series_subgroup_id:
            return await ctx.send(":x: series_subgroup_id not found.")

        replay_ids, summary = replays_found
        # await ctx.send("Matching Ballchasing Replay IDs ({}): {}".format(len(replay_ids), ", ".join(replay_ids)))
        
        tmp_replay_files = await self._download_replays(ctx, replay_ids)
        # await ctx.send("Temp replay files to upload ({}): {}".format(len(tmp_replay_files), ", ".join(tmp_replay_files)))
        
        uploaded_ids = await self._upload_replays(ctx, series_subgroup_id, tmp_replay_files)
        # await ctx.send("replays in subgroup: {}".format(", ".join(uploaded_ids)))
        
        renamed = await self._rename_replays(ctx, uploaded_ids)
        # await ctx.send("replays renamed: {}".format(renamed))
        self._delete_temp_files(tmp_replay_files)
        
        message = ':white_check_mark: {}\n\nReplays added to ballchasing subgroup: <https://ballchasing.com/group/{}>'.format(summary, series_subgroup_id)
        await ctx.send(message)

    @commands.command(aliases=['smb'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def findSixMansBot(self, ctx):
        qs = self.six_mans_cog.queues
        if qs:
            # await ctx.send("Six Mans Queues ({}): **{}**".format(len(qs), ", ".join(q.name for q in qs)))
            for q in qs:
                await ctx.send(q.name)
        else:
            await ctx.send("qs not found.")

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

    @commands.command(aliases=["sbcg", "setTopLevelGroup"])
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
    
    @commands.command(aliases=['bcGroup', 'ballchasingGroup', 'bcg', 'getBCGroup'])
    @commands.guild_only()
    async def bcgroup(self, ctx):
        """Get the top-level ballchasing group to see all season match replays."""
        group_code = await self._get_top_level_group(ctx)
        url = "https://ballchasing.com/group/{}".format(group_code)
        await ctx.send("See all season replays in the top level ballchasing group: {}".format(url))

    @commands.command(aliases=['bcpage', 'mybcpage', 'bcp', 'getBCPage', 'ballchasingpage', 'bcpages'])
    @commands.guild_only()
    async def bcPage(self, ctx):
        """Get the ballchasing pages for registered accounts"""
        group_code = await self._get_top_level_group(ctx)
        member = ctx.message.author
        lines = []
        for acc in await self._get_all_accounts(ctx, member):
            lines.append("<https://ballchasing.com/player/{}/{}>".format(acc[0], acc[1]))
        show_accounts = "**{}**, has registered the following accounts:\n - ".format(member.name) + "\n - ".join(lines)
        await ctx.send(show_accounts)

    @commands.command(aliases=['registeraccount', 'accountregister', 'accountRegister', 'addAccount', 'addaccount', 'addacc'])
    @commands.guild_only()
    async def registerAccount(self, ctx, platform:str, identifier:str):
        """Allows user to register account for ballchasing requests. This may be found by searching your appearances on ballchasing.com

        Examples:
            [p]registerAccount steam 76561199096013422
            [p]registerAccount xbox e4b17b0000000900
            [p]registerAccount ps4 touchetupac2
            [p]registerAccount epic 76edd61bd58841028a8ee27373ae307a
            [p]registerAccount steam
        """
        # Check platform
        platform = platform.lower()
        if platform not in ['steam', 'xbox', 'ps4', 'ps5', 'epic']:
            await ctx.send(":x: \"{}\" is an invalid platform".format(platform))
            return False
        

        member = ctx.message.author
        # Profile can't be seen from bots :/
        # if not identifier:
        #     return 
        #     if platform.lower() in ['ps4', 'ps5']:
        #         await ctx.send(":x: Discord does not support linking to **{}** accounts. Auto-detection failed.".format(platform))
        #         return False

        #     identifier = await self._auto_link_account(member, platform)

        # Validate account -- check for public ballchasing appearances
        valid_account = await self._validate_account(ctx, platform, identifier)

        if valid_account:
            username, appearances = valid_account
        else:
            await ctx.send(":x: No ballchasing replays found for user: {identifier} ({platform}) ".format(identifier=identifier, platform=platform))
            return False

        account_register = await self._get_account_register(ctx)
        
        # Make sure not a repeat account
        if str(member.id) in account_register and [platform, identifier] in account_register[str(member.id)]:
            await ctx.send("{}, you have already registered this account.".format(member.mention))
            return False

        # React to confirm account registration
        prompt = "**{username}** ({platform}) appears in **{count}** ballchasing replays.".format(username=username, platform=platform, count=appearances)
        prompt += "\n\nWould you like to register this account?"
        nvm_message = "Registration cancelled."
        if not await self._react_prompt(ctx, prompt, nvm_message):
            return False
            
        if str(member.id) in account_register:
            account_register[str(member.id)].append([platform, identifier])
        else:
            account_register[str(member.id)] = [[platform, identifier]]
        
        # Register account
        if await self._save_account_register(ctx, account_register):
            await ctx.send("Done")

    @commands.command(aliases=['rmaccount', 'removeAccount'])
    @commands.guild_only()
    async def unregisterAccount(self, ctx, platform, identifier=None):
        remove_accs = []
        account_register = await self._get_account_register(ctx)
        member = ctx.message.author
        if str(member.id) in account_register:
            for account in account_register[str(member.id)]:
                if account[0] == platform:
                    if not identifier or account[1] == identifier:
                        remove_accs.append(account)
        
        if not remove_accs:
            await ctx.send(":x: No matching account has been found.")
            return False
        
        prompt = "React to confirm removal of the following account(s):\n - " + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in remove_accs)
        if not await self._react_prompt(ctx, prompt, "No accounts have been removed."):
            return False
        
        count = 0
        for acc in remove_accs:
            account_register[str(member.id)].remove(acc)
            count += 1
        
        await self._save_account_register(ctx, account_register)
        await ctx.send(":white_check_mark: Removed **{}** account(s).".format(count))

    @commands.command(aliases=['rmaccounts', 'clearaccounts', 'clearAccounts'])
    @commands.guild_only()
    async def unregisterAccounts(self, ctx):
        """Unlinks registered account for ballchasing requests."""
        account_register = await self._get_account_register(ctx)
        discord_id = str(ctx.message.author.id)
        if discord_id in account_register:
            count = len(account_register[discord_id])
            accounts = await self._get_all_accounts(ctx, ctx.message.author)
            prompt = "React to confirm removal of the following accounts ({}):\n - ".format(len(accounts)) + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in accounts)
            if not await self._react_prompt(ctx, prompt, "No accounts have been removed."):
                return False
            
            del account_register[discord_id]
            await ctx.send(":white_check_mark: Removed **{}** account(s).".format(count))
        else:
            await ctx.send("No account found.")

    @commands.command(aliases=['accs', 'myAccounts', 'registeredAccounts'])
    @commands.guild_only()
    async def accounts(self, ctx):
        """view all accounts that have been registered to with your discord account in this guild."""
        member = ctx.message.author
        accounts = await self._get_all_accounts(ctx, member)
        if not accounts:
            await ctx.send("{}, you have not registered any accounts.".format(member.mention))
            return

        show_accounts = "{}, you have registered the following accounts:\n - ".format(member.mention) + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in accounts)
        await ctx.send(show_accounts)

    @commands.command(aliases=['getAccounts', 'getRegisteredAccounts', 'getAccountsRegistered', 'viewAccounts', 'showAccounts'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def memberAccounts(self, ctx, member: discord.Member):
        """view all accounts that have been registered to with your discord account in this guild."""
        accounts = await self._get_all_accounts(ctx, member)
        if not accounts:
            await ctx.send("**{}**, has not registered any accounts.".format(member.name))
            return

        show_accounts = "**{}**, has registered the following accounts:\n - ".format(member.name) + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in accounts)
        await ctx.send(show_accounts)

    @commands.command(aliases=['allaccs', 'allaccounts'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getAllAccounts(self, ctx):
        """lists all accounts registered for troubleshooting purposes"""
        account_register = await self._get_account_register(ctx)
        if not account_register:
            return await ctx.send("No accounts have been registered.")
        output = "All Accounts:\n"
        member_lines = "discord id:         platform - id"
        for member, accs in account_register.items():
            for acc in accs:
                member_lines += "\n{}: {} - {}".format(member, acc[0], acc[1])
                if len(member_lines) > 1800:
                    await ctx.send(output + "\n```{}```".format(member_lines))
                    output = ""
                    members = ""
        await ctx.send(output + "```\n{}\n```".format(member_lines))


    async def _get_all_accounts(self, ctx, member=None):
        if not member:
            member = ctx.message.author
        accs = []
        account_register = await self._get_account_register(ctx)
        discord_id = str(member.id)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                accs.append(account)
        return accs

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

    async def _validate_account(self, ctx, platform, identifier):
        # auth_token = config.auth_token
        auth_token = await self._get_auth_token(ctx)
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

    async def _get_steam_ids(self, ctx, discord_id):
        discord_id = str(discord_id)
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

    def _get_account_replay_team(self, platform, plat_id, replay_data):
        for team in ['blue', 'orange']:
            for player in replay_data['players']:
                if player['id']['platform'] == platform and player['id']['id'] == plat_id:
                    return team
        return None

    async def _is_six_mans_replay(self, ctx, uploader, sm_game, replay_data, use_account=None):
        """searches for the uploader's appearance in the replay under any registered account"""
        if use_account:
            account_register = {uploader.id: [account]}
        else:
            account_register = await self._get_account_register(ctx)
        
        # which team is the uploader supposed to be on
        if uploader in sm_game.blue:
            uploader_sm_team = 'blue'
        elif uploader in sm_game.orange:
            uploader_sm_team = 'orange'
        else:
            return None

        # swap_teams covers the scenario where the teams join incorrectly, assumes group is correct (applies to score summary only)
        swap_teams = False
        for account in account_register[str(uploader.id)]:
            account_replay_team = self._get_account_replay_team(platform, plat_id, replay_data)
            if account_sm_team != account_replay_team:
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
            elif winner == 'blue':
                winner = 'orange'

        return winner

    async def _get_replay_destination(self, ctx, queue, game):
        
        auth_token = await self._get_auth_token(ctx)
        bc_group_owner = await self._get_steam_id_from_token(ctx, auth_token)
        top_level_group = await self._get_top_level_group(ctx)

        # /<top level group>/<queue name>/<game id>
        game_id = game.id
        blue_players = game.blue 
        oran_players = game.orange
        queue_name = queue.name # next(queue.name for queue in self.queues if queue.id == six_mans_queue.id)

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
            next_group_name = str(next_group_name)
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
                
                if 'error' not in data:
                    try:
                        next_subgroup_id = data['id']
                    except:
                        await ctx.send(":x: Error creating Ballchasing group: {}".format(next_group_name))
                        return False
            
        return next_subgroup_id

    async def _find_series_replays(self, ctx, game, winner):
        # search for appearances in private matches
        endpoint = "/replays"
        sort = 'replay-date' # 'created
        sort_dir = 'asc'
        count = 7
        queue_pop_time = ctx.channel.created_at.astimezone().isoformat()
        auth_token = await self._get_auth_token(ctx)
        
        # players = []
        # for player in game.blue:
        #     players.append(player)
        # for player in game.orange:
        #     players.append(player)

        await ctx.send("replay-date-after: {}".format(queue_pop_time))

        for player in game.players:
            for steam_id in await self._get_steam_ids(ctx, player.id):
                await ctx.send(steam_id)
                params = [
                    'uploader={}'.format(steam_id),
                    'playlist=private',
                    'replay-date-after={}'.format(queue_pop_time),
                    # 'count={}'.format(count),
                    # 'sort-by={}'.format(sort),
                    # 'sort-dir={}'.format(sort_dir)
                ]

                r = await self._bc_get_request(ctx, endpoint, params=params, auth_token=auth_token)
                data = r.json()

                await ctx.send("{} - {} | Request Code: {} ({} found)".format(player.name, steam_id[-3:], r.status_code, len(data['list'])))
                if not len(data['list']):
                    await ctx.send(data)

                # checks for correct replays
                oran_wins = 0
                blue_wins = 0
                replay_ids = []
                for replay in data['list']:
                    winner = await self._is_six_mans_replay(ctx, player, game, replay)
                    if winner == 'blue':
                        blue_wins += 1
                    else:
                        oran_wins += 1

                series_summary = "**Blue** {blue_wins} - {oran_wins} **Orange**".format(
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
