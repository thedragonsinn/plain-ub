import asyncio

from pyrogram import filters
from pyrogram.enums import ChatType

from app import BOT, Config, CustomDB, Message, bot
from app.utils.helpers import get_name

PM_USERS = CustomDB("PM_USERS")

PM_GUARD = CustomDB("COMMON_SETTINGS")

ALLOWED_USERS: list[int] = []

allowed_filter = filters.create(lambda _, __, m: m.chat.id in ALLOWED_USERS)

guard_check = filters.create(lambda _, __, ___: Config.PM_GUARD)

RECENT_USERS: dict = {}


async def init_task():
    guard = await PM_GUARD.find_one({"_id": "guard_switch"})
    if not guard:
        return
    global ALLOWED_USERS
    ALLOWED_USERS = [user_id["_id"] async for user_id in PM_USERS.find()]
    Config.PM_GUARD = guard["value"]


@bot.on_message(
    (guard_check & filters.private & filters.incoming)
    & (~allowed_filter & ~filters.bot)
    & ~filters.chat(chats=[bot.me.id]),
    group=0,
)
async def handle_new_pm(bot: BOT, message: Message):
    user_id = message.from_user.id
    RECENT_USERS[user_id] = RECENT_USERS.get(user_id, 0)
    if RECENT_USERS[user_id] == 0:
        await bot.log_text(
            text=f"#PMGUARD\n{message.from_user.mention} [{user_id}] has messaged you.",
            type="info",
        )
    RECENT_USERS[user_id] += 1
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
)
async def auto_approve(bot: BOT, message: Message):
    message = Message.parse(message=message)
    await message.reply("Auto-Approved to PM.", del_in=5)
    ALLOWED_USERS.append(message.chat.id)
    await PM_USERS.insert_one({"_id": message.chat.id})


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
            text=f"PM Guard is enabled: <b>{Config.PM_GUARD}</b>", del_in=8
        )
        return
    value = not Config.PM_GUARD
    Config.PM_GUARD = value
    await asyncio.gather(
        PM_GUARD.add_data({"_id": "guard_switch", "value": value}),
        message.reply(text=f"PM Guard is enabled: <b>{value}</b>!", del_in=8),
    )
    await init_task()


@bot.add_cmd(cmd=["a", "allow"])
async def allow_pm(bot: BOT, message: Message):
    user_id, name = get_user_name(message)
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
    user_id, name = get_user_name(message)
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


def get_user_name(message: Message) -> tuple:
    if message.flt_input and message.flt_input.isdigit():
        user_id = int(message.flt_input)
        return user_id, user_id
    elif message.replied:
        return message.replied.from_user.id, get_name(message.replied.from_user)
    elif message.chat.type == ChatType.PRIVATE:
        return message.chat.id, get_name(message.chat)
    else:
        return 0, 0
