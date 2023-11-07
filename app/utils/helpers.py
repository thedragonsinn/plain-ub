import os

from pyrogram.enums import MessageMediaType
from pyrogram.types import Message, User
from telegraph.aio import Telegraph

from app import Config
from app.utils.downloader import DownloadedFile

TELEGRAPH: None | Telegraph = None


async def post_to_telegraph(title: str, text: str):
    telegraph = await TELEGRAPH.create_page(
        title=title,
        html_content=f"<p>{text}</p>",
        author_name="Plain-UB",
        author_url=Config.UPSTREAM_REPO,
    )
    return telegraph["url"]


def get_name(user: User) -> str:
    first = user.first_name or ""
    last = user.last_name or ""
    return f"{first} {last}".strip()


def extract_user_data(user: User) -> dict:
    return dict(name=get_name(user), username=user.username, mention=user.mention)


async def progress(
    current,
    total,
    response: Message,
    action: str = "",
    file_name: str = "",
    file_path: str = "",
):
    prog = f"{current * 100 / total:.1f}%"
    await response.edit(
        f"<b>{action}</b>"
        f"\n<pre language=bash>"
        f"\nfile={file_name}"
        f"\npath={file_path}"
        f"\nsize={total}mb"
        f"\ncompleted={prog}/pre>"
    )


def get_tg_media_details(message: Message, path: str) -> DownloadedFile | None:
    name = ""
    match message.media:
        case MessageMediaType.PHOTO:
            file = message.photo
            name = "photo.jpg"
        case MessageMediaType.AUDIO:
            file = message.animation
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
    name = name or file.file_name
    return DownloadedFile(
        name=name,
        path=path,
        size=file.file_size / (1024 * 1024),
        full_path=os.path.join(path, name),
    )
