import pickle
from io import BytesIO

from google.genai.chats import AsyncChat
from pyrogram.enums import ChatType, ParseMode

from app import BOT, Convo, Message, bot
from app.plugins.ai.gemini_core import (
    Settings,
    async_client,
    create_prompts,
    get_response_text,
    run_basic_check,
)


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
        message_response = await message.reply("<code>Processing... this may take a while.</code>")
    else:
        message_response = await message.reply(
            "<code>Input received... generating response.</code>"
        )

    try:
        prompts = await create_prompts(message=message)
    except AssertionError as e:
        await message_response.edit(e)
        return

    response = await async_client.models.generate_content(
        contents=prompts, **Settings.get_kwargs(use_search="-s" in message.flags)
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
    FLAGS:
        "-s": use search

    USAGE:
        .aic hello
        keep replying to AI responses with text | media [no need to reply in DM]
        After 5 mins of Idle bot will export history and stop chat.
        use .load_history to continue

    """
    chat = async_client.chats.create(**Settings.get_kwargs("-s" in message.flags))
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
    chat = async_client.chats.create(
        **Settings.get_kwargs(use_search="-s" in message.flags), history=history
    )
    await do_convo(chat=chat, message=message)


CONVO_CACHE: dict[str, Convo] = {}


async def do_convo(chat: AsyncChat, message: Message):
    chat_id = message.chat.id
    old_convo = CONVO_CACHE.get(message.unique_chat_user_id)

    if old_convo in Convo.CONVO_DICT[chat_id]:
        Convo.CONVO_DICT[chat_id].remove(old_convo)

    if message.chat.type in (ChatType.PRIVATE, ChatType.BOT):
        reply_to_user_id = None
    else:
        reply_to_user_id = message._client.me.id

    convo_obj = Convo(
        client=message._client,
        chat_id=chat_id,
        timeout=300,
        check_for_duplicates=False,
        from_user=message.from_user.id,
        reply_to_user_id=reply_to_user_id,
    )

    CONVO_CACHE[message.unique_chat_user_id] = convo_obj

    try:
        async with convo_obj:
            prompt = [message.input]
            reply_to_id = message.id
            while True:
                ai_response = await chat.send_message(prompt)
                ai_response_text = get_response_text(ai_response, add_sources=True, quoted=True)

                _, prompt_message = await convo_obj.send_message(
                    text=f"**>\n•><**\n{ai_response_text}",
                    reply_to_id=reply_to_id,
                    parse_mode=ParseMode.MARKDOWN,
                    get_response=True,
                    disable_preview=True,
                )

                try:
                    prompt = await create_prompts(
                        message=prompt_message, is_chat=True, check_size=False
                    )
                except Exception as e:
                    _, prompt_message = await convo_obj.send_message(
                        text=str(e),
                        reply_to_id=reply_to_id,
                        parse_mode=ParseMode.MARKDOWN,
                        get_response=True,
                        disable_preview=True,
                    )
                    prompt = await create_prompts(
                        message=prompt_message, is_chat=True, check_size=False
                    )

                reply_to_id = prompt_message.id

    finally:
        await export_history(chat, message)
        CONVO_CACHE.pop(message.unique_chat_user_id, 0)


async def export_history(chat: AsyncChat, message: Message):
    doc = BytesIO(pickle.dumps(chat._curated_history))
    doc.name = "AI_Chat_History.pkl"
    caption = get_response_text(
        await chat.send_message("Summarize our Conversation into one line.")
    )
    await bot.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
