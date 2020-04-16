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
            await send_embed(ctx.channel, MSG_LESS_ONE)
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

        top_10 = get_leaderboard(guild, new_balance[:10])[0][0]
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

        storage  = await self.config.guild(guild).balance()
        if not storage:
            await send_embed(ctx, MSG_NO_LEADERBOARD)
            return

        pages, author_page = get_leaderboard(guild, storage, author)

        await menu(ctx, pages, DEFAULT_CONTROLS, page=author_page, timeout=15)

    def wait_captcha(self, guild, bot_id, message):
        captchas = self.cache[guild.id]["bots"][bot_id]["captchas"]  # TODO bots больше не хранится в cache
        captchas.append(message)
        async def captcha_delay(self, guild, bot_id):
            await asyncio.sleep(CAPTCHA_DELAY)
            if message in captchas:
                captchas.remove(message)
                await message_delete(message)
        self.bot.loop.create_task(captcha_delay(self, guild, bot_id))

    async def clear_captchas(self, guild, bot_id):
        captchas = self.cache[guild.id]["bots"][bot_id]["captchas"]  # TODO bots больше не хранится в cache
        for message in captchas:
            await message_delete(message)
        captchas.clear()

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        if guild.id in self.cache:
            if channel == self.cache[guild.id]["channel"]:
                await self.guild_reset(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        if guild.id in self.cache:
            await self.guild_reset(guild)

    async def guild_reset(self, guild):
        await self.config.guild(guild).channel.set(None)
        await self.config.guild(guild).message.set(None)
        self.cancel_task(guild)

    def cancel_task(self, guild):
        self.cache[guild.id]["task"].cancel()
        del self.cache[guild.id]

    async def update_message(self, guild, *attrvalue):
        try:
            message = self.cache[guild.id]["message"]
            embed = get_embed(message)
            for attr, value in attrvalue:
                setattr(embed, attr, value)
            message.edit(embed=embed, suppress=False)
            # TODO Перезапуск таска
        except (discord.HTTPException, AttributeError):
            await self.create_message(self, guild)

    async def create_message(self, guild):
        # TODO Не полный embed, заполнить
        embed = discord.Embed()
        storage = await self.config.guild(guild).balance()
        if storage:
            embed.description = get_leaderboard(guild, storage[:10])[0][0]
        embed._fields = {}
        channel = self.cache[guild.id]["channel"]
        self.cache[guild.id]["waiting"] = True
        message = await channel.send(embed=embed)
        await self.set_config(guild, "message", value=message)

    @commands.admin()
    @bumpreward.command()
    async def channel(self, ctx):
        """
        Создание специального канала.
        """
        guild = ctx.guild
        if guild.id in self.cache:
            await self.cache[guild.id]["channel"].delete()

        old_bots = await self.config.guild(guild).bots()
        bots = {}
        overwrites = {}
        for key in BOTS:
            bot = guild.get_member(int(key))
            if bot is not None:
                overwrites[bot] = discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, embed_links=True, attach_files=True)
                bots[key] = old_bots.get(key)
        await self.config.guild(guild).bots.set(bots)

        if not overwrites:
            await send_embed(ctx.channel, MSG_NO_BOTS)
            return

        channel = await guild.create_text_channel("bumps", overwrites=overwrites)
        await self.config.guild(guild).channel.set(channel.id)

        self.create_task(guild, bots, channel) # TODO Нужно ли здесь передавать bots
        await add_reaction(ctx)


























    @commands.Cog.listener()
    async def on_message(self, ctx):
        channel = ctx.channel
        if channel.type.value != 0:
            return
        guild = ctx.guild
        if guild.id not in self.cache:
            return
        if channel != self.cache[guild.id]["channel"]:
            return

        author = ctx.author
        if author.bot:
            if author == self.bot.user and self.cache[guild.id]["waiting"]:
                self.cache[guild.id]["waiting"] = False
                return




            bot_id = str(author.id)
            if bot_id in BOTS:
                try:
                    msg_type, result = get_message_type(ctx, bot_id)

                    if msg_type == "captcha":
                        self.wait_captcha(guild, bot_id, ctx)
                        return

                    elif msg_type == "success":
                        await self.clear_captchas(guild, bot_id)
                        
                        user = get_member(guild, result[0])
                        if user is not None:
                            reward = await self.config.guild(guild).amount()
                            await self.change_balance(guild, user, reward)
                            footer = ("_footer", {"text": user.display_name, "icon_url": user.avatar_url})
                        else:
                            log.error("Bot_ID: %s\nUnable to parse a user: %s" % (bot_id, [])) # TODO Все сообщение, а не только embed
                            footer = ("_footer", {"text": MSG_UNKOWN_USER})

                        # end_date = get_end_date(minutes=bot_config["cooldown"])
                        # await channel_send_messages(guild, channel, False)
                        await self.update_message(guild, footer, [])


                    elif msg_type == "cooldown":
                        # end_date = get_end_date(*[int(x) for x in result])
                        # await channel_send_messages(guild, channel, False)
                        await self.update_message(guild, [])


                    # await self.set_config(ctx.guild, "bots", bot_id, value=end_date)

                except UnknownType:
                    log.critical("Bot_ID: %s\nEncountered unknown message type: %s" % (bot_id, [])) # TODO Все сообщение, а не только embed
        await message_delete(ctx, delay=1)


    async def create_task(self, guild, bots, channel, message):
        self.cache[guild.id] = {
            "channel": channel,
            "message": message,

            "cooldowns": get_commands(bots),
            "captchas": {},
            "waiting": False,

            "task": self.bot.loop.create_task(self.message_task(guild))
        }
















    # async def message_task(self, guild):
        
    #     commands = self.cache[guild.id]["commands"]

    #     while(commands):
    #         await asyncio.sleep(DELAY)

    #         not_finished = {}
    #         fields = []
    #         for index, info in commands.items():
    #             cooldown = info["cooldown"]
    #             if info["cooldown"] is not None:
    #                 if cooldown <= 0:
    #                     await self.set_channel_send_messages(guild, None)
    #                     text = box(f"+ {MSG_READY:12}", lang="diff")
    #                 else:
    #                     human_time = humanize.naturaldelta(max(cooldown % 3600, 60))
    #                     if (cooldown // 3600) >= 1:
    #                         human_time = humanize.naturaldelta(cooldown) + " " + human_time
    #                     text = box(f"{human_time:14}", lang="py")
    #                     info["cooldown"] -= DELAY
    #                     not_finished[index] = info
    #             else:
    #                 text = box(f"- {MSG_NO_DATA:12}", lang="diff")
    #             name = "**`" + info["name"] + "`**"
    #             fields.append({'name': name, 'value': text, 'inline': True})

    #         commands = not_finished

    #         await self.update_message(guild, ("_fields", fields))            

    # async def init(self):
    #     await self.bot.wait_until_ready()
    #     for guild in self.bot.guilds:
    #         config = await self.config.guild(guild)()
        
    #         channel_id = config["channel"]
    #         if channel_id is None:
    #             continue

    #         channel = guild.get_channel(channel_id)
    #         if channel is None:
    #             await self.config.guild(guild).channel.set(None)
    #             await self.config.guild(guild).message.set(None)
    #         else:
    #             message = await get_message(channel, config["message"])
    #             await clear_channel(guild, channel, message)

    #             self.create_task(guild, config["bots"], channel, message)


    # def update_task(self, guild):
    #     self.cache[guild.id]["task"].cancel()
    #     self.cache[guild.id]["task"] = self.bot.loop.create_task(self.message_task(guild))


    # async def set_config(self, guild, *key, value):
    #     await self.config.guild(guild).set_raw(*key, value=getattr(value, "id", default=value))
    #     set_in_dict(self.cache[guild.id], key, value)