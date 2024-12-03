import asyncio
from datetime import UTC, datetime, timedelta

from pyrogram import filters
from pyrogram.types import User

from app import BOT, Message

from .zombies import ADMIN_STATUS


@BOT.add_cmd(cmd="kick")
async def kick_user(bot: BOT, message: Message):
    user, reason = await message.extract_user_n_reason()
    if not isinstance(user, User):
        await message.reply(user, del_in=10)
        return

    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=user.id)
        await asyncio.sleep(2)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=user.id)
        await message.reply(
            text=f"{message.cmd.capitalize()}ed: {user.mention}\nReason: {reason}"
        )
    except Exception as e:
        await message.reply(text=e, del_in=10)


@BOT.add_cmd(cmd="kick_im", allow_sudo=False)
async def kick_inactive_members(bot: BOT, message: Message):
    """
    CMD: KICK_IM
    INFO: Kick inactive members with message count less than 10
    """

    me = await bot.get_chat_member(message.chat.id, bot.me.id)
    if me.status not in ADMIN_STATUS:
        await message.reply("Cannot kick members without being admin.")
        return

    count = 0
    chat_id = message.chat.id

    async with bot.Convo(
        client=bot,
        chat_id=chat_id,
    ) as convo:
        async for member in bot.get_chat_members(chat_id):

            if member.status in ADMIN_STATUS:
                continue

            user = member.user

            message_count = await bot.search_messages_count(
                chat_id=chat_id, from_user=user.id
            )
            if message_count >= 10:
                continue

            try:
                prompt = await convo.send_message(
                    text=f"Kick {user.mention} with total of {message_count} messages in chat?"
                    f"\nreply with y to continue"
                )

                async def user_filter(_, __, m: Message):
                    return (
                        m.from_user
                        and m.from_user.id == message.from_user.id
                        and m.reply_to_message_id == prompt.id
                    )

                convo.filters = filters.create(user_filter)

                confirmation = await convo.get_response()

                if confirmation.text == "y":
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
