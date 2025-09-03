import pickle
from io import BytesIO

from google.genai.chats import AsyncChat
from pyrogram.enums import ChatType, ParseMode

from app import BOT, Convo, Message, bot
from app.plugins.ai.gemini import AIConfig, Response, async_client
from app.plugins.ai.gemini.utils import create_prompts, run_basic_check


@bot.add_cmd(cmd="aic")
@run_basic_check
async def ai_chat(bot: BOT, message: Message):
    """
    CMD: AICHAT
    INFO: Have a Conversation with Gemini AI.
    FLAGS:
        "-s": use search
        "-i": use image gen/edit mode
        -a: audio output
        -sp: multi speaker output
    USAGE:
        .aic hello
        keep replying to AI responses with text | media [no need to reply in DM]
        After 5 mins of Idle bot will export history and stop chat.
        use .load_history to continue

    """
    chat = async_client.chats.create(**AIConfig.get_kwargs(message.flags))
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

    chat = async_client.chats.create(**AIConfig.get_kwargs(message.flags))
    await do_convo(chat=chat, message=message)


CONVO_CACHE: dict[str, Convo] = {}


async def do_convo(chat: AsyncChat, message: Message):
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
            prompt = await create_prompts(message)
            reply_to_id = message.id

            while True:
                ai_response = await chat.send_message(prompt)
                prompt_message = await send_and_get_resp(
                    convo_obj=conversation_object,
                    response=ai_response,
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
    response,
    reply_to_id: int | None = None,
) -> Message:
    response = Response(response)

    if text := response.text():
        await convo_obj.send_message(
            text=f"**>\n•><**\n{text}",
            reply_to_id=reply_to_id,
            parse_mode=ParseMode.MARKDOWN,
            disable_preview=True,
        )

    if response.image:
        await convo_obj.send_photo(photo=response.image_file, reply_to_id=reply_to_id)

    if response.audio:
        await convo_obj.send_voice(
            voice=response.audio_file,
            waveform=response.audio_file.waveform,
            reply_to_id=reply_to_id,
            duration=response.audio_file.duration,
        )

    return await convo_obj.get_response()


async def export_history(chat: AsyncChat, message: Message):
    doc = BytesIO(pickle.dumps(chat._curated_history))
    doc.name = "AI_Chat_History.pkl"
    caption = Response(await chat.send_message("Summarize our Conversation into one line.")).text()
    await bot.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
