import asyncio
import io
import os.path
import pathlib
import shutil
import time
from functools import wraps
from mimetypes import guess_type

from google.genai.types import File, Part
from ub_core.utils import get_tg_media_details

from app import BOT, Message, extra_config
from app.plugins.ai.gemini import async_client


def run_basic_check(function):
    @wraps(function)
    async def wrapper(bot: BOT, message: Message, *args, **kwargs):
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
        await function(bot, message, *args, **kwargs)

    return wrapper


async def upload_file(file: io.BytesIO | pathlib.Path | str, file_name: str) -> File:
    uploaded_file = await async_client.files.upload(file=file, config={"mime_type": guess_type(file_name)[0]})
    while uploaded_file.state.name == "PROCESSING":
        await asyncio.sleep(5)
        uploaded_file = await async_client.files.get(name=uploaded_file.name)

    return uploaded_file


async def upload_tg_file(message: Message, check_size: bool = True) -> File:
    media = get_tg_media_details(message)

    if check_size:
        assert getattr(media, "file_size", 0) <= 1048576 * 25, "File size exceeds 25mb."

    download_dir = None
    try:
        if getattr(media, "file_size", 0) < 500_000:
            downloaded_file: io.BytesIO = await message.download(in_memory=True)
            file_name = downloaded_file.name
        else:
            download_dir = f"downloads/{time.time()}/"
            downloaded_file: str = await message.download(download_dir)
            file_name = os.path.basename(downloaded_file)

        return await upload_file(downloaded_file, file_name)
    finally:
        if download_dir:
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


async def create_prompts(message: Message, is_chat: bool = False, check_size: bool = True) -> list[Part]:
    default_media_prompt = "Analyse the file and explain."
    input_prompt = message.filtered_input or "answer"

    # Conversational
    if is_chat:
        if message.media:
            prompt = message.caption or PROMPT_MAP.get(message.media.value) or default_media_prompt
            text_part = Part.from_text(text=prompt)
            uploaded_file = await upload_tg_file(message=message, check_size=check_size)
            file_part = Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
            return [text_part, file_part]

        return [Part.from_text(text=message.text)]

    # Single Use
    if reply := message.replied:
        if reply.media:
            prompt = message.filtered_input or PROMPT_MAP.get(reply.media.value) or default_media_prompt
            text_part = Part.from_text(text=prompt)
            uploaded_file = await upload_tg_file(message=reply, check_size=check_size)
            file_part = Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type)
            return [text_part, file_part]

        return [Part.from_text(text=input_prompt), Part.from_text(text=str(reply.text))]

    return [Part.from_text(text=input_prompt)]
