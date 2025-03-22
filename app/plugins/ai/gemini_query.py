import pickle
from io import BytesIO

from google.genai.chats import AsyncChat
from pyrogram.enums import ChatType, ParseMode
from pyrogram.types import InputMediaPhoto

from app import BOT, Convo, Message, bot
from app.plugins.ai.gemini_core import (
    Settings,
    async_client,
    create_prompts,
    get_response_content,
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
        -i: to edit/generate images
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
        resp_str = "<code>Processing... this may take a while.</code>"
    else:
        resp_str = "<code>Input received... generating response.</code>"

    message_response = await message.reply(resp_str)

    try:
        prompts = await create_prompts(message=message)
    except AssertionError as e:
        await message_response.edit(e)
        return

    kwargs = Settings.get_kwargs(use_search="-s" in message.flags, image_mode="-i" in message.flags)

    response = await async_client.models.generate_content(contents=prompts, **kwargs)

    response_text, response_image = get_response_content(response, quoted=True)

    if response_image:
        await message_response.edit_media(
            media=InputMediaPhoto(media=response_image, caption=f"**>\n•> {prompt}<**")
        )
        if response_text and isinstance(message, Message):
            await message_response.reply(response_text)
    else:
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
        "-i": use image gen/edit mode
    USAGE:
        .aic hello
        keep replying to AI responses with text | media [no need to reply in DM]
        After 5 mins of Idle bot will export history and stop chat.
        use .load_history to continue

    """
    chat = async_client.chats.create(
        **Settings.get_kwargs(use_search="-s" in message.flags, image_mode="-i" in message.flags)
    )
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
    pickle.load(doc)

    await resp.edit("__History Loaded... Resuming chat__")

    chat = async_client.chats.create(
        **Settings.get_kwargs(use_search="-s" in message.flags, image_mode="-i" in message.flags)
    )
    await do_convo(chat=chat, message=message, is_reloaded=True)


CONVO_CACHE: dict[str, Convo] = {}


async def do_convo(chat: AsyncChat, message: Message, is_reloaded: bool = False):
    chat_id = message.chat.id

    old_conversation = CONVO_CACHE.get(message.unique_chat_user_id)

    if old_conversation in Convo.CONVO_DICT[chat_id]:
        Convo.CONVO_DICT[chat_id].remove(old_conversation)

    if message.chat.type in (ChatType.PRIVATE, ChatType.BOT):
        reply_to_user_id = None
    else:
        reply_to_user_id = message._client.me.id

    conversation_object = Convo(
        client=message._client,
        chat_id=chat_id,
        timeout=300,
        check_for_duplicates=False,
        from_user=message.from_user.id,
        reply_to_user_id=reply_to_user_id,
    )

    CONVO_CACHE[message.unique_chat_user_id] = conversation_object

    try:
        async with conversation_object:
            prompt = await create_prompts(message, is_chat=is_reloaded)
            reply_to_id = message.id

            while True:
                ai_response = await chat.send_message(prompt)
                response_text, response_image = get_response_content(ai_response, quoted=True)
                prompt_message = await send_and_get_resp(
                    convo_obj=conversation_object,
                    response_text=response_text,
                    response_image=response_image,
                    reply_to_id=reply_to_id,
                )

                try:
                    prompt = await create_prompts(prompt_message, is_chat=True, check_size=False)
                except Exception as e:
                    prompt_message = await send_and_get_resp(
                        conversation_object, str(e), reply_to_id=reply_to_id
                    )
                    prompt = await create_prompts(prompt_message, is_chat=True, check_size=False)

                reply_to_id = prompt_message.id

    except TimeoutError:
        await export_history(chat, message)
    finally:
        CONVO_CACHE.pop(message.unique_chat_user_id, 0)


async def send_and_get_resp(
    convo_obj: Convo,
    response_text: str | None = None,
    response_image: BytesIO | None = None,
    reply_to_id: int | None = None,
) -> Message:

    if response_image:
        await convo_obj.send_photo(photo=response_image, reply_to_id=reply_to_id)

    if response_text:
        await convo_obj.send_message(
            text=f"**>\n•><**\n{response_text}",
            reply_to_id=reply_to_id,
            parse_mode=ParseMode.MARKDOWN,
            disable_preview=True,
        )
    return await convo_obj.get_response()


async def export_history(chat: AsyncChat, message: Message):
    doc = BytesIO(pickle.dumps(chat._curated_history))
    doc.name = "AI_Chat_History.pkl"
    caption, _ = get_response_content(
        await chat.send_message("Summarize our Conversation into one line.")
    )
    await bot.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
