from .bcMatchGroups import BCMatchGroups
from .config import config

def setup(bot):
    bot.add_cog(BCMatchGroups(bot))