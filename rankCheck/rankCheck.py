import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
import requests

defaults =   {"AuthKey": None, "IncludeRankEmojis": False}

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

    @commands.guild_only()
    @commands.command(aliases=['toggleUseRankEmojis'])
    @checks.admin_or_permissions(manage_guild=True)
    async def toggleRankEmojis(self, ctx):
        """Toggle whether or not bot uses rank emojis in the `[p]rlrank` command."""
        new_emoji_status = not await self._use_rank_emojis(ctx)
        await self._save_use_rank_emojis(ctx, new_emoji_status)

        action = "will" if new_emoji_status else "will not"
        message = "The `{}rlrank` command **{}** include rank emojis.".format(ctx.prefix, action)
        await ctx.send(message)

    @commands.command(aliases=['myrank'])
    @commands.guild_only()
    async def rlrank(self, ctx, platform, platform_id):
        """Gets Rocket League Ranks for a given platform and id.
        """
        sent_msg = await ctx.send("_Loading **{}**'s Rocket League ranks..._".format(platform_id))
        key = await self._get_api_key(ctx)
        if not key:
            await sent_msg.edit(content=":x: **{}**'s ranks could not be found.".format(platform_id))
        
        player_info = self._get_rl_ranks(platform, platform_id, key)
        if not player_info:
            return await sent_msg.edit(content=":x: **{}**'s ranks could not be found.".format(platform_id))
        title = "__**{}**'s Rocket League ranks:__".format(handle)
        output = ""
        include_rank_emoji = await self._use_rank_emojis(ctx)
        
        for playlist, data in player_info['ranks'].items():
            emoji = " {}".format(self._get_rank_emoji(ctx, data['rank'])) if include_rank_emoji else ""
            output += "\n**{}**:{} {} {} - {} (-{}/+{})".format(playlist, emoji, data['rank'], data['div'], data['mmr'], data['delta_down'], data['delta_up'])

        await sent_msg.edit(content=title + output)
    
    @commands.command()
    @commands.guild_only()
    async def emoji(self, ctx, emoji):
        await ctx.send(self._get_rank_emoji(ctx, emoji))

    def _get_ranks_embed():
        pass

    def _get_rank_emoji(self, ctx, rank):
        rank_info = rank.split()
        rank_name = ''.join(rank_info[:-1])
        rank_num = rank_info[-1].replace('III', '3').replace('II', '2').replace('I', '1')
        emoji = "{}{}".format(rank_name, rank_num)
        for e in ctx.guild.emojis:
            if e.name == emoji:
                return e
        return ""

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
        rewards  = None
        player_info = {'handle': data['data']['platformInfo']['platformUserHandle'], 'ranks': ranks, 'rewardLevel': rewards}
        return player_info

    async def _get_api_key(self, ctx):
        return await self.config.guild(ctx.guild).AuthKey()
    
    async def _save_api_key(self, ctx, token):
        await self.config.guild(ctx.guild).AuthKey.set(token)
        return True

    async def _use_rank_emojis(self, ctx):
        return await self.config.guild(ctx.guild).IncludeRankEmojis()
    
    async def _save_use_rank_emojis(self, ctx, status: bool):
        await self.config.guild(ctx.guild).IncludeRankEmojis.set(status)
    