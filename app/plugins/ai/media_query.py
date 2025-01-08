import asyncio
import glob
import mimetypes
import os
import shutil
import time
from io import BytesIO

import google.generativeai as genai
from google.ai import generativelanguage as glm
from ub_core.utils import run_shell_cmd

from app import BOT, Message, bot
from app.plugins.ai.models import MODEL, get_response_text, run_basic_check

CODE_EXTS = {
    ".txt",
    ".java",
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".py",
    ".js",
    ".html",
    ".htm",
    ".css",
    ".rb",
    ".php",
    ".swift",
    ".go",
    ".sql",
    ".r",
    ".pl",
    ".kt",
}
PHOTO_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".gif"}
AUDIO_EXTS = {".aac", ".mp3", ".opus", ".m4a", ".ogg"}


@bot.add_cmd(cmd="ocr")
@run_basic_check
async def photo_query(bot: BOT, message: Message):
    """
    CMD: OCR
    INFO: Ask a question to Gemini AI about replied image.
    USAGE: .ocr [reply to a photo] explain the image.
    """
    prompt = message.input
    reply = message.replied
    message_response = await message.reply("processing... this may take a while")

    if not (prompt and reply and reply.photo):
        await message_response.edit("Reply to an image and give a prompt.")
        return

    ai_response_text = await handle_photo(prompt, reply)
    await message_response.edit(ai_response_text)


@bot.add_cmd(cmd="ts")
@run_basic_check
async def audio_to_text(bot: BOT, message: Message):
    """
    CMD: STT (Speech To Text)
    INFO: Convert Audio files to text.
    USAGE: .stt [reply to audio file] summarise/transcribe the audio file.
    """
    default_prompt = (
        "Transcribe the audio file to english alphabets AS IS."
        "\nTranslate it only if the audio is not in hindi/english."
        "\nDo not summarise."
    )
    prompt = message.input or default_prompt
    reply = message.replied
    audio = reply.audio or reply.voice

    message_response = await message.reply("processing... this may take a while")
    if not (reply and audio):
        await message_response.edit("Reply to an audio file and give a prompt.")
        return

    ai_response_text = await handle_audio(prompt, reply)
    await message_response.edit(ai_response_text)


@bot.add_cmd(cmd="ocrv")
@run_basic_check
async def video_to_text(bot: BOT, message: Message):
    """
    CMD: OCRV
    INFO: Convert Video info to text.
    USAGE: .ocrv [reply to video file] summarise the video file.
    """
    default_prompt = "Summarize the file"
    prompt = message.input or default_prompt
    reply = message.replied
    message_response = await message.reply("processing... this may take a while")

    if not (reply and (reply.video or reply.animation)):
        await message_response.edit("Reply to a video and give a prompt.")
        return

    ai_response_text, uploaded_files = await handle_video(prompt, reply)
    await message_response.edit(ai_response_text)

    for uploaded_frame in uploaded_files:
        await asyncio.to_thread(genai.delete_file, name=uploaded_frame.name)


@bot.add_cmd(cmd="aim")
@run_basic_check
async def handle_document(bot: BOT, message: Message):
    """
    CMD: AIM
    INFO: Prompt Ai to perform task for documents containing pic, vid, code, audio.
    USAGE: .aim [reply to a file] convert this file to python | summarise the video, audio, picture.
    """
    prompt = message.input
    reply = message.replied
    document = reply.document
    message_response = await message.reply("processing... this may take a while")

    if not (prompt and reply and document):
        await message_response.edit("Reply to a document and give a prompt.")
        return

    file_name = document.file_name
    if not file_name:
        await message_response.edit("Unsupported file.")
        return

    name, ext = os.path.splitext(file_name)

    if ext in PHOTO_EXTS:
        ai_response_text = await handle_photo(prompt, reply)
    elif ext in AUDIO_EXTS:
        ai_response_text = await handle_audio(prompt, reply)
    elif ext in CODE_EXTS:
        ai_response_text = await handle_code(prompt, reply)
    elif ext in VIDEO_EXTS:
        ai_response_text = await handle_video(prompt, reply)
    else:
        await message_response.edit("Unsupported Media.")
        return

    await message_response.edit(ai_response_text)


async def download_file(file_name: str, message: Message) -> tuple[str, str]:
    download_dir = os.path.join("downloads", str(time.time()))
    file_path = os.path.join(download_dir, file_name)
    await message.download(file_path)
    return file_path, download_dir


async def handle_audio(prompt: str, message: Message, model=MODEL):
    audio = message.document or message.audio or message.voice
    file_name = getattr(audio, "file_name", "audio.aac")

    file_path, download_dir = await download_file(file_name, message)
    file_response = genai.upload_file(path=file_path)

    response = await model.generate_content_async([prompt, file_response])
    response_text = get_response_text(response)

    genai.delete_file(name=file_response.name)
    shutil.rmtree(file_path, ignore_errors=True)

    return response_text


async def handle_code(prompt: str, message: Message, model=MODEL):
    file: BytesIO = await message.download(in_memory=True)
    text = file.getvalue().decode("utf-8")
    final_prompt = f"{text}\n\n{prompt}"
    response = await model.generate_content_async(final_prompt)
    return get_response_text(response)


async def handle_photo(prompt: str, message: Message, model=MODEL):
    file = await message.download(in_memory=True)

    mime_type, _ = mimetypes.guess_type(file.name)
    if mime_type is None:
        mime_type = "image/unknown"

    image_blob = glm.Blob(mime_type=mime_type, data=file.getvalue())
    response = await model.generate_content_async([prompt, image_blob])
    return get_response_text(response)


async def handle_video(prompt: str, message: Message, model=MODEL) -> tuple[str, list]:
    file_name = "v.mp4"
    file_path, download_dir = await download_file(file_name, message)

    output_path = os.path.join(download_dir, "output_frame_%04d.png")
    audio_path = os.path.join(download_dir, "audio.")

    await run_shell_cmd(
        f'ffmpeg -hide_banner -loglevel error -i "{file_path}" -vf "fps=1" "{output_path}"'
        f"&&"
        f'ffmpeg -hide_banner -loglevel error -i "{file_path}" -map 0:a:1 -vn -acodec copy "{audio_path}%(ext)s"'
    )

    prompt_n_uploaded_files = [prompt]

    for frame in glob.glob(f"{download_dir}/*png"):
        uploaded_frame = await asyncio.to_thread(genai.upload_file, frame)
        prompt_n_uploaded_files.append(uploaded_frame)

    for file in glob.glob(f"{audio_path}*"):
        uploaded_file = await asyncio.to_thread(genai.upload_file, file)
        prompt_n_uploaded_files.append(uploaded_file)

    response = await model.generate_content_async(prompt_n_uploaded_files)
    response_text = get_response_text(response)
    shutil.rmtree(download_dir, ignore_errors=True)
    return response_text, prompt_n_uploaded_files
