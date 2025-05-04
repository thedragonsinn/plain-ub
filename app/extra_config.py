from os import getenv

from pyrogram.enums import ChatMemberStatus

ALIVE_MEDIA: str = getenv("ALIVE_MEDIA", "https://telegra.ph/file/a1d35a86c7f54a96188a9.png")

ADMIN_STATUS = {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}

BOT_NAME = getenv("BOT_NAME", "PLAIN-UB")

CUSTOM_PACK_NAME = getenv("CUSTOM_PACK_NAME")

DISABLED_SUPERUSERS: list[int] = []

FBAN_LOG_CHANNEL: int = int(getenv("FBAN_LOG_CHANNEL") or getenv("LOG_CHAT"))

FBAN_SUDO_ID: int = int(getenv("FBAN_SUDO_ID", 0))

FBAN_SUDO_TRIGGER: str = getenv("FBAN_SUDO_TRIGGER")

GEMINI_API_KEY: str = getenv("GEMINI_API_KEY")

LOAD_HANDLERS: bool = True

MESSAGE_LOGGER_CHAT: int = int(getenv("MESSAGE_LOGGER_CHAT") or getenv("LOG_CHAT"))

PM_GUARD: bool = False

PM_LOGGER: bool = False

PM_LOGGER_THREAD_ID: int = int(getenv("PM_LOGGER_THREAD_ID", 0)) or None

TAG_LOGGER: bool = False

TAG_LOGGER_THREAD_ID: int = int(getenv("TAG_LOGGER_THREAD_ID", 0)) or None

UPSTREAM_REPO: str = getenv("UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub")

USE_LEGACY_KANG: int = int(getenv("USE_LEGACY_KANG", 0))
