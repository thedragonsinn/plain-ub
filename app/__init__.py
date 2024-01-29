import os
import tracemalloc

from dotenv import load_dotenv

tracemalloc.start()

load_dotenv("config.env")


if "com.termux" not in os.environ.get("PATH", ""):
    import uvloop

    uvloop.install()


from app.config import Config  # NOQA
from app.core import DB, DB_CLIENT, CustomDB, Message, Convo  # NOQA
from app.core.client import BOT, bot  # NOQA
from app.core.logger import LOGGER  # NOQA
