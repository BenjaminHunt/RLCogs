from .rankCheck import RankCheck

def setup(bot):
    bot.add_cog(RankCheck(bot))
    