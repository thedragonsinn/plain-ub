from app import BOT, Message
from app.plugins.tg_tools.get_message import parse_link


@BOT.add_cmd(cmd="reply")
async def reply(bot: BOT, message: Message) -> None:
    """
    CMD: REPLY
    INFO: Reply to a Message.
    FLAGS:
        -r: reply remotely using message link.
    USAGE:
        .reply HI | .reply -r t.me/... HI
    """
    if "-r" in message.flags:
        input: list[str] = message.filtered_input.split(" ", maxsplit=1)

        if len(input) < 2:
            await message.reply("The '-r' flag requires a message link and text.")
            return

        message_link, text = input
        chat_id, _, reply_to_id = parse_link(message_link.strip())

    else:
        chat_id, text, reply_to_id = message.chat.id, message.input, message.reply_id

    if not text:
        return

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_to_id=reply_to_id,
        disable_preview=True,
    )
