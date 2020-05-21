import re
import discord
from datetime import datetime, timedelta
from redbot.core.utils.chat_formatting import box
from .settings import *
from functools import reduce
from itertools import izip
import operator
import humanize


def get_leaderboard(guild, storage, author=None, page=10, full=False):
    balance_len = len(str(storage[0][1]))
    pound_len = len(str(len(storage)))
    header = f"{'#':{pound_len + 4}}{'Счет':{balance_len + 5}}{'Имя':2}\n"

    i = 1
    pages = []
    author_page = 0
    temp_page = header
    for user_id, balance in storage:
        if author is None or user_id != author.id:
            user = guild.get_member(user_id)
            if user is None:
                continue
            name = user.display_name
        else:
            author_page = i - 1 // page
            name = f"<<{author.display_name}>>"

        temp_page += f"{f'{i}.': <{pound_len + 3}} {balance: <{balance_len + 4}} {name}\n"

        if i % page == 0:
            if full:
                pages.append(box(temp_page, lang="md"))
                temp_page = header
            return box(temp_page, lang="md")
        i += 1

    if temp_page != header:
        pages.append(box(temp_page, lang="md"))
        
    return pages, author_page


def get_end_date(hours=0, minutes=0, seconds=0):
    time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    now = datetime.now()
    end_date = now + time
    formatted = datetime.strftime(end_date, '%Y/%m/%d %H:%M:%S')
    return formatted

def get_cooldowns(bots):
    temp = {}
    for bot_id, end_date in bots.items():
        now = datetime.now()
        time_left = end_date - now
        temp[bot_id] = time_left.total_seconds()
    return temp

def get_end_dates(bots):
    for bot_id, end_date in bots.items():
        bots[bot_id] = datetime.strptime(end_date, '%Y/%m/%d %H:%M:%S')
    return bots

def get_from_dict(data_dict, map_list):
    try:
        return reduce(operator.getitem, map_list, data_dict)
    except KeyError:
        return None

def set_in_dict(data_dict, map_list, value):
    get_from_dict(data_dict, map_list[:-1])[map_list[-1]] = value

async def add_reaction(ctx, emoji = "✅"):
    try:
        await ctx.message.add_reaction(emoji)
    except discord.NotFound:
        pass

def get_message_type(ctx, bot_id):
    embed = get_embed(ctx)
    if embed is None:
        for key, value in BOTS[bot_id]["normal"].items():
            result = re.search(value, ctx.description)
            if result:
                return key, result.groups()
    else:
        for key, value in BOTS[bot_id]["embed"].items():
            string = get_from_dict(embed.to_dict(), value[1])
            if string is not None:
                result = re.search(value[0], string)
                if result:
                    return key, result.groups()
    raise UnknownType

def formatted_naturaldelta(cooldown):
    human_time = humanize.naturaldelta(max(cooldown % 3600, 60))
    if (cooldown // 3600) >= 1:
        human_time = humanize.naturaldelta(cooldown) + " " + human_time
    return human_time

def get_embed(message):
    embeds = message.embeds
    if embeds:
        return embeds[0]
    return None

def get_member(guild, string):
    try:
        return guild.get_member(int(string))
    except ValueError:
        return guild.get_member_named(string)

async def get_message(channel, message_id):
    if message_id is not None:
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            pass
    return None

async def clear_channel(guild, channel, message):
    def is_not_msg(m):
        return m != message
    try:
        await channel.purge(check=is_not_msg)
    except discord.NotFound:
        pass

async def send_simple_embed(channel, text):
    embed = discord.Embed(description=text)
    await channel.send(embed=embed)

async def safe_message_delete(message, delay=None):
    try:
        await message.delete(delay=delay)
    except discord.NotFound:
        pass

async def overwrite_send_messages(guild, channel, lock):
    overwrite = channel.overwrites_for(guild.default_role)
    overwrite.send_messages = lock
    await channel.set_permissions(guild.default_role, overwrite=overwrite)

class UnknownType(Exception):
    pass