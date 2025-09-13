import asyncio
import os
import random
import shutil
import time
from io import BytesIO
from pathlib import Path

from PIL import Image
from pyrogram.enums import MessageMediaType
from pyrogram.errors import StickersetInvalid
from pyrogram.raw import functions
from pyrogram.raw import types as raw_types
from pyrogram.raw.base.messages import StickerSet as BaseStickerSet
from pyrogram.types import User
from pyrogram.utils import FileId
from ub_core import utils as core_utils

from app import BOT, Config, Message, bot, extra_config

EMOJIS = ("☕", "🤡", "🙂", "🤔", "🔪", "😂", "💀")


async def save_sticker(file: Path | BytesIO) -> str:
    client = getattr(bot, "bot", bot)

    sent_file = await client.send_document(
        chat_id=Config.LOG_CHAT,
        document=file,
        message_thread_id=Config.LOG_CHAT_THREAD_ID,
    )

    if isinstance(file, Path) and file.is_file():
        shutil.rmtree(file.parent, ignore_errors=True)

    return sent_file.document.file_id


def resize_photo(input_file: BytesIO) -> BytesIO:
    image = Image.open(input_file)
    maxsize = 512
    scale = maxsize / max(image.width, image.height)
    new_size = (int(image.width * scale), int(image.height * scale))
    image = image.resize(new_size, Image.LANCZOS)
    resized_photo = BytesIO()
    resized_photo.name = "sticker.png"
    image.save(resized_photo, format="PNG")
    return resized_photo


async def photo_kang(message: Message, **_) -> tuple[str, None]:
    file = await message.download(in_memory=True)
    file.seek(0)
    resized_file = await asyncio.to_thread(resize_photo, file)
    return await save_sticker(resized_file), None


async def video_kang(message: Message, ff=False) -> tuple[str, None]:
    video = message.video or message.animation or message.document

    if video.file_size > 5242880:
        raise MemoryError("File Size exceeds 5MB.")

    download_path = Path("downloads") / str(time.time())
    input_file = download_path / "input.mp4"
    output_file = download_path / "sticker.webm"

    download_path.mkdir(parents=True, exist_ok=True)

    await message.download(str(input_file))

    duration = getattr(video, "duration", None)
    if not duration:
        duration = await core_utils.get_duration(file=str(input_file))

    await resize_video(input_file=input_file, output_file=output_file, duration=duration, ff=ff)

    return await save_sticker(output_file), None


async def resize_video(
    input_file: Path | str, output_file: Path | str, duration: int, ff: bool = False
):
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


async def document_kang(message: Message, ff: bool = False) -> tuple[str, None]:
    name, ext = os.path.splitext(core_utils.get_tg_media_details(message).file_name)
    if ext.lower() in core_utils.MediaExts.PHOTO:
        return await photo_kang(message)
    elif ext.lower() in {*core_utils.MediaExts.VIDEO, *core_utils.MediaExts.GIF}:
        return await video_kang(message=message, ff=ff)


async def sticker_kang(message: Message, **_) -> tuple[str, str]:
    sticker = message.sticker
    if sticker.is_animated:
        raise TypeError("Animated Stickers Not Supported.")
    return sticker.file_id, sticker.emoji


MEDIA_TYPE_MAP = {
    MessageMediaType.PHOTO: photo_kang,
    MessageMediaType.VIDEO: video_kang,
    MessageMediaType.ANIMATION: video_kang,
    MessageMediaType.DOCUMENT: document_kang,
    MessageMediaType.STICKER: sticker_kang,
}


async def get_sticker_set(
    client: BOT, user: User
) -> tuple[str, str, bool, raw_types.StickerSet | None]:
    count = 0
    create_new = False
    suffix = f"_by_{client.me.username}" if client.is_bot else ""

    while True:
        shortname = f"P_UB_{user.id}_mixpack_{count}{suffix}"
        try:
            sticker_set: BaseStickerSet = await client.invoke(
                functions.messages.GetStickerSet(
                    stickerset=raw_types.InputStickerSetShortName(short_name=shortname),
                    hash=0,
                )
            )
            sticker_set = sticker_set.set
            if sticker_set.count < 120:
                break
            count += 1
        except StickersetInvalid:
            create_new = True
            sticker_set: BaseStickerSet | None = None
            break

    if extra_config.CUSTOM_PACK_NAME:
        pack_title = extra_config.CUSTOM_PACK_NAME
    else:
        pack_title = f"{user.username or core_utils.get_name(user)}'s kang pack vol {count}"

    return shortname, pack_title, create_new, sticker_set


async def kang_sticker(
    client: BOT, media_file_id: str, emoji: str = None, user: User = None
) -> BaseStickerSet:
    shortname, pack_title, create_new, sticker_set = await get_sticker_set(client, user)

    file_id = FileId.decode(media_file_id)

    document = raw_types.InputDocument(
        access_hash=file_id.access_hash,
        id=file_id.media_id,
        file_reference=file_id.file_reference,
    )

    set_item = raw_types.InputStickerSetItem(
        document=document, emoji=emoji or random.choice(EMOJIS)
    )

    if create_new:
        query = functions.stickers.CreateStickerSet(
            user_id=await bot.resolve_peer(peer_id=user.id),
            short_name=shortname,
            title=pack_title,
            stickers=[set_item],
        )
    else:
        query = functions.stickers.AddStickerToSet(
            stickerset=raw_types.InputStickerSetID(
                id=sticker_set.id, access_hash=sticker_set.access_hash
            ),
            sticker=set_item,
        )

    return await client.invoke(query)


async def kang(bot: BOT, message: Message):
    """
    CMD: KANG
    INFO: Save a sticker/image/gif/video to your sticker pack.
    FLAGS: -f to fastforward video tp fit 3 sec duration.
    USAGE: .kang | .kang -f

    Diffrences to legacy version:
        • Is almost instantaneous because uses built-in methods.
        • Sudo users get their own packs.
        • If in dual mode pack ownership is given to respective Sudo users.
        • Kangs both photo and video stickers into a single pack.
        • As a result video stickers are not limited to the limit of 50.

    Note: if you still would like to use old style set USE_LEGACY_KANG=1
    """
    replied = message.replied

    media_func = MEDIA_TYPE_MAP.get(replied.media)

    if not media_func:
        await message.reply("<code>Unsupported Media...</code>")
        return

    response = await message.reply("<code>Processing...</code>")

    bot = getattr(bot, "bot", bot)

    file_id, emoji = await media_func(message=replied, ff="-f" in message.flags)

    try:
        stickers = await kang_sticker(bot, file_id, emoji, user=message.from_user)
        await response.edit(
            f"Kanged: <a href='t.me/addstickers/{stickers.set.short_name}'>here</a>",
            disable_preview=True,
        )
    except Exception as e:
        await response.edit(str(e))


if not extra_config.USE_LEGACY_KANG:
    BOT.add_cmd("kang")(kang)
