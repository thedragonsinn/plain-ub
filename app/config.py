import asyncio
from os import environ, path
from typing import Callable, Coroutine

from git import Repo

from app.utils import Str


class Cmd(Str):
    def __init__(self, cmd: str, func: Callable, cmd_path: str, sudo: bool):
        self.cmd: str = cmd
        self.cmd_path: str = cmd_path
        self.dirname: str = path.basename(path.dirname(cmd_path))
        self.doc: str = func.__doc__ or "Not Documented."
        self.func: Callable = func
        self.loaded = False
        self.sudo: bool = sudo


class Config:
    BOT_NAME = "PLAIN-UB"

    CMD = Cmd

    CMD_DICT: dict[str, Cmd] = {}

    CMD_TRIGGER: str = environ.get("CMD_TRIGGER", ".")

    DEV_MODE: int = int(environ.get("DEV_MODE", 0))

    DISABLED_SUPERUSERS: list[int] = []

    FBAN_LOG_CHANNEL: int = int(
        environ.get("FBAN_LOG_CHANNEL", environ.get("LOG_CHAT"))
    )

    FBAN_SUDO_ID: int = int(environ.get("FBAN_SUDO_ID", 0))

    FBAN_SUDO_TRIGGER: str = environ.get("FBAN_SUDO_TRIGGER")

    GEMINI_API_KEY: str = environ.get("GEMINI_API_KEY")

    INIT_TASKS: list[Coroutine] = []

    LOG_CHAT: int = int(environ.get("LOG_CHAT"))

    MESSAGE_LOGGER_CHAT: int = int(environ.get("MESSAGE_LOGGER_CHAT", LOG_CHAT))

    MESSAGE_LOGGER_TASK: asyncio.Task | None = None

    OWNER_ID: int = int(environ.get("OWNER_ID"))

    PM_GUARD: bool = False

    PM_LOGGER: bool = False

    REPO: Repo = Repo(".")

    SUDO: bool = False

    SUDO_TRIGGER: str = environ.get("SUDO_TRIGGER", "!")

    SUDO_USERS: list[int] = []

    SUPERUSERS: list[int] = []

    TAG_LOGGER: bool = False

    UPSTREAM_REPO: str = environ.get(
        "UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub"
    )
