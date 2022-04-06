import abc
from .config import config
from datetime import datetime, timezone
import tempfile
import discord
import asyncio
import requests
import urllib.parse

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"TopLevelGroup": None, "SixMansRole": 848403373782204436}
verify_timeout = 30

class BCSixMans(commands.Cog):
    """Manages aspects of Ballchasing Integrations with RSC"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.six_mans_cog = bot.get_cog("SixMans")
        self.account_manager_cog = bot.get_cog("AccountManager")
        # TODO: self.token = await self._auth_token # load on_ready
        # self.bot.loop.create_task(self.observe_six_mans())
        try:
            self.observe_six_mans()
        except:
            pass

    def cog_unload(self):
        """Clean up when cog shuts down."""
        # if self.task:
        #     self.task.cancel()
        try:
            self.observe_six_mans(False)
        except:
            pass
    
    @commands.command(aliases=['ggs', 'gg'])
    @commands.guild_only()
    async def gameOver(self, ctx): # , games_played:int):
        """Finds replays from the six mans series based on the number of games played, and links a new ballchasing group for the series.
        """
        # Find Six Mans Game, Queue
        member = ctx.message.author
        self.six_mans_cog = self.bot.get_cog("SixMans")
        game = None
        for g in self.six_mans_cog.games[ctx.guild]:
            if g.textChannel == ctx.message.channel:
                game = g
                break
        

        if not len(self.six_mans_cog.games[ctx.guild]):
            return
            # await game_text_channel.send("no ongoing games")

        if not game:
            await ctx.send("game not found.")
            return False

        await self._process_six_mans_replays(game)

    @commands.command(aliases=["ssmg", "setSixMansGroup", "setSMG"])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setSMGroup(self, ctx, top_level_group_id):
        """Sets the Top Level Ballchasing Replay group for saving match replays.
        Note: Auth Token must be generated from the Ballchasing group owner
        """
        # TODO: validate group
        top_level_group_id = top_level_group_id.replace('https://', '').replace('ballchasing.com/group/', '')
        await self._save_top_level_group(ctx, top_level_group_id)
        await ctx.send("Done.")
    
    @commands.command(aliases=['smGroup', 'smg', 'tlg', 'getSMGroup'])
    @commands.guild_only()
    async def sixMansGroup(self, ctx):
        """Get the top-level ballchasing group to see all season match replays."""
        group_code = await self._get_top_level_group(ctx.guild)
        url = "https://ballchasing.com/group/{}".format(group_code)
        await ctx.send("See all six mans replays in the top level ballchasing group: {}".format(url))

    @commands.command(aliases=['gsids'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getSteamIds(self, ctx):
        steam_ids = await self._get_steam_ids(ctx, ctx.message.author.id)
        for sid in steam_ids:
            await ctx.send(sid)

    @commands.command(aliases=['cw'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def whenCreated(self, ctx):
        created = ctx.channel.created_at.astimezone(tz=timezone.utc).isoformat()
        await ctx.send("Channel created: {}".format(created))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def bct(self, ctx):
        """ballchasing... time?"""
        # key = await self.account_manager
        return 

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def testa(self, ctx):
        if not self.account_manager_cog:
            return await ctx.send(":x: **Error:** The `accountManager` cog must be loaded to enable this behavior.")
        await ctx.send("good")

    # @commands.command()
    # @commands.guild_only()
    # async def authToken(self, ctx):
    #     await ctx.send("token: {}".format(await self._get_auth_token(ctx.guild)))
        
## OBSERVER PATTERN IMPLEMENTATION ########################

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def observeForBallchasing(self, ctx):
        self.observe_six_mans()
        await ctx.send("Observing.")

    @commands.guild_only()
    @commands.Cog.listener("on_ready")
    async def on_ready(self):
        pass 
        # self.observe_six_mans()

    @commands.guild_only()
    @commands.Cog.listener("on_resumed")
    async def on_resumed(self):
        pass 
        # self.observe_six_mans()

    def observe_six_mans(self, observe=True):
        self.six_mans_cog = self.bot.get_cog("SixMans")
        if observe:
            self.six_mans_cog.add_observer(self)
        else:
            self.six_mans_cog.remove_observer(self)

    async def update(self, game):
        guild = game.queue.guild
        if not await self._get_top_level_group(guild):
            return
        if game.state == config.GS_GAME_OVER:  # TODO: update to be just "over"
            await game.queue.send_message(message=f"Processing **{game.queue.name}** replays (id: {str(game.id)[-3:]}).")
            await self._process_six_mans_replays(game)
            await game.queue.send_message(message="processed!")
            

###########################################################

# ballchasing
    def _bc_get_request(self, auth_token, endpoint, params=[]):
        url = 'https://ballchasing.com/api'
        url += endpoint
        # params = [urllib.parse.quote(p) for p in params]
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
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

# other commands
    async def _process_six_mans_replays(self, game):
        if not self.account_manager_cog:
            return await game.queue.send_message(":x: **Error:** The `accountManager` cog must be loaded to enable this behavior.")
        guild = game.queue.guild
        series_title = f"{str(game.id)[-3:]} | {game.queue.name} Series Replays"
        queue = game.queue
        embed = discord.Embed(
            title=series_title,
            description="_Finding ballchasing replays..._",
            color=discord.Color.default()
        )
        try:
            if game.winner.lower() == 'blue':
                embed.color = discord.Color.blue()
            else:
                embed.color = discord.Color.orange()
        except:
            pass 

        embed.set_footer(text="Game ID: {}".format(game.id))
        emoji_url = guild.icon_url
        if emoji_url:
            embed.set_thumbnail(url=emoji_url)
        
        blue_team = "Blue (W)" if game.winner.lower() == 'blue' else "Blue"
        orange_team = "Orange (W)" if game.winner.lower() == 'orange' else "Orange"
        
        embed.add_field(name=blue_team, value="{}\n".format("\n".join([player.mention for player in game.blue])), inline=True)
        embed.add_field(name=orange_team, value="{}\n".format("\n".join([player.mention for player in game.orange])), inline=True)
        
        messages = await queue.send_message(embed=embed)
        embed_message = messages[0]

        if not await self._get_top_level_group(guild):
            embed.description = ':x: ballchasing group group not found. An Admin must use the `?setBCGroup` command to enable automatic uploads'
            await embed_message.edit(embed=embed)
            # for message in messages:
            #     await message.edit(embed=embed)
            return
        
        # Find Series replays
        replays_found = await self._find_series_replays(guild, game)
        if replays_found:
            replay_ids, summary = replays_found
        if not replays_found:
            embed.description = ":x: No matching replays found."
            await embed_message.edit(embed=embed)
            return
        else:
            await game.queue.send_message(message="@nullidea: {} replays found".format(len(replay_ids)))

        channel = queue.channels[0]
        await channel.send(replays_found)
        await channel.send('A')
        series_subgroup_id = await self._get_series_destination(game)
        await channel.send('B')
        await channel.send(series_subgroup_id)
        # await text_channel.send("Match Subgroup ID: {}".format(series_subgroup_id))
        if not series_subgroup_id:
            await channel.send('XXX')
            embed.description = ":x: series_subgroup_id not found."
            await embed_message.edit(embed=embed)
            return

        await channel.send('C')
        # await text_channel.send("Matching Ballchasing Replay IDs ({}): {}".format(len(replay_ids), ", ".join(replay_ids)))
        
        try:
            embed.description = ":signal_strength: _Processing {} replays..._".format(len(replay_ids))
            await embed_message.edit(embed=embed)
            return
        except:
            pass

        await channel.send('D')

        tmp_replay_files = await self._download_replays(guild, replay_ids)
        uploaded_ids = await self._upload_replays(guild, series_subgroup_id, tmp_replay_files)
        renamed = await self._rename_replays(guild, uploaded_ids)
        
        await channel.send('E')

        embed.description = ':white_check_mark: {}\n\nReplays added to a new [ballchasing subgroup!](https://ballchasing.com/group/{})'.format(summary, len(uploaded_ids), series_subgroup_id)
        await embed_message.edit(embed=embed)
        return

    async def _get_all_accounts(self, guild, member):
        accs = []
        account_register = await self._get_account_register()
        discord_id = str(member.id)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                accs.append(account)
        return accs

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
        auth_token = await self._get_auth_token(ctx.guild)
        endpoint = '/replays'
        params = [
            'player-id={platform}:{identifier}'.format(platform=platform, identifier=identifier),
            'count=1'
        ]
        r = self._bc_get_request(auth_token, endpoint, params)
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

    async def _get_steam_id_from_token(self, guild, auth_token=None):
        if not auth_token:
            auth_token = await self._get_auth_token(guild)
        r = self._bc_get_request(auth_token, "")
        if r.status_code == 200:
            return r.json()['steam_id']
        return None

    async def _get_account_register(self):
        return await self.account_manager_cog.get_account_register()

    async def _get_steam_ids(self, guild, discord_id):
        discord_id = str(discord_id)
        steam_accounts = []
        account_register = await self._get_account_register()
        if discord_id in account_register:
            for account in account_register[discord_id]:
                if account[0] == 'steam':
                    steam_accounts.append(account[1])
        return steam_accounts

    def _get_account_replay_team(self, platform, plat_id, replay_data):
        for team in ['blue', 'orange']:
            for player in replay_data[team]['players']:
                if player['id'] and player['id']['platform'] == platform and player['id']['id'] == str(plat_id):
                    return team
        return None

    async def _is_six_mans_replay(self, guild, uploader, sm_game, replay_data, use_account=None):
        """searches for the uploader's appearance in the replay under any registered account"""
        if use_account:
            account_register = {uploader.id: [use_account]}
        else:
            account_register = await self._get_account_register()
        
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
            platform, plat_id = account
            
            # error here
            account_replay_team = self._get_account_replay_team(platform, plat_id, replay_data)
            # await sm_game.textChannel.send("uploader team: {}\naccount team: {}".format(uploader_sm_team))

            if account_replay_team and uploader_sm_team.lower() != account_replay_team.lower():
                swap_teams = True

        # don't count incomplete replays
        if not self._is_full_replay(replay_data):
            return False

        # determine winner
        orange_goals = replay_data['orange']['goals'] if 'goals' in replay_data['orange'] else 0
        blue_goals = replay_data['blue']['goals'] if 'goals' in replay_data['blue'] else 0
        if blue_goals > orange_goals:
            winner = 'blue'
        else:
            winner = 'orange'
        
        # swap teams if necessary
        if swap_teams:
            # await sm_game.textChannel.send("swapped teams")
            if winner == 'orange':
                winner = 'blue'
            elif winner == 'blue':
                winner = 'orange'

        return winner

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
            for player in replay_data[team]['players']:
                if player['start_time'] == 0:
                    return True
        return False

    async def _find_series_replays(self, guild, game):
        # search for appearances in private matches
        endpoint = "/replays"
        sort = 'replay-date'
        sort_dir = 'desc'
        count = 7
        # queue_pop_time = ctx.channel.created_at.isoformat() + "-00:00"
        queue_pop_time = game.textChannel.created_at # .astimezone(tz=timezone.utc).isoformat()
        queue_pop_time = '{}-00:00'.format(queue_pop_time.isoformat())
        auth_token = await self._get_auth_token(guild)
        if not auth_token:
            return await game.queue.send_message(":x: Guild has no auth token registered.")

        params = [
            'playlist=private',
            # 'replay-date-after={}'.format(urllib.parse.quote(queue_pop_time)),
            'replay-date-after={}'.format(queue_pop_time),
            'count={}'.format(count),
            'sort-by={}'.format(sort),
            'sort-dir={}'.format(sort_dir)
        ]
        await asyncio.sleep(5) # wait 5 seconds for insta-reports
        i = 0
        for player in game.players:
            i += 1
            for steam_id in await self._get_steam_ids(guild, player.id):
                uploaded_by_param='uploader={}'.format(steam_id)
                params.append(uploaded_by_param)
                r = self._bc_get_request(auth_token, endpoint, params=params)

                params.remove(uploaded_by_param)
                data = r.json()

                # checks for correct replays
                oran_wins = 0
                blue_wins = 0
                replay_ids = []
                if 'list' in data:
                    await game.textChannel.send("{} has {} replays uploaded...".format(player.name, len(data['list'])))
                    for replay in data['list']:
                        winner = await self._is_six_mans_replay(guild, player, game, replay)
                        if winner.lower() == 'blue':
                            blue_wins += 1
                        elif winner.lower() == 'orange':
                            oran_wins += 1
                        else:
                            await game.textChannel.send("Winner not defined :/")
                            break
                        replay_ids.append(replay['id'])

                    series_summary = "**Blue** {blue_wins} - {oran_wins} **Orange**".format(
                        blue_wins=blue_wins, oran_wins=oran_wins
                    )

                    if replay_ids:
                        await game.textChannel.send(":)")
                        return replay_ids, series_summary
        print(i)
        return None

    async def _get_series_destination(self, game):
        queue = game.queue
        guild = queue.guild
        # here
        auth_token = await self._get_auth_token(guild)
        bc_group_owner = await self._get_steam_id_from_token(guild, auth_token)
        top_level_group = await self._get_top_level_group(guild)

        
        # /<top level group>/<queue name>/<game id>
        game_id = game.id
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

        r = self._bc_get_request(auth_token, endpoint, params=params)

        data = r.json()

        await queue.send_message("A.b")
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
                        continue
            
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
                # here
                payload = {
                    'name': next_group_name,
                    'parent': current_subgroup_id,
                    'player_identification': config.player_identification,
                    'team_identification': config.team_identification
                }
                await debug_channel.send("POST: {}".format(endpoint))
                await debug_channel.send("parms: {}".format(payload))
                r = self._bc_post_request(auth_token, endpoint, json=payload)
                data = r.json()
                
                if 'error' not in data:
                    try:
                        next_subgroup_id = data['id']
                    except:
                        return False
        
        
        await queue.send_message("A.e")

        return next_subgroup_id

    async def _download_replays(self, guild, replay_ids):
        auth_token = await self._get_auth_token(guild)
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

    async def _upload_replays(self, guild, subgroup_id, files_to_upload):
        endpoint = "/v2/upload"
        params = [
            'visibility={}'.format(config.visibility),
            'group={}'.format(subgroup_id)
        ]
        auth_token = await self._get_auth_token(guild)

        replay_ids_in_group = []
        for replay_file in files_to_upload:
            replay_file.seek(0)
            files = {'file': replay_file}

            r = self._bc_post_request(auth_token, endpoint, params, files=files)
        
            status_code = r.status_code
            data = r.json()
            
            try:
                if status_code == 201:
                    replay_ids_in_group.append(data['id'])
                elif status_code == 409: # Handle duplicate replays
                    patch_endpoint = '/replays/{}/'.format(data['id'])
                    r = self._bc_patch_request(auth_token, patch_endpoint, json={'group': subgroup_id, 'visibility': config.visibility})
                    if r.status_code == 204:
                        replay_ids_in_group.append(data['id'])
            except:
                pass
                # await ctx.send(":x: {} error: {}".format(status_code, data['error']))
            
            replay_file.close()
        
        return replay_ids_in_group

    async def _add_replay_to_group(self, guild, replay_id, subgroup_id, auth_token=None):
        pass

    async def _rename_replays(self, guild, uploaded_replays_ids):
        auth_token = await self._get_auth_token(guild)
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
                await print(":x: {} error.".format(status_code))

            game_number += 1
        return renamed

# json
    async def _get_top_level_group(self, guild):
        return await self.config.guild(guild).TopLevelGroup()
    
    async def _save_top_level_group(self, ctx, group_id):
        await self.config.guild(ctx.guild).TopLevelGroup.set(group_id)

    async def _get_auth_token(self, guild):
        print('atkn')
        return await self.account_manager_cog.get_bc_auth_token(guild)

    async def _save_six_mans_role(self, guild, role):
        await self.config.guild(guild).SixMansRole.set(role)
    
    async def _six_mans_role(self, guild):
        return guild.get_role(await self.config.guild(guild).SixMansRole())

class Observer(metaclass=abc.ABCMeta):
    def __init__(self):
        pass
    
    @abc.abstractmethod
    def update(self, arg):
        pass
    
