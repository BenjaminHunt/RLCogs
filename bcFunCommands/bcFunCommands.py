
import discord
import requests

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions
from .funCmdsReference import FunCmdsReference as fcr

# TODO: Build in player and team stats , just neeed player, team, tier

TYPING_INDICATOR_GIF = "https://cdn.discordapp.com/emojis/522583389350658048.gif?size=96&quality=lossless"
global_defaults = {"CarBodyLookup": {}}
class BCFunCommands(commands.Cog):
    """Neat misc ballchasing related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_global(**global_defaults)
        self.account_manager_cog = bot.get_cog("AccountManager")
        # TODO: self.token = await self._auth_token # load on_ready

    @commands.command(aliases=['camera', 'mycam', 'cs'])
    @commands.guild_only()
    async def settings(self, ctx, *, player:discord.Member=None):
        """Get the settings from your latest game"""
        looking: discord.Message = await ctx.send(TYPING_INDICATOR_GIF)
        if not player:
            player = ctx.author
        
        token = await self.get_auth_token(player)
        accounts = await self.get_member_accounts(player)
        
        if not accounts:
            return await ctx.send(f":x: {player.name} has not registered any accounts.")

        target_replay_id = self.get_latest_replay_id_from_accounts(token, accounts)
        if not target_replay_id:
            return await ctx.send(":x: No recent replays found")

        full_replay_json = self.get_full_replay_json(token, target_replay_id)
        target_account = self.which_account_in_full_replay(full_replay_json, accounts)
        player_data = self.get_player_data_from_replay(full_replay_json, target_account[0], target_account[1])

        embed = await self.get_player_settings_embed(target_replay_id, player, player_data)

        await looking.delete()
        await ctx.send(embed=embed)

    @commands.command()
    @commands.guild_only()
    async def carbodies(self, ctx):
        car_map_list = []
        car_lookup_map = await self.config.CarBodyLookup()

        for id, name in car_lookup_map.items():
            car_map_list.append(f"{id}: {name}")
        
        await ctx.send("```\n{}\n```".format('\n'.join(car_lookup_map)))

    @commands.command()
    @commands.guild_only()
    async def roles(self, ctx):
        roles = ctx.author.roles
        roles.sort(key=lambda r: r.position, reverse=True)
        role_pings = ', '.join([role.mention for role in roles])
        role_colors = ', '.join([str(role.color.value) for role in roles])
        embed = discord.Embed(
            title = f"{ctx.author.name}'s Roles",
            color = self.get_member_color(ctx.author),
            description=role_pings + ' - ' # + role_colors
        )
        await ctx.send(embed=embed)

# region ballchasing
    
    # TODO: Make requests async
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

    # replay processing
    def get_latest_replay_id_from_accounts(self, token, accounts):
        # get latest account replays
        json_replays = []
        for account in accounts:
            platform = account[0]
            plat_id = account[1]
            replay = self.get_latest_account_replay(token, platform, plat_id)
            if replay:
                json_replays.append(replay)
        
        if json_replays:
            json_replays = sorted(json_replays, key = lambda replay: replay['date'])
            json_replays.reverse()
            return json_replays[0]['id']
        
        return None

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
                account_info = [
                    player.get("id", {}).get('platform', None),
                    player.get("id", {}).get('id', None)
                ]
                if account_info in account_list:
                    return account_info
        return None
    
    def get_player_data_from_replay(self, replay_json, platform, platform_id):
        for team in ['blue', 'orange']:
            for player in replay_json[team].get('players', []):
                account_match = (
                    player.get("id", {}).get('platform', None) == platform
                    and
                    player.get("id", {}).get('id', None) == platform_id
                )
                if account_match:
                    return player
        return {}
                
    def get_latest_account_replay(self, token, platform, plat_id):
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

    # access json data
    async def get_auth_token(self, member: discord.Member):
        # return member token if exists else guild token
        token = await self.account_manager_cog._get_member_bc_token(member)
        if token:
            return token 
        token = await self.account_manager_cog.get_bc_auth_token(member.guild)
        return token

    # misc
    def get_code_title(self, code):
        return fcr.DATA_CODE_NAME_MAP.get(code.lower(), code)

    def get_member_color(self, member: discord.Member):
        roles = member.roles
        roles.sort(key=lambda r: r.position, reverse=True)
        for role in roles:
            if role.color:
                return role.color
        return None

    # embed
    async def get_player_settings_embed(self, replay_id, member, player_data):
        member_color = self.get_member_color(member)

        embed = discord.Embed(
            title=f"{member.name}'s latest settings",
            color=member_color
        )
        if member.avatar_url:
            embed.set_thumbnail(url=member.avatar_url)
        
        # Preformat Camera Settings
        cam_settings = player_data.get("camera")

        cam_settings_order = ["fov", "distance", "height", "pitch", "stiffness", "swivel_speed" , "transition_speed"]
        cam_settings_list = []
        for setting in cam_settings_order:
            setting_name = self.get_code_title(setting)
            cam_settings_list.append(f"{setting_name}: {cam_settings.get(setting, 'N/A')}")
        
        cam_str = "```\n{}\n```".format('\n'.join(cam_settings_list))

        name = player_data.get('name')
        platform = player_data['id']['platform']
        plat_id = player_data['id']['id']
        player_page_link = f'https://ballchasing.com/player/{platform}/{plat_id}'

        car_id = player_data.get("car_id", "X")
        car_str = await self.lookup_car_id(car_id)
        car_str = car_str if car_str else f"Not Found: {car_id}"
        steer_sens = f"steering sensitivity: {player_data.get('steering_sensitivity')}"

        # Build Embed
        embed.add_field(name="Account", value=f"[{platform} | {name}]({player_page_link})", inline=False)
        embed.add_field(name="Camera Settings", value=cam_str, inline=False)
        embed.add_field(name="Sensitivity Settings", value='```\n{}\n```'.format(steer_sens), inline=False)

        if car_str:
            embed.add_field(name="Car Choice", value=f"```{car_str}```", inline=False)

        embed.add_field(name="Source Replay", value=f"[Click Here to view](https://ballchasing.com/replay/{replay_id})", inline=False)

        return embed 

# endregion

# region json

    async def lookup_car_id(self, car_id):
        car_lookup_map = await self.config.CarBodyLookup()
        return car_lookup_map.get(str(car_id), None)

# endregion

