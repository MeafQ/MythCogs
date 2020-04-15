import discord
from redbot.core import checks, commands
from redbot.core.bot import Red



class EmbedCatcher(commands.Cog):
    __author__ = "MeafQ"
    __version__ = "1.0.0" 

    def __init__(self, bot: Red):
        self.bot = bot

        
    @commands.Cog.listener()
    async def on_message(self, ctx):
        channel = ctx.channel
        if channel.type.value != 0:
            return
        author = ctx.author
        if not author.bot:
            return
        if author.id == 464272403766444044:
            embed = get_embed(ctx)
            if embed is not None:
                print(embed.to_dict())


def get_embed(message):
    embeds = message.embeds
    if embeds:
        return embeds[0]
    return None
        