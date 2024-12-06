from pyrogram.enums import MessageMediaType
from ub_core import BOT, Message
from ub_core.utils import get_tg_media_details

MEDIA_TYPE_MAP: dict[MessageMediaType, str] = {
    MessageMediaType.PHOTO: "photo",
    MessageMediaType.VIDEO: "video",
    MessageMediaType.ANIMATION: "animation",
}


@BOT.add_cmd("spoiler")
async def mark_spoiler(bot: BOT, message: Message):
    """
    CMD: SPOILER
    INFO: Convert Non-Spoiler media to Spoiler
    USAGE: .spoiler [reply to a photo | video | animation]
    """
    reply_method_str = MEDIA_TYPE_MAP.get(message.media)

    if not message.media or message.document or not reply_method_str:
        await message.reply(text="Reply to a Photo | Video | Animation")
        return

    media = get_tg_media_details(message=message)

    kwargs = {reply_method_str: media.file_id, "has_spoiler": True}

    if message.media == MessageMediaType.ANIMATION and bot.is_user:
        kwargs["unsave"] = True

    reply_method = getattr(message, f"reply_{reply_method_str}")

    await reply_method(**kwargs)
