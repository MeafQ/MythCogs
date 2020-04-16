import re
import discord
from datetime import datetime, timedelta
from redbot.core.utils.chat_formatting import box
from .settings import *
from functools import reduce
import operator


def get_leaderboard(guild, storage, author=None, page=10, first=False):
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
            user = guild.get_member(user_id)
            if user is None:
                continue
            name = user.display_name
        else:
            author_page = i // 10
            name = f"<<{author.display_name}>>"

        temp_page += f"{f'{i}.': <{pound_len + 3}} {balance: <{balance_len + 4}} {name}\n"

        if i % page == 0:
            if first:
                return box(temp_page, lang="md")

            pages.append(box(temp_page, lang="md"))
            temp_page = header
        i += 1

    if temp_page != header:
        pages.append(box(temp_page, lang="md"))
        
    return pages, author_page

def set_bots_permissions(obj_bots, overwrites = {}):
    for bot in obj_bots:
        overwrites[bot] = discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True, attach_files=True)
    return overwrites

def get_end_date(hours=0, minutes=0, seconds=0):
    time = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    now = datetime.now()
    end_date = now + time
    formatted = datetime.strftime(end_date, '%Y/%m/%d %H:%M:%S')
    return formatted

def get_cooldown(end_date):
    if end_date is not None:
        end_date = datetime.strptime(end_date, '%Y/%m/%d %H:%M:%S')
        now = datetime.now()
        time_left = end_date - now
        return time_left.total_seconds()
    return None

def sort_commands(bots):
    temp = {}
    i = 0
    for bot_id, end_date in bots.items():
        temp[i] = {"name": BOTS[bot_id]["command"], "cooldown": get_cooldown(end_date)}
        i += 1
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


def get_message_type(embed, parsers):
    for key, value in parsers.items():
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

async def get_message(channel, message_id):   # TODO Тоже самое
    if message_id is not None:
        try:
            return await channel.fetch_message(message_id)
        except discord.NotFound:
            pass
    return None

async def clear_channel(guild, channel, message_id=None):
    def is_not_msg(m):
        return m.id != message_id
    try:
        await channel.purge(check=is_not_msg)
    except discord.NotFound:
        pass

async def send_embed(channel, text):
    embed = discord.Embed(description=text)
    await channel.send(embed=embed)

class UnknownType(Exception):
    pass