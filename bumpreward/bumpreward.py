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
MSG_NOT_ZERO = "Размер награды не может быть меньше единицы."
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

        # self.create_task(guild, bots, channel)
        await add_reaction(ctx)

    # @commands.admin()
    # @bumpreward.command()
    # async def amount(self, ctx, *, amount : int):
    #     """
    #     Изменение размера награды.
    #     """
    #     if amount <= 0:
    #         await send_embed(ctx.channel, MSG_LESS_ZERO)
    #         return
    #     await self.config.guild(ctx.guild).amount.set(amount)
    #     await add_reaction(ctx)

    # @commands.admin()
    # @bumpreward.command(name="set")
    # async def cmd_set(self, ctx, user : discord.Member, *, amount : int):
    #     """
    #     Прибавить или убавить баланса пользователя.
    #     **-** Ноль сбрасывает баланс.
    #     """
    #     await self.change_balance(ctx.guild, user, amount)
    #     await add_reaction(ctx)

    async def change_balance(self, guild, user, amount):
        old_storage = await self.config.guild(guild).balance()
        for i in range(len(old_storage)):
            if old_storage[i][0] == user.id:
                if amount != 0:
                    amount = max(old_storage[i][1] + amount, 0)
                old_storage[i][1] = amount
                break
        else:
            old_storage.append((user.id, amount))

        new_storage = sorted(old_storage, key=lambda tup: tup[1], reverse=True)

        if new_storage:
            self.cache[guild.id]["embed"].description = get_leaderboard(guild, new_storage[:10])[0][0]

        await self.config.guild(guild).balance.set(new_storage)


    # @commands.cooldown(rate=2, per=300, type=commands.BucketType.user)
    # @bumpreward.command()
    # async def balance(self, ctx, author: discord.Member = None):
    #     """
    #     Список баланса пользователей.
    #     """
    #     if author is None:
    #         author = ctx.author
    #     guild = ctx.guild

    #     storage  = await self.config.guild(guild).balance()
    #     if not storage:
    #         await send_embed(ctx, MSG_NO_LEADERBOARD)
    #         return

    #     pages, author_page = get_leaderboard(guild, storage, author)

    #     await menu(ctx, pages, DEFAULT_CONTROLS, page=author_page, timeout=15)


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
            bot_config = BOTS.get(bot_id)
            
            if bot_config is not None:
                embed = get_embed(ctx)
                try:
                    if embed is None:
                        msg_type, result = get_normal_type(embed, bot_config["normal"])
                    else:
                        msg_type, result = get_embed_type(embed, bot_config["embed"])

                    if msg_type == "success":
                        user = get_member(guild, *result)
                        if user is not None:
                            self.cache[guild.id]["embed"].set_footer(text=user.display_name, icon_url=user.avatar_url)
                            await self.change_balance(guild, user, await self.config.guild(guild).amount())
                        else:
                            self.cache[guild.id]["embed"].set_footer(text=MSG_UNKOWN_USER)
                            log.error("Bot_ID: %s\nUnable to parse a user: %s" % (bot_id, embed.to_dict()))
                        await self.remove_captchas(guild, bot_id)
                        end_date = get_end_date(minutes=bot_config["cooldown"])
                    elif msg_type == "cooldown":
                        end_date = get_end_date(*[int(x) for x in result])
                    elif msg_type == "captcha":
                        self.add_captcha(guild, bot_id, ctx)
                        return
                    await self.set_channel_send_messages(guild, channel, False)
                    await self.set_config(ctx.guild, "bots", bot_id, value=end_date)
                    self.update_task(guild)
                except UnknownType:
                    log.critical("Bot_ID: %s\nEncountered unknown message type: %s" % (bot_id, embed.to_dict()))
        try:
            await ctx.delete(delay=1)
        except discord.NotFound:
            pass


    async def message_task(self, guild):
        
        commands = self.cache[guild.id]["commands"]
        embed = self.cache[guild.id]["embed"]

        while(commands):
            await asyncio.sleep(DELAY)

            not_finished = {}
            for index, info in commands.items():
                cooldown = info["cooldown"]
                if info["cooldown"] is not None:
                    if cooldown <= 0:
                        await self.set_channel_send_messages(guild, None)
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

            await self.update_message(guild)


    # async def set_channel_send_messages(self, guild, lock):
    #     channel = self.cache[guild.id]["channel"]
    #     overwrite = channel.overwrites_for(guild.default_role)
    #     print(overwrite.send_messages)
    #     if overwrite.send_messages != lock:
    #         overwrite.send_messages = lock
    #         await channel.set_permissions(guild.default_role, overwrite=overwrite)

    # def add_captcha(self, guild, bot_id, ctx):
    #     captchas = self.cache[guild.id]["bots"][bot_id]["captchas"]
    #     captchas.append(ctx)
    #     print(self.cache[guild.id]["bots"][bot_id]["captchas"])
    #     print(captchas)
    #     async def captcha_delay(self, guild, bot_id):
    #         await asyncio.sleep(CAPTCHA_DELAY)
    #         if ctx in captchas:
    #             captchas.remove(ctx)
    #             try:
    #                 await ctx.delete()
    #             except discord.NotFound:
    #                 pass
    #     self.bot.loop.create_task(captcha_delay(self, guild, bot_id))

    # async def remove_captchas(self, guild, bot_id):
    #     captchas = self.cache[guild.id]["bots"][bot_id]["captchas"]
    #     for message in captchas:
    #         try:
    #             await message.delete()
    #         except discord.NotFound:
    #             pass
    #     captchas = []


    # @commands.Cog.listener()
    # async def on_guild_channel_delete(self, channel):
    #     guild = channel.guild
    #     if guild.id in self.cache:
    #         if channel == self.cache[guild.id]["channel"]:
    #             await self.guild_reset(guild)

    # @commands.Cog.listener()
    # async def on_guild_remove(self, guild):
    #     if guild.id in self.cache:
    #         await self.guild_reset(guild)

    # async def guild_reset(self, guild):
    #     await self.config.guild(guild).channel.set(None)
    #     await self.config.guild(guild).message.set(None)
    #     self.cancel_task(guild)

    async def update_message(self, guild):
        message = self.cache[guild.id]["message"]
        embed = self.cache[guild.id]["embed"]
        try:
            await message.edit(embed=embed, suppress=False)
        except (discord.HTTPException, AttributeError):
            self.cache[guild.id]["waiting"] = True
            message = await channel.send(embed=embed)
            await self.set_config(guild, "message", value=message)

    async def init(self):
        await self.bot.wait_until_ready()
        for guild in self.bot.guilds:
            config = await self.config.guild(guild)()
        
            channel_id = config["channel"]
            if channel_id is None:
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                await self.config.guild(guild).channel.set(None)
                await self.config.guild(guild).message.set(None)
            else:
                message = await get_message(channel, config["message"])
                await clear_channel(guild, channel, message)

                self.create_task(guild, config["bots"], channel, message)


    async def create_task(self, guild, bots, channel, message = None):
        if message is None:
            embed = discord.Embed()
            storage = await self.config.guild(guild).balance()
            if storage:
                embed.description = get_leaderboard(guild, storage[:10])[0][0]
        else:
            embed = get_embed(message)

        self.cache[guild.id] = {
            "channel": channel,
            "message": message,

            "embed": embed,
            "commands": sort_commands(bots),
            "waiting": False,

            "task": self.bot.loop.create_task(self.message_task(guild))
        }

    # def cancel_task(self, guild):
    #     self.cache[guild.id]["task"].cancel()
    #     del self.cache[guild.id]

    # def update_task(self, guild):
    #     self.cache[guild.id]["task"].cancel()
    #     self.cache[guild.id]["task"] = self.bot.loop.create_task(self.message_task(guild))

    # async def set_config(self, guild, *key, value):
    #     await self.config.guild(guild).set_raw(*key, value=getattr(value, "id", default=value))
    #     set_in_dict(self.cache[guild.id], key, value)