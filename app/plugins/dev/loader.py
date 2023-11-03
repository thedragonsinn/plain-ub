import importlib
import sys
import traceback

from app import Config, bot
from app.core import Message


async def loader(bot: bot, message: Message) -> Message | None:
    if (
        not message.replied
        or not message.replied.document
        or not message.replied.document.file_name.endswith(".py")
    ):
        return await message.reply("reply to a plugin.")
    reply: Message = await message.reply("Loading....")
    file_name: str = message.replied.document.file_name.rstrip(".py")
    reload = sys.modules.pop(f"app.temp.{file_name}", None)
    status: str = "Reloaded" if reload else "Loaded"
    await message.replied.download("app/temp/")
    try:
        importlib.import_module(f"app.temp.{file_name}")
    except BaseException:
        return await reply.edit(str(traceback.format_exc()))
    await reply.edit(f"{status} {file_name}.py.")


if Config.DEV_MODE:
    Config.CMD_DICT["load"] = loader
