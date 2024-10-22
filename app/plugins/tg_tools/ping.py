from datetime import datetime

from app import BOT, Message


# Not my Code
# Prolly from Userge/UX/VenomX IDK
@BOT.add_cmd(cmd="ping")
async def ping_bot(bot: BOT, message: Message):
    start = datetime.now()
    resp: Message = await message.reply("Checking Ping.....")
    end = (datetime.now() - start).microseconds / 1000
    await resp.edit(f"Pong! {end} ms.")
