import discord
import asyncio
from redbot.core import checks, commands
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.bot import Red
from datetime import datetime, timedelta, date
from string import Template


SHORT_FORMAT = '%H:%M:%S'

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


class BumpTest(commands.Cog):
    """
    Тестовая имитация bump бота.
    **Используйте `[p]bumptest`.**
    """
    __author__ = "MeafQ"
    __version__ = "1.0.0" 

    def __init__(self, bot: Red):
        self.bot = bot
        self.end_date = datetime.now()
        
    
    @checks.admin_or_permissions(administrator=True)
    @commands.command()
    @commands.guild_only()
    async def bumptest(self, ctx):
        """
        Настройки для BumpReward.
        """
        try:
            channel = ctx.channel

            timeleft = get_seconds_left(self.end_date)
            ended = timeleft.total_seconds() <= 0
            if ended:
                formatted = date.strftime(self.end_date, SHORT_FORMAT)
                embed = discord.Embed(description="**Write the code from the image** `(Example:  1234)`")
                embed.set_image(url="https://media.discordapp.net/attachments/672872362953146370/690599775287902329/WPbRpNcyDwdiSd0dCuaX.png")
                await ctx.send(embed=embed)
                
                predicate = MessagePredicate.equal_to("8409", ctx)
                await self.bot.wait_for("message", timeout=30, check=predicate)
                embed = discord.Embed(title="Top Discord Servers", url="https://discordapp.com",
                    description="Server bumped by %s :thumbsup:\r[+1 Bonus point]" % ctx.author.mention)
                await ctx.send(embed=embed)
                self.end_date = get_end_date(1)
            else:
                formatted = strfdelta(timeleft, "%H:%M:%S")
                embed = discord.Embed(description=":alarm_clock: The next Bump for this server will be available in %s \
                    \r :arrows_counterclockwise: The next Bump for your account will be available in 23:59:59" % formatted)
                await ctx.send(embed=embed)
        except asyncio.TimeoutError:
            pass