from .rankCheck import RankCheck
from .config import config

def setup(bot):
    bot.add_cog(RankCheck(bot))
    