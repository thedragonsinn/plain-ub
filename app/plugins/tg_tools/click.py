from app import BOT, Message


@BOT.add_cmd(cmd="click")
async def click(bot: BOT, message: Message):
    """
    CMD: CLICK
    INFO: Clicks a button in replied message
    USAGE:
        .click ok (clicks a button with text ok)
        .click 0 (clicks the button at index 0)
    """
    if not (message.input and message.replied):
        await message.reply("reply to a message containing a button and give a button to click")
        return
    try:
        button_name = message.input.strip()
        button = int(button_name) if button_name.isdigit() else button_name
        await message.replied.click(button)
    except Exception as e:
        await message.reply(str(e), del_in=5)
