import asyncio
import os
import random
import shutil
import time
from io import BytesIO

from PIL import Image
from pyrogram.enums import MessageMediaType
from pyrogram.errors import StickersetInvalid
from pyrogram.raw.functions.messages import GetStickerSet
from pyrogram.raw.types import InputStickerSetShortName
from ub_core.utils.helpers import get_name
from ub_core.utils.media_helper import MediaExts
from ub_core.utils.shell import get_duration, run_shell_cmd

from app import BOT, Message, bot

EMOJIS = ("☕", "🤡", "🙂", "🤔", "🔪", "😂", "💀")


@bot.add_cmd(cmd="kang")
async def kang_sticker(bot: BOT, message: Message):
    """
    CMD: KANG
    INFO: Save a sticker/image/gif/video to your sticker pack.
    FLAGS: -f to fastforward video tp fit 3 sec duration.
    USAGE: .kang | .kang -f
    """

    response = await message.reply("Checking input")
    media_coro = get_sticker_media_coro(message)
    if not media_coro:
        await response.edit("Unsupported Media.")
        return
    kwargs: dict = await media_coro
    pack_title, pack_name, create_new = await get_sticker_set(
        limit=kwargs["limit"], is_video=kwargs["is_video"]
    )
    if create_new:
        await create_n_kang(
            kwargs=kwargs, pack_title=pack_title, pack_name=pack_name, message=message
        )
        await response.edit(
            text=f"Kanged: <a href='t.me/addstickers/{pack_name}'>here</a>"
        )
        return
    async with bot.Convo(client=bot, chat_id="stickers", timeout=60) as convo:
        await convo.send_message(text="/addsticker", get_response=True, timeout=5)
        await convo.send_message(text=pack_name, get_response=True, timeout=5)
        if kwargs.get("sticker"):
            await message.reply_to_message.copy(chat_id="stickers", caption="")
            await convo.get_response()
        else:
            await convo.send_document(
                document=kwargs["file"], get_response=True, timeout=5
            )
        await convo.send_message(
            text=kwargs.get("emoji") or random.choice(EMOJIS),
            get_response=True,
            timeout=5,
        )
        await convo.send_message(text="/done", get_response=True, timeout=5)
    if kwargs.get("path"):
        shutil.rmtree(kwargs["path"], ignore_errors=True)
    await response.edit(text=f"Kanged: <a href='t.me/addstickers/{pack_name}'>here</a>")


async def create_n_kang(
    kwargs: dict, pack_title: str, pack_name: str, message: Message
):
    async with bot.Convo(client=bot, chat_id="stickers", timeout=60) as convo:
        await convo.send_message(text=kwargs["cmd"], get_response=True, timeout=5)
        await convo.send_message(text=pack_title, get_response=True, timeout=5)
        if kwargs.get("sticker"):
            await message.reply_to_message.copy(chat_id="stickers", caption="")
            await convo.get_response(timeout=5)
        else:
            await convo.send_document(
                document=kwargs["file"], get_response=True, timeout=5
            )
        await convo.send_message(
            text=kwargs.get("emoji") or random.choice(EMOJIS),
            get_response=True,
            timeout=5,
        )
        await convo.send_message(text="/publish", get_response=True, timeout=5)
        await convo.send_message("/skip")
        await convo.send_message(pack_name, get_response=True, timeout=5)
    if kwargs.get("path"):
        shutil.rmtree(kwargs["path"], ignore_errors=True)


async def get_sticker_set(limit: int, is_video=False) -> tuple[str, str, bool]:
    count = 0
    pack_name = f"PUB_{bot.me.id}_pack"
    video = "_video" if is_video else ""
    create_new = False
    while True:
        try:
            sticker = await bot.invoke(
                GetStickerSet(
                    stickerset=InputStickerSetShortName(
                        short_name=f"{pack_name}{video}_{count}"
                    ),
                    hash=0,
                )
            )
            if sticker.set.count < limit:
                break
            count += 1
        except StickersetInvalid:
            create_new = True
            break
    if cus_nick := os.environ.get("CUSTOM_PACK_NAME"):
        pack_title = cus_nick + video
    else:
        pack_title = (
            f"{bot.me.username or get_name(bot.me)}'s {video}kang pack vol {count}"
        )
    return pack_title, f"{pack_name}{video}_{count}", create_new


