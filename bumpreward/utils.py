import re
import discord
from datetime import datetime, timedelta
from redbot.core.utils.chat_formatting import box
from .settings import *
from functools import reduce
import operator


def get_leaderboard(guild, storage, author=None):
    balance_len = len(str(storage[0][1]))
    pound_len = len(str(len(storage)))

    header = f"{'#':{pound_len + 4}}{'Счет':{balance_len + 5}}{'Имя':2}\n"

    pages = []
    author_page = 0
    temp_page = header
    i = 1
    for user_id, balance in storage:
        user_id = int(user_id)

        if user_id != getattr(author, "id", None):
            name = guild.get_member(user_id).display_name
        else:
            author_page = i // 10
            name = f"<<{author.display_name}>>"

        temp_page += f"{f'{i}.': <{pound_len + 3}} {balance: <{balance_len + 4}} {name}\n"

        if i % 10 == 0:
            pages.append(box(temp_page, lang="md"))
            temp_page = header
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

def get_cooldown(end_date):
    end_date = datetime.strptime(end_date, '%Y/%m/%d %H:%M:%S')
    now = datetime.now()
    time_left = end_date - now
    return time_left.total_seconds()

def get_commands(bots):
    temp = {}
    index = 0
    for bot_id, end_date in bots.items():
        temp[bot_id] = {
            "index": index,
            "name": BOTS[bot_id]["command"],
            "cooldown": get_cooldown(end_date) if end_date is not None else 0
        }
        index += 1
    return temp

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

async def send_embed(channel, text):
    embed = discord.Embed(description=text)
    await channel.send(embed=embed)

async def message_delete(message, delay=None):
    try:
        await message.delete(delay=delay)
    except discord.NotFound:
        pass

async def channel_send_messages(guild, channel, lock):
    overwrite = channel.overwrites_for(guild.default_role)
    if overwrite.send_messages != lock:
        overwrite.send_messages = lock
        await channel.set_permissions(guild.default_role, overwrite=overwrite)

# def set_field_at()

class UnknownType(Exception):
    pass

class UnknownUser(Exception):
    pass