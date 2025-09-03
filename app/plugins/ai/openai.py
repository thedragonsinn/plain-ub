from base64 import b64decode
from io import BytesIO
from os import environ

import openai
from pyrogram.enums import ParseMode
from pyrogram.types import InputMediaPhoto

from app import BOT, Message
from app.plugins.ai.gemini.config import SYSTEM_INSTRUCTION

OPENAI_CLIENT = environ.get("OPENAI_CLIENT", "")
OPENAI_MODEL = environ.get("OPENAI_MODEL", "gpt-4o")

AI_CLIENT = getattr(openai, f"Async{OPENAI_CLIENT}OpenAI")

if AI_CLIENT == openai.AsyncAzureOpenAI:
    text_init_kwargs = dict(
        api_key=environ.get("AZURE_OPENAI_API_KEY"),
        api_version=environ.get("OPENAI_API_VERSION"),
        azure_endpoint=environ.get("AZURE_OPENAI_ENDPOINT"),
        azure_deployment=environ.get("AZURE_DEPLOYMENT"),
    )
    image_init_kwargs = dict(
        api_key=environ.get("DALL_E_API_KEY"),
        api_version=environ.get("DALL_E_API_VERSION"),
        azure_endpoint=environ.get("DALL_E_ENDPOINT"),
        azure_deployment=environ.get("DALL_E_DEPLOYMENT"),
    )
else:
    text_init_kwargs = dict(
        api_key=environ.get("OPENAI_API_KEY"), base_url=environ.get("OPENAI_BASE_URL")
    )
    image_init_kwargs = dict(
        api_key=environ.get("DALL_E_API_KEY"), base_url=environ.get("DALL_E_ENDPOINT")
    )

try:
    TEXT_CLIENT = AI_CLIENT(**text_init_kwargs)
except:
    TEXT_CLIENT = None

try:
    DALL_E_CLIENT = AI_CLIENT(**image_init_kwargs)
except:
    DALL_E_CLIENT = None


@BOT.add_cmd(cmd="gpt")
async def chat_gpt(bot: BOT, message: Message):
    """
    CMD: GPT
    INFO: Ask a question to chat gpt.

    SETUP:
        To use this command you need to set either of these vars.

            For Default Client:
                OPENAI_API_KEY = your API key
                OPENAI_MODEL = model (optional, defaults to gpt-4o)
                OPENAI_BASE_URL = a custom endpoint (optional)

            For Azure Client:
                OPENAI_CLIENT="Azure"
                OPENAI_API_VERSION = your version
                OPENAI_MODEL = your azure model
                AZURE_OPENAI_API_KEY = your api key
                AZURE_OPENAI_ENDPOINT = your azure endpoint
                AZURE_DEPLOYMENT = your azure deployment

    USAGE:
        .gpt hi
        .gpt [reply to a message]
    """
    if TEXT_CLIENT is None:
        await message.reply("OpenAI Creds not set or are invalid.\nCheck Help.")
        return

    reply_text = message.replied.text if message.replied else ""

    prompt = f"{reply_text}\n\n\n{message.input}".strip()

    if not prompt:
        await message.reply("Ask a Question | Reply to a message.")
        return

    chat_completion = await TEXT_CLIENT.chat.completions.create(
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": prompt},
        ],
        model=OPENAI_MODEL,
    )

    response = chat_completion.choices[0].message.content

    await message.reply(text=f"**>\n••> {prompt}<**\n" + response, parse_mode=ParseMode.MARKDOWN)


@BOT.add_cmd(cmd="igen")
async def chat_gpt(bot: BOT, message: Message):
    """
    CMD: IGEN
    INFO: Generate Images using Dall-E.

    SETUP:
        To use this command you need to set either of these vars.

            For Default Client:
                DALL_E_API_KEY = your API key
                DALL_E_ENDPOINT = a custom endpoint (optional)

            For Azure Client:
                OPENAI_CLIENT="Azure"
                DALL_E_API_KEY = your api key
                DALL_E_API_VERSION = your version
                DALL_E_ENDPOINT = your azure endpoint
                DALL_E_DEPLOYMENT = your azure deployment

    FLAGS:
        -v: for vivid style images (default)
        -n: for less vivid and natural type of images
        -s: to send with spoiler
        -p: portrait output
        -l: landscape output

    USAGE:
        .igen cats on moon
    """
    if DALL_E_CLIENT is None:
        await message.reply("OpenAI Creds not set or are invalid.\nCheck Help.")
        return

    prompt = message.filtered_input.strip()

    if not prompt:
        await message.reply("Give a prompt to generate image.")
        return

    response = await message.reply("Generating image...")

    if "-p" in message.flags:
        output_res = "1024x1792"
    elif "-l" in message.flags:
        output_res = "1792x1024"
    else:
        output_res = "1024x1024"

    try:
        generated_image = await DALL_E_CLIENT.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=output_res,
            quality="hd",
            response_format="b64_json",
            style="natural" if "-n" in message.flags else "vivid",
        )
    except Exception:
        await response.edit("Something went wrong... Check log channel.")
        raise

    image_io = BytesIO(b64decode(generated_image.data[0].b64_json))
    image_io.name = "photo.png"

    await response.edit_media(
        InputMediaPhoto(
            media=image_io, caption=f"**>\n{prompt}\n<**", has_spoiler="-s" in message.flags
        )
    )
