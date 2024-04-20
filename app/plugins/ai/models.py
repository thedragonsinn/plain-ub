import google.generativeai as genai

from app import Message, extra_config


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


TEXT_MODEL = genai.GenerativeModel(
    model_name="gemini-pro",
    generation_config=GENERATION_CONFIG,
    safety_settings=SAFETY_SETTINGS,
)

IMAGE_MODEL = genai.GenerativeModel(
    model_name="gemini-pro-vision",
    generation_config=GENERATION_CONFIG,
    safety_settings=SAFETY_SETTINGS,
)

MEDIA_MODEL = genai.GenerativeModel(
    model_name="models/gemini-1.5-pro-latest",
    generation_config=GENERATION_CONFIG,
    safety_settings=SAFETY_SETTINGS,
)


async def basic_check(message: Message):
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
    return 1


def get_response_text(response):
    return "\n".join([part.text for part in response.parts])
