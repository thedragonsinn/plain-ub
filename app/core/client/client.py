import asyncio
import glob
import importlib
import inspect
import os
import sys
from functools import wraps
from io import BytesIO

from pyrogram import Client, filters, idle
from pyrogram.enums import ParseMode
from pyrogram.types import Message as Msg
from telegraph.aio import Telegraph

from app import DB, Config
from app.core import Conversation, Message, logger
from app.utils import aiohttp_tools, helpers


def import_modules():
    for py_module in glob.glob(pathname="app/**/[!^_]*.py", recursive=True):
        name = os.path.splitext(py_module)[0]
        py_name = name.replace("/", ".")
        try:
            importlib.import_module(py_name)
        except Exception as exc:
            logger.LOGGER.error(exc.with_exception())


async def init_tasks():
    sudo = await DB.SUDO.find_one({"_id": "sudo_switch"})
    if sudo:
        Config.SUDO = sudo["value"]
    Config.SUDO_USERS = [sudo_user["_id"] async for sudo_user in DB.SUDO_USERS.find()]
    Config.SUDO_CMD_LIST = [
        sudo_cmd["_id"] async for sudo_cmd in DB.SUDO_CMD_LIST.find()
    ]

    helpers.TELEGRAPH = Telegraph()
    await helpers.TELEGRAPH.create_account(
        short_name="Plain-UB", author_name="Plain-UB", author_url=Config.UPSTREAM_REPO
    )

    import_modules()
    await aiohttp_tools.session_switch()


class BOT(Client):
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

    @staticmethod
    def add_cmd(cmd: str | list):
        def the_decorator(func):
            path = inspect.stack()[1][1]

            @wraps(func)
            def wrapper():
                if isinstance(cmd, list):
                    for _cmd in cmd:
                        Config.CMD_DICT[_cmd] = {"func": func, "path": path}
                else:
                    Config.CMD_DICT[cmd] = {"func": func, "path": path}

            wrapper()
            return func

        return the_decorator

    @staticmethod
    async def get_response(
        chat_id: int, filters: filters.Filter = None, timeout: int = 8
    ) -> Message | None:
        try:
            async with Conversation(
                chat_id=chat_id, filters=filters, timeout=timeout
            ) as convo:
                response: Message | None = await convo.get_response()
                return response
        except Conversation.TimeOutError:
            return

    async def boot(self) -> None:
        await super().start()
        logger.LOGGER.info("Started")
        await asyncio.gather(
            init_tasks(), self.edit_restart_msg(), self.log(text="<i>Started</i>")
        )
        await idle()
        await aiohttp_tools.session_switch()
        DB._client.close()

    async def edit_restart_msg(self) -> None:
        restart_msg = int(os.environ.get("RESTART_MSG", 0))
        restart_chat = int(os.environ.get("RESTART_CHAT", 0))
        if restart_msg and restart_chat:
            await super().get_chat(restart_chat)
            await super().edit_message_text(
                chat_id=restart_chat, message_id=restart_msg, text="__Started__"
            )
            os.environ.pop("RESTART_MSG", "")
            os.environ.pop("RESTART_CHAT", "")

    async def log(
        self,
        text="",
        traceback="",
        chat=None,
        func=None,
        message: Message | Msg | None = None,
        name="log.txt",
        disable_web_page_preview=True,
        parse_mode=ParseMode.HTML,
    ) -> Message | Msg:
        if message:
            return (await message.copy(chat_id=Config.LOG_CHAT))  # fmt: skip
        if traceback:
            text = (
                "#Traceback"
                f"\n<b>Function:</b> {func}"
                f"\n<b>Chat:</b> {chat}"
                f"\n<b>Traceback:</b>"
                f"\n<code>{traceback}</code>"
            )
        return await self.send_message(
            chat_id=Config.LOG_CHAT,
            text=text,
            name=name,
            disable_web_page_preview=disable_web_page_preview,
            parse_mode=parse_mode,
        )

    async def restart(self, hard=False) -> None:
        await aiohttp_tools.session_switch()
        await super().stop(block=False)
        DB._client.close()
        if hard:
            os.remove("logs/app_logs.txt")
            os.execl("/bin/bash", "/bin/bash", "run")
        os.execl(sys.executable, sys.executable, "-m", "app")


    async def send_message(
        self, chat_id: int | str, text, name: str = "output.txt", **kwargs
    ) -> Message | Msg:
        text = str(text)
        if len(text) < 4096:
            return Message.parse_message(
                (await super().send_message(chat_id=chat_id, text=text, **kwargs))
            )
        doc = BytesIO(bytes(text, encoding="utf-8"))
        doc.name = name
        kwargs.pop("disable_web_page_preview", "")
        return await super().send_document(chat_id=chat_id, document=doc, **kwargs)
