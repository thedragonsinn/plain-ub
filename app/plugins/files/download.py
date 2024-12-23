import asyncio
import os
import time

from ub_core.utils import (Download, DownloadedFile, get_tg_media_details,
                           progress)

from app import BOT, Message, bot


@bot.add_cmd(cmd="download")
async def down_load(bot: BOT, message: Message):
    """
    CMD: DOWNLOAD
    INFO: Download Files/TG Media to Bot server.
    FLAGS: "-f" for custom filename
    USAGE:
        .download URL | Reply to Media
        .download -f file.ext URL | Reply to Media
    """
    response = await message.reply("Checking Input...")

    if (not message.replied or not message.replied.media) and not message.input:
        await response.edit(
            "Invalid input...\nReply to a message containing media or give a link with cmd."
        )
        return

    dl_dir_name = os.path.join("downloads", str(time.time()))

    await response.edit("Input verified....Starting Download...")

    file_name = None
    dl_obj: None = None

    if message.replied and message.replied.media:

        if "-f" in message.flags:
            file_name = message.filtered_input

        download_coro = telegram_download(
            message=message.replied,
            response=response,
            dir_name=dl_dir_name,
            file_name=file_name,
        )

    else:

        if "-f" in message.flags:
            file_name, url = message.filtered_input.split(maxsplit=1)
        else:
            url = message.filtered_input

        if url.startswith("https://t.me/"):
             download_coro = telegram_download(
                message=await bot.get_messages(link=url),
                response=response,
                dir_name=dl_dir_name,
                file_name=file_name,
            )
        else:
            dl_obj: Download = await Download.setup(
              url=url,
              dir=dl_dir_name,
              message_to_edit=response,
              custom_file_name=file_name,
            )
            download_coro = dl_obj.download()

    try:
        downloaded_file: DownloadedFile = await download_coro
        await response.edit(
            f"<code>{downloaded_file.path}</code>"
            f"\n\n<code>{downloaded_file.size}</code> mb"
            "\n\n<b>Downloaded.</b>"
        )
        return downloaded_file

    except asyncio.exceptions.CancelledError:
        await response.edit("Cancelled....")

    except TimeoutError:
        await response.edit("Download Timeout...")

    except Exception as e:
        await response.edit(str(e))
    finally:
        if dl_obj:
            await dl_obj.close()


async def telegram_download(
    message: Message, response: Message, dir_name: str, file_name: str | None = None
) -> DownloadedFile:
    """
    :param message: Message Containing Media
    :param response: Response to Edit
    :param dir_name: Download path
    :param file_name: Custom File Name
    :return: DownloadedFile
    """
    tg_media = get_tg_media_details(message)

    file_name = file_name or tg_media.file_name

    media_obj: DownloadedFile = DownloadedFile(file=os.path.join(dir_name, file_name), size=tg_media.file_size)

    progress_args = (response, "Downloading...", media_obj.path)

    await message.download(
        file_name=media_obj.path,
        progress=progress,
        progress_args=progress_args,
    )
    return media_obj
