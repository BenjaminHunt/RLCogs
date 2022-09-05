from .testCog import TestCog

def setup(bot):
    bot.add_cog(TestCog(bot))