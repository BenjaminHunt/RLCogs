import abc
import discord
import asyncio
import urllib.parse
import operator

from redbot.core import Config
from redbot.core import commands
from redbot.core import checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {"RoleRanges": {}, "LogChannel": None, "Players": {}, "Results": []}
verify_timeout = 30
k_factor = 30

class SixMansElo(commands.Cog):
    """Manages aspects of Ballchasing Integrations with RSC"""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)
        self.players = []
        self.six_mans_cog = bot.get_cog("SixMans")

        try:
            self.observe_six_mans()
        except:
            pass
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setLogChannel(self, ctx, log_channel: discord.TextChannel):
        """Sets the channel where all transaction messages will be posted"""
        await self._save_log_channel(ctx.guild, log_channel.id)
        await ctx.send("Done")
    
    @commands.guild_only()
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsetLogChannel(self, ctx):
        """Sets the channel where all transaction messages will be posted"""
        await self._save_log_channel(ctx.guild, None)
        await ctx.send("Done")
    
    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPlayers(self, ctx, *players_to_add):
        """Add the players provided to the player list.

        Arguments:

        players_to_add -- One or more players in the following format:
        ```
        "['<player_id>','<wins>', '<losses>', '<elo_rating>']"
        ```
        Each player should be separated by a space.

        Examples:
        ```
        [p]addPlayers "['123456789','2', '1', '1000']"
        [p]addPlayers "['123456789','2', '1', '1000']" "['987654321','1', '2', '950']"
        ```
        """
        addedCount = 0
        try:
            for playerStr in players_to_add:
                player = ast.literal_eval(playerStr)
                playerAdded = await self._add_player(ctx, *player)
                if playerAdded:
                    addedCount += 1
                else:
                    await ctx.send("Error adding player: {0}".format(repr(player)))
        finally:
            await ctx.send("Added {0} players(s).".format(addedCount))
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addPlayer(self, ctx, member: discord.Member, wins: int, losses: int, elo_rating: int):
        """Add a single player and their info to the file system."""
        playerAdded = await self._add_player(ctx, member, wins, losses, elo_rating)
        if(playerAdded):
            await ctx.send("Done.")
        else:
            await ctx.send("Error adding player: {0}".format(member.name))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def clearEloRoles(self, ctx):
        await self._save_role_ranges(ctx.guild, {})
        await ctx.send("Done")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def addEloRole(self, ctx, role: discord.Role, min_elo: float, max_elo: float):
        # Save Elo Role
        await self._register_role_range(role, min_elo, max_elo)
        
        # Log Role addition
        log_channel = await self._get_log_channel(role.guild)
        
        # Add roles to appropriate existing players
        for player in self.players:
            if player.elo_rating >= min_elo and player.elo_rating <= max_elo:
                await player.member.add_roles(role)
                if log_channel:
                    message = "{} has had their roles updated!".format(player.member.mention)
                    message += "\n\t - **Added:** {}".format(role.name)
        await ctx.send("Done.")

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def getEloRanges(self, ctx):
        elos = await self._get_role_ranges(ctx.guild)

        elo_roles = [guild.get_role(int(role_id)) for role_id in elos.keys()]
        elo_roles = sorted(elo_roles, key=operator.attrgetter('position'))

        out = "Elo Ranges"
        for role_id in elo_roles:
            elo_range = elos[str(role_id)]
            role = ctx.guild.get_role(int(role_id))
            out += "\n- {}: [{}-{}]".format(role.mention, elo_range[0], elo_range[1])
        
        await ctx.send(out)

    @commands.guild_only()
    @commands.Cog.listener("on_guild_role_delete")
    async def on_guild_role_delete(self, role):
        await self._unregister_elo_role(role)

## OBSERVER PATTERN IMPLEMENTATION ########################

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def observeForElo(self, ctx):
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

    def observe_six_mans(self):
        self.six_mans_cog = self.bot.get_cog("SixMans")
        self.six_mans_cog.add_observer(self)

    async def update(self, game):
        await game.textChannel.send("State: {}".format(game.game_state))
        if game.game_state == "game over":
            await self._finish_series(game)
            

