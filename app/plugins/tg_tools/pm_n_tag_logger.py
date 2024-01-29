import asyncio
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatType, MessageEntityType
from pyrogram.errors import MessageIdInvalid

from app import BOT, Config, CustomDB, Message, bot

LOGGER = CustomDB("COMMON_SETTINGS")

MESSAGE_CACHE: dict[int, list[Message]] = defaultdict(list)


async def init_task():
    tag_check = await LOGGER.find_one({"_id": "tag_logger_switch"})
    pm_check = await LOGGER.find_one({"_id": "pm_logger_switch"})
    if tag_check:
        Config.TAG_LOGGER = tag_check["value"]
    if pm_check:
        Config.PM_LOGGER = pm_check["value"]
    Config.MESSAGE_LOGGER_TASK = asyncio.create_task(runner())


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
            text=f"{text.capitalize()} Logger is enabled: <b>{getattr(Config, conf_str)}</b>!",
            del_in=8,
        )
        return
    value: bool = not getattr(Config, conf_str)
    setattr(Config, conf_str, value)
    await asyncio.gather(
        LOGGER.add_data({"_id": f"{text}_logger_switch", "value": value}),
        message.reply(
            text=f"{text.capitalize()} Logger is enabled: <b>{value}</b>!", del_in=8
        ),
        bot.log_text(
            text=f"#{text.capitalize()}Logger is enabled: <b>{value}</b>!", type="info"
        ),
    )
    if not Config.MESSAGE_LOGGER_TASK or Config.MESSAGE_LOGGER_TASK.done():
        Config.MESSAGE_LOGGER_TASK = asyncio.create_task(runner())


basic_filters = (
    ~filters.channel
    & ~filters.bot
    & ~filters.service
    & ~filters.chat(chats=[bot.me.id])
    & ~filters.me
)


@bot.on_message(
    filters=basic_filters
    & filters.private
    & filters.create(lambda _, __, ___: Config.PM_LOGGER),
    group=2,
)
async def pm_logger(bot: BOT, message: Message):
    cache_message(message)


tag_filter = filters.create(lambda _, __, ___: Config.TAG_LOGGER)


@bot.on_message(
    filters=(basic_filters & filters.reply & tag_filter) & ~filters.private, group=2
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
    filters=(basic_filters & filters.mentioned & tag_filter) & ~filters.private, group=2
)
async def mention_logger(bot: BOT, message: Message):
    for entity in message.entities or []:
        if (
            entity.type == MessageEntityType.MENTION
            and entity.user
            and entity.user.id == bot.me.id
        ):
            cache_message(message)
    message.continue_propagation()


@bot.on_message(
    filters=(basic_filters & (filters.text | filters.media) & tag_filter)
    & ~filters.private,
    group=2,
)
async def username_logger(bot: BOT, message: Message):
    text = message.text or message.caption or ""
    if bot.me.username and f"@{bot.me.username}" in text:
        cache_message(message)
    message.continue_propagation()


def cache_message(message: Message):
    m_id = message.chat.id
    if len(MESSAGE_CACHE[m_id]) > 10:
        bot.log.error("Flood detected, Message not cached.")
        return
    MESSAGE_CACHE[m_id].append(message)


async def runner():
    if not (Config.TAG_LOGGER or Config.PM_LOGGER):
        return
    last_pm_logged_id = 0
    while True:
        cached_keys = list(MESSAGE_CACHE.keys())
        if not cached_keys:
            await asyncio.sleep(5)
            continue
        first_key = cached_keys[0]
        cached_list = MESSAGE_CACHE.copy()[first_key]
        if not cached_list:
            MESSAGE_CACHE.pop(first_key)
        for idx, msg in enumerate(cached_list):
            if msg.chat.type == ChatType.PRIVATE:
                if last_pm_logged_id != first_key:
                    last_pm_logged_id = first_key
                    log_info = True
                else:
                    log_info = False
                await log_pm(message=msg, log_info=log_info)
            else:
                await log_chat(message=msg)
            MESSAGE_CACHE[first_key].remove(msg)
            await asyncio.sleep(5)
        await asyncio.sleep(15)


async def log_pm(message: Message, log_info: bool):
    if log_info:
        await bot.send_message(
            chat_id=Config.MESSAGE_LOGGER_CHAT,
            text=f"#PM\n{message.from_user.mention} [{message.from_user.id}]",
        )
    try:
        await message.forward(Config.MESSAGE_LOGGER_CHAT)
    except MessageIdInvalid:
        notice = (
            f"{message.from_user.mention} [{message.from_user.id}] deleted this message."
            f"\n\n---\n\n"
            f"Message: \n<a href='{message.link}'>{message.chat.title or message.chat.first_name}</a> ({message.chat.id})"
            f"\n\n---\n\n"
            f"Caption:\n{message.caption or 'No Caption in media.'}"
        )

        await message.copy(Config.MESSAGE_LOGGER_CHAT, caption=notice)


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
        try:
            await message.reply_to_message.forward(Config.MESSAGE_LOGGER_CHAT)
        except MessageIdInvalid:
            await message.reply_to_message.copy(
                Config.MESSAGE_LOGGER_CHAT, caption=notice
            )
    try:
        logged = await message.forward(Config.MESSAGE_LOGGER_CHAT)
        await logged.reply(
            text=f"#TAG\n{mention} [{u_id}]\nMessage: \n<a href='{message.link}'>{message.chat.title}</a> ({message.chat.id})",
        )
    except MessageIdInvalid:
        await message.copy(Config.MESSAGE_LOGGER_CHAT, caption=notice)
