from os import environ

BOT_NAME = "PLAIN-UB"

DISABLED_SUPERUSERS: list[int] = []

FBAN_LOG_CHANNEL: int = int(environ.get("FBAN_LOG_CHANNEL", environ.get("LOG_CHAT")))

FBAN_SUDO_ID: int = int(environ.get("FBAN_SUDO_ID", 0))

FBAN_SUDO_TRIGGER: str = environ.get("FBAN_SUDO_TRIGGER")

GEMINI_API_KEY: str = environ.get("GEMINI_API_KEY")

LOAD_HANDLERS: bool = True

MESSAGE_LOGGER_CHAT: int = int(
    environ.get("MESSAGE_LOGGER_CHAT", environ.get("LOG_CHAT"))
)

PM_GUARD: bool = False

PM_LOGGER: bool = False

TAG_LOGGER: bool = False

UPSTREAM_REPO: str = environ.get(
    "UPSTREAM_REPO", "https://github.com/thedragonsinn/plain-ub"
)
