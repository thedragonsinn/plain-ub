import asyncio

from pyrogram.enums import ChatType
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
    """
    CMD: PURGE
    INFO: DELETE MULTIPLE MESSAGES
    USAGE:
        .purge [reply to message]
    """
    chat_id = message.chat.id

    start_message: int = message.reply_id

    # Not replied to a message
    if not start_message:
        await message.reply("Reply to a message.")
        return

    # Replied was topic creation message
    if message.thread_origin_message:
        await message.reply("Reply to a message.")
        return

    # Get Topic messages till replied
    if message.is_topic_message:
        message_ids = []

        async for _message in bot.get_discussion_replies(
            chat_id=message.chat.id, message_id=message.message_thread_id, limit=100
        ):
            message_ids.append(_message.id)
            if _message.id == message.reply_id or len(message_ids) > 100:
                break
    else:
        # Generate Message Ids
        message_ids: list[int] = list(range(start_message, message.id))

        # Get messages from server if chat is private or ids are too big.
        if message.chat.type in {ChatType.PRIVATE, ChatType.BOT} or len(message_ids) > 100:
            messages = await bot.get_messages(chat_id=chat_id, message_ids=message_ids, replies=0)
            message_ids = [message.id for message in messages]

    # Perform Quick purge of bigger chunks
    if len(message_ids) < 100:
        chunk_size = 50
        sleep_interval = 2
    else:
        chunk_size = 25
        sleep_interval = 5

    for chunk in create_chunks(message_ids, chunk_size=chunk_size):
        await bot.delete_messages(chat_id=chat_id, message_ids=chunk, revoke=True)
        await asyncio.sleep(sleep_interval)
