import asyncio

from pyrogram import filters
from pyrogram.enums import ChatType, MessageEntityType
from pyrogram.errors import MessageIdInvalid

from app import BOT, Config, CustomDB, Message, bot

TLOGGER = CustomDB("COMMON_SETTINGS")

MESSAGE_CACHE: dict[int, list[Message]] = {}


async def init_task():
    log_check = await TLOGGER.find_one({"_id": "tlogger_switch"})
    if not log_check:
        return
    Config.TLOGGER = log_check["value"]
    Config.TLOGGER_TASK = asyncio.create_task(tlogger_runner())


@bot.add_cmd(cmd="tlogger")
async def logger_switch(bot: BOT, message: Message):
    """
    CMD: TLOGGER
    INFO: Enable/Disable PM and Tag Logger.
    FLAGS: -c to check status.
    USAGE:
        .tlogger | .tlogger -c
    """
    if "-c" in message.flags:
        await message.reply(
            text=f"PM and Tag Logger is enabled: <b>{Config.TLOGGER}</b>", del_in=8
        )
        return
    value = not Config.TLOGGER
    Config.TLOGGER = value
    await asyncio.gather(
        TLOGGER.add_data({"_id": "tlogger_switch", "value": value}),
        message.reply(text=f"PM and Tag Logger is enabled: <b>{value}</b>!", del_in=8),
    )


@bot.on_message(
    filters=(~filters.channel & ~filters.bot & ~filters.service) & filters.incoming,
    group=2,
)
async def tlogger_cacher(bot: BOT, message: Message):
    if not Config.TLOGGER:
        return
    if message.chat.type == ChatType.PRIVATE:
        cache_message(message)
        return
    if message.mentioned:
        for entity in message.entities:
            if (
                entity.type == MessageEntityType.MENTION
                and entity.user
                and entity.user.id == bot.me.id
            ):
                cache_message(message)
                if message.reply_to_message:
                    cache_message(message.reply_to_message)
                return
    text = message.text or message.caption
    if text and bot.me.username and bot.me.username in text:
        cache_message(message)
        if message.reply_to_message:
            cache_message(message.reply_to_message)


def cache_message(message: Message):
    id = message.chat.id
    if id in MESSAGE_CACHE.keys():
        MESSAGE_CACHE[id].append(message)
    else:
        MESSAGE_CACHE[id] = [message]


async def tlogger_runner():
    if not Config.TLOGGER:
        return
    while True:
        for cache_id, cached_list in MESSAGE_CACHE.items():
            if not cached_list:
                MESSAGE_CACHE.pop(cache_id)
                continue
            for msg in cached_list:
                try:
                    await msg.forward(Config.TLOGGER_CHAT)
                    await bot.send_message(
                        chat_id=Config.TLOGGER_CHAT,
                        text=f"{msg.from_user.mention} [{msg.from_user.id}] in Chat:\n{msg.link}",
                    )
                except MessageIdInvalid:
                    await log_deleted_message(msg)
                MESSAGE_CACHE[cache_id].remove(msg)
                await asyncio.sleep(15)
            await asyncio.sleep(30)
        await asyncio.sleep(5)


async def log_deleted_message(message: Message):
    notice = f"{message.from_user.mention} [{message.from_user.id}] deleted this message.\n\nLink: {message.link}\n\nText:\n"
    if not message.media:
        await bot.send_message(
            chat_id=Config.TLOGGER_CHAT,
            text=notice + message.text,
            disable_web_page_preview=True,
        )
        return
    kwargs = dict(
        chat_id=Config.TLOGGER_CHAT, caption=f"{notice}Caption:\n\n{message.caption}"
    )
    if message.photo:
        await bot.send_photo(**kwargs, photo=message.photo.file_id)
    elif message.audio:
        await bot.send_audio(**kwargs, audio=message.audio.file_id)
    elif message.animation:
        await bot.send_animation(
            **kwargs, animation=message.animation.file_id, unsave=True
        )
    elif message.document:
        await bot.send_document(
            **kwargs, document=message.document.file_id, force_document=True
        )
    elif message.video:
        await bot.send_video(**kwargs, video=message.video.file_id)
    elif message.voice:
        await bot.send_voice(**kwargs, voice=message.voice.file_id)
    elif message.sticker:
        await bot.send_sticker(
            chat_id=Config.TLOGGER_CHAT, sticker=message.sticker.file_id
        )
    else:
        await bot.send_message(chat_id=Config.TLOGGER_CHAT, text=str(message))
