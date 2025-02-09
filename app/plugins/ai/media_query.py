import asyncio
import os
import shutil
import time
from mimetypes import guess_type

from pyrogram.types.messages_and_media import Audio, Photo, Video, Voice
from ub_core.utils import get_tg_media_details

from app import Message
from app.plugins.ai.models import async_client, get_response_text

PROMPT_MAP = {
    Video: "Summarize video and audio from the file",
    Photo: "Summarize the image file",
    Voice: (
        "\nDo not summarise."
        "\nTranscribe the audio file to english alphabets AS IS."
        "\nTranslate it only if the audio is not english."
        "\nIf the audio is in hindi: Transcribe it to hinglish without translating."
    ),
}
PROMPT_MAP[Audio] = PROMPT_MAP[Voice]


async def handle_media(prompt: str, media_message: Message, **kwargs) -> str:
    media = get_tg_media_details(media_message)

    if getattr(media, "file_size", 0) >= 1048576 * 25:
        return "Error: File Size exceeds 25mb."

    prompt = prompt.strip() or PROMPT_MAP.get(
        type(media), "Analyse the file and explain."
    )

    download_dir = os.path.join("downloads", str(time.time())) + "/"
    downloaded_file: str = await media_message.download(download_dir)

    uploaded_file = await async_client.files.upload(
        file=downloaded_file,
        config={
            "mime_type": getttr(media, "mime_type", guess_type(downloaded_file)[0])
        },
    )

    while uploaded_file.state.name == "PROCESSING":
        await asyncio.sleep(5)
        uploaded_file = await async_client.files.get(name=uploaded_file.name)

    response = await async_client.models.generate_content(
        **kwargs, contents=[uploaded_file, prompt]
    )
    response_text = get_response_text(response, quoted=True)

    shutil.rmtree(download_dir, ignore_errors=True)
    return response_text
