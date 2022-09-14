import discord

from redbot.core import Config, commands, checks
from redbot.core.utils.predicates import ReactionPredicate
from redbot.core.utils.menus import start_adding_reactions

defaults = {'TimeZone': 'America/New_York'}


WHITE_X_REACT = "\U0000274E"

class NullyUtil(commands.Cog):
    """Test misc commands for anything!"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=1234567893, force_registration=True)
        self.config.register_guild(**defaults)


    @commands.guild_only()
    @commands.command(aliases=['addEmote', 'addemoji', 'addemote'])
    @checks.admin_or_permissions(manage_guild=True)
    async def addEmoji(self, ctx, emoji, *, emoji_name=None):
        await ctx.send(f"{emoji} is of type {type(emoji)}")
        guild : discord.Guild = ctx.guild
        if len(guild.emojis) >= guild.emoji_limit:
            return await ctx.reply(":x: The guild has already met its emoji limit.")
        
        if not emoji_name:
            emoji_name = emoji.name

        emoji_bytes : bytes = await emoji.read()
        await guild.create_custom_emoji(name=emoji_name, image=emoji_bytes)
        await ctx.reply("Done")

