import os

from pyrogram.enums import ChatType

from app import bot, BOT, Message


@bot.add_cmd(cmd="restart")
async def restart(bot: BOT, message: Message, u_resp: Message | None = None) -> None:
    reply: Message = u_resp or await message.reply("restarting....")
    if reply.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        os.environ["RESTART_MSG"] = str(reply.id)
        os.environ["RESTART_CHAT"] = str(reply.chat.id)
    await bot.restart(hard="-h" in message.flags)
