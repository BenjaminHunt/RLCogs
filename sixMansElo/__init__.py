from .sixMansElo import SixMansElo
from .config import config

def setup(bot):
    bot.add_cog(SixMansElo(bot))