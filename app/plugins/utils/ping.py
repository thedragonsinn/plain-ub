from datetime import datetime

from app import bot
from app.core import Message


# Not my Code
# Prolly from Userge/UX/VenomX IDK
@bot.add_cmd(cmd="ping")
async def ping_bot(bot: bot, message: Message):
    start = datetime.now()
    resp: Message = await message.reply("Checking Ping.....")
    end = (datetime.now() - start).microseconds / 1000
    await resp.edit(f"Pong! {end} ms.")
