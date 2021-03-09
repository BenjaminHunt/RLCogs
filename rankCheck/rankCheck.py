import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
import requests

defaults =   {"AuthKey": None}

class RankCheck(commands.Cog):
    """Manages aspects of Ballchasing Integrations with RSC"""

    def __init__(self, bot):
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        # TODO: self.token = await self._auth_token # load on_ready

    @commands.command(aliases=['setTRNAuthKey'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setAuthTRNToken(self, ctx, api_key):
        """Sets the Auth Key for Tracker Network API requests.
        """
        token_set = await self._save_api_key(ctx, api_key)
        if(token_set):
            await ctx.send(":white_check_mark: API Key has been set.")
            await ctx.message.delete()
        else:
            await ctx.send(":x: Error setting auth token.")

    @commands.command(aliases=['myrank'])
    @commands.guild_only()
    async def rlrank(self, ctx, platform, platform_id):
        """Gets Rocket League Ranks for a given platform and id.
        """
        sent_msg = await ctx.send("_Loading **{}** Rocket League ranks..._".format(platform_id))
        key = await self._get_api_key(ctx)
        if not key:
            await sent_msg.edit(content=":x: **{}**'s ranks could not be found.".format(platform_id))
        
        ranks_response = self._get_rl_ranks(platform, platform_id, key)
        if ranks_response:
            handle, ranks = ranks_response
        else:
            return await sent_msg.edit(content=":x: **{}**'s ranks could not be found.".format(platform_id))
        title = "__**{}**'s Rocket League ranks:__".format(handle)
        output = ""
        for playlist, data in ranks.items():
            output += "\n**{}**: {} {} - {} (-{}/+{})".format(playlist, data['rank'], data['div'], data['mmr'], data['delta_down'], data['delta_up'])

        await sent_msg.edit(content=title + output)
    
    def _get_ranks_embed():
        pass

    def _get_rl_ranks(self, platform, plat_id, api_key):
        game = 'rocket-league'
        url = 'https://public-api.tracker.gg/v2/{}/standard/profile'.format(game)

        endpoint = '/{}/{}'.format(platform, plat_id)
        request_url = url + endpoint

        r = requests.get(request_url, headers={'TRN-Api-Key': api_key})
        if r.status_code != 200:
            return False

        data = r.json()
        ranks = {}
        handle = data['data']['platformInfo']['platformUserHandle']
        for segment in data['data']['segments']:
            playlist = segment['metadata']['name']
            if segment['type'] == 'playlist' and playlist != 'Un-Ranked':
                ranks[playlist] = {}
                div_segment = segment['stats']['division']['metadata']
                ranks[playlist]['mmr'] = segment['stats']['rating']['value']
                ranks[playlist]['rank'] = segment['stats']['tier']['metadata']['name']
                ranks[playlist]['div'] = div_segment['name']
                ranks[playlist]['delta_up'] = div_segment['deltaUp'] if 'deltaUp' in div_segment else 0
                ranks[playlist]['delta_down'] = div_segment['deltaDown'] if 'deltaDown' in div_segment else 0
        return handle, ranks

    async def _get_api_key(self, ctx):
        return await self.config.guild(ctx.guild).AuthKey()
    
    async def _save_api_key(self, ctx, token):
        await self.config.guild(ctx.guild).AuthKey.set(token)
        return True

