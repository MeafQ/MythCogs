import asyncio
import discord
from discord.ext import tasks
from discord.utils import get
from redbot.core import Config, checks, bank, commands
from redbot.core.data_manager import bundled_data_path
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from redbot.core.bot import Red
import logging
import humanize
from .utils import *
from .settings import *


log = logging.getLogger("red.mythcogs.bumpreward")

DEFAULT_GUILD = {
    "channel": None,
    "message": None,
    "user": None,
    "bots": {},
    "balance": [],
    "amount": 0
}

MSG_UNKOWN_USER = "⛔ Неизвестный пользователь"
MSG_READY = "Готово"
MSG_NO_DATA = "Нет данных"
MSG_NO_BOTS = "Нет поддерживаемых ботов."
MSG_NO_CHANNEL = "Не создан специальный канал."
    

class BumpReward(commands.Cog):
    """
    Автозачисление валюты за bump сервера.
    **Используйте `[p]bumpreward`.**
    """
    __author__ = "MeafQ"
    __version__ = "1.1.1" 

    def __init__(self, bot: Red):
        humanize.i18n.activate("ru_MY", path=str(bundled_data_path(self)))
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8604591552404110, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self.bot.loop.create_task(self.init())
        self.cache = {}
        
    def cog_unload(self):
        for guild in self.bot.guilds:
            self.cancel_task(guild)


    @commands.guild_only()
    @commands.bot_has_permissions(
        manage_messages=True, 
        manage_channels=True, 
        manage_roles=True,
        send_messages=True, 
        read_message_history=True,
        embed_links=True,
        add_reactions=True)
    @commands.group(invoke_without_command=True)
    async def bumpreward(self, ctx):
        """
        Настройки для BumpReward.
        """
        pass
        

    @commands.admin()
    @bumpreward.command()
    async def channel(self, ctx):
        """
        Создание специального канала.
        """
        guild = ctx.guild
        obj_bots = await self.update_bots(guild)
        if not obj_bots:
            await send_embed(ctx.channel, MSG_NO_BOTS)
            return

        channel = self.cache[guild.id]["channel"]
        if channel is not None:
            await channel.delete()
        
        overwrites = set_bots_permissions(obj_bots)
        channel = await guild.create_text_channel("bumps", overwrites=overwrites)
        await self.set_config(guild, "channel", value=channel)
        await self.set_config(guild, "user", value=ctx.author)
        self.create_task(guild)
        await add_reaction(ctx)


    @commands.admin()
    @bumpreward.command()
    async def bots(self, ctx):
        """
        Обновление на сервере списка поддерживаемых ботов.
        """
        guild = ctx.guild
        channel = self.cache[guild.id]["channel"]
        if channel is None:
            await send_embed(ctx.channel, MSG_NO_CHANNEL)
        obj_bots = await self.update_bots(guild)
        if not obj_bots:
            await send_embed(ctx.channel, MSG_NO_BOTS)
            return
        overwrites = set_bots_permissions(obj_bots, channel.overwrites)
        await channel.edit(overwrites=overwrites)
        await add_reaction(ctx)

    async def update_bots(self, guild):
        old_bots = self.cache[guild.id]["bots"]
        new_bots = {}
        obj_bots = []
        for key in BOTS:
            bot = guild.get_member(int(key))
            if bot is not None:
                obj_bots.append(bot)
                new_bots[key] = old_bots.get(key)
        await self.set_config(guild, "bots", value=new_bots)
        return obj_bots


    @commands.admin()
    @bumpreward.command()
    async def amount(self, ctx, *, number : int):
        """
        Изменение размера награды.
        """
        await self.set_config(ctx.guild, "amount", value=number)
        await add_reaction(ctx)


    @commands.admin()
    @bumpreward.command(name="set")
    async def cmd_set(self, ctx, user : discord.Member, *, number : int):
        """
        Прибавить или убавить баланса пользователя.
        **-** Ноль сбрасывает баланс.
        """
        await self.change_balance(ctx.guild, user, number)
        await add_reaction(ctx)

    async def change_balance(self, guild, user, amount):
        old_storage = await self.config.guild(guild).balance()
        for i in range(len(old_storage)):
            if old_storage[i][0] == user.id:
                if amount != 0:
                    amount = max(old_storage[i][1] + amount, 0)
                elif self.cache[guild.id]["amount"] == 0:
                    return
                old_storage[i][1] = amount
                break
        else:
            old_storage.append((user.id, amount))

        new_storage = sorted(old_storage, key=lambda tup: tup[1], reverse=True)

        message = self.cache[guild.id]["message"]
        embed = get_embed(message)
        if new_storage:
            embed.description = get_leaderboard(guild, new_storage, first=True, page=10)
        await message.edit(embed=embed)

        await self.config.guild(guild).balance.set(new_storage)


    @commands.cooldown(rate=2, per=300, type=commands.BucketType.user)
    @bumpreward.command()
    async def balance(self, ctx, author: discord.Member = None):
        """
        Список баланса пользователей.
        """
        if author is None:
            author = ctx.author
        guild = ctx.guild

        storage  = await self.config.guild(guild).balance()
        if not storage:
            return await send_embed(ctx, "Нет пользователей в списке.")

        pages, author_page = get_leaderboard(guild, storage, author)

        await menu(ctx, pages, DEFAULT_CONTROLS, page=author_page, timeout=15)


    @commands.Cog.listener()
    async def on_message(self, ctx):
        channel = ctx.channel
        if channel.type.value != 0:
            return
        guild = ctx.guild
        try:
            if channel != self.cache[guild.id]["channel"]:
                return
        except KeyError:
            return
        author = ctx.author
        if author.bot:
            if author == self.bot.user and self.cache[guild.id]["waiting"]:
                self.cache[guild.id]["waiting"] = False
                return

            bot_id = str(author.id)
            if bot_id in self.cache[guild.id]["bots"]:
                embed = get_embed(ctx)
                if embed is not None:
                    bot_config = BOTS[bot_id]

                    try:
                        msg_type, result = get_message_type(embed, bot_config["parser"])
                        if msg_type == "success":
                            user = get_member(guild, *result)
                            if user is not None:
                                await self.set_config(ctx.guild, "user", value=user)
                                await self.change_balance(guild, user, self.cache[guild.id]["amount"])
                            else:
                                await self.set_config(ctx.guild, "user", value=None)
                                log.error("Bot_ID: %s\nUnable to parse a user: %s" % (bot_id, embed.to_dict()))
                            await self.captcha_checker(guild, bot_id)
                            end_date = get_end_date(minutes=bot_config["cooldown"])
                        elif msg_type == "cooldown":
                            end_date = get_end_date(*[int(x) for x in result])
                        elif msg_type == "captcha":
                            self.captcha_task(guild, bot_id, ctx)
                            return
                        await self.set_channel_send_messages(guild, channel, False)
                        await self.set_config(ctx.guild, "bots", bot_id, value=end_date)
                        self.update_task(guild)
                    except UnknownType:
                        log.critical("Bot_ID: %s\nEncountered unknown message type: %s" % (bot_id, embed.to_dict()))
        await asyncio.sleep(1)
        try:
            await ctx.delete()
        except discord.NotFound:
            pass


    async def message_task(self, guild):
        channel = self.cache[guild.id]["channel"]
        message = self.cache[guild.id]["message"]
        user = self.cache[guild.id]["user"]
        bots = self.cache[guild.id]["bots"]

        if message is None:
            embed = discord.Embed()
        else:
            embed = get_embed(message)


        if user is not None:
            embed.set_footer(text=user.display_name, icon_url=user.avatar_url)
        else:
            embed.set_footer(text=MSG_UNKOWN_USER)
            
        commands = sort_commands(bots)
        while(commands):
            not_finished = {}
            for index, info in commands.items():
                cooldown = info["cooldown"]
                if info["cooldown"] is not None:
                    if cooldown <= 0:
                        if not self.cache[guild.id]["permission"]:
                            await self.set_channel_send_messages(guild, channel, None)
                        text = box(f"+ {MSG_READY:12}", lang="diff")
                    else:
                        human_time = humanize.naturaldelta(max(cooldown % 3600, 60))
                        if (cooldown // 3600) >= 1:
                            human_time = humanize.naturaldelta(cooldown) + " " + human_time
                        text = box(f"{human_time:14}", lang="py")
                        info["cooldown"] -= DELAY
                        not_finished[index] = info
                else:
                    text = box(f"- {MSG_NO_DATA:12}", lang="diff")
                name = "**`" + info["name"] + "`**"
                try:
                    embed.set_field_at(index=index, name=name, value=text, inline=True)
                except IndexError:
                    embed.add_field(name=name, value=text, inline=True)
            commands = not_finished
            try:
                await message.edit(embed=embed, suppress=False)
            except (discord.HTTPException, AttributeError):
                self.cache[guild.id]["waiting"] = True
                storage = await self.config.guild(guild).balance()
                if storage:
                    embed.description = get_leaderboard(guild, storage)[0][0]
                message = await channel.send(embed=embed)
                await self.set_config(guild, "message", value=message)

            await asyncio.sleep(DELAY)
            embed = get_embed(message)


    async def set_channel_send_messages(self, guild, channel, lock):
        overwrite = channel.overwrites_for(guild.default_role)
        overwrite.send_messages = lock
        await channel.set_permissions(guild.default_role, overwrite=overwrite)
        self.cache[guild.id]["permission"] = lock

    def captcha_task(self, guild, bot_id, ctx):
        self.cache[guild.id]["captcha"].setdefault(bot_id, []).append(ctx)
        async def captcha_delay(self, guild, bot_id):
            await asyncio.sleep(CAPTCHA_DELAY)
            if ctx in self.cache[guild.id]["captcha"][bot_id]:
                self.cache[guild.id]["captcha"][bot_id].remove(ctx)
                try:
                    await ctx.delete()
                except discord.NotFound:
                    pass
        self.bot.loop.create_task(captcha_delay(self, guild, bot_id))

    async def captcha_checker(self, guild, bot_id):
        captcha = self.cache[guild.id]["captcha"].get(bot_id, [])
        if captcha:
            for message in captcha:
                try:
                    await message.delete()
                except discord.NotFound:
                    pass
            self.cache[guild.id]["captcha"][bot_id] = []

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        if channel == self.cache[guild.id]["channel"]:
            await self.set_config(guild, "channel", value=None)
            await self.set_config(guild, "message", value=None)
            self.cancel_task(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        del self.cache[guild.id]
        self.cancel_task(guild)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.guild_startup(guild)

    async def init(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            await self.guild_startup(guild)

    async def guild_startup(self, guild):
        config = await self.config.guild(guild)()

        self.cache[guild.id] = {
            "task": None,
            "waiting": False,
            "permission": False,
            "captcha": {},
            "bots": config["bots"],
            "amount": config["amount"]
        }
        
        channel = guild.get_channel(config["channel"])
        self.cache[guild.id]["channel"] = channel
        if channel is None:
            await self.config.guild(guild).channel.set(None)
            await self.config.guild(guild).message.set(None)
        else:
            message = await get_message(channel, config["message"])
            self.cache[guild.id]["message"] = message
            if message is None:
                await self.config.guild(guild).message.set(None)
                
            await clear_channel(guild, channel, config["message"])
            self.create_task(guild)

        user = guild.get_member(config["user"])
        self.cache[guild.id]["user"] = user
        if user is None:
            await self.config.guild(guild).user.set(None)

    def create_task(self, guild):
        task = self.bot.loop.create_task(self.message_task(guild))
        self.cache[guild.id]["task"] = task

    def update_task(self, guild):
        self.cancel_task(guild)
        self.create_task(guild)
    
    def cancel_task(self, guild):
        task = self.cache[guild.id]["task"]
        if task is not None:
            task.cancel()

    async def set_config(self, guild, *key, value):
        try:
            await self.config.guild(guild).set_raw(*key, value=value.id)
        except AttributeError:
            await self.config.guild(guild).set_raw(*key, value=value)
        set_in_dict(self.cache[guild.id], key, value)