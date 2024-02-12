import google.generativeai as genai
from pyrogram import filters

from app import BOT, Message, bot, Config, Convo

MODEL = genai.GenerativeModel("gemini-pro")


async def init_task():
    if Config.GEMINI_API_KEY:
        genai.configure(api_key=Config.GEMINI_API_KEY)


async def basic_check(message: Message):
    if not Config.GEMINI_API_KEY:
        await message.reply(
            "Gemini API KEY not found."
            "\nGet it <a href=https://ai.google.dev/''>HERE</a> "
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
    response = await MODEL.generate_content_async(message.input)
    await message.reply(response)


@bot.add_cmd(cmd="aichat")
async def ai_chat(bot: BOT, message: Message):
    """
    CMD: AICHAT
    INFO: Have a Conversation with Gemini AI.
    USAGE:
        .aichat hello
        keep replying to AI responses
    """
    if not (await basic_check(message)):  # fmt:skip
        return
    try:
        await do_convo(message)
    except TimeoutError:
        await message.reply("AI Chat TimeOut.")


async def do_convo(message: Message):
    chat = MODEL.start_chat(history=[])
    prompt = message.input
    async with Convo(
        client=bot,
        chat_id=message.chat.id,
        filters=generate_filter(message),
        timeout=600,
    ) as convo:
        while True:
            ai_response = (await chat.send_message_async(prompt)).text
            _, prompt = await convo.send_message(
                text=f"<b>GEMINI AI</b>:\n\n{ai_response}", get_response=True
            )


def generate_filter(message: Message):
    async def _filter(_, __, msg: Message):
        if (
            not msg.text
            or not msg.from_user
            or msg.from_user.id != message.from_user.id
            or not msg.reply_to_message
            or not msg.reply_to_message.from_user
            or msg.reply_to_message.from_user.id == bot.me.id
        ):
            return False
        return True

    return filters.create(_filter)
