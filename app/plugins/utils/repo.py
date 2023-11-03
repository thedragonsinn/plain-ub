from app import Config, bot
from app.core import Message


@bot.add_cmd(cmd="repo")
async def sauce(bot: bot, message: Message) -> None:
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"<a href='{Config.UPSTREAM_REPO}'>Plain-UB.</a>",
        reply_to_message_id=message.reply_id or message.id,
        disable_web_page_preview=True,
    )
