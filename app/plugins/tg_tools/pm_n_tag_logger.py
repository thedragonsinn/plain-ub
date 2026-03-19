import asyncio
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import MessageIdInvalid
from ub_core.utils.helpers import get_name

from app import BOT, CustomDB, Message, bot, extra_config

SETTINGS = CustomDB["COMMON_SETTINGS"]

MESSAGE_CACHE: dict[int, list[Message]] = defaultdict(list)
FLOOD_LIST: set[int] = set()

LAST_PM_ID: int = 0
CHAT_TYPES = (ChatType.GROUP, ChatType.SUPERGROUP)


async def init_task():
    tag_check = await SETTINGS.find_one({"_id": "tag_logger_switch"})
    pm_check = await SETTINGS.find_one({"_id": "pm_logger_switch"})
    if tag_check:
        extra_config.TAG_LOGGER = tag_check["value"]
    if pm_check:
        extra_config.PM_LOGGER = pm_check["value"]


async def log_filter(_, bot: BOT, message: Message) -> bool:
    # skip service messages
    if message.service:
        return False

    chat = message.chat
    # skip support messages like OTPs
    if not chat or chat.is_support:
        return False
    # skip forward restricted
    if message.has_protected_content or chat.has_protected_content:
        return False
    # skip saved messages
    if chat.id == bot.me.id:
        return False
    # skip bot messages
    if message.from_user and message.from_user.is_bot:
        return False
    # skip your own messages
    if message.from_user and (message.from_user.is_self or message.outgoing):
        return False
    # finally see if loggers are enabled
    if chat.type == ChatType.PRIVATE:
        return extra_config.PM_LOGGER
    elif message.mentioned and chat.type in CHAT_TYPES:
        return extra_config.TAG_LOGGER
    else:
        return False


@bot.on_message(filters=filters.create(log_filter))
async def message_cacher(bot: BOT, message: Message):
    chat_id = message.chat.id

    if len(MESSAGE_CACHE[chat_id]) >= 10 and chat_id not in FLOOD_LIST:
        bot.log.error(f"Message not Logged from chat: {get_name(message.chat)}")
        FLOOD_LIST.add(chat_id)
        return

    FLOOD_LIST.discard(chat_id)
    MESSAGE_CACHE[chat_id].append(message)
    message.continue_propagation()


@BOT.register_worker(interval=10, name="pm-tag-worker")
async def pm_tag_worker():
    if not (extra_config.TAG_LOGGER or extra_config.PM_LOGGER):
        return

    for key, val in MESSAGE_CACHE.copy().items():
        if not val:
            continue

        for msg in val:
            try:
                await log_message(msg)
            except Exception as e:
                bot.log.error(e, exc_info=True)
            finally:
                MESSAGE_CACHE[key].remove(msg)

            await asyncio.sleep(2)

    new_data = {k: v for k, v in MESSAGE_CACHE.items() if v}
    MESSAGE_CACHE.clear()
    MESSAGE_CACHE.update(new_data)


def get_info_to_log(message: Message) -> str | None:
    if message.sender_chat:
        mention, user_id = message.sender_chat.title, message.sender_chat.id
    else:
        mention, user_id = message.from_user.mention(style=ParseMode.HTML), message.from_user.id

    if message.chat.type == ChatType.PRIVATE:
        global LAST_PM_ID
        if message.chat.id != LAST_PM_ID:
            LAST_PM_ID = message.chat.id
            return f"#PM\n{mention} [{user_id}]"
        return None

    return (
        f"#TAG\n{mention} [{user_id}]\nMessage: \n<a href='{message.link}'>{message.chat.title}</a> ({message.chat.id})"
    )


async def log_message(message: Message) -> None:
    # PM
    if message.chat.type == ChatType.PRIVATE:
        reply_to_message = None
        thread_id = extra_config.PM_LOGGER_THREAD_ID
    # Tag
    else:
        reply_to_message = message.reply_to_message
        thread_id = extra_config.TAG_LOGGER_THREAD_ID

    extra_info = get_info_to_log(message)
    if extra_info:
        await bot.send_message(
            chat_id=extra_config.MESSAGE_LOGGER_CHAT,
            text=extra_info,
            message_thread_id=thread_id,
            parse_mode=ParseMode.HTML,
        )
        await asyncio.sleep(1)

    to_forward_ids = [message.id]

    if reply_to_message:
        to_forward_ids.insert(0, reply_to_message.id)

    try:
        # Try to schedule forward of messages
        forwarded = await bot.forward_messages(
            from_chat_id=message.chat.id,
            chat_id=extra_config.MESSAGE_LOGGER_CHAT,
            message_ids=to_forward_ids,
            message_thread_id=thread_id,
        )
    except (MessageIdInvalid, BaseException):
        await asyncio.sleep(1)
        forwarded = []

    if len(forwarded) == len(to_forward_ids):
        return

    [await m.delete() for m in forwarded]

    if reply_to_message:
        await reply_to_message.copy(chat_id=extra_config.MESSAGE_LOGGER_CHAT, message_thread_id=thread_id)

    await asyncio.sleep(1)
    sent_message = await message.copy(chat_id=extra_config.MESSAGE_LOGGER_CHAT, message_thread_id=thread_id)
    await sent_message.reply("This message was deleted by sender.")


@bot.add_cmd(cmd=["taglogger", "pmlogger"])
async def logger_switch(bot: BOT, message: Message):
    """
    CMD: TAGLOGGER | PMLOGGER
    INFO: Enable/Disable PM or Tag Logger.
    FLAGS: -c to check status.
    """
    text = "pm" if message.cmd == "pmlogger" else "tag"
    conf_str = f"{text.upper()}_LOGGER"

    if "-c" in message.flags:
        await message.reply(
            text=f"{text.capitalize()} Logger is enabled: <b>{getattr(extra_config, conf_str)}</b>!", del_in=8
        )
        return

    value: bool = not getattr(extra_config, conf_str)
    setattr(extra_config, conf_str, value)

    await asyncio.gather(
        SETTINGS.add_data({"_id": f"{text}_logger_switch", "value": value}),
        message.reply(text=f"{text.capitalize()} Logger is enabled: <b>{value}</b>!", del_in=8),
        bot.log_text(text=f"#{text.capitalize()}Logger is enabled: <b>{value}</b>!", type="info"),
    )
