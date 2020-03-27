from .bumpreward import BumpReward


def setup(bot):
    bot.add_cog(BumpReward(bot))
