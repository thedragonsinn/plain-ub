from app import Config, bot
from app.core import Message


@bot.add_cmd(cmd="help")
async def cmd_list(bot: bot, message: Message) -> None:
    commands: str = "\n".join(
        [f"<code>{message.trigger}{cmd}</code>" for cmd in Config.CMD_DICT.keys()]
    )
    await message.reply(
        f"<b>Available Commands:</b>\n\n{commands}", del_in=30, block=True
    )
