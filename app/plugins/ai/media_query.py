import asyncio
import os
import shutil
import time

import google.generativeai as genai
from pyrogram.types.messages_and_media import Audio, Photo, Video, Voice
from ub_core.utils import get_tg_media_details

from app import Message
from app.plugins.ai.models import MODEL, get_response_text

PROMPT_MAP = {
    Video: "Summarize the video file",
    Photo: "Summarize the image file",
    Voice: (
        "\nDo not summarise."
        "\nTranscribe the audio file to english alphabets AS IS."
        "\nTranslate it only if the audio is not english."
        "\nIf the audio is in hindi: Transcribe it to hinglish without translating."
    ),
}
PROMPT_MAP[Audio] = PROMPT_MAP[Voice]


async def handle_media(prompt: str, media_message: Message, model=MODEL) -> str:
    media = get_tg_media_details(media_message)

    if getattr(media, "file_size", 0) >= 1048576 * 25:
        return "Error: File Size exceeds 25mb."

    prompt = prompt.strip() or PROMPT_MAP.get(
        type(media), "Analyse the file and explain."
    )

    download_dir = os.path.join("downloads", str(time.time()))
    downloaded_file = await media_message.download(download_dir)

    uploaded_file = await asyncio.to_thread(genai.upload_file, downloaded_file)

    while uploaded_file.state.name == "PROCESSING":
        await asyncio.sleep(5)
        uploaded_file = await asyncio.to_thread(genai.get_file, uploaded_file.name)

    response = await model.generate_content_async([prompt, uploaded_file])
    response_text = get_response_text(response)

    shutil.rmtree(download_dir, ignore_errors=True)
    return response_text
