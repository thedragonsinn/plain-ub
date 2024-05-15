import pickle
from io import BytesIO

from pyrogram import filters
from pyrogram.enums import ParseMode

from app import BOT, Convo, Message, bot
from app.plugins.ai.models import TEXT_MODEL, basic_check, get_response_text

CONVO_CACHE: dict[str, Convo] = {}


@bot.add_cmd(cmd="ai")
async def question(bot: BOT, message: Message):
    """
    CMD: AI
    INFO: Ask a question to Gemini AI.
    USAGE: .ai what is the meaning of life.
    """

    if not await basic_check(message):
        return

    prompt = message.input

    response = await TEXT_MODEL.generate_content_async(prompt)

    response_text = get_response_text(response)

    if not isinstance(message, Message):
        await message.edit(
            text=f"```\n{prompt}```**GEMINI AI**:\n{response_text.strip()}",
            parse_mode=ParseMode.MARKDOWN,
        )
    else:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"```\n{prompt}```**GEMINI AI**:\n{response_text.strip()}",
            parse_mode=ParseMode.MARKDOWN,
            reply_to_message_id=message.reply_id or message.id,
        )


@bot.add_cmd(cmd="aichat")
async def ai_chat(bot: BOT, message: Message):
    """
    CMD: AICHAT
    INFO: Have a Conversation with Gemini AI.
    USAGE:
        .aichat hello
        keep replying to AI responses
        After 5 mins of Idle bot will export history and stop chat.
        use .load_history to continue
    """
    if not await basic_check(message):
        return
    chat = TEXT_MODEL.start_chat(history=[])
    await do_convo(chat=chat, message=message)


@bot.add_cmd(cmd="load_history")
async def history_chat(bot: BOT, message: Message):
    """
    CMD: LOAD_HISTORY
    INFO: Load a Conversation with Gemini AI from previous session.
    USAGE:
        .load_history {question} [reply to history document]
    """
    if not await basic_check(message):
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
    chat = TEXT_MODEL.start_chat(history=history)
    await do_convo(chat=chat, message=message)


async def do_convo(chat, message: Message):
    prompt = message.input
    reply_to_message_id = message.id

    old_convo = CONVO_CACHE.get(message.unique_chat_user_id)

    if old_convo:
        Convo.CONVO_DICT[message.chat.id].remove(old_convo)

    convo_obj = Convo(
        client=message._client,
        chat_id=message.chat.id,
        filters=generate_filter(message),
        timeout=300,
        check_for_duplicates=False,
    )

    CONVO_CACHE[message.unique_chat_user_id] = convo_obj

    try:
        async with convo_obj:
            while True:
                ai_response = await chat.send_message_async(prompt)
                ai_response_text = get_response_text(ai_response)
                text = f"**GEMINI AI**:\n\n{ai_response_text}"
                _, prompt_message = await convo_obj.send_message(
                    text=text,
                    reply_to_message_id=reply_to_message_id,
                    parse_mode=ParseMode.MARKDOWN,
                    get_response=True,
                )
                prompt, reply_to_message_id = prompt_message.text, prompt_message.id
    except TimeoutError:
        await export_history(chat, message)

    CONVO_CACHE.pop(message.unique_chat_user_id, 0)


def generate_filter(message: Message):
    async def _filter(_, __, msg: Message):
        if (
            not msg.text
            or not msg.from_user
            or msg.from_user.id != message.from_user.id
            or not msg.reply_to_message
            or not msg.reply_to_message.from_user
            or msg.reply_to_message.from_user.id != message._client.me.id
        ):
            return False
        return True

    return filters.create(_filter)


async def export_history(chat, message: Message):
    doc = BytesIO(pickle.dumps(chat.history))
    doc.name = "AI_Chat_History.pkl"
    caption = get_response_text(
        await chat.send_message_async("Summarize our Conversation into one line.")
    )
    await bot.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
