import asyncio
from datetime import UTC, datetime, timedelta

from pyrogram.types import User

from app import BOT, Message
from app.extra_config import ADMIN_STATUS


@BOT.add_cmd(cmd="kick")
async def kick_user(bot: BOT, message: Message):
    """
    CMD: KICK
    INFO: Kicks a person out of the chat.
    """
    user, reason = await message.extract_user_n_reason()
    if not isinstance(user, User):
        await message.reply(user, del_in=10)
        return

    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=user.id)
        await asyncio.sleep(2)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=user.id)
        await message.reply(text=f"{message.cmd.capitalize()}ed: {user.mention}\nReason: {reason}")
    except Exception as e:
        await message.reply(text=e, del_in=10)


@BOT.add_cmd(cmd="kick_im", allow_sudo=False)
async def kick_inactive_members(bot: BOT, message: Message):
    """
    CMD: KICK_IM
    INFO: Kick inactive members with message count less than 10
    """

    if not (message.chat.admin_privileges and message.chat.admin_privileges.can_restrict_members):
        await message.reply("Cannot kick members without being admin.")
        return

    count = 0
    chat_id = message.chat.id

    async with bot.Convo(client=bot, chat_id=chat_id, from_user=message.from_user.id) as convo:
        async for member in bot.get_chat_members(chat_id):
            if member.status in ADMIN_STATUS:
                continue

            user = member.user

            message_count = await bot.search_messages_count(chat_id=chat_id, from_user=user.id)
            if message_count >= 10:
                continue

            try:
                prompt = await convo.send_message(
                    text=f"Kick {user.mention} with total of {message_count} messages in chat?"
                    f"\nreply with y to continue"
                )

                convo.reply_to_message_id = prompt.id

                text, _ = await convo.get_quote_or_text(lower=True)

                if text == "y":
                    await bot.ban_chat_member(
                        chat_id=chat_id,
                        user_id=user.id,
                        until_date=datetime.now(UTC) + timedelta(seconds=60),
                    )
                    await prompt.edit(f"Kicked {user.mention}")
                    count += 1

                else:
                    await prompt.edit("Aborted, continuing onto next the member.")

            except TimeoutError:
                pass

    await message.reply(f"Kicked {count} inactive members.")
