import asyncio
import os

from pyrogram.errors import BadRequest
from ub_core.utils import get_name

from app import BOT, Message


@BOT.add_cmd(cmd="ids")
async def get_ids(bot: BOT, message: Message) -> None:
    reply: Message = message.replied
    if reply:
        resp_str: str = ""

        reply_user, reply_forward = reply.forward_from_chat, reply.from_user

        resp_str += f"<b>{get_name(reply.chat)}</b>: <code>{reply.chat.id}</code>\n"

        if reply_forward:
            resp_str += (
                f"<b>{get_name(reply_forward)}</b>: <code>{reply_forward.id}</code>\n"
            )

        if reply_user:
            resp_str += f"<b>{get_name(reply_user)}</b>: <code>{reply_user.id}</code>"
    elif message.input:
        resp_str: int = (await bot.get_chat(message.input[1:])).id
    else:
        resp_str: str = (
            f"<b>{get_name(message.chat)}</b>: <code>{message.chat.id}</code>"
        )
    await message.reply(resp_str)


@BOT.add_cmd(cmd="join")
async def join_chat(bot: BOT, message: Message) -> None:
    chat: str = message.input
    try:
        await bot.join_chat(chat)
    except (KeyError, BadRequest):
        try:
            await bot.join_chat(os.path.basename(chat).strip())
        except Exception as e:
            await message.reply(str(e))
            return
    await message.reply("Joined")


@BOT.add_cmd(cmd="leave")
async def leave_chat(bot: BOT, message: Message) -> None:
    if message.input:
        chat = message.input
    else:
        chat = message.chat.id
        await message.reply(
            text=f"Leaving current chat in 5\nReply with `{message.trigger}c` to cancel",
            del_in=5,
            block=True,
        )
        await asyncio.sleep(5)
    try:
        await bot.leave_chat(chat)
    except Exception as e:
        await message.reply(str(e))
