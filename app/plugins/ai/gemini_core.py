import asyncio
import io
import logging
import shutil
import time
from functools import wraps
from mimetypes import guess_type

from google.genai.client import AsyncClient, Client
from google.genai.types import (
    DynamicRetrievalConfig,
    File,
    GenerateContentConfig,
    GoogleSearchRetrieval,
    Part,
    SafetySetting,
    Tool,
)
from ub_core.utils import get_tg_media_details

from app import BOT, CustomDB, Message, extra_config

logging.getLogger("google_genai.models").setLevel(logging.WARNING)

DB_SETTINGS = CustomDB["COMMON_SETTINGS"]

try:
    client: Client | None = Client(api_key=extra_config.GEMINI_API_KEY)
    async_client: AsyncClient | None = client.aio
except:
    client = async_client = None


async def init_task():
    model_info = await DB_SETTINGS.find_one({"_id": "gemini_model_info"}) or {}
    if model_name := model_info.get("model_name"):
        Settings.TEXT_MODEL = model_name
    if image_model := model_info.get("image_model_name"):
        Settings.IMAGE_MODEL = image_model


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

        await function(bot, message)

    return wrapper


def get_response_content(
    response, quoted: bool = False, add_sources: bool = True
) -> tuple[str, io.BytesIO | None]:

    try:
        candidate = response.candidates
        parts = candidate[0].content.parts
        parts[0]
    except (AttributeError, IndexError, TypeError):
        return "Query failed... Try again", None

    try:
        image_data = io.BytesIO(parts[0].inline_data.data)
        image_data.name = "photo.jpg"
    except (AttributeError, IndexError):
        image_data = None

    text = "\n".join([part.text for part in parts if part.text])
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

    if final_text and quoted and "```" not in final_text:
        final_text = f"**>\n{final_text}<**"

    return final_text, image_data


async def save_file(message: Message, check_size: bool = True) -> File | None:
    media = get_tg_media_details(message)

    if check_size:
        assert getattr(media, "file_size", 0) <= 1048576 * 25, "File size exceeds 25mb."

    download_dir = f"downloads/{time.time()}/"
    try:
        downloaded_file: str = await message.download(download_dir)
        uploaded_file = await async_client.files.upload(
            file=downloaded_file,
            config={
                "mime_type": getattr(media, "mime_type", None) or guess_type(downloaded_file)[0]
            },
        )
        while uploaded_file.state.name == "PROCESSING":
            await asyncio.sleep(5)
            uploaded_file = await async_client.files.get(name=uploaded_file.name)

        return uploaded_file

    finally:
        shutil.rmtree(download_dir, ignore_errors=True)


PROMPT_MAP = {
    "video": "Summarize video and audio from the file",
    "photo": "Summarize the image file",
    "voice": (
        "\nDo not summarise."
        "\nTranscribe the audio file to english alphabets AS IS."
        "\nTranslate it only if the audio is not english."
        "\nIf the audio is in hindi: Transcribe it to hinglish without translating."
    ),
}
PROMPT_MAP["audio"] = PROMPT_MAP["voice"]


async def create_prompts(
    message: Message, is_chat: bool = False, check_size: bool = True
) -> list[File, str] | list[str]:

    default_media_prompt = "Analyse the file and explain."
    input_prompt = message.filtered_input or "answer"

    # Conversational
    if is_chat:
        if message.media:
            prompt = message.caption or PROMPT_MAP.get(message.media.value) or default_media_prompt
            text_part = Part.from_text(text=prompt)
            uploaded_file = await save_file(message=message, check_size=check_size)
            file_part = Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
            return [text_part, file_part]

        return [Part.from_text(text=message.text)]

    # Single Use
    if reply := message.replied:
        if reply.media:
            prompt = (
                message.filtered_input or PROMPT_MAP.get(reply.media.value) or default_media_prompt
            )
            text_part = Part.from_text(text=prompt)
            uploaded_file = await save_file(message=reply, check_size=check_size)
            file_part = Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
            return [text_part, file_part]

        return [Part.from_text(text=input_prompt), Part.from_text(text=str(reply.text))]

    return [Part.from_text(text=input_prompt)]


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
        f"<b>Current Model</b>: <code>"
        f"{Settings.TEXT_MODEL if "-i" not in message.flags else Settings.IMAGE_MODEL}</code>"
        f"\n\n<blockquote expandable=True><pre language=text>{model_str}</pre></blockquote>"
        "\n\nReply to this message with the <code>model name</code> to change to a different model."
    )

    model_info_response = await message.reply(update_str)

    model_response = await model_info_response.get_response(
        timeout=60, reply_to_message_id=model_info_response.id, from_user=message.from_user.id
    )

    if not model_response:
        await model_info_response.delete()
        return

    if model_response.text not in model_list:
        await model_info_response.edit(f"<code>Invalid Model... Try again</code>")
        return

    if "-i" in message.flags:
        data_key = "image_model_name"
        Settings.IMAGE_MODEL = model_response.text
    else:
        data_key = "model_name"
        Settings.TEXT_MODEL = model_response.text

    await DB_SETTINGS.add_data({"_id": "gemini_model_info", data_key: model_response.text})
    resp_str = f"{model_response.text} saved as model."
    await model_info_response.edit(resp_str)
    await bot.log_text(text=resp_str, type=f"ai_{data_key}")


SAFETY_SETTINGS = [
    # SafetySetting(category="HARM_CATEGORY_UNSPECIFIED", threshold="BLOCK_NONE"),
    SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
    SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
]

SEARCH_TOOL = Tool(
    google_search=GoogleSearchRetrieval(
        dynamic_retrieval_config=DynamicRetrievalConfig(dynamic_threshold=0.3)
    )
)

SYSTEM_INSTRUCTION = (
    "Answer precisely and in short unless specifically instructed otherwise."
    "\nIF asked related to code, do not comment the code and do not explain the code unless instructed."
)


class Settings:
    TEXT_MODEL = "gemini-2.0-flash"

    TEXT_CONFIG = GenerateContentConfig(
        candidate_count=1,
        max_output_tokens=1024,
        response_modalities=["Text"],
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.69,
        tools=[],
    )

    IMAGE_MODEL = "gemini-2.0-flash-exp"

    IMAGE_CONFIG = GenerateContentConfig(
        candidate_count=1,
        max_output_tokens=1024,
        response_modalities=["Text", "Image"],
        # system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.99,
    )

    @staticmethod
    def get_kwargs(use_search: bool = False, image_mode: bool = False) -> dict:
        if image_mode:
            return {"model": Settings.IMAGE_MODEL, "config": Settings.IMAGE_CONFIG}

        tools = Settings.TEXT_CONFIG.tools

        if not use_search and SEARCH_TOOL in tools:
            tools.remove(SEARCH_TOOL)

        if use_search and SEARCH_TOOL not in tools:
            tools.append(SEARCH_TOOL)

        return {"model": Settings.TEXT_MODEL, "config": Settings.TEXT_CONFIG}
