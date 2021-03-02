from .bcSixMans import BCSixMans
from .config import config

def setup(bot):
    bot.add_cog(BCSixMans(bot))