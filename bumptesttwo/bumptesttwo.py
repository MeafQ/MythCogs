import discord
import asyncio
from redbot.core import checks, commands
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.bot import Red
from datetime import datetime, timedelta, date
from string import Template


def get_end_date(cooldown):
    now = datetime.now()
    end_date = now + timedelta(minutes=cooldown)
    return end_date

def get_seconds_left(end_date):
    now = datetime.now()
    diff = end_date - now
    return diff

class DeltaTemplate(Template):
    delimiter = "%"

def strfdelta(tdelta, fmt):
    d = {"D": tdelta.days}
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    d["H"] = '{:02d}'.format(hours)
    d["M"] = '{:02d}'.format(minutes)
    d["S"] = '{:02d}'.format(seconds)
    t = DeltaTemplate(fmt)
    return t.substitute(**d)


class BumpTestTwo(commands.Cog):
    """
    Тестовая имитация bump бота.
    **Используйте `[p]bumptest`.**
    """
    __author__ = "MeafQ"
    __version__ = "1.0.0" 

    def __init__(self, bot: Red):
        self.bot = bot
        self.end_date = datetime.now()
        
    
    @commands.command()
    @commands.guild_only()
    async def uptest(self, ctx):
        """
        Тестовая имитация bump бота.
        """
        try:
            channel = ctx.channel

            timeleft = get_seconds_left(self.end_date)
            ended = timeleft.total_seconds() <= 0
            if ended:
                embed = discord.Embed(timestamp=datetime.now(), title="Сервер Up", description="Нравится сервер?\nОцени его на **сайте**!")
                embed.set_footer(text=ctx.author.name + "#" + ctx.author.discriminator)
                await ctx.send(embed=embed)
                self.end_date = get_end_date(1)
            else:
                formatted = strfdelta(timeleft, "%H:%M:%S")
                embed = discord.Embed(timestamp=datetime.now())
                embed.set_author(name="🕜 %s до следующего Up" % formatted)
                embed.set_footer(text=ctx.author.name + "#" + ctx.author.discriminator)
                await ctx.send(embed=embed)
        except asyncio.TimeoutError:
            pass