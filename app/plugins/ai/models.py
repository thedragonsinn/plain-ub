from functools import wraps

import google.generativeai as genai
from pyrogram import filters

from app import BOT, CustomDB, Message, extra_config

SETTINGS = CustomDB("COMMON_SETTINGS")

GENERATION_CONFIG = {"temperature": 0.69, "max_output_tokens": 2048}

SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
]

SYSTEM_INSTRUCTION = (
    "Answer precisely and in short unless specifically instructed otherwise."
    "\nWhen asked related to code, do not comment the code and do not explain unless instructed."
)

MODEL = genai.GenerativeModel(
    generation_config=GENERATION_CONFIG,
    safety_settings=SAFETY_SETTINGS,
    system_instruction=SYSTEM_INSTRUCTION,
)


async def init_task():
    if extra_config.GEMINI_API_KEY:
        genai.configure(api_key=extra_config.GEMINI_API_KEY)

    model_info = await SETTINGS.find_one({"_id": "gemini_model_info"}) or {}
    model_name = model_info.get("model_name")
    if model_name:
        MODEL._model_name = model_name


@BOT.add_cmd(cmd="lmodels")
async def list_ai_models(bot: BOT, message: Message):
    """
    CMD: LIST MODELS
    INFO: List and change Gemini Models.
    USAGE: .lmodels
    """
    model_list = [
        model.name
        for model in genai.list_models()
        if "generateContent" in model.supported_generation_methods
    ]

    model_str = "\n".join(model_list)
    update_str = (
        f"\n\nCurrent Model: {MODEL._model_name}"
        "\n\nTo change to a different model,"
        "Reply to this message with the model name."
    )

    model_reply = await message.reply(
        f"<blockquote expandable=True><pre language=text>{model_str}</pre></blockquote>{update_str}"
    )

    async def resp_filters(_, c, m):
        return m.reply_id == model_reply.id

    response = await model_reply.get_response(
        filters=filters.create(resp_filters), timeout=60
    )

    if not response:
        await model_reply.delete()
        return

    if response.text not in model_list:
        await model_reply.edit(
            f"Invalid Model... run <code>{message.trigger}lmodels</code> again"
        )
        return

    await SETTINGS.add_data({"_id": "gemini_model_info", "model_name": response.text})
    await model_reply.edit(f"{response.text} saved as model.")
    await model_reply.log()
    MODEL._model_name = response.text


def run_basic_check(function):
    @wraps(function)
    async def wrapper(bot: BOT, message: Message):
        if not extra_config.GEMINI_API_KEY:
            await message.reply(
                "Gemini API KEY not found."
                "\nGet it <a href='https://makersuite.google.com/app/apikey'>HERE</a> "
                "and set GEMINI_API_KEY var."
            )
            return

        if not (message.input or message.replied):
            await message.reply("<code>Ask a Question | Reply to a Message</code>")
            return

        try:
            await function(bot, message)
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
