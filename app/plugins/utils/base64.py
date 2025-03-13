# Plugin made by @tusharchopra07

import importlib
import subprocess
import sys
import base64
import asyncio

def ensure_module(module_name):
    try:
        importlib.import_module(module_name)
    except ImportError:
        print(f"{module_name} is not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", module_name])
        print(f"{module_name} has been installed.")

ensure_module('app')

from app import BOT, bot, Message

@bot.add_cmd(cmd="encode64")
async def encode_base64(bot: BOT, message: Message):
    try:
        if message.reply_to_message and message.reply_to_message.text:
            text_to_encode = message.reply_to_message.text
        else:
            text_to_encode = message.text.split(maxsplit=1)[1]

        encoded_text = base64.b64encode(text_to_encode.encode('utf-8')).decode('utf-8')

        await message.reply(f"**Encoded Base64:**\n`{encoded_text}`")

    except IndexError:
        await message.reply("Please provide text to encode or reply to a message.")
    except Exception as e:
        await message.reply(f"An error occurred: {str(e)}")


@bot.add_cmd(cmd="decode64")
async def decode_base64(bot: BOT, message: Message):
    try:
        if message.reply_to_message and message.reply_to_message.text:
            text_to_decode = message.reply_to_message.text
        else:
            text_to_decode = message.text.split(maxsplit=1)[1]

        decoded_text = base64.b64decode(text_to_decode).decode('utf-8')

        await message.reply(f"**Decoded Text:**\n`{decoded_text}`")

    except IndexError:
        await message.reply("Please provide base64 text to decode or reply to a message.")
    except Exception as e:
        await message.reply(f"An error occurred: {str(e)}")

print("Base64 encoding/decoding plugin has been loaded successfully.")
