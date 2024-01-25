import os
import tracemalloc

from dotenv import load_dotenv

tracemalloc.start()

load_dotenv("config.env")

from app.config import Config  # NOQA
from app.core.db import DB, DB_CLIENT, CustomDB  # NOQA
from app.core import Message  # NOQA

from app.core.logger import getLogger  # NOQA

LOGGER = getLogger("PLAIN-UB")

from app.core.client.client import BOT  # NOQA


if "com.termux" not in os.environ.get("PATH", ""):
    import uvloop

    uvloop.install()

bot: BOT = BOT()
