from pyrogram.enums import ParseMode
from pyrogram.types import InputMediaAudio, InputMediaPhoto
from ub_core import BOT, Message, bot, utils

from app.plugins.ai.gemini import Response, async_client, get_model_config
from app.plugins.ai.gemini.code import upload_codebase
from app.plugins.ai.gemini.utils import create_prompts, run_basic_check


@bot.add_cmd(cmd="ai")
@run_basic_check
async def question(bot: BOT, message: Message):
    """
    CMD: AI
    INFO: Ask a question to Gemini AI or get info about replied message / media.
    FLAGS:
        -s: to use Search
        -i: to edit/generate images
        -a: to generate audio
            -m: male voice
            -f: female voice
        -sp: to create speech between two people
        -wc: uploads ub repo and core and extra modules [ if set ] to ai for context

    USAGE:
        .ai what is the meaning of life.
        .ai [reply to a message] (sends replied text as query)
        .ai [reply to message] [extra prompt relating to replied text]

        .ai [reply to image | video | gif]
        .ai [reply to image | video | gif] [custom prompt]

        .ai -a [-m|-f] <text to speak> (defaults to female voice)

        .ai -sp TTS the following conversation between Joe and Jane:
            Joe: How's it going today Jane?
            Jane: Not too bad, how about you?

        .ai -wc how does the -wc flag in .ai work, what are the potential usages?
    """

    reply = message.replied
    quoted_prompt = utils.wrap_in_block_quote(f"•> {message.filtered_input.strip()}", "**>", "<**")

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

    kwargs = get_model_config(flags=message.flags)

    if "-wc" in message.flags:
        prompts.append(await upload_codebase())

    response = await async_client.models.generate_content(contents=prompts, **kwargs)

    response = Response(response)

    if response.image:
        await message_response.edit_media(media=InputMediaPhoto(media=response.image_file, caption=quoted_prompt))
        return

    if response.audio:
        if isinstance(message, Message):
            await message.reply_voice(
                voice=response.audio_file,
                waveform=response.audio_file.waveform,
                duration=response.audio_file.duration,
                caption=quoted_prompt,
            )
        else:
            await message_response.edit_media(
                media=InputMediaAudio(
                    media=response.audio_file, caption=quoted_prompt, duration=response.audio_file.duration
                )
            )
        return

    await message_response.edit(
        text="\n".join((quoted_prompt, response.text_with_sources())),
        parse_mode=ParseMode.MARKDOWN,
        disable_preview=True,
    )
