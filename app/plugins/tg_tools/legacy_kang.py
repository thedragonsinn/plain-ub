import asyncio
import os
import random
import shutil
import time
from io import BytesIO

from PIL import Image
from pyrogram import raw
from pyrogram.enums import MessageMediaType
from pyrogram.errors import StickersetInvalid
from ub_core import utils as core_utils

from app import BOT, Message, bot, extra_config

EMOJIS = ("☕", "🤡", "🙂", "🤔", "🔪", "😂", "💀")


async def get_sticker_set(limit: int, is_video=False) -> tuple[str, str, bool]:
    count = 0
    pack_name = f"PUB_{bot.me.id}_pack"
    video = "_video" if is_video else ""
    create_new = False
    while True:
        try:
            sticker = await bot.invoke(
                raw.functions.messages.GetStickerSet(
                    stickerset=raw.types.InputStickerSetShortName(
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
            f"{bot.me.username or core_utils.get_name(bot.me)}'s {video}kang pack vol {count}"
        )
    return pack_title, f"{pack_name}{video}_{count}", create_new


async def photo_kang(message: Message, **_) -> dict:
    download_path = os.path.join("downloads", str(time.time()))
    os.makedirs(download_path, exist_ok=True)

    input_file = os.path.join(download_path, "photo.jpg")
    await message.download(input_file)

    file = await asyncio.to_thread(resize_photo, input_file)

    return dict(cmd="/newpack", limit=120, is_video=False, file=file, path=download_path)


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
        duration = await core_utils.get_duration(file=input_file)
    else:
        duration = video.duration
    await resize_video(input_file=input_file, output_file=output_file, duration=duration, ff=ff)
    return dict(cmd="/newvideo", limit=50, is_video=True, file=output_file, path=download_path)


async def resize_video(input_file: str, output_file: str, duration: int, ff: bool = False):
    cmd = f"ffmpeg -hide_banner -loglevel error -i '{input_file}' -vf "
    if ff:
        cmd += '"scale=w=512:h=512:force_original_aspect_ratio=decrease,setpts=0.3*PTS" '
        cmd += "-ss 0 -t 3 -r 30 -loop 0 -an -c:v libvpx-vp9 -b:v 256k -fs 256k "
    elif duration < 3:
        cmd += '"scale=w=512:h=512:force_original_aspect_ratio=decrease" '
        cmd += "-ss 0 -r 30 -an -c:v libvpx-vp9 -b:v 256k -fs 256k "
    else:
        cmd += '"scale=w=512:h=512:force_original_aspect_ratio=decrease" '
        cmd += "-ss 0 -t 3 -r 30 -an -c:v libvpx-vp9 -b:v 256k -fs 256k "
    await core_utils.run_shell_cmd(cmd=f"{cmd}'{output_file}'")


async def document_kang(message: Message, ff: bool = False) -> dict:
    name, ext = os.path.splitext(message.document.file_name)
    if ext.lower() in core_utils.MediaExts.PHOTO:
        return await photo_kang(message)
    elif ext.lower() in {*core_utils.MediaExts.VIDEO, *core_utils.MediaExts.GIF}:
        return await video_kang(message=message, ff=ff)


async def sticker_kang(message: Message, **_) -> dict:
    emoji = message.sticker.emoji
    sticker = message.sticker

    if sticker.is_animated:
        raise TypeError("Animated Stickers Not Supported.")

    if sticker.is_video:
        input_file: BytesIO = await message.download(in_memory=True)
        input_file.seek(0)
        return dict(cmd="/newvideo", emoji=emoji, is_video=True, file=input_file, limit=50)

    return dict(cmd="/newpack", emoji=emoji, is_video=False, sticker=sticker, limit=120)


MEDIA_TYPE_MAP = {
    MessageMediaType.PHOTO: photo_kang,
    MessageMediaType.VIDEO: video_kang,
    MessageMediaType.ANIMATION: video_kang,
    MessageMediaType.DOCUMENT: document_kang,
    MessageMediaType.STICKER: sticker_kang,
}


async def create_n_kang(kwargs: dict, pack_title: str, pack_name: str, message: Message):
    async with bot.Convo(client=bot, chat_id="stickers", timeout=5) as convo:
        await convo.send_message(text=kwargs["cmd"], get_response=True)
        await convo.send_message(text=pack_title, get_response=True)

        if kwargs.get("sticker"):
            await message.reply_to_message.copy(chat_id="stickers", caption="")
            await convo.get_response()
        else:
            await convo.send_document(document=kwargs["file"], get_response=True)

        await convo.send_message(
            text=kwargs.get("emoji") or random.choice(EMOJIS), get_response=True
        )
        await convo.send_message(text="/publish", get_response=True)
        await convo.send_message("/skip")
        await convo.send_message(pack_name, get_response=True)

    if kwargs.get("path"):
        shutil.rmtree(kwargs["path"], ignore_errors=True)


async def kang_sticker(bot: BOT, message: Message):
    """
    CMD: LEGACY KANG
    INFO: Save a sticker/image/gif/video to your sticker pack.
    FLAGS: -f to fastforward video tp fit 3 sec duration.
    USAGE: .kang | .kang -f
    """
    replied = message.replied

    media_func = MEDIA_TYPE_MAP.get(replied.media)

    if not media_func:
        await message.reply("Unsupported Media.")
        return

    response: Message = await message.reply("<code>Processing...</code>")

    kwargs: dict = await media_func(message=replied, ff="-f" in message.flags)

    pack_title, pack_name, create_new = await get_sticker_set(
        limit=kwargs["limit"], is_video=kwargs["is_video"]
    )

    if create_new:
        await create_n_kang(
            kwargs=kwargs, pack_title=pack_title, pack_name=pack_name, message=message
        )
        await response.edit(text=f"Kanged: <a href='t.me/addstickers/{pack_name}'>here</a>")
        return

    async with bot.Convo(client=bot, chat_id="stickers", timeout=5) as convo:
        await convo.send_message(text="/addsticker", get_response=True)
        await convo.send_message(text=pack_name, get_response=True)

        if kwargs.get("sticker"):
            await replied.copy(chat_id="stickers", caption="")
            await convo.get_response()
        else:
            await convo.send_document(document=kwargs["file"], get_response=True)

        await convo.send_message(
            text=kwargs.get("emoji") or random.choice(EMOJIS), get_response=True
        )
        await convo.send_message(text="/done", get_response=True)

    if kwargs.get("path"):
        shutil.rmtree(kwargs["path"], ignore_errors=True)

    await response.edit(
        text=f"Kanged: <a href='t.me/addstickers/{pack_name}'>here</a>",
        disable_preview=True,
    )


if extra_config.USE_LEGACY_KANG:
    BOT.add_cmd("kang")(kang_sticker)
