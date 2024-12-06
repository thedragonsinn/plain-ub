from ub_core import BOT, Message

LEECH_TYPE_MAP: dict[str, str] = {
    "-p": "photo",
    "-a": "audio",
    "-v": "video",
    "-g": "animation",
    "-d": "document",
}


@BOT.add_cmd("l")
async def leech_urls_to_tg(bot: BOT, message: Message):
    """
    CMD: L (leech)
    INFO: Instantly Upload Media to TG from Links without Downloading.
    FLAGS:
        -p: photo
        -a: audio
        -v: video
        -g: gif
        -d: document

        -s: to leech with spoiler

    USAGE:
        .l { flag } link | file_id
        .l { flag } -s link | file_id
    """

    try:
        method_str = LEECH_TYPE_MAP.get(message.flags[0])

        assert method_str and message.filtered_input

        reply_method = getattr(message, f"reply_{method_str}")

        kwargs = {method_str: message.filtered_input}

        if "-s" in message.flags:
            kwargs["has_spoiler"] = True

        if "-g" in message.flags and bot.is_user:
            kwargs["unsave"] = True

        await reply_method(**kwargs)

    except (IndexError, AssertionError):
        await message.reply("Invalid Input.\nCheck Help!")
        return

    except Exception as exc:
        await message.reply(exc)
        return
