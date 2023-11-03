from urllib.parse import urlparse

from app import bot
from app.core import Message


def get_message(link: str) -> tuple[int | str, int]:
    parsed_url: str = urlparse(link).path.strip("/")
    chat, id = parsed_url.lstrip("c/").split("/")
    if chat.isdigit():
        chat = int(f"-100{chat}")
    return chat, int(id)


@bot.add_cmd(cmd="reply")
async def reply(bot: bot, message: Message) -> None:
    if "-r" in message.flags:
        input: list[str] = message.flt_input.split(" ", maxsplit=1)
        if len(input) < 2:
            await message.reply("The '-r' flag requires a message link and text.")
            return
        message_link, text = input
        chat_id, reply_to_message_id = get_message(message_link.strip())
    else:
        text: str = message.input
        chat_id = message.chat.id
        reply_to_message_id = message.reply_id
    if not text:
        return
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_message_id=reply_to_message_id,
        disable_web_page_preview=True,
    )
