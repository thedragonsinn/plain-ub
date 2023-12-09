from pyrogram import filters as _filters
from pyrogram.types import Message

from app import Config
from app.core.client.conversation import Conversation

convo_filter = _filters.create(
    lambda _, __, message: (message.chat.id in Conversation.CONVO_DICT.keys())
    and (not message.reactions)
)


def cmd_check(message: Message, trigger: str, sudo: bool = False) -> bool:
    start_str = message.text.split(maxsplit=1)[0]
    cmd = start_str.replace(trigger, "", 1)
    if sudo and cmd not in Config.SUDO_CMD_LIST:
        return False
    return bool(cmd in Config.CMD_DICT.keys())


def basic_check(message: Message):
    if message.reactions or not message.text or not message.from_user:
        return True


def owner_check(filters, client, message: Message) -> bool:
    if (
        basic_check(message)
        or not message.text.startswith(Config.CMD_TRIGGER)
        or message.from_user.id != Config.OWNER_ID
        or (message.chat.id != Config.OWNER_ID and not message.outgoing)
    ):
        return False
    cmd = cmd_check(message, Config.CMD_TRIGGER)
    return cmd


owner_filter = _filters.create(owner_check)


def sudo_check(filters, client, message: Message) -> bool:
    if (
        not Config.SUDO
        or basic_check(message)
        or not message.text.startswith(Config.SUDO_TRIGGER)
        or message.from_user.id not in Config.SUDO_USERS
    ):
        return False
    cmd = cmd_check(message, Config.SUDO_TRIGGER, sudo=True)
    return cmd


sudo_filter = _filters.create(sudo_check)
