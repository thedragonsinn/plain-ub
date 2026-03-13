import asyncio
import datetime
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from ub_core.utils.helpers import get_name

from app import BOT, CustomDB, Message, bot, extra_config

SETTINGS = CustomDB["COMMON_SETTINGS"]

MESSAGE_CACHE: dict[int, list[Message]] = defaultdict(list)
FLOOD_LIST: list[int] = []

LAST_PM_ID: int = 0


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


BASIC_FILTERS = (
    ~filters.channel
    & ~filters.bot
    & ~filters.service
    & ~filters.chat(chats=[bot.me.id])
    & ~filters.me
    & ~filters.create(lambda _, __, m: m.chat.is_support)
)
PM_FILTER = BASIC_FILTERS & filters.private & filters.create(lambda _, __, ___: extra_config.PM_LOGGER)
TAG_FILTER = (
    BASIC_FILTERS & filters.mentioned & filters.create(lambda _, __, ___: extra_config.TAG_LOGGER)
) & ~filters.private


@bot.on_message(filters=PM_FILTER | TAG_FILTER)
async def _logger(bot: BOT, message: Message):
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

    new_data = {k: v for k, v in MESSAGE_CACHE.items() if v}
    MESSAGE_CACHE.clear()
    MESSAGE_CACHE.update(new_data)


async def log_pm(message: Message, log_info: bool):
    extra_info = None

    if log_info:
        extra_info = f"#PM\n{message.from_user.mention} [{message.from_user.id}]"

    await log_message(message=message, extra_info=extra_info, thread_id=extra_config.PM_LOGGER_THREAD_ID)


async def log_chat(message: Message):
    if message.sender_chat:
        mention, u_id = message.sender_chat.title, message.sender_chat.id
    else:
        mention, u_id = message.from_user.mention(style=ParseMode.HTML), message.from_user.id

    extra_info = (
        f"#TAG\n{mention} [{u_id}]\nMessage: \n<a href='{message.link}'>{message.chat.title}</a> ({message.chat.id})"
    )

    await log_message(
        message=message,
        reply_to_message=message.reply_to_message,
        extra_info=extra_info,
        thread_id=extra_config.TAG_LOGGER_THREAD_ID,
    )


async def log_message(
    message: Message, reply_to_message: Message | None = None, thread_id: int = None, extra_info: str = None
) -> None:

    schedule_date = datetime.datetime.now(datetime.UTC) + datetime.timedelta(seconds=10)

    if extra_info:
        await bot.send_message(
            chat_id=extra_config.MESSAGE_LOGGER_CHAT,
            text=extra_info,
            message_thread_id=thread_id,
            parse_mode=ParseMode.HTML,
            schedule_date=schedule_date,
        )

    to_forward_ids = [message.id]

    if reply_to_message:
        to_forward_ids.insert(0, reply_to_message.id)

    # Try to schedule forward of messages
    forwarded = await bot.forward_messages(
        from_chat_id=message.chat.id,
        chat_id=extra_config.MESSAGE_LOGGER_CHAT,
        message_ids=to_forward_ids,
        message_thread_id=thread_id,
        schedule_date=schedule_date + datetime.timedelta(seconds=1),
    )

    # Manually copy them if forward fails
    if len(forwarded) != len(to_forward_ids):
        if reply_to_message:
            await reply_to_message.copy(
                chat_id=extra_config.MESSAGE_LOGGER_CHAT,
                message_thread_id=thread_id,
                schedule_date=schedule_date + datetime.timedelta(seconds=1),
            )
        await message.copy(
            chat_id=extra_config.MESSAGE_LOGGER_CHAT,
            message_thread_id=thread_id,
            schedule_date=schedule_date + datetime.timedelta(2),
        )
