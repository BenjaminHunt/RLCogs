
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
    @checks.admin_or_permissions(manage_guild=True)
    async def settings(self, ctx, *, player:discord.Member=None):
        """Get the settings from your latest game"""
        if not player:
            player = ctx.author
        accounts = self.get_member_accounts(player)
        
        json_replays = []
        for account in accounts:
            platform = account[0]
            plat_id = account[1]
            json_replays.append(self.get_latest_replay(platform, plat_id))
        
        json_replays.sort(key=lambda replay: replay["date"])
        full_replay_json = self.get_full_replay_json(json_replays[0]['id'])
        target_account = self.which_account_in_full_replay(full_replay_json, accounts)
        player_data = self.get_player_data_from_replay(full_replay_json, target_account[0], target_account[1])

        embed = self.get_player_settings_embed(player, player_data)

        await ctx.send(embed=embed)


# region ballchasing
    async def _bc_get_request(self, guild, endpoint, params=[], auth_token=None):
        if not auth_token:
            auth_token = await self.get_bc_auth_token(guild)
        
        url = 'https://ballchasing.com/api'
        url += endpoint
        # params = [urllib.parse.quote(p) for p in params]
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        # url = urllib.parse.quote_plus(url)
        
        return requests.get(url, headers={'Authorization': auth_token})

    async def _bc_post_request(self, guild, endpoint, params=[], auth_token=None, json=None, data=None, files=None):
        if not auth_token:
            auth_token = await self.get_bc_auth_token(guild)
        
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.post(url, headers={'Authorization': auth_token}, json=json, data=data, files=files)

    async def _bc_patch_request(self, guild, endpoint, params=[], auth_token=None, json=None, data=None):
        if not auth_token:
            auth_token = await self.get_bc_auth_token(guild)

        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.patch(url, headers={'Authorization': auth_token}, json=json, data=data)

# endregion 

# region helper functions
    async def get_full_replay_json(self, replay_id):
        pass 

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
                
    def get_latest_replay(self, platform, plat_id):
        pass 

    def get_auth_token(self, member):
        # return member token if exists else guild token
        pass 

    def get_player_settings_embed(self, member, player_data):
        if member.roles:
            color = member.roles[0].color
        else:
            color = None

        embed = discord.Embed(
            title=f"{member.name}'s latest settings: {player_data.get('name')}",
            color=color
        )
        if member.avatar_url:
            embed.set_thumbnail(url=member.avatar_url)
        
        
        cam_settings = player_data.get("camera")
        cam_settings_list = ''

        for k, v in cam_settings.items():
            cam_settings_list.append(f"{k}: {v}")
        
        cam_str = f"```\n{'\n'.join(cam_settings_list)}\n```"

        embed.description = cam_str

        return embed 

# endregion