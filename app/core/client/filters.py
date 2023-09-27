from pyrogram import filters as _filters

from app import Config


def dynamic_cmd_filter(_, __, message) -> bool:
    if (
        not message.text
        or not message.text.startswith(Config.TRIGGER)
        or not message.from_user
        or message.from_user.id not in Config.USERS
    ):
        return False

    start_str = message.text.split(maxsplit=1)[0]
    cmd = start_str.replace(Config.TRIGGER, "", 1)
    cmd_check = cmd in Config.CMD_DICT
    reaction_check = not message.reactions
    return bool(cmd_check and reaction_check)


cmd_filter = _filters.create(dynamic_cmd_filter)
convo_filter = _filters.create(
    lambda _, __, message: (message.chat.id in Config.CONVO_DICT)
    and (not message.reactions)
)
