import discord
from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
import requests
import urllib

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
    async def setTRNAuthToken(self, ctx, api_key):
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
        new_emoji_status = not await self._use_rank_emojis(ctx.guild)
        await self._save_use_rank_emojis(ctx.guild, new_emoji_status)

        action = "will" if new_emoji_status else "will not"
        message = "The `{}rlrank` command **{}** include rank emojis.".format(ctx.prefix, action)
        await ctx.send(message)

    @commands.command(aliases=['myrank'])
    @commands.guild_only()
    async def rlrank(self, ctx, platform, *, platform_id):
        """Gets Rocket League Ranks for a given platform and id.
        
        Valid Platforms: epic, steam, xbl, psn, switch
        """
        return await self._process_rlrank(ctx.channel, platform, platform_id)

    @commands.Cog.listener("on_message")
    async def on_message(self, message):
        words = message.content.split()
        if words[0] == 'rlrank':
            return await self._process_rlrank(message.channel, words[1], ' '.join(words[2:]))


    async def _process_rlrank(self, channel, platform, platform_id):
        platform = platform.lower()
        sent_msg = await channel.send("_Loading **{}**'s Rocket League ranks..._".format(platform_id))
        key = await self._get_api_key(channel.guild)
        if not key:
            await sent_msg.edit(content=":x: **{}**'s ranks could not be found.".format(platform_id))
        supported_platforms = ['epic', 'steam', 'xbl', 'xbox', 'psn', 'switch']
        
        if platform not in supported_platforms:
            return await sent_msg.edit(content=":x: **{}** is not a supported platform.".format(platform))
        platform = 'xbl' if platform == 'xbox' else platform
        
        player_info = await self._get_rl_ranks(platform, platform_id, key, channel)
        if player_info['status'] != 200:
            if player_info['status'] == 429:
                return await sent_msg.edit(content=":x: Rate Limit Exceeded. Please try again later.".format(platform_id))
            return await sent_msg.edit(content=":x: **{}**'s ranks could not be found.".format(platform_id))
        
        include_rank_emojis = await self._use_rank_emojis(channel.guild)
        embed = self._get_ranks_embed(channel.guild, player_info, include_rank_emojis)
        await sent_msg.edit(content="", embed=embed)

    def _get_ranks_embed(self, guild, player_info, include_rank_emojis=False):
        standard_mode_names = ['Ranked Duel 1v1', 'Ranked Doubles 2v2', 'Ranked Standard 3v3', 'Tournament Matches']
        standard_mode_ranks = []
        extra_mode_names = ['Hoops', 'Rumble', 'Dropshot', 'Snowday']
        extra_mode_ranks = []
        for playlist, data in player_info['competitiveRanks'].items():
            emoji = " {}".format(self._get_rank_emoji(guild, data['rank'])) if include_rank_emojis else ""
            # rank_entry = "**{}**:{} {} {} - {} (-{}/+{})".format(playlist, emoji, data['rank'], data['div'], data['mmr'], data['delta_down'], data['delta_up'])
            rank_entry = "**{}**:{} {} {} - {}".format(playlist, emoji, data['rank'], data['div'], data['mmr'])
            if playlist in standard_mode_names:
                standard_mode_ranks.append(rank_entry)
            elif playlist in extra_mode_names:
                extra_mode_ranks.append(rank_entry)
        
        reward_level = self._get_reward_level(guild, player_info['rewardLevel'], include_rank_emojis)
        casual_mmr = "**Casual MMR** - {}".format(player_info['casualMMR'])
        description = "{}\n**Season Reward Level: {}".format(casual_mmr, reward_level) if reward_level else casual_mmr

        embed = discord.Embed(
            title="{}'s Rocket League Ranks".format(player_info['handle']),
            description=description,
            color=discord.Colour.blurple()
        )
        embed.add_field(name="Standard Modes", value="\n{}".format('\n'.join(standard_mode_ranks)), inline=False)
        embed.add_field(name="Extra Modes", value="\n{}".format('\n'.join(extra_mode_ranks)), inline=False)
        
        game = "Rocket League"
        rl_emoji = self._get_server_emoji(guild, game)
        if rl_emoji:
            embed.set_footer(icon_url=rl_emoji.url, text=game)
            embed.set_thumbnail(url=rl_emoji.url)
        return embed

    def _get_reward_level(self, guild, reward_level, include_rank_emojis):
        rank = "{}1".format(reward_level.title())
        reward_emoji = self._get_rank_emoji(guild, rank) if include_rank_emojis else ""
        return "{} {}".format(reward_emoji, player_info['rewardLevel'])

        try:
            rank = "{}1".format(reward_level.title())
            reward_emoji = self._get_rank_emoji(guild, rank) if include_rank_emojis else ""
            return "{} {}".format(reward_emoji, player_info['rewardLevel'])
        except:
            return None

    def _get_rank_emoji(self, guild, rank):
        rank_info = rank.split()
        rank_name = ''.join(rank_info[:-1])
        rank_num = rank_info[-1].replace('III', '3').replace('II', '2').replace('I', '1')
        emoji = "{}{}".format(rank_name, rank_num)
        return self._get_server_emoji(guild, emoji)
    
    def _get_server_emoji(self, guild, emoji):
        emoji = emoji.replace(" ", "")
        for e in guild.emojis:
            if e.name == emoji:
                return e
        return None

    async def _get_rl_ranks(self, platform, plat_id, api_key, channel=None):
        game = 'rocket-league'
        url = 'https://public-api.tracker.gg/v2/{}/standard/profile'.format(game)

        endpoint = '/{}/{}'.format(platform, urllib.parse.quote(plat_id))
        request_url = url + endpoint

        r = requests.get(request_url, headers={'TRN-Api-Key': api_key})
        if r.status_code != 200:
            return {'status': r.status_code}

        
        rewards  = None
        data = r.json()
        casual_mmr = 0
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
            elif segment['type'] == 'playlist' and playlist == 'Un-Ranked':
                casual_mmr = segment['stats']['rating']['value']
            elif segment['type'] == 'overview':
                rewards = segment['stats']['seasonRewardLevel']['metadata']['rankName']
                try:
                    await channel.send(rewards)
                except:
                    pass

        player_info = {'status': r.status_code, 'handle': data['data']['platformInfo']['platformUserHandle'], 'casualMMR': casual_mmr, 'competitiveRanks': ranks, 'rewardLevel': rewards}
        return player_info

    async def _get_api_key(self, guild):
        return await self.config.guild(guild).AuthKey()
    
    async def _save_api_key(self, ctx, token):
        await self.config.guild(ctx.guild).AuthKey.set(token)
        return True

    async def _use_rank_emojis(self, guild):
        return await self.config.guild(guild).IncludeRankEmojis()
    
    async def _save_use_rank_emojis(self, guild, status: bool):
        await self.config.guild(guild).IncludeRankEmojis.set(status)
    