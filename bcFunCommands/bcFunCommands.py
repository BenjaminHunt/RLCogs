
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


class BCFunCommands(commands.Cog):
    """Neat misc ballchasing related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.account_manager_cog = bot.get_cog("AccountManager")
        # TODO: self.token = await self._auth_token # load on_ready

    @commands.command(aliases=['mycam', 'cs'])
    @commands.guild_only()
    async def settings(self, ctx, *, player:discord.Member=None):
        """Get the settings from your latest game"""
        looking = await ctx.send("Let's take a look...")
        if not player:
            player = ctx.author
        
        token = await self.get_auth_token(player)
        accounts = await self.get_member_accounts(player)
        
        if not accounts:
            return await ctx.send(f":x: {player.name} has not registered any accounts.")

        json_replays = []
        for account in accounts:
            platform = account[0]
            plat_id = account[1]
            replay = self.get_latest_replay(token, platform, plat_id)
            if replay:
                json_replays.append(replay)
        
        if not json_replays:
            return await ctx.send(":x: No recent replays found")

        json_replays.sort(key=lambda replay: replay["date"])
        target_replay_id = json_replays[0]['id']
        full_replay_json = self.get_full_replay_json(token, target_replay_id)
        target_account = self.which_account_in_full_replay(full_replay_json, accounts)
        player_data = self.get_player_data_from_replay(full_replay_json, target_account[0], target_account[1])

        embed = self.get_player_settings_embed(target_replay_id, player, player_data)

        await ctx.send(embed=embed)


# region ballchasing
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

# endregion 

# region helper functions
    def get_full_replay_json(self, token, replay_id):
        endpoint = f'/replays/{replay_id}'
        response = self._bc_get_request(token, endpoint)
        data = response.json()

        try:
            return data
        except:
            return None

    async def get_member_accounts(self, member: discord.Member):
        discord_id = str(member.id)
        account_register = await self.account_manager_cog.get_account_register()
        if discord_id in account_register:
            return account_register.get(discord_id, [])
    
    def which_account_in_full_replay(self, replay_json, account_list=[]):
        for team in ['blue', 'orange']:
            for player in replay_json[team].get('players', []):
                account_info = [player['id']['platform'], player['id']['id']]
                if account_info in account_list:
                    return account_info
        return None
    
    def get_player_data_from_replay(self, replay_json, platform, platform_id):
        for team in ['blue', 'orange']:
            for player in replay_json[team].get('players', []):
                account_match = (
                    player['id']['platform'] == platform
                    and
                    player['id']['id'] == platform_id
                )
                if account_match:
                    return player
        return {}
                
    def get_latest_replay(self, token, platform, plat_id):
        endpoint = '/replays'
        params = [
            'sort-by=replay-date',
            'sort-dir=desc',
            'count=1',
            f'player-id={platform}:{plat_id}'
        ]
        response = self._bc_get_request(token, endpoint, params)
        data = response.json()

        try:
            return data['list'][0]
        except:
            return None

    async def get_auth_token(self, member: discord.Member):
        # return member token if exists else guild token
        token = await self.account_manager_cog._get_member_bc_token(member)
        if token:
            return token 
        token = await self.account_manager_cog.get_bc_auth_token(member.guild)
        return token

    def get_member_color(self, member: discord.Member):
        for role in member.roles:
            if role.color:
                return role.color
        return None

    def get_player_settings_embed(self, replay_id, member, player_data):
        member_color = self.get_member_color(member)

        embed = discord.Embed(
            title=f"{member.name}'s latest settings: {player_data.get('name')}",
            color=member_color
        )
        if member.avatar_url:
            embed.set_thumbnail(url=member.avatar_url)
        
        
        cam_settings = player_data.get("camera")
        cam_settings_list = []

        for k, v in cam_settings.items():
            cam_settings_list.append(f"{k}: {v}")
        
        cam_str = "```\n{}\n```".format('\n'.join(cam_settings_list))

        name = player_data.get('name')
        platform = player_data['id']['platform']
        plat_id = player_data['id']['id']
        player_page_link = f'https://ballchasing.com/player/{platform}/{plat_id}'

        embed.add_field(name="Account", value=f"[{platform} | {name}]({player_page_link})", inline=False)
        embed.add_field(name="Camera Settings", value=cam_str, inline=False)
        embed.add_field(name="Replay", value=f"[Click Here to view](https://ballchasing.com/replay/{replay_id})", inline=False)

        # embed.description = cam_str

        return embed 

# endregion