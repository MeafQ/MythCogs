from .deveval import DevEval


def setup(bot):
    bot.add_cog(DevEval(bot))
