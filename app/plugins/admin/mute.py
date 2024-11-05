from pyrogram.types import ChatPermissions, User

from app import BOT, Message


@BOT.add_cmd(cmd="mute")
async def mute_or_unmute(bot: BOT, message: Message):
    user, reason = await message.extract_user_n_reason()

    if not isinstance(user, User):
        await message.reply(user, del_in=10)
        return

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=ChatPermissions(
                can_send_messages=False,
                can_pin_messages=False,
                can_invite_users=False,
                can_change_info=False,
                can_send_media_messages=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
            ),
        )
        await message.reply(
            text=f"{message.cmd.capitalize()}d: {user.mention}\nReason: {reason}"
        )
    except Exception as e:
        await message.reply(text=e, del_in=10)
