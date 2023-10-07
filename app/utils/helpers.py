from pyrogram.types import User

from app import Config

TELEGRAPH = None


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
