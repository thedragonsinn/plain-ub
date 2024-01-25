import os
import asyncio
from logging import (
    ERROR,
    INFO,
    WARNING,
    Handler,
    StreamHandler,
    basicConfig,
    getLogger,
    handlers,
)

os.makedirs("logs", exist_ok=True)


class TgErrorHandler(Handler):
    def emit(self, log_record):
        if log_record.levelno < ERROR:
            return
        from app import bot
        if not bot.is_connected:
            return 
        text = (
            f"#{log_record.levelname} #TRACEBACK"
            f"\n<b>Line No</b>: <code>{log_record.lineno}</code>"
            f"\n<b>Func</b>: <code>{log_record.funcName}</code>"
            f"\n<b>Module</b>: <code>{log_record.module}</code>"
            f"\n<b>Time</b>: <code>{log_record.asctime}</code>"
            f"\n<b>Error Message</b>:\n<pre language=python>{log_record.message}</pre>"
        )
        asyncio.run_coroutine_threadsafe(
            coro=bot.log_text(text=text, name="traceback.txt"), loop=bot.loop
        )


basicConfig(
    level=INFO,
    format="[%(levelname)s] [%(asctime)s] [%(name)s] [%(module)s]: %(message)s",
    datefmt="%d-%m-%y %I:%M:%S %p",
    handlers={
        handlers.RotatingFileHandler(
            filename="logs/app_logs.txt",
            mode="a",
            maxBytes=5 * 1024 * 1024,
            backupCount=2,
            encoding=None,
            delay=0,
        ),
        StreamHandler(),
        TgErrorHandler(),
    },
)

getLogger("pyrogram").setLevel(WARNING)
getLogger("httpx").setLevel(WARNING)
getLogger("aiohttp.access").setLevel(WARNING)
