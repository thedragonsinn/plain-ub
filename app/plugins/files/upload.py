import asyncio
import glob
import os
import time

from ub_core.utils import (
    Download,
    DownloadedFile,
    MediaType,
    bytes_to_mb,
    check_audio,
    get_duration,
    progress,
    take_ss,
)

from app import BOT, Config, Message, bot


async def video_upload(file: DownloadedFile, has_spoiler: bool) -> dict[str, dict]:
    thumb = await take_ss(file.full_path, path=file.path)
    if not await check_audio(file.full_path):
        return dict(
            method=bot.send_animation,
            kwargs=dict(
                thumb=thumb,
                unsave=True,
                animation=file.full_path,
                duration=await get_duration(file.full_path),
                has_spoiler=has_spoiler,
            ),
        )
    return dict(
        method=bot.send_video,
        kwargs=dict(
            thumb=thumb,
            video=file.full_path,
            duration=await get_duration(file.full_path),
            has_spoiler=has_spoiler,
        ),
    )


async def photo_upload(file: DownloadedFile, has_spoiler: bool) -> dict[str, dict]:
    return dict(
        method=bot.send_photo,
        kwargs=dict(photo=file.full_path, has_spoiler=has_spoiler),
    )


async def audio_upload(file: DownloadedFile, has_spoiler: bool) -> dict[str, dict]:
    return dict(
        method=bot.send_audio,
        kwargs=dict(
            audio=file.full_path, duration=await get_duration(file=file.full_path)
        ),
    )


async def doc_upload(file: DownloadedFile, has_spoiler: bool) -> dict[str, dict]:
    return dict(
        method=bot.send_document,
        kwargs=dict(document=file.full_path, force_document=True),
    )


FILE_TYPE_MAP = {
    MediaType.PHOTO: photo_upload,
    MediaType.DOCUMENT: doc_upload,
    MediaType.GIF: video_upload,
    MediaType.AUDIO: audio_upload,
    MediaType.VIDEO: video_upload,
}


def file_check(file: str) -> bool:
    return os.path.isfile(file)


def check_size(size: int | float) -> bool:
    limit = 3999 if bot.me.is_premium else 1999
    return size < limit


@bot.add_cmd(cmd="upload")
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

    elif input.startswith("http") and not file_check(input):

        dl_obj: Download = await Download.setup(
            url=input,
            path=os.path.join("downloads", str(time.time())),
            message_to_edit=response,
        )

        if not check_size(dl_obj.size):
            await response.edit("<b>Aborted</b>, File size exceeds TG Limits!!!")
            return

        try:
            file: DownloadedFile = await dl_obj.download()
        except asyncio.exceptions.CancelledError:
            await response.edit("Cancelled...")
            return
        except TimeoutError:
            await response.edit("Download Timeout...")
            return

    elif file_check(input):
        file = DownloadedFile(
            name=input,
            path=os.path.dirname(input),
            full_path=input,
            size=bytes_to_mb(os.path.getsize(input)),
        )

        if not check_size(file.size):
            await response.edit("<b>Aborted</b>, File size exceeds TG Limits!!!")
            return

    elif "-bulk" in message.flags:
        await bulk_upload(message=message, response=response)
        return

    else:
        await response.edit("invalid `cmd` | `url` | `file path`!!!")
        return

    await response.edit("uploading....")
    await upload_to_tg(file=file, message=message, response=response)


async def bulk_upload(message: Message, response: Message):

    if "-r" in message.flags:
        path_regex = message.filtered_input
    else:
        path_regex = os.path.join(message.filtered_input, "*")

    file_list = [f for f in glob.glob(path_regex) if file_check(f)]

    if not file_list:
        await response.edit("Invalid Folder path/regex or Folder Empty")
        return

    await response.edit(f"Preparing to upload {len(file_list)} files.")

    for file in file_list:

        file_info = DownloadedFile(
            name=os.path.basename(file),
            path=os.path.dirname(file),
            full_path=file,
            size=bytes_to_mb(os.path.getsize(file)),
        )

        if not check_size(file_info.size):
            await response.reply(
                f"Skipping {file_info.name} due to size exceeding limit."
            )
            continue

        temp_resp = await response.reply(f"starting to upload `{file_info.name}`")

        await upload_to_tg(file=file_info, message=message, response=temp_resp)
        await asyncio.sleep(3)

    await response.delete()


async def upload_to_tg(file: DownloadedFile, message: Message, response: Message):

    progress_args = (response, "Uploading...", file.name, file.full_path)

    if "-d" in message.flags:
        method_n_kwargs: dict = dict(
            method=bot.send_document,
            kwargs=dict(document=file.full_path, force_document=True),
        )
    else:
        method_n_kwargs: dict = await FILE_TYPE_MAP[file.type](
            file, has_spoiler="-s" in message.flags
        )

    try:
        await method_n_kwargs["method"](
            chat_id=message.chat.id,
            reply_to_message_id=message.reply_id,
            progress=progress,
            progress_args=progress_args,
            caption=file.name,
            **method_n_kwargs["kwargs"],
        )
        await response.delete()
    except asyncio.exceptions.CancelledError:
        await response.edit("Cancelled....")
        raise
