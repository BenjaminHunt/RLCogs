from .accountManager import AccountManager
from .config import config

def setup(bot):
    bot.add_cog(AccountManager(bot))