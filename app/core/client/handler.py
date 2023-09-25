import asyncio
import traceback
from datetime import datetime

from pyrogram.enums import ChatType

from app import DB, Config, bot
from app.core import CallbackQuery, Message, filters


@bot.on_message(filters.cmd_filter)
@bot.on_edited_message(filters.cmd_filter)
async def cmd_dispatcher(bot, message) -> None:
    message = Message.parse_message(message)
    func = Config.CMD_DICT[message.cmd]
    coro = func(bot, message)
    await run_coro(coro, message)


@bot.on_callback_query()
async def callback_handler(bot: bot, cb):
    if (
        cb.message.chat.type == ChatType.PRIVATE
        and (datetime.now() - cb.message.date).total_seconds() > 30
    ):
        return await cb.edit_message_text(f"Query Expired. Try again.")
    banned = await DB.BANNED.find_one({"_id": cb.from_user.id})
    if banned:
        return
    cb = CallbackQuery.parse_cb(cb)
    func = Config.CALLBACK_DICT.get(cb.cmd)
    if not func:
        return
    coro = func(bot, cb)
    await run_coro(coro, Message.parse_message(cb.message))


async def run_coro(coro, message) -> None:
    try:
        task = asyncio.Task(coro, name=message.task_id)
        await task
    except asyncio.exceptions.CancelledError:
        await bot.log(text=f"<b>#Cancelled</b>:\n<code>{message.text}</code>")
    except BaseException:
        await bot.log(
            traceback=str(traceback.format_exc()),
            chat=message.chat.title or message.chat.first_name,
            func=coro.__name__,
            name="traceback.txt",
        )
