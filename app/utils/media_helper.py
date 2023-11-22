from enum import Enum, auto
from os.path import basename, splitext
from urllib.parse import urlparse

from pyrogram.enums import MessageMediaType
from pyrogram.types import Message


class MediaType(Enum):
    AUDIO = auto()
    DOCUMENT = auto()
    GIF = auto()
    GROUP = auto()
    MESSAGE = auto()
    PHOTO = auto()
    VIDEO = auto()


class MediaExts:
    PHOTO = {".png", ".jpg", ".jpeg"}
    VIDEO = {".mp4", ".mkv", ".webm"}
    GIF = {".gif"}
    AUDIO = {".aac", ".mp3", ".opus", ".m4a", ".ogg", ".flac"}


def bytes_to_mb(size: int):
    return round(size / 1048576, 1)


def get_filename(url: str) -> str:
    name = basename(urlparse(url).path.rstrip("/"))
    if name.lower().endswith((".webp", ".heic")):
        name = name + ".jpg"
    elif name.lower().endswith(".webm"):
        name = name + ".mp4"
    return name


def get_type(url: str | None = "", path: str | None = "") -> MediaType | None:
    if url:
        media = get_filename(url)
    else:
        media = path
    name, ext = splitext(media)
    if ext in MediaExts.PHOTO:
        return MediaType.PHOTO
    if ext in MediaExts.VIDEO:
        return MediaType.VIDEO
    if ext in MediaExts.GIF:
        return MediaType.GIF
    if ext in MediaExts.AUDIO:
        return MediaType.AUDIO
    return MediaType.DOCUMENT


def get_tg_media_details(message: Message):
    match message.media:
        case MessageMediaType.PHOTO:
            file = message.photo
            file.file_name = "photo.jpg"
        case MessageMediaType.AUDIO:
            file = message.audio
        case MessageMediaType.ANIMATION:
            file = message.animation
        case MessageMediaType.DOCUMENT:
            file = message.document
        case MessageMediaType.STICKER:
            file = message.sticker
        case MessageMediaType.VIDEO:
            file = message.video
        case MessageMediaType.VOICE:
            file = message.voice
        case _:
            return
    return file
