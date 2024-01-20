import re

from app import BOT, Message, bot


@bot.add_cmd(cmd="resp")
async def respond(bot: BOT, message: Message):
    """
    CMD: RESP
    INFO: Respond to a Logged Message.
    USAGE:
        .resp [chat_id | reply to a message containing info] hi
    """
    if message.replied:
        inp_text = message.replied.text
        match = re.search(pattern=r"\[(\d+)\]", string=inp_text)
        if match:
            chat_id = match.group(1)
            text = message.input
    elif message.input:
        chat_id, text = message.input.split(" ")
    else:
        await message.reply("Unable to extract chat_id and text.")
        return
    await bot.send_message(
        chat_id=int(chat_id), text=text, disable_web_page_preview=True
    )
