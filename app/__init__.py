import os

from dotenv import load_dotenv
load_dotenv("config.env")

from app.config import Config
from app.core.db import DB
from app.core.client.client import BOT

if "com.termux" not in os.environ.get("PATH", ""):
    import uvloop

    uvloop.install()

bot = BOT()
