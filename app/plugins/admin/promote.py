import asyncio

from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
from pyrogram.errors import FloodWait
from pyrogram.types import ChatPrivileges, User

from app import BOT, Message

DEMOTE_PRIVILEGES = ChatPrivileges(can_manage_chat=False)

NO_PRIVILEGES = ChatPrivileges(
    can_manage_chat=True,
    can_manage_video_chats=False,
    can_pin_messages=False,
    can_delete_messages=False,
    can_change_info=False,
    can_restrict_members=False,
    can_invite_users=False,
    can_promote_members=False,
    is_anonymous=False,
)


@BOT.add_cmd(cmd=["promote", "demote"])
async def promote_or_demote(bot: BOT, message: Message) -> None:
    """
    CMD: PROMOTE | DEMOTE
    INFO: Add/Remove an Admin.
    FLAGS:
        PROMOTE: -full for full rights, -anon for anon admin
    USAGE:
        PROMOTE: .promote [ -anon | -full ] [ UID | REPLY | @ ] Title[Optional]
        DEMOTE: .demote [ UID | REPLY | @ ]
    """
    response: Message = await message.reply(
        f"Trying to {message.cmd.capitalize()}....."
    )

    my_status = await bot.get_chat_member(chat_id=message.chat.id, user_id=bot.me.id)
    my_privileges = my_status.privileges

    if not (
        my_status.status in {ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR}
        and my_privileges.can_promote_members
    ):
        await response.edit("You don't to have enough rights to do this.")
        return

    user, title = await message.extract_user_n_reason()

    if not isinstance(user, User):
        await response.edit(user, del_in=10)
        return

    my_privileges.can_promote_members = "-full" in message.flags
    my_privileges.is_anonymous = "-anon" in message.flags

    promote = message.cmd == "promote"

    if promote:
        final_privileges = NO_PRIVILEGES if "-wr" in message.flags else my_privileges
    else:
        final_privileges = DEMOTE_PRIVILEGES

    response_text = f"{message.cmd.capitalize()}d: {user.mention}"

    try:
        await bot.promote_chat_member(
            chat_id=message.chat.id, user_id=user.id, privileges=final_privileges
        )

        if promote:
            await asyncio.sleep(1)
            await bot.set_administrator_title(
                chat_id=message.chat.id, user_id=user.id, title=title or "Admin"
            )

            if title:
                response_text += f"\nTitle: {title}"
            if "-wr" in message.flags:
                response_text += "\nWithout Rights: True"

        await response.edit(text=response_text)
    except Exception as e:
        await response.edit(text=e, del_in=10, block=True)


@BOT.add_cmd(cmd="demote_all", allow_sudo=False)
async def demote_all(bot: BOT, message: Message):
    me = await bot.get_chat_member(message.chat.id, bot.me.id)
    if me.status != ChatMemberStatus.OWNER:
        await message.reply("Cannot Demote all without being Chat Owner.")
        return

    resp = await message.reply("Hang on demoting all Admins...")
    count = 0

    async for member in bot.get_chat_members(
        chat_id=message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS
    ):
        try:
            await bot.promote_chat_member(
                chat_id=message.chat.id,
                user_id=member.user.id,
                privileges=DEMOTE_PRIVILEGES,
            )
        except FloodWait as f:
            await asyncio.sleep(f.value + 10)
            await bot.promote_chat_member(
                chat_id=message.chat.id,
                user_id=member.user.id,
                privileges=DEMOTE_PRIVILEGES,
            )
        await asyncio.sleep(0.5)
        count += 1

    await resp.edit(f"Demoted <b>{count}</b> admins in {message.chat.title}.")
    await resp.log()
