import os
import time

from app import BOT, bot, Config 
from app.core import Message
from app.utils.downloader import Download, DownloadedFile
from app.utils.helpers import progress
from app.utils.media_helper import MediaType, bytes_to_mb
from app.utils.shell import check_audio, get_duration, take_ss


async def video_upload(
    file: DownloadedFile, has_spoiler: bool
) -> dict[str, bot.send_video, bot.send_animation, dict]:
    thumb = await take_ss(file.full_path)
    if not check_audio(file.full_path):
        return {
            "method": bot.send_animation,
            "kwargs": {
                "thumb": thumb,
                "unsave": True,
                "animation": file.full_path,
                "duration": get_duration(file.full_path),
                "has_spoiler": has_spoiler,
            },
        }
    return {
        "method": bot.send_video,
        "kwargs": {
            "thumb": thumb,
            "video": file.full_path,
            "duration": get_duration(file.full_path),
            "has_spoiler": has_spoiler,
        },
    }


async def photo_upload(
    file: DownloadedFile, has_spoiler: bool
) -> dict[str, bot.send_photo, dict]:
    return {
        "method": bot.send_photo,
        "kwargs": {"photo": file.full_path, "has_spoiler": has_spoiler},
    }


async def audio_upload(
    file: DownloadedFile, has_spoiler: bool
) -> dict[str, bot.send_audio, dict]:
    return {
        "method": bot.send_audio,
        "kwargs": {
            "audio": file.full_path,
            "duration": get_duration(file=file.full_path),
        },
    }


async def doc_upload(
    file: DownloadedFile, has_spoiler: bool
) -> dict[str, bot.send_document, dict]:
    return {
        "method": bot.send_document,
        "kwargs": {"document": file.full_path, "force_document": True},
    }


FILE_TYPE_MAP = {
    MediaType.PHOTO: photo_upload,
    MediaType.DOCUMENT: doc_upload,
    MediaType.GIF: video_upload,
    MediaType.AUDIO: audio_upload,
    MediaType.VIDEO: video_upload,
}


def file_check(file: str):
    return os.path.isfile(file)


@bot.add_cmd(cmd="upload")
async def upload(bot: BOT, message: Message):
    input = message.flt_input
    if not input:
        await message.reply("give a file url | path to upload.")
        return
    response = await message.reply("checking input...")
    if input in Config.CMD_DICT:
        await message.reply_document(document=Config.CMD_DICT[input]["path"])
        await response.delete()
        return 
    elif input.startswith("http") and not file_check(input):
        dl_obj: Download = await Download.setup(
            url=message.input,
            path=os.path.join("downloads", str(time.time())),
            message_to_edit=response,
        )
        file: DownloadedFile = await dl_obj.download()
    elif file_check(input):
        file = DownloadedFile(
            name=input,
            path=input,
            full_path=input,
            size=bytes_to_mb(os.path.getsize(input)),
        )
    else:
        await response.edit("invalid `cmd` | `url` | `file path`!!!")
        return
    await response.edit("uploading....")
    progress_args = (response, "Uploading...", file.name, file.full_path)
    if "-d" in message.flags:
        media: dict = {
            "method": bot.send_document,
            "kwargs": {"document": file.full_path, "force_document": True},
        }
    else:
        media: dict = await FILE_TYPE_MAP[file.type](
            file, has_spoiler="-s" in message.flags
        )
    await media["method"](
        chat_id=message.chat.id,
        reply_to_message_id=message.reply_id,
        progress=progress,
        progress_args=progress_args,
        **media["kwargs"]
    )
    await response.delete()
