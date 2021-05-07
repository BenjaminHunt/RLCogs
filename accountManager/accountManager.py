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
global_defaults = {"AccountRegister": {}}
verify_timeout = 30

class AccountManager(commands.Cog):
    """Manages aspects of Ballchasing Integrations with RSC"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_global(**global_defaults)
        self.config.register_guild(**defaults)
        # TODO: self.token = await self._auth_token # load on_ready

    @commands.command(aliases=['setBCAuthKey'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setBCAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Ballchasing API requests.
        Note: Auth Token must be generated from the Ballchasing group owner
        """
        try:
            await self._save_bc_auth_token(ctx, auth_token)
            await ctx.send("Done.")
        except:
            await ctx.send(":x: Error setting auth token.")

    @commands.command(aliases=['setTRNAuthKey'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def setTRNAuthToken(self, ctx, auth_token):
        """Sets the Auth Key for Tracker Network API requests.
        """
        try:
            await self._save_trn_auth_token(ctx, auth_token)
            await ctx.send("Done.")
        except:
            await ctx.send(":x: Error setting auth token.")

    @commands.command(aliases=['bcpage', 'mybc', 'bcp', 'getBCPage', 'bcprofile', 'bcpages'])
    @commands.guild_only()
    async def bcProfile(self, ctx):
        """Get the ballchasing pages for registered accounts"""
        member = ctx.message.author
        lines = []
        for acc in await self._get_member_accounts(member):
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
        valid_account = await self._validate_account(ctx, platform, identifier)

        if valid_account:
            username, appearances = valid_account
        else:
            found = False
            identifier = await self._trn_id_lookup(ctx.guild, platform, identifier)
            if identifier:
                valid_account = await self._validate_account(ctx, platform, identifier)
                if valid_account:
                    username, appearances = valid_account
                    found = True
            
            if not found:
                await ctx.send(":x: No ballchasing replays found for user: **{identifier}** ({platform}) ".format(identifier=identifier, platform=platform))
                return False

        account_register = await self._get_account_register()
        
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
        await self._save_account_register(account_register)
        await ctx.send("Done")

    @commands.command(aliases=['rmaccount', 'removeAccount'])
    @commands.guild_only()
    async def unregisterAccount(self, ctx, platform, identifier=None):
        remove_accs = []
        account_register = await self._get_account_register()
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
        account_register = await self._get_account_register(ctx.guild)
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
        accounts = await self._get_member_accounts(member)
        if not accounts:
            await ctx.send("{}, you have not registered any accounts.".format(member.mention))
            return

        show_accounts = "{}, you have registered the following accounts:\n - ".format(member.mention) + "\n - ".join("{}: {}".format(acc[0], acc[1]) for acc in accounts)
        await ctx.send(show_accounts)

    @commands.command(aliases=['getAccounts', 'getRegisteredAccounts', 'getAccountsRegistered', 'viewAccounts', 'showAccounts'])
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def memberAccounts(self, ctx, *, member: discord.Member):
        """view all accounts that have been registered to with your discord account in this guild."""
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
        account_register = await self._get_account_register()
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
        account_register = await self._get_account_register()
        discord_id = str(member.id)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                accs.append(account)
        return accs

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
        print(data['data']['platformInfo'])
        try:
            return data['data']['platformInfo']['platformUserIdentifier']
        except:
            return None


    async def _bc_get_request(self, guild, endpoint, params=[], auth_token=None):
        if not auth_token:
            auth_token = await self._get_bc_auth_token(guild)
        
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
            auth_token = await self._get_bc_auth_token(guild)
        
        url = 'https://ballchasing.com/api'
        url += endpoint
        params = '&'.join(params)
        if params:
            url += "?{}".format(params)
        
        return requests.post(url, headers={'Authorization': auth_token}, json=json, data=data, files=files)

    async def _bc_patch_request(self, guild, endpoint, params=[], auth_token=None, json=None, data=None):
        if not auth_token:
            auth_token = await self._get_bc_auth_token(guild)

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
        auth_token = await self._get_bc_auth_token(ctx.guild)
        endpoint = '/replays'
        params = [
            'player-id={platform}:{identifier}'.format(platform=platform, identifier=identifier),
            'count=1'
        ]
        r = await self._bc_get_request(ctx.guild, endpoint, params)
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
            auth_token = await self._get_bc_auth_token(guild)
        r = await self._bc_get_request(guild, "")
        if r.status_code == 200:
            return r.json()['steam_id']
        return None

    async def _get_steam_ids(self, guild, discord_id):
        discord_id = str(discord_id)
        steam_accounts = []
        account_register = await self._get_account_register(guild)
        if discord_id in account_register:
            for account in account_register[discord_id]:
                if account[0] == 'steam':
                    steam_accounts.append(account[1])
        return steam_accounts

    # json db
    async def _get_bc_auth_token(self, guild):
        return await self.config.guild(guild).BCAuthToken()
    
    async def _save_bc_auth_token(self, ctx, token):
        await self.config.guild(ctx.guild).BCAuthToken.set(token)
  
    async def _get_trn_auth_token(self, guild):
        return await self.config.guild(guild).TRNAuthToken()
    
    async def _save_trn_auth_token(self, ctx, token):
        await self.config.guild(ctx.guild).TRNAuthToken.set(token)

    async def _get_account_register(self):
        return await self.config.AccountRegister()
    
    async def _save_account_register(self, account_register):
        await self.config.AccountRegister.set(account_register)
