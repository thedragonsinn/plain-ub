from pyrogram.enums import MessageMediaType
from ub_core import BOT, Message
from ub_core.utils import get_tg_media_details

MEDIA_TYPE_MAP: dict[MessageMediaType, str] = {
    MessageMediaType.PHOTO: "photo",
    MessageMediaType.VIDEO: "video",
}


@BOT.add_cmd("spoiler")
async def mark_spoiler(bot: BOT, message: Message):
    """
    CMD: SPOILER
    INFO: Convert Non-Spoiler media to Spoiler
    USAGE: .spoiler [reply to a photo | video]
    """
    reply_message = message.replied

    try:
        reply_method_str = MEDIA_TYPE_MAP.get(reply_message.media)
        assert reply_method_str and not reply_message.document

    except (AssertionError, AttributeError):
        await message.reply(text="Reply to a Photo | Video")
        return

    media = get_tg_media_details(message=reply_message)

    kwargs = {reply_method_str: media.file_id, "has_spoiler": True}

    reply_method = getattr(message, f"reply_{reply_method_str}")

    await reply_method(**kwargs)
