from app import BOT
from app.core import Message


# @bot.add_cmd(cmd="download")
async def down_load(bot: BOT, message: Message):
    response = await message.reply("Checking Input...")
    if (not message.replied or not message.replied.media) and not message.input:
        await response.edit(
            "Invalid input...\nReply to a message containing media or give a link with cmd."
        )
        return
    if message.replied:
        await telegram_download(message.replied)


async def telegram_download(message: Message):
    ...
