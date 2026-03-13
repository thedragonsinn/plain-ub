import logging

from google.genai.client import AsyncClient, Client

from app import Config, CustomDB, extra_config

logging.getLogger("google_genai.models").setLevel(logging.WARNING)

DB_SETTINGS = CustomDB["COMMON_SETTINGS"]

try:
    client: Client | None = Client(api_key=extra_config.GEMINI_API_KEY)
    async_client: AsyncClient | None = client.aio
    Config.TASK_MANAGER.add_exit(client.close)
    Config.TASK_MANAGER.add_exit(async_client.aclose)
except:
    client = async_client = None