###########################################################

    async def _finish_series(self, game, update_roles=True):
        if not game.winner or game.winner.lower() not in ['blue', 'orange']:
            return False 

        # get blue avg elo
        blue_players = [self._get_player_by_id(blue_player) for blue_player in game.blue]
        orange_players = [self._get_player_by_id(orange_player) for orange_player in game.orange]

        # remove/ignore players who aren't found
        while None in blue_players:
            blue_players.remove(None)
        while None in orange_players:
            orange_players.remove(None)
        
        avg_blue_elo = self._get_avg_team_rating(blue_players)
        avg_orange_elo = self._get_avg_team_rating(orange_players)

        # determine winner
        blue_wins = 0
        orange_wins = 0
        if game.winner.lower() == 'blue':
            blue_wins = 1
        else:
            orange_wins = 1

        # calculate new team elo
        new_blue_elo, new_orange_elo, = self._update_elo(elo1, elo2, blue_wins/(blue_wins + orange_wins))

        blue_diff = new_blue_elo - avg_blue_elo
        orange_diff = new_orange_elo - avg_orange_elo

        # apply new elo on players
        for player in blue_players:
            self._update_player_info(player, blue_wins, orange_wins, player.elo_rating + blue_diff)
        for player in orange_players:
            self._update_player_info(player, orange_wins, blue_wins, player.elo_rating + orange_diff)
        
        await self._save_players(blue_players + orange_players)

        if update_roles:
            for player in blue_players + orange_players:
                await self._reassign_elo_roles(player.member, player.elo_rating)

#region Adjust Player Ratings
    async def _reassign_elo_roles(self, player: discord.Member, player_elo: int=None):
        if player_elo == None:
            elo = await self._get_player_rating(player)
        
        log_channel = await self._get_log_channel(player.guild)

        guild = player.guild
        all_elo_roles = await self._get_sm_roles(guild)
        remove_roles = list(set(all_elo_roles) & set(player.roles))
        add_elo_roles = await self._get_elo_roles(elo)

        keep_roles = list(set(add_elo_roles) & set(remove_roles))
        for role in keep_roles:
            add_elo_roles.remove(role)
            remove_roles.remove(role)
        
        if add_elo_roles or remove_roles:
            try:
                await player.remove_roles(*remove_roles)
                await player.add_roles(*add_elo_roles)

                # return add_elo_roles, remove_roles
                if log_channel:
                    message = "{} has had their roles updated!".format(player.mention)
                    if add_elo_roles:
                        message += "\n\t - **Added:** {}".format(', '.join(role.name for role in add_elo_roles))
                    if remove_roles:
                        message += "\n\t - **Removed:** {}".format(', '.join(role.name for role in remove_roles))
            except: 
                return False

    def _get_avg_team_rating(self, players):
        total = 0
        for member in players:
            total += player.elo_rating
        
        return total/len(players)

    async def _get_player_rating(self, player: discord.Member):
        pass 

    def _update_player_info(self, player, new_wins, new_losses, new_elo_rating):
        player.wins += new_wins
        player.losses += new_losses
        player.elo_rating = new_elo_rating

    async def _get_elo_roles(self, guild: discord.Guild, elo):
        elo_roles = []
        for role, elo_range in (await self._get_role_ranges(guild)):
            min_elo = elo_range[0]
            max_elo = elo_range[1]
            if elo >= min_elo and elo <= max_elo:
                elo_roles.append(role)
        return elo_roles

    async def _get_player_sm_roles(self, player: discord.Member):
        return list(set(await self._get_sm_roles(member.guild)) & set(player.roles))

    def _update_elo(self, elo1: int, elo2: int, result: float):
        """Calculates and returns the new Elo ratings for the two elo ratings based on their match results and the K-factor.
        Result param should be a decimal between 0 and 1 relating to the match results for elo1, i.e. a result of 1 
        means player 1 won all the games in the match, a result of .25 means player 1 won 25% of the games in the match, etc."""
        elo_dif = int(player_1_elo) - int(player_2_elo)
        exponent = -1 * (elo_dif / 100)
        expectation = 1 / (1 + pow(10, exponent))
        new_elo1 = round(int(elo1) + (k_factor * (result - expectation)))
        new_elo2 = round(int(elo2) + (k_factor * ((1 - result) - (1 - expectation))))
        return new_elo1, new_elo2

#endRegion Adjust Player Ratings

