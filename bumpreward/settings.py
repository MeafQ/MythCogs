import re

SHORT_PATTERN = re.compile(r'(\d\d):(\d\d):(\d\d)')
ID_PATTERN = re.compile(r'<@!?(.+?)>')
NAME_PATTERN = re.compile(r'(.+?#\d{4})')
DELAY = 60
CAPTCHA_DELAY = 15

MSG_UNKOWN_USER = "⛔ Неизвестный пользователь"
MSG_READY = "Готово"
MSG_NO_DATA = "Нет данных"
MSG_NO_BOTS = "Нет поддерживаемых ботов."
MSG_NO_CHANNEL = "Не создан специальный канал."
MSG_LESS_ONE = "Размер награды не может быть меньше единицы."
MSG_NO_LEADERBOARD = "Нет пользователей в базе данных."

BOTS = {
    "315926021457051650": {
        "index": 1,
        "embed": {
            "cooldown": [SHORT_PATTERN, ["description"]],
            "success": [ID_PATTERN, ["description"]],
            "captcha": ["(?i)write the code", ["description"]]
        },
        "cooldown": 240,
        "command": "!bump"
    },
    "464272403766444044": {
        "index": 2,
        "embed": {
            "cooldown": [SHORT_PATTERN, ["author", "name"]],
            "success": [NAME_PATTERN, ["footer", "text"]]
        },
        "normal": {
            "captcha": "(?i)введите код"
        },
        "cooldown": 240,
        "command": "s.up"
    }
}



