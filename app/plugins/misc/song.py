import json
import shutil
from pathlib import Path
from time import time
from urllib.parse import urlparse

from pyrogram.enums import MessageEntityType
from pyrogram.types import InputMediaAudio
from ub_core.utils import aio, run_shell_cmd

from app import BOT, Message

domains = [
    "www.youtube.com",
    "youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtube-nocookie.com",
    "music.youtube.com",
]


def is_yt_url(url: str) -> bool:
    return urlparse(url).netloc in domains


def extract_link_from_reply(message: Message) -> str | None:
    if not message:
        return

    for link in message.text_list:
        if is_yt_url(link):
            return link

    for entity in message.entities or []:
        if entity.type == MessageEntityType.TEXT_LINK and is_yt_url(entity.url):
            return entity.url

    return None


@BOT.add_cmd(cmd="song")
async def song_dl(bot: BOT, message: Message):
    """
    CMD: SONG
    INFO: Download given song from youtube.
    WARNING: THIS CMD MAY NOT WORK ON SERVERS.
    """

    query = extract_link_from_reply(message.replied) or message.filtered_input

    if not query:
        await message.reply("Give a song name or link to download.")
        return

    response: Message = await message.reply("Searching....")

    download_path: Path = Path("downloads") / str(time())

    query_or_search: str = query if query.startswith("http") else f"ytsearch:{query}"

    song_info: dict = await get_download_info(query=query_or_search, path=download_path)

    audio_files: list = list(download_path.glob("*mp3"))

    if not audio_files:
        await response.edit("Song Not found.")
        return

    audio_file = audio_files[0]

    url = song_info.get("webpage_url")

    await response.edit(f"`Uploading {audio_file.name}....`")

    await response.edit_media(
        InputMediaAudio(
            media=str(audio_file),
            caption=f"<a href={url}>{audio_file.name}</a>" if url else None,
            duration=int(song_info.get("duration", 0)),
            performer=song_info.get("channel", ""),
            thumb=await aio.in_memory_dl(song_info.get("thumbnail")),
        )
    )

    shutil.rmtree(download_path, ignore_errors=True)


async def get_download_info(query: str, path: Path) -> dict:
    download_cmd = (
        f"yt-dlp -o '{path / '%(title)s.%(ext)s'}' "
        f"-f 'bestaudio' "
        f"--no-warnings "
        f"--ignore-errors "
        f"--ignore-no-formats-error "
        f"--quiet "
        f"--no-playlist "
        f"--audio-quality 0 "
        f"--audio-format mp3 "
        f"--extract-audio "
        f"--embed-thumbnail "
        f"--embed-metadata "
        f"--print-json "
        f"'{query}'"
    )

    try:
        song_info = (await run_shell_cmd(download_cmd, timeout=60, ret_val="")).strip()

        serialised_json = json.loads(song_info)
        return serialised_json

    except TimeoutError:
        shutil.rmtree(path=path, ignore_errors=True)

    except json.JSONDecodeError:
        pass

    return {}
