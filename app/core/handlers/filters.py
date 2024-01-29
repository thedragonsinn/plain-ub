from pyrogram import filters as _filters
from pyrogram.types import Message

from app import Config
from app.core.conversation import Conversation

convo_filter = _filters.create(
    lambda _, __, message: (message.chat.id in Conversation.CONVO_DICT.keys())
    and (not message.reactions)
)


def cmd_check(message: Message, trigger: str, sudo: bool = False) -> bool:
    start_str = message.text.split(maxsplit=1)[0]
    cmd = start_str.replace(trigger, "", 1)
    cmd_obj = Config.CMD_DICT.get(cmd)
    if not cmd_obj:
        return False
    if sudo:
        in_sudo = cmd in Config.SUDO_CMD_LIST
        has_access = Config.CMD_DICT[cmd].sudo
        return in_sudo and has_access
    return True


def basic_check(message: Message):
    return message.reactions or not message.text or not message.from_user


def owner_check(filters, client, message: Message) -> bool:
    if (
        basic_check(message)
        or not message.text.startswith(Config.CMD_TRIGGER)
        or message.from_user.id != Config.OWNER_ID
        or (message.chat.id != Config.OWNER_ID and not message.outgoing)
    ):
        return False
    return cmd_check(message, Config.CMD_TRIGGER)


owner_filter = _filters.create(owner_check)


def sudo_check(filters, client, message: Message) -> bool:
    if (
        not Config.SUDO
        or basic_check(message)
        or not message.text.startswith(Config.SUDO_TRIGGER)
        or message.from_user.id not in Config.SUDO_USERS
    ):
        return False
    return cmd_check(message, Config.SUDO_TRIGGER, sudo=True)


sudo_filter = _filters.create(sudo_check)


def super_user_check(filter, client, message: Message):
    if (
        basic_check(message)
        or not message.text.startswith(Config.SUDO_TRIGGER)
        or message.from_user.id not in Config.SUPERUSERS
        or message.from_user.id in Config.DISABLED_SUPERUSERS
    ):
        return False
    return cmd_check(message, Config.SUDO_TRIGGER)


super_user_filter = _filters.create(super_user_check)
