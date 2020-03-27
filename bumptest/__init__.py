from .bumptest import BumpTest


def setup(bot):
    bot.add_cog(BumpTest(bot))
