import json
import os

from git import Repo


class _Config:
    class CMD:
        def __init__(self, func, path, doc):
            self.func = func
            self.path = path
            self.doc = doc or "Not Documented."

    def __init__(self):
        self.CMD_DICT: dict[str, _Config.CMD] = {}

        self.CMD_TRIGGER: str = os.environ.get("CMD_TRIGGER", ".")

        self.DEV_MODE: int = int(os.environ.get("DEV_MODE", 0))

        self.DB_URL: str = os.environ.get("DB_URL")

        self.FBAN_LOG_CHANNEL: int = int(
            os.environ.get("FBAN_LOG_CHANNEL", os.environ.get("LOG_CHAT"))
        )
        self.INIT_TASKS: list = []

        self.LOG_CHAT: int = int(os.environ.get("LOG_CHAT"))

        self.REPO = Repo(".")

        self.SUDO: bool = False

        self.SUDO_TRIGGER: str = os.environ.get("SUDO_TRIGGER", "!")

        self.OWNER_ID = int(os.environ.get("OWNER_ID"))

        self.SUDO_CMD_LIST: list[str] = []

        self.SUDO_USERS: list[int] = []

        self.UPSTREAM_REPO: str = os.environ.get(
            "UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub"
        )

    def __str__(self):
        config_dict = self.__dict__.copy()
        config_dict["DB_URL"] = "SECURED"
        return json.dumps(config_dict, indent=4, ensure_ascii=False, default=str)


Config = _Config()
