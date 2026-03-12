import asyncio
import datetime
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatType, MessageEntityType, ParseMode
from pyrogram.errors import MessageIdInvalid
from ub_core.utils.helpers import get_name

from app import BOT, LOGGER, CustomDB, Message, bot, extra_config

SETTINGS = CustomDB["COMMON_SETTINGS"]

LAST_PM_ID: int = 0
MESSAGE_CACHE: dict[int, list[Message]] = defaultdict(list)
FLOOD_LIST: list[int] = []


async def init_task():
    tag_check = await SETTINGS.find_one({"_id": "tag_logger_switch"})
    pm_check = await SETTINGS.find_one({"_id": "pm_logger_switch"})
    if tag_check:
        extra_config.TAG_LOGGER = tag_check["value"]
    if pm_check:
        extra_config.PM_LOGGER = pm_check["value"]


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
            text=f"{text.capitalize()} Logger is enabled: <b>{getattr(extra_config, conf_str)}</b>!",
            del_in=8,
        )
        return

    value: bool = not getattr(extra_config, conf_str)
    setattr(extra_config, conf_str, value)

    await asyncio.gather(
        SETTINGS.add_data({"_id": f"{text}_logger_switch", "value": value}),
        message.reply(text=f"{text.capitalize()} Logger is enabled: <b>{value}</b>!", del_in=8),
        bot.log_text(text=f"#{text.capitalize()}Logger is enabled: <b>{value}</b>!", type="info"),
    )


BASIC_FILTERS = (
    ~filters.channel
    & ~filters.bot
    & ~filters.service
    & ~filters.chat(chats=[bot.me.id])
    & ~filters.me
    & ~filters.create(lambda _, __, m: m.chat.is_support)
)


@bot.on_message(
    filters=BASIC_FILTERS & filters.private & filters.create(lambda _, __, ___: extra_config.PM_LOGGER),
)
async def pm_logger(bot: BOT, message: Message):
    cache_message(message)


TAG_FILTER = filters.create(lambda _, __, ___: extra_config.TAG_LOGGER)


@bot.on_message(
    filters=(BASIC_FILTERS & filters.reply & TAG_FILTER) & ~filters.private,
)
async def reply_logger(bot: BOT, message: Message):
    if (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.id == bot.me.id
    ):
        cache_message(message)
    message.continue_propagation()


@bot.on_message(
    filters=(BASIC_FILTERS & filters.mentioned & TAG_FILTER) & ~filters.private,
)
async def mention_logger(bot: BOT, message: Message):
    for entity in message.entities or []:
        if entity.type == MessageEntityType.MENTION and entity.user and entity.user.id == bot.me.id:
            cache_message(message)
    message.continue_propagation()


@bot.on_message(
    filters=(BASIC_FILTERS & (filters.text | filters.media) & TAG_FILTER) & ~filters.private,
)
async def username_logger(bot: BOT, message: Message):
    text = message.text or message.caption or ""
    if bot.me.username and f"@{bot.me.username}" in text:
        cache_message(message)
    message.continue_propagation()


def cache_message(message: Message):
    chat_id = message.chat.id
    if len(MESSAGE_CACHE[chat_id]) >= 10 and chat_id not in FLOOD_LIST:
        bot.log.error(f"Message not Logged from chat: {get_name(message.chat)}")
        FLOOD_LIST.append(chat_id)
        return
    if chat_id in FLOOD_LIST:
        FLOOD_LIST.remove(chat_id)
    MESSAGE_CACHE[chat_id].append(message)


@BOT.register_worker(interval=5, name="pm-tag-worker")
async def worker():
    if not (extra_config.TAG_LOGGER or extra_config.PM_LOGGER):
        return

    for key, val in MESSAGE_CACHE.copy().items():
        if not val:
            continue

        for msg in val:
            if msg.chat.type == ChatType.PRIVATE:
                global LAST_PM_ID
                await log_pm(message=msg, log_info=LAST_PM_ID != key)
                LAST_PM_ID = key
            else:
                await log_chat(message=msg)

            MESSAGE_CACHE[key].remove(msg)
            await asyncio.sleep(5)

        await asyncio.sleep(15)

    new_data = {k: v for k, v in MESSAGE_CACHE.items() if v}
    MESSAGE_CACHE.clear()
    MESSAGE_CACHE.update(new_data)


async def log_pm(message: Message, log_info: bool):
    if log_info:
        await bot.send_message(
            chat_id=extra_config.MESSAGE_LOGGER_CHAT,
            text=f"#PM\n{message.from_user.mention} [{message.from_user.id}]",
            message_thread_id=extra_config.PM_LOGGER_THREAD_ID,
        )
    notice = (
        f"{message.from_user.mention} [{message.from_user.id}] deleted this message."
        f"\n\n---\n\n"
        f"Message: \n<a href='{message.link}'>{message.chat.title or message.chat.first_name}</a> ({message.chat.id})"
        f"\n\n---\n\n"
        f"Caption:\n{message.caption or 'No Caption in media.'}"
    )
    await log_message(message=message, notice=notice, thread_id=extra_config.PM_LOGGER_THREAD_ID)


async def log_chat(message: Message):
    if message.sender_chat:
        mention, u_id = message.sender_chat.title, message.sender_chat.id
    else:
        mention, u_id = message.from_user.mention, message.from_user.id
    notice = (
        f"{mention} [{u_id}] deleted this message."
        f"\n\n---\n\n"
        f"Message: \n<a href='{message.link}'>{message.chat.title or message.chat.first_name}</a> ({message.chat.id})"
        f"\n\n---\n\n"
        f"Caption:\n{message.caption or 'No Caption in media.'}"
    )

    if message.reply_to_message:
        await log_message(message.reply_to_message, thread_id=extra_config.TAG_LOGGER_THREAD_ID)

    await log_message(
        message=message,
        notice=notice,
        extra_info=f"#TAG\n{mention} [{u_id}]\nMessage: \n<a href='{message.link}'>{message.chat.title}</a> ({message.chat.id})",
        thread_id=extra_config.TAG_LOGGER_THREAD_ID,
    )


async def log_message(
    message: Message,
    notice: str | None = None,
    extra_info: str | None = None,
    thread_id: int = None,
):
    schedule_date = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=10)
    try:
        logged_message: Message = await message.forward(
            extra_config.MESSAGE_LOGGER_CHAT,
            message_thread_id=thread_id,
            schedule_date=schedule_date,
        )
        if extra_info:
            await logged_message.reply(extra_info, parse_mode=ParseMode.HTML, schedule_date=schedule_date)
    except MessageIdInvalid:
        schedule_date = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=10)
        logged_message = await message.copy(
            extra_config.MESSAGE_LOGGER_CHAT,
            message_thread_id=thread_id,
            schedule_date=schedule_date,
        )
        if notice:
            await logged_message.reply(notice, parse_mode=ParseMode.HTML, schedule_date=schedule_date)
    except Exception as e:
        LOGGER.error(f"Error logging message [{get_name(message.chat)} - {message.id}]: {e}")
        return

    # wait till message is sent
    wait_time = schedule_date - datetime.datetime.now(datetime.UTC)
    await asyncio.sleep(wait_time.total_seconds())

    return None
