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
    "bots": {},
    "amount": 1,
    "balance": []
}

MSG_UNKOWN_USER = "⛔ Неизвестный пользователь"
MSG_READY = "Готово"
MSG_NO_DATA = "Нет данных"
MSG_NO_BOTS = "Нет поддерживаемых ботов."
MSG_NO_CHANNEL = "Не создан специальный канал."
MSG_LESS_ONE = "Размер награды не может быть меньше единицы."
MSG_NO_LEADERBOARD = "Нет пользователей в базе данных."
    

class BumpReward(commands.Cog):
    """
    Автозачисление валюты за bump сервера.
    **Используйте `[p]bumpreward`.**
    """
    __author__ = "MeafQ"
    __version__ = "1.2.0" 

    def __init__(self, bot: Red):
        humanize.i18n.activate("ru_MY", path=str(bundled_data_path(self)))
        self.bot = bot
        self.config = Config.get_conf(self, identifier=8604591552404110, force_registration=True)
        self.config.register_guild(**DEFAULT_GUILD)
        self.bot.loop.create_task(self.init())
        self.cache = {}
        
    def cog_unload(self):
        for guild_cache in self.cache.values():
            guild_cache["task"].cancel()
        self.cache.clear()

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
    async def amount(self, ctx, *, amount : int):
        """
        Изменение размера награды.
        """
        if amount <= 0:
            await send_simple_embed(ctx.channel, MSG_LESS_ONE)
            return
        await self.config.guild(ctx.guild).amount.set(amount)
        await add_reaction(ctx)

    @commands.admin()
    @bumpreward.command(name="set")
    async def cmd_set(self, ctx, user : discord.Member, *, amount : int):
        """
        Прибавить или убавить баланса пользователя.
        **-** Ноль сбрасывает баланс.
        """
        await self.change_balance(ctx.guild, user, amount)
        await add_reaction(ctx)

    async def change_balance(self, guild, user, amount):
        old_balance = await self.config.guild(guild).balance()
        for i in range(len(old_balance)):
            if old_balance[i][0] == user.id:
                if amount != 0:
                    amount = max(old_balance[i][1] + amount, 0)
                old_balance[i][1] = amount
                break
        else:
            old_balance.append((user.id, amount))

        new_balance = sorted(old_balance, key=lambda tup: tup[1], reverse=True)
        await self.config.guild(guild).balance.set(new_balance)

        top_10 = get_leaderboard(guild, new_balance)
        await self.update_message(guild, ("description", top_10))

    @commands.cooldown(rate=2, per=300, type=commands.BucketType.user)
    @bumpreward.command()
    async def balance(self, ctx, author: discord.Member = None):
        """
        Список баланса пользователей.
        """
        if author is None:
            author = ctx.author
        guild = ctx.guild

        storage = await self.config.guild(guild).balance()
        if not storage:
            await send_simple_embed(ctx, MSG_NO_LEADERBOARD)
            return

        pages, author_page = get_leaderboard(guild, storage, author, full=True)

        await menu(ctx, pages, DEFAULT_CONTROLS, page=author_page, timeout=15)

    def wait_captcha(self, guild, bot_id, message):
        captchas = self.cache[guild.id]["captchas"][bot_id]
        captchas.append(message)
        async def captcha_delay(self, guild, bot_id):
            await asyncio.sleep(CAPTCHA_DELAY)
            if message in captchas:
                captchas.remove(message)
                await safe_message_delete(message)
        self.bot.loop.create_task(captcha_delay(self, guild, bot_id))

    async def clear_captchas(self, guild, bot_id):
        captchas = self.cache[guild.id]["captchas"][bot_id]
        for message in captchas:
            await safe_message_delete(message)
        captchas.clear()

    def restart_task(self, guild, message):
        self.cache[guild.id]["task"].cancel()
        self.cache[guild.id]["task"] = self.bot.loop.create_task(self.message_task(guild, message))

    def start_task(self, guild, message, bots):
        self.cache[guild.id] = {
            "message": message,

            "bots": strptime_dates(bots),
            "captchas": dict.fromkeys(bots, []),
            "task": self.bot.loop.create_task(self.message_task(guild, message)),

            "waiting": False,
            "lock": False
        }

    def stop_task(self, guild):
        self.cache[guild.id]["task"].cancel()
        del self.cache[guild.id]

    async def config_reset(self, guild):
        await self.config.guild(guild).channel.set(None)
        await self.config.guild(guild).message.set(None)
        await self.config.guild(guild).bots.set({})

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        if guild.id in self.cache:
            if channel == self.cache[guild.id]["channel"]:
                await self.config_reset(guild)
                self.stop_task(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        if guild.id in self.cache:
            await self.config_reset(guild)
            self.stop_task(guild)

    async def init(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            config = await self.config.guild(guild)()
        
            channel_id = config["channel"]
            if channel_id is None:
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                await self.config_reset(guild)
            else:
                message = await safe_get_message(channel, config["message"])
                await clear_channel(channel, message)

                self.start_task(guild, message, config["bots"])

    @commands.admin()
    @bumpreward.command()
    async def channel(self, ctx):
        """
        Создание специального канала.
        """
        guild = ctx.guild
        if guild.id in self.cache:
            message = self.cache[guild.id]["message"]
            await message.channel.delete()

        bots = {}
        for bot_id in BOTS:
            bot = guild.get_member(int(bot_id))
            if bot is not None:
                bots[bot_id] = datetime.now()
        if not bots:
            await send_simple_embed(ctx, MSG_NO_BOTS)
            return
        await self.config.guild(guild).bots.set(bots)

        channel = await guild.create_text_channel("BUMPREWARD")
        await self.config.guild(guild).channel.set(channel.id)
        
        message = await self.create_message(guild, channel, bots)
        await self.config.guild(guild).message.set(message.id)
        
        await add_reaction(ctx)

    async def create_message(self, guild, channel, bots):
        embed = discord.Embed()
        storage = await self.config.guild(guild).balance()
        if storage:
            embed.description = get_leaderboard(guild, storage)

        message = await channel.send(embed=embed)
        self.start_task(guild, message, bots)
        return message

    async def safe_edit_message(self, guild, message, embed):
        try:
            await message.edit(embed=embed, suppress=False)
        except (discord.HTTPException):
            self.cache[guild.id]["waiting"] = True
            message = await channel.send(embed=embed)
            await self.config.guild(guild).message.set(message.id)
            self.cache[guild.id]["message"] = message
        return message











    # def attrs_cooldown_field(bot_id, text):
    #     index = BOTS[bot_id]["index"]
    #     field = {
    #         'name': "**`" + BOTS[bot_id]["command"] + "`**", 
    #         'value': text, 
    #         'inline': True
    #     }
    #     return index, field

    # async def set_config(self, guild, *key, value):
    #     await self.config.guild(guild).set_raw(*key, value=getattr(value, "id", default=value))
    #     set_in_dict(self.cache[guild.id], key, value)

    async def process_cooldowns(self, guild, embed, channel): # TODO Обдумать
        bots = self.cache[guild.id]["bots"]
        cooldowns = get_cooldowns(bots)
        for bot_id in cooldowns:
            cooldown = cooldowns[bot_id]

            if cooldown <= 0:
                text = box(f"+ {MSG_READY:12}", lang="diff")
                await overwrite_send_messages(guild, channel, None)
                del bots[bot_id]
            else:
                human_time = formatted_naturaldelta(cooldown)
                text = box(f"{human_time:14}", lang="py")

            #embed._fields[index] = value
            setattr(embed._fields, *attrs_cooldown_field(bot_id, text))
    
    async def update_message(self, guild, *attrvalue):
        message = self.cache[guild.id]["message"]
        embed = get_embed(message)
        for attr, value in attrvalue:
            setattr(embed, attr, value)

        await self.process_cooldowns(guild, embed, message.channel)

        message = await self.safe_edit_message(guild, message, embed)
        self.restart_task(guild, message)

    async def message_task(self, guild, message):
        embed = get_embed(message)
        while self.cache[guild.id]["bots"]:
            await asyncio.sleep(DELAY)

            await self.process_cooldowns(guild, embed, message.channel)

            message = await self.safe_edit_message(guild, message, embed)      











    # async def update_time(self, guild, bot_id, hours=0, minutes=0, seconds=0):
    #     await self.config.guild(guild).set_raw("bots", bot_id, value=get_end_date(hours, minutes, seconds))
    #     self.cache[guild.id]["cooldowns"][bot_id] = (hours * 60 + minutes) * 60 + seconds

    # @commands.Cog.listener()
    # async def on_message(self, ctx):
    #     channel = ctx.channel
    #     if channel.type.value != 0:
    #         return
    #     guild = ctx.guild
    #     if guild.id not in self.cache:
    #         return
    #     if channel != self.cache[guild.id]["channel"]:
    #         return

    #     author = ctx.author
    #     if author.bot:
    #         if self.cache[guild.id]["waiting"]:
    #             self.cache[guild.id]["waiting"] = False
    #             return

    #         bot_id = str(author.id)
    #         if bot_id in BOTS:
    #             try:
    #                 msg_type, result = get_message_type(ctx, bot_id)

    #                 if msg_type == "captcha":
    #                     self.wait_captcha(guild, bot_id, ctx)
    #                     return

    #                 elif msg_type == "success":
    #                     await self.clear_captchas(guild, bot_id)
                        
    #                     user = get_member(guild, result[0])
    #                     if user is not None:
    #                         reward = await self.config.guild(guild).amount()
    #                         await self.change_balance(guild, user, reward)
    #                         footer = {"text": user.display_name, "icon_url": user.avatar_url}
    #                     else:
    #                         log.error(f"Bot_ID: {bot_id}\nUnable to parse a user: {get_full_content(ctx)}")
    #                         footer = {"text": MSG_UNKOWN_USER}

    #                     cooldown = await self.config.guild(guild).cooldown()
    #                     #await self.update_time(guild, bot_id, minutes=cooldown) # TODO Доделать
    #                     await self.update_message(guild, ("_footer", footer))

    #                 elif msg_type == "cooldown":
    #                     #await self.update_time(guild, bot_id, *[int(x) for x in result]) # TODO Доделать
    #                     await self.update_message(guild)

    #                 #await channel_send_messages(guild, channel, False)  # TODO Доделать

    #             except UnknownType:
    #                 log.critical(f"Bot_ID: {bot_id}\nEncountered unknown message type: {get_full_content(ctx)}")
    #                 await safe_message_delete(ctx, delay=15)
    #                 return

    #     await safe_message_delete(ctx, delay=1)



