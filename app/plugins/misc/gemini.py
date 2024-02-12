import pickle
from io import BytesIO

import google.generativeai as genai
from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message as Msg

from app import BOT, Config, Convo, Message, bot

MODEL = genai.GenerativeModel("gemini-pro")


async def init_task():
    if Config.GEMINI_API_KEY:
        genai.configure(api_key=Config.GEMINI_API_KEY)


async def basic_check(message: Message):
    if not Config.GEMINI_API_KEY:
        await message.reply(
            "Gemini API KEY not found."
            "\nGet it <a href='https://ai.google.dev/'>HERE</a> "
            "and set GEMINI_API_KEY var."
        )
        return
    if not message.input:
        await message.reply("Ask a Question.")
        return
    return 1


@bot.add_cmd(cmd="ai")
async def question(bot: BOT, message: Message):
    """
    CMD: AI
    INFO: Ask a question to Gemini AI.
    USAGE: .ai what is the meaning of life.
    """
    if not (await basic_check(message)):  # fmt:skip
        return
    response = (await MODEL.generate_content_async(message.input)).text
    await message.reply(response)


@bot.add_cmd(cmd="aichat")
async def ai_chat(bot: BOT, message: Message):
    """
    CMD: AICHAT
    INFO: Have a Conversation with Gemini AI.
    USAGE:
        .aichat hello
        keep replying to AI responses
        After 5mins of Idle bot will export history n stop chat.
        use .load_history to continue
    """
    if not (await basic_check(message)):  # fmt:skip
        return
    try:
        chat = MODEL.start_chat(history=[])
        await do_convo(chat=chat, message=message)
    except TimeoutError:
        await export_history(chat, message)


@bot.add_cmd(cmd="load_history")
async def ai_chat(bot: BOT, message: Message):
    """
    CMD: LOAD_HISTORY
    INFO: Load a Conversation with Gemini AI from previous session.
    USAGE:
        .load_history {question} [reply to history document]
    """
    reply = message.replied
    if (
        not message.input
        or not reply
        or not reply.document
        or not reply.document.file_name
        or reply.document.file_name != "AI_Chat_History.txt"
    ):
        await message.reply(
            "Give an input to continue Convo and Reply to a Valid History file."
        )
        return
        resp = await message.reply("<i>Loading History...</i>")
    try:
        history = pickle.load((await reply.download(in_memory=True)))
        await resp.edit("<i>History Loaded... Resuming chat</i>")
        chat = MODEL.start_chat(history=history)
        await do_convo(chat=chat, message=message)
    except TimeoutError:
        await export_history(chat, message)


async def do_convo(chat, message: Message):
    prompt = message.input
    reply_to_message_id = message.id
    async with Convo(
        client=bot,
        chat_id=message.chat.id,
        filters=generate_filter(message),
        timeout=300,
    ) as convo:
        while True:
            if isinstance(prompt, (Message, Msg)):
                reply_to_message_id = prompt.id
                prompt = prompt.text
            ai_response = (await chat.send_message_async(prompt)).text
            _, prompt = await convo.send_message(
                text=f"<b>GEMINI AI</b>:\n\n{ai_response}",
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.MARKDOWN,
                get_response=True,
            )


def generate_filter(message: Message):
    async def _filter(_, __, msg: Message):
        if (
            not msg.text
            or not msg.from_user
            or msg.from_user.id != message.from_user.id
            or not msg.reply_to_message
            or not msg.reply_to_message.from_user
            or msg.reply_to_message.from_user.id != bot.me.id
        ):
            return False
        return True

    return filters.create(_filter)


async def export_history(chat, message: Message):
    doc = BytesIO(pickle.dumps(chat.history))
    doc.name = "AI_Chat_History.txt"
    await bot.send_document(
        chat_id=message.from_user.id, document=doc, caption=message.text
    )
