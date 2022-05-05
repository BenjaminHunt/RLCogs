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

defaults = {"BCAuthToken": None, "TRNAuthToken": None}
global_defaults = {"AccountRegister": {}, "BCTokens": {}}
verify_timeout = 15

class AccountManager(commands.Cog):
    """Manages aspects of Ballchasing Integrations with RSC"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_global(**global_defaults)
        self.config.register_guild(**defaults)
        # TODO: self.token = await self._auth_token # load on_ready

    @commands.command(aliases=['setBCAuthKey', 'setGuildBCAuthToken'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setBCAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Ballchasing API requests.
        Note: Auth Token must be generated from the Ballchasing group owner
        """
        await ctx.message.delete()
        try:
            await self._save_bc_auth_token(ctx.guild, auth_token)
            await ctx.send(":white_check_mark: Guild Ballchasing Auth Token has been set.")
        except:
            await ctx.send(":x: Error setting auth token.")

    @commands.command(aliases=['setMyBCAuthKey', 'setMyUploadToken'])
    async def setMyBCAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Ballchasing API requests for the given user.
        """
        member = ctx.author
        try:
            try:
                await ctx.message.delete()
            except:
                pass
            r = await self._bc_get_request(auth_token, '')
            await ctx.send("+++")

            if r.status_code == 200:
                await self._save_member_bc_token(member, auth_token)

                msg = f":white_check_mark: {member.name}, your Ballchasing Auth Token has been set"
                
                steam_id = r.json().get('steam_id', None)
                
                if steam_id:
                    account_register = await self.get_account_register()
        
                    # Make sure not a repeat account
                    account = ["steam", str(steam_id)]
                    if account in account_register.get(str(member.id), []):
                        if str(member.id) in account_register:
                            if account not in account_register[str(member.id)]:
                                    account_register[str(member.id)].append(account)
                            else:
                                account_register[str(member.id)] = [account]
                            await self._save_account_register(account_register)
                            msg += " and your steam account has been registered"


                await ctx.send(f"{msg}.")
            else:
                await ctx.send(":x: The upload token you passed is invalid.")
        except Exception as e:
            await ctx.send(f":x: Error setting auth token: {e}")

    @commands.command(aliases=['tokencheck'])
    async def tokenCheck(self, ctx):
        member = ctx.author
        token = await self._get_member_bc_token(member)
        if token:
            await ctx.send(f"Your token: {token}")
        else:
            await ctx.send(":(")

    @commands.command(aliases=['clearMyBCAuthKey'])
    async def clearMyBCAuthToken(self, ctx):
        """Sets the Auth Key for Ballchasing API requests for the given user.
        """
        member = ctx.message.author
        try:
            try:
                await ctx.message.delete()
            except:
                pass
            await self._save_member_bc_token(member, None)
            await ctx.send(":white_check_mark: {}, your Ballchasing Auth Token has been removed.".format(member.name))
        except:
            await ctx.send(":x: Error clearing auth token.")

    # disabled
    @commands.command(aliases=['setTRNAuthKey'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setTRNAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Tracker Network API requests.

        Note: Tracker Network's Rocket League API has been disabled :x:
        """
        return
        await ctx.message.delete()
        try:
            await self._save_trn_auth_token(ctx.guild, auth_token)
            await ctx.send(":white_check_mark: Guild Tracker Network Auth Token has been set.")
        except:
            await ctx.send(":x: Error setting auth token.")

    @commands.command(aliases=['bcpage', 'mybc', 'bcp', 'getBCPage', 'bcprofile', 'bcpages', 'bcaccs'])
    @commands.guild_only()
    async def bcProfile(self, ctx, member:discord.Member=None):
        """Get the ballchasing pages for registered accounts"""
        if not member:
            member = ctx.author
        linked_accounts = []
        for acc in await self._get_member_accounts(member):
            platform = acc[0]
            plat_id = acc[1]

            latest_replay = await self.get_latest_account_replay(ctx.guild, platform, plat_id)
            player_data = self.get_player_data_from_replay(latest_replay, platform, plat_id)
            acc_player_name = player_data.get('name')

            linked_accounts.append(f"[{platform} | {acc_player_name}](https://ballchasing.com/player/{platform}/{plat_id})")
        
        all_accounts_linked = " - " + "\n - ".join(linked_accounts)

        accounts_embed = discord.Embed(
            title = f"{member.nick if member.nick else member.name}'s Accounts",
            color = discord.Color.blue() if linked_accounts else discord.Color.red(),
            description = all_accounts_linked if linked_accounts else "No accounts have been registered."
        )
        await ctx.send(embed=accounts_embed)

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
        initial_id = identifier
        # Check platform
        platform = platform.lower()
        if platform not in ['steam', 'xbox', 'ps4', 'ps5', 'epic']:
            await ctx.send(":x: \"{}\" is an invalid platform".format(platform))
            return False
        
        if not await self.get_bc_auth_token(ctx.guild):
            return await ctx.send(":x: An admin must register a ballchasing auth token to enable memebers to register accounts.")

        member = ctx.message.author
        valid_account = await self._validate_account(ctx, platform, identifier)
        # Tracker Network down
        # if not valid_account:
        #     if await self._get_trn_auth_token(ctx.guild):
        #         identifier = await self._trn_id_lookup(ctx.guild, platform, identifier)
        #         valid_account = await self._validate_account(ctx, platform, identifier)
        #     else:
        #         valid_account = False

        if valid_account:
            username, appearances = valid_account
        else:
            # here
            # message = ":x: No ballchasing replays found for user: **{identifier}** ({platform}) ".format(identifier=initial_id, platform=platform)
            # if platform == 'epic':
            #     message += "\nTry finding the ballchasing ID for this epic account by searching for the account manually."
            # await ctx.send(message)
            # return False
            prompt = "It appears that no games have been played on this account. Would you like to add it anyways?"
            prompt += "\n_Warning: This may cause issues if the account does not exist_"
            nvm_message = "Registration cancelled."
            if await self._react_prompt(ctx, prompt, nvm_message):
                account_register = await self.get_account_register()
                if str(member.id) in account_register:
                    if [platform, identifier] not in account_register[str(member.id)]:
                        account_register[str(member.id)].append([platform, identifier])
                else:
                    account_register[str(member.id)] = [[platform, identifier]]
                await self._save_account_register(account_register)
                await ctx.send("Done.")
            return

        account_register = await self.get_account_register()
        
        # Make sure not a repeat account
        if ["steam", str(identifier)] in account_register.get(str(member.id), []):
            await ctx.send("{}, you have already registered this account.".format(member.mention))
            return False

        # React to confirm account registration
        appearances = "10000+" if str(appearances) == "10000" else appearances
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
        await self._save_account_register(account_register)
        await ctx.send("Done")

    @commands.command(aliases=['rmaccount', 'removeAccount'])
    @commands.guild_only()
    async def unregisterAccount(self, ctx, platform, identifier=None):
        remove_accs = []
        account_register = await self.get_account_register()
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
        
        await self._save_account_register(account_register)
        await ctx.send(":white_check_mark: Removed **{}** account(s).".format(count))

    @commands.command(aliases=['rmaccounts', 'clearaccounts', 'clearAccounts'])
    @commands.guild_only()
    async def unregisterAccounts(self, ctx):
        """Unlinks registered account for ballchasing requests."""
        account_register = await self.get_account_register(ctx.guild)
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
        """View all accounts that have been registered to with your discord account in this guild."""
        member = ctx.message.author
        accounts = await self._get_member_accounts(member)
        if not accounts:
            await ctx.send("{}, you have not registered any accounts.".format(member.mention))
            return

        show_accounts = "{}, you have registered the following accounts:\n - ".format(member.mention) + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in accounts)
        await ctx.send(show_accounts)

    @commands.command(aliases=['addMemberAccount', 'addmemberaccount', 'addmemberacc'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def registerMemberAccount(self, ctx, member: discord.Member, platform:str, identifier:str):
        """Allows user to register account for ballchasing requests. This may be found by searching your appearances on ballchasing.com

        Examples:
            [p]registerAccount nullidea steam 76561199096013422
            [p]registerAccount noobz xbox e4b17b0000000900
        """
        # Check platform
        platform = platform.lower()
        if platform not in ['steam', 'xbox', 'ps4', 'ps5', 'epic']:
            await ctx.send(":x: \"{}\" is an invalid platform".format(platform))

        if not await self.get_bc_auth_token(ctx.guild):
            return await ctx.send(":x: An admin must register a ballchasing auth token to enable memebers to register accounts.")

        try:
            valid_account = await self._validate_account(ctx, platform, identifier)
        except:
            prompt = "It appears that no games have been played on this account. Would you like to add it anyways?"
            prompt += "\n_Warning: This may cause issues if the account does not exist_"
            nvm_message = "Registration cancelled."
            if await self._react_prompt(ctx, prompt, nvm_message):
                account_register = await self.get_account_register()
                if str(member.id) in account_register:
                    if [platform, identifier] not in account_register[str(member.id)]:
                        account_register[str(member.id)].append([platform, identifier])
                else:
                    account_register[str(member.id)] = [[platform, identifier]]
                await self._save_account_register(account_register)
                await ctx.send("Done.")
                return

        if valid_account:
            username, appearances = valid_account
        
        account_register = await self.get_account_register()
        
        # Make sure not a repeat account
        if str(member.id) in account_register and [platform, identifier] in account_register[str(member.id)]:
            await ctx.send("{}, you have already registered this account.".format(member.mention))
            return False

        # React to confirm account registration
        appearances = "10000+" if str(appearances) == "10000" else appearances
        
        member_name = member.display_name
        
        prompt = "**{username}** ({platform}) appears in **{count}** ballchasing replays.".format(username=username, platform=platform, count=appearances)
        prompt += "\n\nWould you like to register this account for **{}**?".format(member_name)
        nvm_message = "Registration cancelled."
        if not await self._react_prompt(ctx, prompt, nvm_message):
            return False
            
        if str(member.id) in account_register:
            account_register[str(member.id)].append([platform, identifier])
        else:
            account_register[str(member.id)] = [[platform, identifier]]
        
        # Register account
        await self._save_account_register(account_register)
        await ctx.send("Done")
    
    @commands.command(aliases=['getAccounts', 'getRegisteredAccounts', 'getAccountsRegistered', 'viewAccounts', 'showAccounts'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def memberAccounts(self, ctx, *, member: discord.Member):
        """View all accounts that have been registered to with your discord account in this guild."""
        accounts = await self._get_member_accounts(member)
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
        account_register = await self.get_account_register()
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


    async def _get_member_accounts(self, member):
        accs = []
        account_register = await self.get_account_register()
        discord_id = str(member.id)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                accs.append(account)
        return accs

    # Disabled
    async def _trn_id_lookup(self, guild, platform, identifier):
        game = 'rocket-league'
        url = 'https://public-api.tracker.gg/v2/{}/standard/profile'.format(game)

        endpoint = '/{}/{}'.format(platform, urllib.parse.quote(identifier))
        request_url = url + endpoint

        api_key = await self._get_trn_auth_token(guild)
        r = requests.get(request_url, headers={'TRN-Api-Key': api_key})
        if r.status_code != 200:
            return False

        rewards = None
        data = r.json()
        try:
            return data['data']['platformInfo']['platformUserIdentifier']
        except:
            return None

# ballchasing
    # TODO: Update requests to not require guild - auth_token defaults to preloaded data
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

# other commands
    async def get_latest_account_replay(self, guild, platform, plat_id):
        endpoint = '/replays'
        params = [
            'sort-by=replay-date',
            'sort-dir=desc',
            'count=1',
            f'player-id={platform}:{plat_id}'
        ]
        response = await self._bc_get_request(guild, endpoint, params)
        data = response.json()

        try:
            return data['list'][0]
        except:
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
        auth_token = await self.get_bc_auth_token(ctx.guild)
        endpoint = '/replays'
        params = [
            'player-id={platform}:{identifier}'.format(platform=platform, identifier=identifier),
            'count=1'
        ]
        r = await self._bc_get_request(ctx.guild, endpoint, params)
        data = r.json()
        
        appearances = 0
        username = None
        if 'list' in data:
            for team_color in ['blue', 'orange']:
                for game in data['list']:
                    for player in game[team_color]['players']:
                        try:
                            if player['id']['platform'] == platform and player['id']['id'] == identifier:
                                username = player['name']
                                appearances = data['count']
                                break
                        except KeyError:
                            pass
        if username:
            return username, appearances
        return False

    async def _get_steam_id_from_token(self, guild, auth_token=None):
        if not auth_token:
            auth_token = await self.get_bc_auth_token(guild)
        r = await self._bc_get_request(guild, "")
        if r.status_code == 200:
            return r.json()['steam_id']
        return None

    async def _get_steam_ids(self, guild, discord_id):
        discord_id = str(discord_id)
        steam_accounts = []
        account_register = await self.get_account_register(guild)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                if account[0] == 'steam':
                    steam_accounts.append(account[1])
        return steam_accounts

# json db
    async def get_bc_auth_token(self, guild):
        return await self.config.guild(guild).BCAuthToken()
    
    async def _save_bc_auth_token(self, guild, token):
        await self.config.guild(guild).BCAuthToken.set(token)
  
    # TODO: move member tokens from bcMatchGroups to accountManager
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
        if token:
            tokens[str(member.id)] = token
            await self.config.BCTokens.set(tokens)
        else:
            try:
                del tokens[str(member.id)]
                await self.config.BCTokens.set(tokens)
            except:
                pass 

    # region disabled
    async def _get_trn_auth_token(self, guild):
        return await self.config.guild(guild).TRNAuthToken()
    
    async def _save_trn_auth_token(self, guild, token):
        await self.config.guild(guild).TRNAuthToken.set(token)
    # endregion disabled

    async def get_account_register(self):
        return await self.config.AccountRegister()
    
    async def _save_account_register(self, account_register):
        await self.config.AccountRegister.set(account_register)

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
        if token:
            tokens[str(member.id)] = token
            await self.config.BCTokens.set(tokens)
        else:
            try:
                del tokens[str(member.id)]
                await self.config.BCTokens.set(tokens)
            except:
                pass
