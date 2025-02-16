import asyncio
import os
import shutil
import time
from mimetypes import guess_type

from pyrogram.types.messages_and_media import Audio, Photo, Video, Voice
from ub_core.utils import get_tg_media_details

from app import Message
from app.plugins.ai.models import async_client

PROMPT_MAP = {
    Video: "Summarize video and audio from the file",
    Photo: "Summarize the image file",
    Voice: (
        "Transcribe this audio. "
        "Use ONLY english alphabet to express hindi. "
        "Do not translate."
        "Do not write anything extra than the transcription. Use proper punctuation, and formatting."
        "\n\nIMPORTANT - YOU ARE ONLY ALLOWED TO USE ENGLISH ALPHABET."
    ),
}
PROMPT_MAP[Audio] = PROMPT_MAP[Voice]


async def handle_ai_query(prompt: str, query: Message | None, **kwargs) -> str:

    if query and query.text:
        prompts = [str(query.text), prompt or "answer"]
    elif query is None:
        prompts = [prompt]
        query = message
    
    media = get_tg_media_details(query)

    if media is not None:
        if getattr(media, "file_size", 0) >= 1048576 * 25:
            return "Error: File Size exceeds 25mb."

        prompt = prompt.strip() or PROMPT_MAP.get(
            type(media), "Analyse the file and explain."
        )

        download_dir = os.path.join("downloads", str(time.time())) + "/"
        downloaded_file: str = await query.download(download_dir)

        uploaded_file = await async_client.files.upload(
            file=downloaded_file,
            config={
            "mime_type": getattr(media, "mime_type", guess_type(downloaded_file)[0])
            },
        )

        while uploaded_file.state.name == "PROCESSING":
            await asyncio.sleep(5)
            uploaded_file = await async_client.files.get(name=uploaded_file.name)

        prompts = [uploaded_file, prompt]
        
        shutil.rmtree(download_dir, ignore_errors=True)
            
    response = await async_client.models.generate_content(
        **kwargs, contents=prompts
    )
    
    return response
