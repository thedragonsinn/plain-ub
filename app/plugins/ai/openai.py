import openai
from pyrogram.enums import ParseMode

from app import BOT, LOGGER, Message
from app.extra_config import OPENAI_CLIENT, OPENAI_MODEL
from app.plugins.ai.models import SYSTEM_INSTRUCTION

try:
    CLIENT = getattr(openai, f"Async{OPENAI_CLIENT}OpenAI")()
except Exception as e:
    LOGGER.error(e)
    CLIENT = None


@BOT.add_cmd(cmd="gpt")
async def chat_gpt(bot: BOT, message: Message):
    """
    CMD: GPT
    INFO: Ask a question to chat gpt.

    SETUP:
        To use this command you need to set either of these vars.

            For Default Client:
                OPENAI_API_KEY = your API key
                OPENAI_MODEL = model (optional, defaults to gpt-4o)
                OPENAI_BASE_URL = a custom endpoint (optional)

            For Azure Client:
                OPENAI_CLIENT="Azure"
                OPENAI_API_VERSION = your version
                OPENAI_MODEL = your azure model
                AZURE_OPENAI_API_KEY = your api key
                AZURE_OPENAI_ENDPOINT = your azure endpoint

    USAGE:
        .gpt hi
        .gpt [reply to a message]
    """
    if CLIENT is None:
        await message.reply(f"OpenAI Creds not set or are invalid.\nCheck Help.")
        return

    reply_text = message.replied.text if message.replied else ""

    prompt = f"{reply_text}\n\n\n{message.input}".strip()

    if not prompt:
        await message.reply("Ask a Question | Reply to a message.")
        return

    chat_completion = await CLIENT.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        model=OPENAI_MODEL,
    )

    response = chat_completion.choices[0].message.content
    await message.reply(
        text=f"```\n{prompt}```**GPT**:\n{response}", parse_mode=ParseMode.MARKDOWN
    )
