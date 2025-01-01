import asyncio

from ub_core.utils.helpers import create_chunks

from app import BOT, Message
from app.plugins.tg_tools.get_message import parse_link


@BOT.add_cmd(cmd="del")
async def delete_message(bot: BOT, message: Message) -> None:
    """
    CMD: DEL
    INFO: Delete the replied message.
    FLAGS: -r to remotely delete a text using its link.
    USAGE:
        .del | .del -r t.me/......
    """
    if "-r" in message.flags:
        chat_id, _, message_id = parse_link(message.filtered_input)
        await bot.delete_messages(chat_id=chat_id, message_ids=message_id, revoke=True)
        return
    await message.delete(reply=True)


@BOT.add_cmd(cmd="purge")
async def purge_(bot: BOT, message: Message) -> None:
    start_message: int = message.reply_id

    if not start_message:
        await message.reply("reply to a message")
        return

    end_message: int = message.id

    message_ids: list[int] = [i for i in range(int(start_message), int(end_message))]

    for chunk in create_chunks(message_ids, chunk_size=25):
        await bot.delete_messages(
            chat_id=message.chat.id, message_ids=chunk, revoke=True
        )
        await asyncio.sleep(5)
