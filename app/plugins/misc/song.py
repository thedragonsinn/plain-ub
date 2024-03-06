import asyncio
import glob
import os
import shutil
from time import time
from urllib.parse import urlparse

import yt_dlp
from ub_core.utils.aiohttp_tools import aio

from app import Message, bot

domains = [
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtube-nocookie.com",
    "music.youtube.com",
]


class FakeLogger(object):
    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        pass


@bot.add_cmd(cmd="song")
async def song_dl(bot: bot, message: Message) -> None | Message:
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
    audio_format = "mp3" if "-m" in message.flags else "opus"
    song_info: dict = await get_download_info(
        query=query_or_search, path=download_path, audio_format=audio_format
    )
    if song_info is None:
        await message.reply("Download Timed Out.")
        return
    if not query_or_search.startswith("http"):
        song_info: str = song_info["entries"][0]
    duration: int = song_info["duration"]
    artist: str = song_info["channel"]
    thumb = await aio.in_memory_dl(song_info["thumbnail"])
    down_path: list = glob.glob(os.path.join(download_path, "*"))
    if not down_path:
        await response.edit("Song Not found.")
        return
    await response.edit("Uploading....")
    for audio_file in down_path:
        if audio_file.endswith((".opus", ".mp3")):
            await message.reply_audio(
                audio=audio_file,
                duration=int(duration),
                performer=str(artist),
                thumb=thumb,
            )
    await response.delete()
    shutil.rmtree(download_path, ignore_errors=True)


async def get_download_info(query: str, path: str, audio_format: str) -> dict | None:
    yt_opts = {
        "logger": FakeLogger(),
        "outtmpl": os.path.join(path, "%(title)s.%(ext)s"),
        "format": "bestaudio",
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": audio_format},
            {"key": "FFmpegMetadata"},
            {"key": "EmbedThumbnail"},
        ],
    }
    ytdl: yt_dlp.YoutubeDL = yt_dlp.YoutubeDL(yt_opts)
    try:
        async with asyncio.timeout(30):
            yt_info: dict = await asyncio.to_thread(ytdl.extract_info, query)
            return yt_info
    except asyncio.TimeoutError:
        shutil.rmtree(path=path, ignore_errors=True)
