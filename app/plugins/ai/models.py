from functools import wraps

import google.generativeai as genai
from app import BOT, Message, extra_config


async def init_task():
    if extra_config.GEMINI_API_KEY:
        genai.configure(api_key=extra_config.GEMINI_API_KEY)


GENERATION_CONFIG = {"temperature": 0.69, "max_output_tokens": 2048}

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]


MODEL = genai.GenerativeModel(
    model_name="models/gemini-1.5-flash",
    generation_config=GENERATION_CONFIG,
    safety_settings=SAFETY_SETTINGS,
)


async def run_basic_check(func):

    @wraps(func)
    async def wrapper(bot: BOT, message: Message):

        if not extra_config.GEMINI_API_KEY:
            await message.reply(
                "Gemini API KEY not found."
                "\nGet it <a href='https://makersuite.google.com/app/apikey'>HERE</a> "
                "and set GEMINI_API_KEY var."
            )
            return

        if not message.input:
            await message.reply("Ask a Question.")
            return

        try:
            await func(bot, message)
        except Exception as e:

            if "User location is not supported for the API use" in str(e):
                await message.reply(
                    "Your server location doesn't allow gemini yet."
                    "\nIf you are on koyeb change your app region to Washington DC."
                )
                return

            raise

    return wrapper


def get_response_text(response):
    return "\n".join([part.text for part in response.parts])