#region SixMansRoles settings
    async def _register_role_range(self, role: discord.Role, min_elo: float, max_elo: float):
        if min_elo > max_elo:
            return False 
        guild = role.guild
        role_ranges = await self._get_role_ranges(guild)
        channel = guild.get_channel(816122799679864902)
        await channel.send("> {}".format(role_ranges))
        role_ranges[str(role.id)] = [min_elo, max_elo]
        await self._save_role_ranges(guild, role_ranges)

    async def _unregister_elo_role(self, role: discord.Role):
        guild = role.guild
        role_ranges = await self._get_role_ranges(guild)
        if str(role.id) in role_ranges:
            del role_ranges[str(role.id)]
            await self._save_role_ranges(role_ranges)
            if log_channel:
                await log_channel.send("The Six Mans role **{}** has been removed.".format(role.name))

    async def _get_role_range(self, role: discord.Role):
        guild = role.guild
        role_ranges = await self._get_role_ranges(guild)
        for sm_role_id, role_range in role_ranges.items():
            sm_role = guild.get_role(int(sm_role_id))
            if role == sm_role:
                return role_range[0], rolerange[1]
        return None
    
    async def _get_sm_roles(self, guild: discord.Guild):
        return [guild.get_role(int(role_id)) for role_id in (await self._get_role_ranges(guild)).keys()]

    async def _get_role_ranges(self, guild: discord.Guild):
        return await self.config.guild(guild).RoleRanges()

    async def _save_role_ranges(self, guild: discord.Guild, role_ranges):
        await self.config.guild(guild).RoleRanges.set(role_ranges)

#endregion SixMansRoles settings

#region uncategoriezed helpers
    def _get_player_by_id(self, member_id: discord.Member, players=None):
        if not players:
            players = self.players
        for player in players:
            if player.member.id == member_id:
                return player
        return None

    async def _add_player(self, ctx, member, wins, losses, elo_rating, assign_elo_roles=True):
        await self.load_players(ctx)
        players = self.players
        
        wins = int(wins)
        losses = int(losses)
        elo_rating = int(elo_rating)

        # Validation of input
        # There are other validations we could do, but don't
        #     - that there aren't extra args for example
        errors = []
        if not isinstance(member, discord.Member):
            try:
                member = await commands.MemberConverter().convert(ctx, member)
            except:
                errors.append("Member {} not found.".format(member))
        if wins < 0:
            errors.append("Wins cannot be a negative number.")
        if losses < 0:
            errors.append("Losses cannot be a negative number.")
        if not elo_rating:
            errors.append("Elo rating not found.")
        if errors:
            await ctx.send(":x: Errors with input:\n\n  "
                               "* {0}\n".format("\n  * ".join(errors)))
            return

        try:
            player = Player(member, wins, losses, elo_rating, -1)
            players.append(player)
            if add_elo_roles:
                await self._reassign_elo_roles(member, elo_rating)
        except:
            return False
        await self._save_players(ctx, players)
        return True

    async def _remove_player(self, ctx, member: discord.Member):
        await self.load_players(ctx)
        players = self.players

        try:
            player = await self.get_player_by_id(self.players, member.id)
            if not player:
                await ctx.send("{0} does not seem to be a current player.".format(member.name))
                return False
            players.remove(player)
        except ValueError:
            await ctx.send("{0} does not seem to be a current player.".format(member.name))
            return False
        await self._save_players(ctx, players)
        return True

#endregion uncategorized helpers

#region load/save methods
    async def _save_log_channel(self, guild, channel_id):
        await self.config.guild(guild).LogChannel.set(channel_id)

    async def _get_log_channel(self, guild: discord.Guild):
        guild.get_channel(await self.config.guild(guild).LogChannel())

    async def load_players(self, ctx, force_load = False):
        players = await self._players(ctx)
        player_list = []
        remove_player = False
        for value in players.values():
            member = ctx.guild.get_member(value["Id"])
            if not member:
                # Member not found in server, don't add to list of players and 
                # re-save list at the end to ensure they get removed
                remove_player = True
                continue
            wins = value["Wins"]
            losses = value["Losses"]
            elo_rating = value["EloRating"]
            # temp_rating = value["TempRating"]
            player = Player(member, wins, losses, elo_rating)
            player_list.append(player)

        self.players = player_list
        if remove_player:
            await self._save_players(ctx, self.players)

    async def _players(self, ctx):
        return await self.config.guild(ctx.guild).Players()

    async def _save_players(self, ctx, players):
        player_dict = {}
        for player in players:
            player_dict[player.member.id] = player._to_dict()
        await self.config.guild(ctx.guild).Players.set(player_dict)

#endregion

class Player:
    def __init__(self, member: discord.Member, wins: int, losses: int, elo_rating: int):
        self.member = member
        self.wins = wins
        self.losses = losses
        self.elo_rating = elo_rating

    def _to_dict(self):
        return {
            "Id": self.member.id,
            "Wins": self.wins,
            "Losses": self.losses,
            "EloRating": self.elo_rating,
            "TempRating": self.temp_rating
        }