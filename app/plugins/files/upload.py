import asyncio
import glob
import os
import time
from functools import partial
from typing import Union

from pyrogram.types import ReplyParameters
from ub_core.utils import (
    Download,
    DownloadedFile,
    MediaType,
    check_audio,
    get_duration,
    progress,
    take_ss,
)

from app import BOT, Config, Message

UPLOAD_TYPES = Union[BOT.send_audio, BOT.send_document, BOT.send_photo, BOT.send_video]


async def video_upload(
    bot: BOT, file: DownloadedFile, has_spoiler: bool
) -> UPLOAD_TYPES:
    thumb = await take_ss(file.path, path=file.path)
    if not await check_audio(file.path):
        return partial(
            bot.send_animation,
            thumb=thumb,
            unsave=True,
            animation=file.path,
            duration=await get_duration(file.path),
            has_spoiler=has_spoiler,
        )
    return partial(
        bot.send_video,
        thumb=thumb,
        video=file.path,
        duration=await get_duration(file.path),
        has_spoiler=has_spoiler,
    )


async def photo_upload(
    bot: BOT, file: DownloadedFile, has_spoiler: bool
) -> UPLOAD_TYPES:
    return partial(bot.send_photo, photo=file.path, has_spoiler=has_spoiler)


async def audio_upload(bot: BOT, file: DownloadedFile, *_, **__) -> UPLOAD_TYPES:
    return partial(
        bot.send_audio,
        audio=file.path,
        duration=await get_duration(file=file.path),
    )


async def doc_upload(bot: BOT, file: DownloadedFile, *_, **__) -> UPLOAD_TYPES:
    return partial(
        bot.send_document, document=file.path, disable_content_type_detection=True
    )


FILE_TYPE_MAP = {
    MediaType.PHOTO: photo_upload,
    MediaType.DOCUMENT: doc_upload,
    MediaType.GIF: video_upload,
    MediaType.AUDIO: audio_upload,
    MediaType.VIDEO: video_upload,
}


def file_exists(file: str) -> bool:
    return os.path.isfile(file)


def size_over_limit(size: int | float, client: BOT) -> bool:
    limit = 3999 if client.me.is_premium else 1999
    return size > limit


@BOT.add_cmd(cmd="upload")
async def upload(bot: BOT, message: Message):
    """
    CMD: UPLOAD
    INFO: Upload Media/Local Files/Plugins to TG.
    FLAGS:
        -d: to upload as doc.
        -s: spoiler.
        -bulk: for folder upload.
        -r: file name regex [ to be used with -bulk only ]
    USAGE:
        .upload [-d] URL | Path to File | CMD
        .upload -bulk downloads/videos
        .upload -bulk -d -s downloads/videos
        .upload -bulk -r -s downloads/videos/*.mp4 (only uploads mp4)
    """
    input = message.filtered_input

    if not input:
        await message.reply("give a file url | path to upload.")
        return

    response = await message.reply("checking input...")

    if input in Config.CMD_DICT:
        await message.reply_document(document=Config.CMD_DICT[input].cmd_path)
        await response.delete()
        return

    elif input.startswith("http") and not file_exists(input):

        try:
            async with Download(
                url=input,
                dir=os.path.join("downloads", str(time.time())),
                message_to_edit=response,
            ) as dl_obj:
                if size_over_limit(dl_obj.size, client=bot):
                    await response.edit(
                        "<b>Aborted</b>, File size exceeds TG Limits!!!"
                    )
                    return

                await response.edit("URL detected in input, Starting Download....")
                file: DownloadedFile = await dl_obj.download()

        except asyncio.exceptions.CancelledError:
            await response.edit("Cancelled...")
            return

        except TimeoutError:
            await response.edit("Download Timeout...")
            return

        except Exception as e:
            await response.edit(str(e))
            return

    elif file_exists(input):
        file = DownloadedFile(file=input)

        if size_over_limit(file.size, client=bot):
            await response.edit("<b>Aborted</b>, File size exceeds TG Limits!!!")
            return

    elif "-bulk" in message.flags:
        await bulk_upload(message=message, response=response)
        return

    else:
        await response.edit("invalid `cmd` | `url` | `file path`!!!")
        return

    await response.edit("Uploading....")
    await upload_to_tg(file=file, message=message, response=response)


async def bulk_upload(message: Message, response: Message):

    if "-r" in message.flags:
        path_regex = message.filtered_input
    else:
        path_regex = os.path.join(message.filtered_input, "*")

    file_list = [f for f in glob.glob(path_regex) if file_exists(f)]

    if not file_list:
        await response.edit("Invalid Folder path/regex or Folder Empty")
        return

    await response.edit(f"Preparing to upload {len(file_list)} files.")

    for file in file_list:

        file_info = DownloadedFile(file=file)

        if size_over_limit(file_info.size, client=message._client):
            await response.reply(
                f"Skipping {file_info.name} due to size exceeding limit."
            )
            continue

        temp_resp = await response.reply(f"starting to upload `{file_info.name}`")

        await upload_to_tg(file=file_info, message=message, response=temp_resp)
        await asyncio.sleep(3)

    await response.delete()


async def upload_to_tg(file: DownloadedFile, message: Message, response: Message):

    progress_args = (response, "Uploading...", file.path)

    if "-d" in message.flags:
        upload_method = partial(
            message._client.send_document,
            document=file.path,
            disable_content_type_detection=True,
        )
    else:
        upload_method: UPLOAD_TYPES = await FILE_TYPE_MAP[file.type](
            bot=message._client, file=file, has_spoiler="-s" in message.flags
        )

    try:
        await upload_method(
            chat_id=message.chat.id,
            reply_parameters=ReplyParameters(message_id=message.reply_id),
            progress=progress,
            progress_args=progress_args,
            caption=file.name,
        )
        await response.delete()

    except asyncio.exceptions.CancelledError:
        await response.edit("Cancelled....")
        raise
