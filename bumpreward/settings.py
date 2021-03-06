import re


SHORT_FORMAT = '%H:%M:%S'
SHORT_PATTERN = re.compile(r'(\d\d):(\d\d):(\d\d)')
ID_PATTERN = re.compile(r'<@!?(.+?)>')
NAME_PATTERN = re.compile(r'(.+?#\d{4})')
DELAY = 60
CAPTCHA_DELAY = 15

BOTS = {
    "315926021457051650": {
        "parser": {
            "cooldown": [SHORT_PATTERN, ["description"]],
            "success": [ID_PATTERN, ["description"]],
            "captcha": ["(?i)write the code", ["description"]]
        },
        "cooldown": 240,
        "command": "!bump",
    },
    "464272403766444044": {
        "parser": {
            "cooldown": [SHORT_PATTERN, ["author", "name"]],
            "success": [NAME_PATTERN, ["footer", "text"]]
        },
        "cooldown": 240,
        "command": "s.up",
    }
}



