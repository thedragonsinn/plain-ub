import logging
from functools import wraps

from google.genai.client import AsyncClient, Client
from google.genai.types import (
    DynamicRetrievalConfig,
    GenerateContentConfig,
    GoogleSearchRetrieval,
    SafetySetting,
    Tool,
)
from pyrogram import filters

from app import BOT, CustomDB, Message, extra_config

logging.getLogger("google_genai.models").setLevel(logging.WARNING)

DB_SETTINGS = CustomDB("COMMON_SETTINGS")

try:
    client: Client = Client(api_key=extra_config.GEMINI_API_KEY)
    async_client: AsyncClient = client.aio
except:
    client = async_client = None


class Settings:
    MODEL = "gemini-2.0-flash"

    # fmt:off
    CONFIG = GenerateContentConfig(

        candidate_count=1,

        system_instruction=(
            "Answer precisely and in short unless specifically instructed otherwise."
            "\nIF asked related to code, do not comment the code and do not explain the code unless instructed."
        ),

        temperature=0.69,

        max_output_tokens=1024,

        safety_settings=[
            # SafetySetting(category="HARM_CATEGORY_UNSPECIFIED", threshold="BLOCK_NONE"),
            SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
            SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
            SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
            SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
        ],
        # fmt:on

        tools=[],
    )

    SEARCH_TOOL = Tool(
                google_search=GoogleSearchRetrieval(
                    dynamic_retrieval_config=DynamicRetrievalConfig(
                        dynamic_threshold=0.3
                    )
                )
            )

    @staticmethod
    def get_kwargs(use_search:bool=False) -> dict:
        tools = Settings.CONFIG.tools

        if not use_search and Settings.SEARCH_TOOL in tools:
            tools.remove(Settings.SEARCH_TOOL)

        if use_search and Settings.SEARCH_TOOL not in tools:
            tools.append(Settings.SEARCH_TOOL)

        return {"model": Settings.MODEL, "config": Settings.CONFIG}


async def init_task():
    model_info = await DB_SETTINGS.find_one({"_id": "gemini_model_info"}) or {}
    model_name = model_info.get("model_name")
    if model_name:
        Settings.MODEL = model_name


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


def get_response_text(response, quoted: bool = False, add_sources: bool = True):
    candidate = response.candidates[0]
    text = "\n".join([part.text for part in candidate.content.parts])
    sources = ""

    if add_sources:
        try:
            hrefs = [
                f"[{chunk.web.title}]({chunk.web.uri})"
                for chunk in candidate.grounding_metadata.grounding_chunks
            ]
            sources = "\n\nSources: " + " | ".join(hrefs)
        except (AttributeError, TypeError):
            sources = ""

    final_text = (text.strip() + sources).strip()
    return f"**>\n{final_text}<**" if quoted and "```" not in final_text else final_text


@BOT.add_cmd(cmd="llms")
async def list_ai_models(bot: BOT, message: Message):
    """
    CMD: LIST MODELS
    INFO: List and change Gemini Models.
    USAGE: .llms
    """
    model_list = [
        model.name.lstrip("models/")
        async for model in await async_client.models.list(config={"query_base": True})
        if "generateContent" in model.supported_actions
    ]

    model_str = "\n\n".join(model_list)

    update_str = (
        f"<b>Current Model</b>: <code>{Settings.MODEL}</code>\n\n"
        f"<blockquote expandable=True><pre language=text>{model_str}</pre></blockquote>"
        "\n\nReply to this message with the <code>model name</code> to change to a different model."
    )

    model_reply = await message.reply(update_str)

    response = await model_reply.get_response(
        timeout=60, reply_to_message_id=model_reply.id, from_user=message.from_user.id
    )

    if not response:
        await model_reply.delete()
        return

    if response.text not in model_list:
        await model_reply.edit(
            f"Invalid Model... run <code>{message.trigger}{message.cmd}</code> again"
        )
        return

    await DB_SETTINGS.add_data(
        {"_id": "gemini_model_info", "model_name": response.text}
    )

    resp_str = f"{response.text} saved as model."

    await model_reply.edit(resp_str)

    await bot.log_text(text=resp_str, type="ai")

    Settings.MODEL = response.text