def get_sticker_media_coro(message: Message):
    match message.reply_to_message.media:
        case MessageMediaType.PHOTO:
            return photo_kang(message.reply_to_message)
        case MessageMediaType.ANIMATION:
            return video_kang(message.reply_to_message, ff="-f" in message.flags)
        case MessageMediaType.DOCUMENT:
            return document_kang(message.reply_to_message, ff="-f" in message.flags)
        case MessageMediaType.STICKER:
            return sticker_kang(message.reply_to_message)
        case MessageMediaType.VIDEO:
            return video_kang(message.reply_to_message, ff="-f" in message.flags)
        case _:
            return


async def photo_kang(message: Message) -> dict:
    download_path = os.path.join("downloads", str(time.time()))
    os.makedirs(download_path, exist_ok=True)
    input_file = os.path.join(download_path, "photo.jpg")
    await message.download(input_file)
    file = await asyncio.to_thread(resize_photo, input_file)
    return dict(
        cmd="/newpack", limit=120, is_video=False, file=file, path=download_path
    )


def resize_photo(input_file: str) -> BytesIO:
    image = Image.open(input_file)
    maxsize = 512
    scale = maxsize / max(image.width, image.height)
    new_size = (int(image.width * scale), int(image.height * scale))
    image = image.resize(new_size, Image.LANCZOS)
    resized_photo = BytesIO()
    resized_photo.name = "sticker.png"
    image.save(resized_photo, format="PNG")
    return resized_photo


async def video_kang(message: Message, ff=False) -> dict:
    video = message.video or message.animation or message.document
    if video.file_size > 5242880:
        raise MemoryError("File Size exceeds 5MB.")
    download_path = os.path.join("downloads", f"{time.time()}")
    os.makedirs(download_path, exist_ok=True)
    input_file = os.path.join(download_path, "input.mp4")
    output_file = os.path.join(download_path, "sticker.webm")
    await message.download(input_file)
    if not hasattr(video, "duration"):
        duration = await get_duration(file=input_file)
    else:
        duration = video.duration
    await resize_video(
        input_file=input_file, output_file=output_file, duration=duration, ff=ff
    )
    return dict(
        cmd="/newvideo", limit=50, is_video=True, file=output_file, path=download_path
    )


async def resize_video(
    input_file: str, output_file: str, duration: int, ff: bool = False
):
    cmd = f"ffmpeg -hide_banner -loglevel error -i '{input_file}' -vf "
    if ff:
        cmd += (
            '"scale=w=512:h=512:force_original_aspect_ratio=decrease,setpts=0.3*PTS" '
        )
        cmd += "-ss 0 -t 3 -r 30 -loop 0 -an -c:v libvpx-vp9 -b:v 256k -fs 256k "
    elif duration < 3:
        cmd += '"scale=w=512:h=512:force_original_aspect_ratio=decrease" '
        cmd += "-ss 0 -r 30 -an -c:v libvpx-vp9 -b:v 256k -fs 256k "
    else:
        cmd += '"scale=w=512:h=512:force_original_aspect_ratio=decrease" '
        cmd += "-ss 0 -t 3 -r 30 -an -c:v libvpx-vp9 -b:v 256k -fs 256k "
    await run_shell_cmd(cmd=f"{cmd}'{output_file}'")


async def document_kang(message: Message, ff: bool = False) -> dict:
    name, ext = os.path.splitext(message.document.file_name)
    if ext.lower() in MediaExts.PHOTO:
        return (await photo_kang(message))  # fmt:skip
    elif ext.lower() in {*MediaExts.VIDEO, *MediaExts.GIF}:
        return (await video_kang(message=message, ff=ff))  # fmt:skip


async def sticker_kang(message: Message) -> dict:
    emoji = message.sticker.emoji
    sticker = message.sticker
    if sticker.file_name.lower().endswith(".webp"):
        return dict(
            cmd="/newpack", emoji=emoji, is_video=False, sticker=sticker, limit=120
        )
    elif sticker.file_name.lower().endswith(".webm"):
        input_file: BytesIO = await message.download(in_memory=True)
        input_file.seek(0)
        return dict(
            emoji=emoji, file=input_file, cmd="/newvideo", is_video=True, limit=50
        )
