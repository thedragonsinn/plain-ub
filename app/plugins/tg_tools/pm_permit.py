import asyncio
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatType
from ub_core.utils.helpers import get_name

from app import BOT, CustomDB, Message, bot, extra_config

PM_USERS = CustomDB("PM_USERS")

PM_GUARD = CustomDB("COMMON_SETTINGS")

ALLOWED_USERS: list[int] = []

allowed_filter = filters.create(lambda _, __, m: m.chat.id in ALLOWED_USERS)

guard_check = filters.create(lambda _, __, ___: extra_config.PM_GUARD)

RECENT_USERS: dict = defaultdict(int)


async def init_task():
    guard = (await PM_GUARD.find_one({"_id": "guard_switch"})) or {}
    extra_config.PM_GUARD = guard.get("value", False)
    [ALLOWED_USERS.append(user_id["_id"]) async for user_id in PM_USERS.find()]


@bot.on_message(
    (guard_check & filters.private & filters.incoming)
    & (~allowed_filter & ~filters.bot)
    & ~filters.chat(chats=[bot.me.id])
    & ~filters.service,
    group=0,
    is_command=False,
)
async def handle_new_pm(bot: BOT, message: Message):
    user_id = message.from_user.id
    if RECENT_USERS[user_id] == 0:
        await bot.log_text(
            text=f"#PMGUARD\n{message.from_user.mention} [{user_id}] has messaged you.",
            type="info",
        )
    RECENT_USERS[user_id] += 1

    if message.chat.is_support:
        return

    if RECENT_USERS[user_id] >= 5:
        await message.reply("You've been blocked for spamming.")
        await bot.block_user(user_id)
        RECENT_USERS.pop(user_id)
        await bot.log_text(
            text=f"#PMGUARD\n{message.from_user.mention} [{user_id}] has been blocked for spamming.",
            type="info",
        )
        return
    if RECENT_USERS[user_id] % 2:
        await message.reply(
            "You are not authorised to PM.\nWait until you get authorised."
        )


@bot.on_message(
    (guard_check & filters.private & filters.outgoing)
    & (~allowed_filter & ~filters.bot)
    & ~filters.chat(chats=[bot.me.id]),
    group=2,
    is_command=False,
)
async def auto_approve(bot: BOT, message: Message):
    message = Message.parse(message=message)
    ALLOWED_USERS.append(message.chat.id)
    await asyncio.gather(
        PM_USERS.insert_one({"_id": message.chat.id}),
        message.reply("Auto-Approved to PM.", del_in=5),
    )


@bot.add_cmd(cmd="pmguard")
async def pmguard(bot: BOT, message: Message):
    """
    CMD: PMGUARD
    INFO: Enable/Disable PM GUARD.
    FLAGS: -c to check guard status.
    USAGE:
        .pmguard | .pmguard -c
    """
    if "-c" in message.flags:
        await message.reply(
            text=f"PM Guard is enabled: <b>{extra_config.PM_GUARD}</b>", del_in=8
        )
        return
    value = not extra_config.PM_GUARD
    extra_config.PM_GUARD = value
    await asyncio.gather(
        PM_GUARD.add_data({"_id": "guard_switch", "value": value}),
        message.reply(text=f"PM Guard is enabled: <b>{value}</b>!", del_in=8),
    )


@bot.add_cmd(cmd=["a", "allow"])
async def allow_pm(bot: BOT, message: Message):
    """
    CMD: A | ALLOW
    INFO: Approve a User to PM.
    USAGE: .a|.allow [reply to a user or in pm]
    """
    user_id, name = get_userID_name(message)
    if not user_id:
        await message.reply(
            "Unable to extract User to allow.\n<code>Give user id | Reply to a user | use in PM.</code>"
        )
        return
    if user_id in ALLOWED_USERS:
        await message.reply(f"{name} is already approved.")
        return
    ALLOWED_USERS.append(user_id)
    RECENT_USERS.pop(user_id, 0)
    await asyncio.gather(
        message.reply(text=f"{name} allowed to PM.", del_in=8),
        PM_USERS.insert_one({"_id": user_id}),
    )


@bot.add_cmd(cmd="nopm")
async def no_pm(bot: BOT, message: Message):
    user_id, name = get_userID_name(message)
    if not user_id:
        await message.reply(
            "Unable to extract User to Dis-allow.\n<code>Give user id | Reply to a user | use in PM.</code>"
        )
        return
    if user_id not in ALLOWED_USERS:
        await message.reply(f"{name} is not approved to PM.")
        return
    ALLOWED_USERS.remove(user_id)
    await asyncio.gather(
        message.reply(text=f"{name} Dis-allowed to PM.", del_in=8),
        PM_USERS.delete_data(user_id),
    )


def get_userID_name(message: Message) -> tuple:
    if message.filtered_input and message.filtered_input.isdigit():
        user_id = int(message.filtered_input)
        return user_id, user_id
    elif message.replied:
        return message.replied.from_user.id, get_name(message.replied.from_user)
    elif message.chat.type == ChatType.PRIVATE:
        return message.chat.id, get_name(message.chat)
    else:
        return 0, 0
