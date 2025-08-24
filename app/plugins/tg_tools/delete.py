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


@BOT.add_cmd("del_uh")
async def delete_user_history(bot: BOT, message: Message):
    if not (message.replied and message.chat.type in {ChatType.GROUP, ChatType.SUPERGROUP}):
        await message.reply("Reply to the user's message and use in a chat.")
        return

    user = message.replied.from_user
    warning = await message.reply(
        f"Delete all messages from {user.mention}?\nReply with `y` to continue."
    )
    text, _ = await warning.get_response(quote=True, lower=True)
    if text == "y":
        await bot.delete_user_history(chat_id=message.chat.id, user_id=user.id)
        await warning.edit("Done.")
        await bot.log_text(
            f"Deleted all texts from {user.mention} in chat <a href='{message.link}'>{message.chat.title}</a> [{message.chat.id}]",
            type="info",
        )
    else:
        await warning.edit("Aborted...")


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

    if not start_message:
        await message.reply("Reply to a message.")
        return

    message_ids: list[int] = []
    
    # Iterate through chat history backwards from the command message
    async for _message in bot.get_chat_history(chat_id=chat_id, offset_id=message.id):
        if _message.id == message.id:
            continue
            
        message_ids.append(_message.id)

        # Stop when we reach the replied-to message
        if _message.id == start_message:
            break

        if len(message_ids) >= 100:
            await bot.delete_messages(chat_id=chat_id, message_ids=message_ids, revoke=True)
            message_ids.clear()
            await asyncio.sleep(2)

    # Delete any remaining messages
    if message_ids:
        await bot.delete_messages(chat_id=chat_id, message_ids=message_ids, revoke=True)

    # Delete the command and the replied-to message itself
    await message.delete(reply=True)
