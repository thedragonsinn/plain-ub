import pickle
from io import BytesIO

from pyrogram import filters
from pyrogram.enums import ParseMode

from app import BOT, Convo, Message, bot
from app.plugins.ai.models import MODEL, get_response_text, run_basic_check

CONVO_CACHE: dict[str, Convo] = {}


@bot.add_cmd(cmd="ai")
@run_basic_check
async def question(bot: BOT, message: Message):
    """
    CMD: AI
    INFO: Ask a question to Gemini AI.
    USAGE: .ai what is the meaning of life.
    """
    reply = message.replied
    reply_text = reply.text if reply else ""
    prompt = f"{reply_text}\n\n\n{message.input}".strip()

    response = await MODEL.generate_content_async(prompt)
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
            reply_to_id=message.reply_id or message.id,
        )


@bot.add_cmd(cmd="aic")
@run_basic_check
async def ai_chat(bot: BOT, message: Message):
    """
    CMD: AICHAT
    INFO: Have a Conversation with Gemini AI.
    USAGE:
        .aic hello
        keep replying to AI responses
        After 5 mins of Idle bot will export history and stop chat.
        use .load_history to continue
    """
    chat = MODEL.start_chat(history=[])
    await do_convo(chat=chat, message=message)


@bot.add_cmd(cmd="lh")
@run_basic_check
async def history_chat(bot: BOT, message: Message):
    """
    CMD: LOAD_HISTORY
    INFO: Load a Conversation with Gemini AI from previous session.
    USAGE:
        .lh {question} [reply to history document]
    """
    reply = message.replied

    try:
        assert reply.document.file_name == "AI_Chat_History.pkl"
    except (AssertionError, AttributeError):
        await message.reply("Reply to a Valid History file.")
        return

    resp = await message.reply("<i>Loading History...</i>")
    doc = await reply.download(in_memory=True)
    doc.seek(0)

    history = pickle.load(doc)
    await resp.edit("<i>History Loaded... Resuming chat</i>")
    chat = MODEL.start_chat(history=history)
    await do_convo(chat=chat, message=message)


async def do_convo(chat, message: Message):
    prompt = message.input
    reply_to_id = message.id
    chat_id = message.chat.id
    old_convo = CONVO_CACHE.get(message.unique_chat_user_id)

    if old_convo in Convo.CONVO_DICT[chat_id]:
        Convo.CONVO_DICT[chat_id].remove(old_convo)

    convo_obj = Convo(
        client=message._client,
        chat_id=chat_id,
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
                    reply_to_id=reply_to_id,
                    parse_mode=ParseMode.MARKDOWN,
                    get_response=True,
                )
                prompt, reply_to_id = prompt_message.text, prompt_message.id

    except TimeoutError:
        await export_history(chat, message)

    CONVO_CACHE.pop(message.unique_chat_user_id, 0)


def generate_filter(message: Message):
    async def _filter(_, __, msg: Message):
        try:
            assert (
                msg.text
                and msg.from_user.id == message.from_user.id
                and msg.reply_to_message.from_user.id == message._client.me.id
            )
            return True
        except (AssertionError, AttributeError):
            return False

    return filters.create(_filter)


async def export_history(chat, message: Message):
    doc = BytesIO(pickle.dumps(chat.history))
    doc.name = "AI_Chat_History.pkl"
    caption = get_response_text(
        await chat.send_message_async("Summarize our Conversation into one line.")
    )
    await bot.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
