from .embedcatcher import EmbedCatcher


def setup(bot):
    bot.add_cog(EmbedCatcher(bot))
