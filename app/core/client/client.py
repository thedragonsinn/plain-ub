import glob
import importlib
import os
import sys
from functools import wraps
from io import BytesIO

from pyrogram import Client, idle
from pyrogram.enums import ParseMode
from pyrogram.types import Message as Msg

from app import DB, Config
from app.core import Message
from app.utils import aiohttp_tools


async def import_modules():
    for py_module in glob.glob(pathname="app/**/*.py", recursive=True):
        name = os.path.splitext(py_module)[0]
        py_name = name.replace("/", ".")
        importlib.import_module(py_name)


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
    def add_cmd(cmd: str, cb: bool = False):
        def the_decorator(func):
            @wraps(func)
            def wrapper():
                config_dict = Config.CMD_DICT
                if cb:
                    config_dict = Config.CALLBACK_DICT
                if isinstance(cmd, list):
                    for _cmd in cmd:
                        config_dict[_cmd] = func
                else:
                    config_dict[cmd] = func

            wrapper()
            return func

        return the_decorator

    async def boot(self) -> None:
        await super().start()
        await import_modules()
        await aiohttp_tools.session_switch()
        await self.edit_restart_msg()
        print("started")
        await self.log(text="<i>Started</i>")
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
            return (await message.copy(chat_id=Config.LOG_CHAT))
        if traceback:
            text = f"""
#Traceback
<b>Function:</b> {func}
<b>Chat:</b> {chat}
<b>Traceback:</b>
<code>{traceback}</code>"""
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
