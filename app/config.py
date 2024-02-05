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


class _Config(Str):
    CMD = Cmd

    def __init__(self):
        self.CMD_DICT: dict[str, Cmd] = {}

        self.CMD_TRIGGER: str = os.environ.get("CMD_TRIGGER", ".")

        self.DEV_MODE: int = int(os.environ.get("DEV_MODE", 0))

        self.DISABLED_SUPERUSERS: list[int] = []

        self.FBAN_LOG_CHANNEL: int = int(
            os.environ.get("FBAN_LOG_CHANNEL", os.environ.get("LOG_CHAT"))
        )

        self.INIT_TASKS: list[Coroutine] = []

        self.LOG_CHAT: int = int(os.environ.get("LOG_CHAT"))

        self.MESSAGE_LOGGER_CHAT: int = int(
            os.environ.get("MESSAGE_LOGGER_CHAT", self.LOG_CHAT)
        )

        self.MESSAGE_LOGGER_TASK: asyncio.Task | None = None

        self.OWNER_ID: int = int(os.environ.get("OWNER_ID"))

        self.PM_GUARD: bool = False

        self.PM_LOGGER: bool = False

        self.REPO: Repo = Repo(".")

        self.SUDO: bool = False

        self.SUDO_TRIGGER: str = os.environ.get("SUDO_TRIGGER", "!")

        self.SUDO_CMD_LIST: list[str] = []

        self.SUDO_USERS: list[int] = []

        self.SUPERUSERS: list[int] = []

        self.TAG_LOGGER: bool = False

        self.UPSTREAM_REPO: str = os.environ.get(
            "UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub"
        )


Config = _Config()
