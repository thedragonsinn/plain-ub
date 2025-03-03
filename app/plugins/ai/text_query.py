import pickle
from io import BytesIO

from google.genai.chats import AsyncChat
from pyrogram.enums import ParseMode

from app import BOT, Convo, Message, bot
from app.plugins.ai.media_query import handle_media
from app.plugins.ai.models import (
    Settings,
    async_client,
    get_response_text,
    run_basic_check,
)

CONVO_CACHE: dict[str, Convo] = {}


@bot.add_cmd(cmd="ai")
@run_basic_check
async def question(bot: BOT, message: Message):
    """
    CMD: AI
    INFO: Ask a question to Gemini AI or get info about replied message / media.
    FLAGS:
        -s: to use Search
    USAGE:
        .ai what is the meaning of life.
        .ai [reply to a message] (sends replied text as query)
        .ai [reply to message] [extra prompt relating to replied text]

        .ai [reply to image | video | gif]
        .ai [reply to image | video | gif] [custom prompt]
    """
    reply = message.replied
    prompt = message.filtered_input

    if reply and reply.media:
        message_response = await message.reply(
            "<code>Processing... this may take a while.</code>"
        )
        response_text = await handle_media(
            prompt=prompt,
            media_message=reply,
            **Settings.get_kwargs(use_search="-s" in message.flags),
        )
    else:
        message_response = await message.reply(
            "<code>Input received... generating response.</code>"
        )
        if reply and reply.text:
            prompts = [str(reply.text), message.input or "answer"]
        else:
            prompts = [message.input]

        response = await async_client.models.generate_content(
            contents=prompts,
            **Settings.get_kwargs(use_search="-s" in message.flags),
        )
        response_text = get_response_text(response, quoted=True)

    await message_response.edit(
        text=f"**>\n•> {prompt}<**\n{response_text}",
        parse_mode=ParseMode.MARKDOWN,
        disable_preview=True,
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
    chat = async_client.chats.create(**Settings.get_kwargs())
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

    if not message.input:
        await message.reply(f"Ask a question along with {message.trigger}{message.cmd}")
        return

    try:
        assert reply.document.file_name == "AI_Chat_History.pkl"
    except (AssertionError, AttributeError):
        await message.reply("Reply to a Valid History file.")
        return

    resp = await message.reply("`Loading History...`")
    doc = await reply.download(in_memory=True)
    doc.seek(0)

    history = pickle.load(doc)
    await resp.edit("__History Loaded... Resuming chat__")
    chat = async_client.chats.create(**Settings.get_kwargs(), history=history)
    await do_convo(chat=chat, message=message)


async def do_convo(chat: AsyncChat, message: Message):
    prompt = message.input
    reply_to_id = message.id
    chat_id = message.chat.id
    old_convo = CONVO_CACHE.get(message.unique_chat_user_id)

    if old_convo in Convo.CONVO_DICT[chat_id]:
        Convo.CONVO_DICT[chat_id].remove(old_convo)

    convo_obj = Convo(
        client=message._client,
        chat_id=chat_id,
        timeout=300,
        check_for_duplicates=False,
        from_user=message.from_user.id,
        reply_to_user_id=message._client.me.id,
    )

    CONVO_CACHE[message.unique_chat_user_id] = convo_obj

    try:
        async with convo_obj:
            while True:
                ai_response = await chat.send_message(prompt)
                ai_response_text = get_response_text(ai_response, quoted=True)
                text = f"**GEMINI AI**:{ai_response_text}"
                _, prompt_message = await convo_obj.send_message(
                    text=text,
                    reply_to_id=reply_to_id,
                    parse_mode=ParseMode.MARKDOWN,
                    get_response=True,
                    disable_preview=True,
                )
                prompt, reply_to_id = prompt_message.text, prompt_message.id

    except TimeoutError:
        await export_history(chat, message)

    CONVO_CACHE.pop(message.unique_chat_user_id, 0)


async def export_history(chat: AsyncChat, message: Message):
    doc = BytesIO(pickle.dumps(chat._curated_history))
    doc.name = "AI_Chat_History.pkl"
    caption = get_response_text(
        await chat.send_message("Summarize our Conversation into one line.")
    )
    await bot.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
