import asyncio
import glob
import importlib
import os
import sys
import traceback
from io import BytesIO

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode
from pyrogram.types import Message as Msg

from app import DB_CLIENT, LOGGER, Config, Message
from app.core.decorators.add_cmd import AddCmd
from app.utils.aiohttp_tools import aio


def import_modules():
    for py_module in glob.glob(pathname="app/**/[!^_]*.py", recursive=True):
        name = os.path.splitext(py_module)[0]
        py_name = name.replace("/", ".")
        try:
            mod = importlib.import_module(py_name)
            if hasattr(mod, "init_task"):
                Config.INIT_TASKS.append(mod.init_task())
        except BaseException:
            LOGGER.error(traceback.format_exc())


class BOT(Client, AddCmd):
    def __init__(self):
        super().__init__(
            name="bot",
            api_id=int(os.environ.get("API_ID")),
            api_hash=os.environ.get("API_HASH"),
            session_string=os.environ.get("SESSION_STRING"),
            in_memory=True,
            parse_mode=ParseMode.DEFAULT,
            sleep_threshold=30,
            max_concurrent_transmissions=2,
        )
        from app.core.client.conversation import Conversation

        self.Convo = Conversation
        self.log = LOGGER

    async def get_response(
        self, chat_id: int, filters: filters.Filter = None, timeout: int = 8
    ) -> Message | None:
        try:
            async with self.Convo(
                chat_id=chat_id, filters=filters, timeout=timeout
            ) as convo:
                response: Message | None = await convo.get_response()
                return response
        except TimeoutError:
            return

    async def boot(self) -> None:
        await super().start()
        LOGGER.info("Connected to TG.")
        import_modules()
        LOGGER.info("Plugins Imported.")
        await asyncio.gather(*Config.INIT_TASKS)
        Config.INIT_TASKS.clear()
        LOGGER.info("Init Tasks Completed.")
        await self.log_text(text="<i>Started</i>")
        LOGGER.info("Idling...")
        await idle()
        await aio.session.close()
        LOGGER.info("DB Closed.")
        DB_CLIENT.close()

    async def log_text(
        self,
        text,
        name="log.txt",
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML,
        type: str = "",
    ) -> Message | Msg:
        if type:
            if hasattr(LOGGER, type):
                getattr(LOGGER, type)(text)
            text = f"#{type}\n{text}"

        return (await self.send_message(
            chat_id=Config.LOG_CHAT,
            text=text,
            name=name,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=parse_mode,
        ))  # fmt:skip

    @staticmethod
    async def log_message(message: Message | Msg):
        return (await message.copy(chat_id=Config.LOG_CHAT))  # fmt: skip

    async def restart(self, hard=False) -> None:
        await aio.session.close()
        await super().stop(block=False)
        LOGGER.info("Closing DB...")
        DB_CLIENT.close()
        if hard:
            os.remove("logs/app_logs.txt")
            os.execl("/bin/bash", "/bin/bash", "run")
        LOGGER.info("Restarting...")
        os.execl(sys.executable, sys.executable, "-m", "app")

    async def send_message(
        self,
        chat_id: int | str,
        text,
        name: str = "output.txt",
        disable_web_page_preview: bool = False,
        **kwargs,
    ) -> Message | Msg:
        text = str(text)
        if len(text) < 4096:
            message = await super().send_message(
                chat_id=chat_id,
                text=text,
                disable_web_page_preview=disable_web_page_preview,
                **kwargs,
            )
            return Message.parse_message(message=message)
        doc = BytesIO(bytes(text, encoding="utf-8"))
        doc.name = name
        # fmt:skip
        return await super().send_document(chat_id=chat_id, document=doc, **kwargs)
