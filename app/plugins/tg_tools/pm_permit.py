import asyncio
from collections import defaultdict

from pyrogram import filters
from pyrogram.enums import ChatType
from ub_core.utils.helpers import get_name

from app import BOT, CustomDB, Message, bot, extra_config

PM_USERS = CustomDB["PM_USERS"]
SETTINGS = CustomDB["COMMON_SETTINGS"]

SETTING_KEY = "pm_permit_info"
OLD_KEY = "guard_switch"

ALLOWED_USERS: set[int] = set()
RECENT_MESSAGE_COUNT: dict = defaultdict(int)


async def init_task():
    await migrate_keys()
    guard = (await SETTINGS.find_one({"_id": SETTING_KEY})) or {}
    extra_config.PM_GUARD = guard.get("value", False)
    extra_config.PM_GUARD_TEXT = guard.get("warn_message", "You are not authorised to PM.")

    [ALLOWED_USERS.add(user_id["_id"]) async for user_id in PM_USERS.find()]


async def migrate_keys():
    guard = await SETTINGS.find_one({"_id": OLD_KEY})

    if not guard:
        return

    guard["_id"] = SETTING_KEY
    await SETTINGS.add_data(guard)
    await SETTINGS.delete_data({"_id": OLD_KEY})


async def pm_permit_filter(_, __, message: Message):
    # Return False if:
    if (
        # PM_GUARD is False
        not extra_config.PM_GUARD
        # Chat is not Private
        or message.chat.type != ChatType.PRIVATE
        # Chat is already approved
        or message.chat.id in ALLOWED_USERS
        # Saved Messages
        or message.chat.id == bot.me.id
        # PM is BOT
        or message.from_user.is_bot
        # Telegram Service Messages like OTPs.
        or message.from_user.is_support
        # Chat Service Messages like pinned a pic etc
        or message.service
    ):
        return False
    return True


PERMIT_FILTER = filters.create(pm_permit_filter)


@bot.on_message(PERMIT_FILTER & filters.incoming, group=0)
async def handle_new_pm(bot: BOT, message: Message):
    user_id = message.from_user.id
    if RECENT_MESSAGE_COUNT[user_id] == 0:
        await bot.log_text(
            text=f"#PMGUARD\n{message.from_user.mention} [{user_id}] has messaged you.",
            type="info",
        )
    RECENT_MESSAGE_COUNT[user_id] += 1

    if message.chat.is_support:
        return

    if RECENT_MESSAGE_COUNT[user_id] >= 5:
        await message.reply("You've been blocked for spamming.")
        await bot.block_user(user_id)
        RECENT_MESSAGE_COUNT.pop(user_id)
        await bot.log_text(
            text=f"#PMGUARD\n{message.from_user.mention} [{user_id}] has been blocked for spamming.",
            type="info",
        )
        return
    if RECENT_MESSAGE_COUNT[user_id] % 2:
        await message.reply(text=f"{extra_config.PM_GUARD_TEXT}")


@bot.on_message(PERMIT_FILTER & filters.outgoing, group=2)
async def auto_approve(bot: BOT, message: Message):
    message = Message(message=message)
    ALLOWED_USERS.add(message.chat.id)
    await asyncio.gather(
        PM_USERS.insert_one({"_id": message.chat.id}),
        message.reply(text="Auto-Approved to PM.", del_in=5),
    )


@bot.add_cmd(cmd="pmguard")
async def pm_guard(bot: BOT, message: Message):
    """
    CMD: PMGUARD
    INFO: Enable/Disable PM GUARD.
    FLAGS: -c to check guard status.
    USAGE:
        .pmguard | .pmguard -c
    """
    if "-c" in message.flags:
        await message.reply(text=f"PM Guard is enabled: <b>{extra_config.PM_GUARD}</b>", del_in=8)
        return

    value = not extra_config.PM_GUARD
    extra_config.PM_GUARD = value

    await asyncio.gather(
        SETTINGS.add_data({"_id": SETTING_KEY, "value": value}),
        message.reply(text=f"PM Guard is enabled: <b>{value}</b>!", del_in=8),
    )


@bot.add_cmd(cmd="pmsg")
async def pmsg(bot: BOT, message: Message):
    """
    CMD: PMSG
    INFO: Show/Change PM GUARD MESSAGE.
    USAGE:
        .pmsg | .pmsg New Message
    """
    warn_message = message.input.strip()

    if not warn_message:
        await message.reply(text=f"PM Guard text: <b>{extra_config.PM_GUARD_TEXT}</b>!", del_in=8)
        return

    extra_config.PM_GUARD_TEXT = warn_message

    await asyncio.gather(
        SETTINGS.add_data({"_id": SETTING_KEY, "warn_message": warn_message}),
        message.reply(text=f"PM Guard text: <b>{warn_message}</b>!", del_in=8),
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

    ALLOWED_USERS.add(user_id)
    RECENT_MESSAGE_COUNT.pop(user_id, 0)
    await asyncio.gather(
        message.reply(text=f"{name} allowed to PM.", del_in=8),
        PM_USERS.insert_one({"_id": user_id}),
    )


@bot.add_cmd(cmd="nopm")
async def no_pm(bot: BOT, message: Message):
    """
    CMD: NO PM
    INFO: Dis-Allow a user to PM.
    """
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
