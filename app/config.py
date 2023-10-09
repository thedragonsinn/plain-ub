import os
from typing import Callable

from pyrogram.filters import Filter
from pyrogram.types import Message


class Config:
    CMD_DICT: dict[str, Callable] = {}

    CMD_TRIGGER: str = os.environ.get("CMD_TRIGGER", ".")

    CONVO_DICT: dict[int, dict[str | int, Message | Filter | None]] = {}

    DEV_MODE: int = int(os.environ.get("DEV_MODE", 0))

    DB_URL: str = os.environ.get("DB_URL")

    FBAN_LOG_CHANNEL: int = int(
        os.environ.get("FBAN_LOG_CHANNEL", os.environ.get("LOG_CHAT"))
    )

    LOG_CHAT: int = int(os.environ.get("LOG_CHAT"))

    SUDO: bool = False

    SUDO_TRIGGER: str = os.environ.get("SUDO_TRIGGER", "!")

    OWNER_ID = int(os.environ.get("OWNER_ID"))

    SUDO_CMD_LIST: list[str] = []

    SUDO_USERS: list[int] = []

    UPSTREAM_REPO: str = os.environ.get(
        "UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub"
    )
