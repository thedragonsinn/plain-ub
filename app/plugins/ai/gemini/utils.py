import asyncio
import shutil
import time
from functools import wraps
from mimetypes import guess_type

from google.genai.types import File, Part
from ub_core.utils import get_tg_media_details

from app import BOT, Message, extra_config
from app.plugins.ai.gemini import DB_SETTINGS, AIConfig, async_client


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
) -> list[File, str] | list[Part]:
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
        f"{AIConfig.TEXT_MODEL if '-i' not in message.flags else AIConfig.IMAGE_MODEL}</code>"
        f"\n\n<blockquote expandable=True><pre language=text>{model_str}</pre></blockquote>"
        "\n\nReply to this message with the <code>model name</code> to change to a different model."
    )

    model_info_response = await message.reply(update_str)

    model_name, _ = await model_info_response.get_response(
        timeout=60,
        reply_to_message_id=model_info_response.id,
        from_user=message.from_user.id,
        quote=True,
    )

    if not model_name:
        await model_info_response.delete()
        return

    if model_name not in model_list:
        await model_info_response.edit("<code>Invalid Model... Try again</code>")
        return

    if "-i" in message.flags:
        data_key = "image_model_name"
        AIConfig.IMAGE_MODEL = model_name
    else:
        data_key = "model_name"
        AIConfig.TEXT_MODEL = model_name

    await DB_SETTINGS.add_data({"_id": "gemini_model_info", data_key: model_name})
    resp_str = f"{model_name} saved as model."
    await model_info_response.edit(resp_str)
    await bot.log_text(text=resp_str, type=f"ai_{data_key}")
