import asyncio
import glob
import json
import os
import shutil
from time import time
from urllib.parse import urlparse

from ub_core.utils import MediaExts, aio, run_shell_cmd

from app import BOT, Message, bot

domains = [
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtube-nocookie.com",
    "music.youtube.com",
]


@bot.add_cmd(cmd="song")
async def song_dl(bot: BOT, message: Message) -> None | Message:
    reply_query = None

    for link in message.reply_text_list:
        if urlparse(link).netloc in domains:
            reply_query = link
            break

    query = reply_query or message.filtered_input

    if not query:
        await message.reply("Give a song name or link to download.")
        return

    response: Message = await message.reply("Searching....")

    download_path: str = os.path.join("downloads", str(time()))

    query_or_search: str = query if query.startswith("http") else f"ytsearch:{query}"

    song_info: dict = await get_download_info(query=query_or_search, path=download_path)

    duration, artist, thumb = 0, "", None

    if isinstance(song_info, dict):
        duration: int = song_info["duration"]
        artist: str = song_info["channel"]
        thumb = await aio.in_memory_dl(song_info["thumbnail"])

    down_path: list = glob.glob(os.path.join(download_path, "*"))

    if not down_path:
        await response.edit("Song Not found.")
        return

    await response.edit("Uploading....")

    for audio_file in down_path:
        if audio_file.endswith(tuple(MediaExts.AUDIO)):
            await message.reply_audio(
                audio=audio_file,
                duration=int(duration),
                performer=str(artist),
                thumb=thumb,
            )

    await response.delete()

    shutil.rmtree(download_path, ignore_errors=True)


async def get_download_info(query: str, path: str):
    download_cmd = (
        f"yt-dlp -o '{os.path.join(path, '%(title)s.%(ext)s')}' "
        f"-f 'bestaudio' "
        f"--no-warnings "
        f"--ignore-errors "
        f"--ignore-no-formats-error "
        f"--quiet "
        f"--no-playlist "
        f"--audio-quality 0 "
        f"--extract-audio "
        f"--embed-thumbnail "
        f"--embed-metadata "
        f"--print-json "
        f"'{query}'"
    )
    try:

        async with asyncio.timeout(30):

            song_info = (await run_shell_cmd(download_cmd)).strip()

            serialised_json = json.loads(song_info)
            return serialised_json

    except asyncio.TimeoutError:
        shutil.rmtree(path=path, ignore_errors=True)

    except json.JSONDecodeError:
        return
