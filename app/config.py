import json
import os
from typing import Coroutine


class Config:
    CMD_DICT: dict["str", Coroutine] = {}

    CALLBACK_DICT: dict["str", Coroutine] = {}

    DEV_MODE: int = int(os.environ.get("DEV_MODE", 0))

    DB_URL: str = os.environ.get("DB_URL")

    LOG_CHAT: int = int(os.environ.get("LOG_CHAT"))

    TRIGGER: str = os.environ.get("TRIGGER", ".")

    USERS: list[int] = json.loads(os.environ.get("USERS", "[]"))

    UPSTREAM_REPO: str = os.environ.get(
        "UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub"
    )
