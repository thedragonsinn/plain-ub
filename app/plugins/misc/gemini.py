import pickle
from io import BytesIO

import google.generativeai as genai
from pyrogram import filters
from pyrogram.enums import ParseMode

from app import BOT, Convo, Message, bot, extra_config

MODEL = genai.GenerativeModel(
    "gemini-pro", safety_settings={"HARASSMENT": "block_none"}
)

INSTRUCTIONS = "Your response length must not exceed 4000 for all of my question(s):\n"


async def init_task():
    if extra_config.GEMINI_API_KEY:
        genai.configure(api_key=extra_config.GEMINI_API_KEY)


async def basic_check(message: Message):
    if not extra_config.GEMINI_API_KEY:
        await message.reply(
            "Gemini API KEY not found."
            "\nGet it <a href='https://makersuite.google.com/app/apikey'>HERE</a> "
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
    prompt = INSTRUCTIONS + message.input
    response = await MODEL.generate_content_async(prompt)
    response_text = get_response_text(response)
    await message.reply(
        text="**GEMINI AI**:\n\n" + response_text, parse_mode=ParseMode.MARKDOWN
    )


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
    chat = MODEL.start_chat(history=[])
    try:
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
    if not (await basic_check(message)):  # fmt:skip
        return
    reply = message.replied
    if (
        not reply
        or not reply.document
        or not reply.document.file_name
        or reply.document.file_name != "AI_Chat_History.pkl"
    ):
        await message.reply("Reply to a Valid History file.")
        return
    resp = await message.reply("<i>Loading History...</i>")
    doc: BytesIO = (await reply.download(in_memory=True)).getbuffer()  # NOQA
    history = pickle.loads(doc)
    await resp.edit("<i>History Loaded... Resuming chat</i>")
    chat = MODEL.start_chat(history=history)
    try:
        await do_convo(chat=chat, message=message, history=True)
    except TimeoutError:
        await export_history(chat, message)


def get_response_text(response):
    return "\n".join([part.text for part in response.parts])


async def do_convo(chat, message: Message, history: bool = False):
    if not history:
        prompt = INSTRUCTIONS + message.input
    else:
        prompt = message.input
    reply_to_message_id = message.id
    async with Convo(
        client=bot,
        chat_id=message.chat.id,
        filters=generate_filter(message),
        timeout=300,
        check_for_duplicates=False,
    ) as convo:
        while True:
            ai_response = await chat.send_message_async(prompt)
            ai_response_text = get_response_text(ai_response)
            text = f"**GEMINI AI**:\n\n{ai_response_text}"
            _, prompt_message = await convo.send_message(
                text=text,
                reply_to_message_id=reply_to_message_id,
                parse_mode=ParseMode.MARKDOWN,
                get_response=True,
            )
            prompt, reply_to_message_id = prompt_message.text, prompt_message.id


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
    doc.name = "AI_Chat_History.pkl"
    await bot.send_document(
        chat_id=message.from_user.id, document=doc, caption=message.text
    )
