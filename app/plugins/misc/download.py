import asyncio
import os
import time

from app import BOT, bot
from app.core import Message
from app.utils.downloader import Download, DownloadedFile
from app.utils.helpers import progress
from app.utils.media_helper import get_tg_media_details


@bot.add_cmd(cmd="download")
async def down_load(bot: BOT, message: Message):
    """
    CMD: DOWNLOAD
    INFO: Download Files/TG Media to Bot server.
    USAGE: 
        .download URL | Reply to Media
    """
    response = await message.reply("Checking Input...")
    if (not message.replied or not message.replied.media) and not message.input:
        await response.edit(
            "Invalid input...\nReply to a message containing media or give a link with cmd."
        )
        return
    dl_path = os.path.join("downloads", str(time.time()))
    await response.edit("Input verified....Starting Download...")
    if message.replied and message.replied.media:
        download_coro = telegram_download(
            message=message.replied, response=response, path=dl_path
        )
    else:
        dl_obj: Download = await Download.setup(
            url=message.input, path=dl_path, message_to_edit=response
        )
        download_coro = dl_obj.download()
    try:
        downloaded_file: DownloadedFile = await download_coro
        await response.edit(
            f"<b>Download Completed</b>"
            f"\n<pre language=bash>"
            f"\nfile={downloaded_file.name}"
            f"\npath={downloaded_file.full_path}"
            f"\nsize={downloaded_file.size}mb</pre>"
        )
        return downloaded_file

    except asyncio.exceptions.CancelledError:
        await response.edit("Cancelled....")
    except TimeoutError:
        await response.edit("Download Timeout...")
    except Exception as e:
        await response.edit(str(e))


async def telegram_download(
    message: Message, response: Message, path: str
) -> DownloadedFile:
    tg_media = get_tg_media_details(message)
    media_obj: DownloadedFile = DownloadedFile(
        name=tg_media.file_name,
        path=path,
        size=round(tg_media.file_size / 1048576, 1),
        full_path=os.path.join(path, tg_media.file_name),
    )
    progress_args = (
        response,
        "Downloading...",
        media_obj.name,
        media_obj.full_path)
    await message.download(
        file_name=media_obj.full_path,
        progress=progress,
        progress_args=progress_args,
    )
    return media_obj
