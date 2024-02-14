import asyncio
import os
from typing import Callable, Coroutine

from git import Repo

from app.utils import Str


class Cmd(Str):
    def __init__(self, cmd: str, func: Callable, path: str, sudo: bool):
        self.cmd: str = cmd
        self.func: Callable = func
        self.path: str = path
        self.dirname: str = os.path.basename(os.path.dirname(path))
        self.doc: str = func.__doc__ or "Not Documented."
        self.sudo: bool = sudo


class Config:
    BOT_NAME = "PLAIN-UB"

    CMD = Cmd

    CMD_DICT: dict[str, Cmd] = {}

    CMD_TRIGGER: str = os.environ.get("CMD_TRIGGER", ".")

    DEV_MODE: int = int(os.environ.get("DEV_MODE", 0))

    DISABLED_SUPERUSERS: list[int] = []

    FBAN_LOG_CHANNEL: int = int(
        os.environ.get("FBAN_LOG_CHANNEL", os.environ.get("LOG_CHAT"))
    )

    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY")

    INIT_TASKS: list[Coroutine] = []

    LOG_CHAT: int = int(os.environ.get("LOG_CHAT"))

    MESSAGE_LOGGER_CHAT: int = int(os.environ.get("MESSAGE_LOGGER_CHAT", LOG_CHAT))

    MESSAGE_LOGGER_TASK: asyncio.Task | None = None

    OWNER_ID: int = int(os.environ.get("OWNER_ID"))

    PM_GUARD: bool = False

    PM_LOGGER: bool = False

    REPO: Repo = Repo(".")

    SUDO: bool = False

    SUDO_TRIGGER: str = os.environ.get("SUDO_TRIGGER", "!")

    SUDO_CMD_LIST: list[str] = []

    SUDO_USERS: list[int] = []

    SUPERUSERS: list[int] = []

    TAG_LOGGER: bool = False

    UPSTREAM_REPO: str = os.environ.get(
        "UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub"
    )
