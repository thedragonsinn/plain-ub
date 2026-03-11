import asyncio
import re

from pyrogram import filters
from pyrogram.types import Chat, User
from ub_core.utils.helpers import get_name

from app import BOT, Config, CustomDB, Message, bot, extra_config

FBAN_TASK_LOCK = asyncio.Lock()

FED_DB = CustomDB["FED_LIST"]

BASIC_FILTER = filters.user([609517172, 2059887769, 1376954911, 885745757]) & ~filters.service

FBAN_REGEX = BASIC_FILTER & filters.regex(
    r"(New FedBan|"
    r"starting a federation ban|"
    r"start a federation ban|"
    r"FedBan Reason update|"
    r"FedBan reason updated|"
    r"Would you like to update this reason)",
    re.IGNORECASE,
)


UNFBAN_REGEX = BASIC_FILTER & filters.regex(r"(New un-FedBan|I'll give|Un-FedBan)", re.IGNORECASE)


@bot.add_cmd(cmd="addf")
async def add_fed(bot: BOT, message: Message):
    """
    CMD: ADDF
    INFO: Add a Fed Chat to DB.
    FLAGS:
        -n: number of bots to fban in
        -name: name to set in db
    USAGE:
        .addf
        .addf -n 3 -name NAME
        .addf -name NAME
    """
    data = dict(
        name=message.input or message.chat.title,
        type=str(message.chat.type),
        total_bots=1,
    )

    try:
        if "-n" in message.flags:
            data["total_bots"] = int(message.get_flag_value("-n"))
        if "-name" in message.flags:
            data["name"] = int(message.get_flag_value("-name"))
    except Exception as e:
        await message.reply(f"Invalid input: {e}")
        return

    text = (
        f"#FBANS"
        f"\n<b>{data['name']}</b>: <code>{message.chat.id}</code> added to FED LIST."
        f"\nTotal bots to wait for: {data['total_bots']}"
    )

    await asyncio.gather(
        FED_DB.add_data({"_id": message.chat.id, **data}),
        message.reply(text=text, del_in=5, block=True),
        bot.log_text(text=text, type="info"),
    )


@bot.add_cmd(cmd="delf")
async def remove_fed(bot: BOT, message: Message):
    """
    CMD: DELF
    INFO: Delete a Fed from DB.
    FLAGS: -all to delete all feds.
    USAGE:
        .delf | .delf id | .delf -all
    """
    if "-all" in message.flags:
        await FED_DB.drop()
        await message.reply("FED LIST cleared.")
        return

    chat: int | str | Chat = message.input or message.chat
    name = ""

    if isinstance(chat, Chat):
        name = f"Chat: {chat.title}\n"
        chat = chat.id
    elif chat.lstrip("-").isdigit():
        chat = int(chat)

    deleted: int = await FED_DB.delete_data(id=chat)

    if deleted:
        text = f"#FBANS\n<b>{name}</b><code>{chat}</code> removed from FED LIST."
        await message.reply(text=text, del_in=8)
        await bot.log_text(text=text, type="info")
    else:
        await message.reply(text=f"<b>{name or chat}</b> not in FED LIST.", del_in=8)


@bot.add_cmd(cmd="listf")
async def fed_list(bot: BOT, message: Message):
    """
    CMD: LISTF
    INFO: View Connected Feds.
    FLAGS:
        -id:
            to list Fed Chat IDs.
        -n:
            to list bot count
    USAGE: .listf | .listf -id
    """
    output_list: list[str] = []

    total = 0

    async for fed in FED_DB.find():
        output_list.append(f"<b>• {fed['name']}</b>")

        if "-id" in message.flags:
            output_list.append(f"  <code>{fed['_id']}</code>")

        if "-n" in message.flags:
            output_list.append(f"  <code>{fed['total_bots']} </code>")

        total += 1

    if not total:
        await message.reply("You don't have any Feds Connected.")
        return

    output_list.insert(0, f"List of <b>{total}</b> Connected Feds:\n\n")

    await message.reply("\n".join(output_list), del_in=30, block=True)


@bot.add_cmd(cmd=["fban", "fbanp"])
async def fed_ban(bot: BOT, message: Message):
    """
    CMD: FBAN / FBANP
    INFO:
        Initiates a fed-ban in fed-chats added in .addf
        If cmd is fbanp, it logs the replied message as proof for fban
        and appends the link in reason.
    FLAGS:
        -nrc: Don't do sudo fban
    USAGE:
        .fban(p) [uid | @ | reply to message] reason
    """
    progress: Message = await message.reply("❯")

    extracted_info = await get_user_reason(message=message, progress=progress)

    if not extracted_info:
        await progress.edit("Unable to extract user info.")
        return

    user_id, user_mention, reason = extracted_info

    if user_id in [Config.OWNER_ID, *Config.SUPERUSERS, *Config.SUDO_USERS]:
        await progress.edit("Cannot Fban Owner/Sudo users.")
        return

    proof_str: str = ""
    if message.cmd == "fbanp":
        if not message.replied:
            await progress.edit("Reply to a proof")
            return
        proof = await message.replied.forward(extra_config.FBAN_LOG_CHANNEL)
        proof_str = f"\n{ {proof.link} }"

    reason = f"{reason}{proof_str}"

    if message.replied and message.chat.admin_privileges and message.chat.admin_privileges.can_restrict_members:
        await message.replied.reply(text=f"!dban {reason}", disable_preview=True, del_in=3, block=False)
        bot_resp = await message.get_response(
            filters=BASIC_FILTER & filters.regex(r"anonymous|Banned", re.IGNORECASE), timeout=5
        )
        if bot_resp and "anonymous" in bot_resp.text.lower() and bot_resp.reply_markup:
            await bot_resp.click(0)

    fban_cmd: str = f"/fban <a href='tg://user?id={user_id}'>{user_id}</a> {reason}"

    await perform_fed_task(
        user_id=user_id,
        user_mention=user_mention,
        command=fban_cmd,
        task_filter=FBAN_REGEX,
        task_type="Fban",
        reason=reason,
        progress=progress,
        message=message,
    )


@bot.add_cmd(cmd="unfban")
async def un_fban(bot: BOT, message: Message):
    """
    CMD: UBFBAN
    INFO:
        Initiates a fed-unban in fed-chats added in .addf
    FLAGS:
        -nrc: Don't do sudo unfban
    USAGE:
        .unfban [uid | @ | reply to message] reason
    """
    progress: Message = await message.reply("❯")
    extracted_info = await get_user_reason(message=message, progress=progress)

    if not extracted_info:
        await progress.edit("Unable to extract user info.")
        return

    user_id, user_mention, reason = extracted_info
    unfban_cmd: str = f"/unfban <a href='tg://user?id={user_id}'>{user_id}</a> {reason}"

    await perform_fed_task(
        user_id=user_id,
        user_mention=user_mention,
        command=unfban_cmd,
        task_filter=UNFBAN_REGEX,
        task_type="Un-FBan",
        reason=reason,
        progress=progress,
        message=message,
    )


async def get_user_reason(message: Message, progress: Message) -> tuple[int, str, str] | None:
    user, reason = await message.extract_user_n_reason()
    if isinstance(user, str):
        await progress.edit(user)
        return
    if not isinstance(user, User):
        user_id = user
        user_mention = f"<a href='tg://user?id={user_id}'>{user_id}</a>"
    else:
        user_id = user.id
        user_mention = user.mention
    return user_id, user_mention, reason


async def perform_fed_task(*args, **kwargs):
    async with FBAN_TASK_LOCK:
        await _perform_fed_task(*args, **kwargs)


async def _perform_fed_task(
    user_id: int,
    user_mention: str,
    command: str,
    task_filter: filters.Filter,
    task_type: str,
    reason: str,
    progress: Message,
    message: Message,
):
    await progress.edit("❯❯")

    total: int = 0
    failed_bans: list[str] = []

    async for fed in FED_DB.find():
        chat_id = int(fed["_id"])
        total += 1
        fed_name = fed["name"]
        try:
            async with bot.Convo(client=bot, chat_id=chat_id, timeout=8, filters=task_filter) as convo:
                await convo.send_message(text=command, disable_preview=True)

                coroutines = (convo.get_response() for _ in range(0, fed.get("total_bots", 1)))

                bot_responses: tuple[Message | None] = await asyncio.gather(*coroutines, return_exceptions=True)

                for msg in bot_responses:
                    if isinstance(msg, Message):
                        if "Would you like to update this reason" in msg.text:
                            await msg.click("Update reason")

                        continue

                    if fed_name not in failed_bans:
                        failed_bans.append(fed_name)

        except Exception as e:
            await bot.log_text(
                text=f"An Error occurred while banning in fed: {fed_name} [{chat_id}]\nError: {e}",
                type=task_type.upper(),
            )
            failed_bans.append(fed_name)
            continue

        await asyncio.sleep(1)

    if not total:
        await progress.edit("You Don't have any feds connected!")
        return

    task_status = (
        f"❯❯❯ <b>{task_type}ned</b> {user_mention}"
        f"\n<b>ID</b>: {user_id}"
        f"\n<b>Reason</b>: {reason}"
        f"\n<b>Initiated in</b>: {message.chat.title or 'PM'}"
    )

    if failed_bans:
        task_status += f"\n<b>Failed</b in>: {len(failed_bans)} / {total}"
    else:
        task_status += f"\n<b>{task_type}ned</b in>: <b>{total}</b> feds"

    failed = ("\n• " + "\n• ".join(failed_bans)) if failed_bans else ""
    sudo = f"\n\n<b>By</b>: {get_name(message.from_user)}" if not message.is_from_owner else ""

    await bot.send_message(
        chat_id=extra_config.FBAN_LOG_CHANNEL,
        text=task_status + failed + sudo,
        disable_preview=True,
    )

    await progress.edit(text=task_status + sudo, del_in=5, block=True, disable_preview=True)

    if "-nrc" not in message.flags:
        await handle_sudo_fban(command=command)


async def handle_sudo_fban(command: str):
    sudo_acc = extra_config.FBAN_SUDO_ID or extra_config.FBAN_SUDO_USERNAME

    if not (sudo_acc and extra_config.FBAN_SUDO_TRIGGER):
        return

    sudo_cmd = command.replace("/", extra_config.FBAN_SUDO_TRIGGER, 1)
    head, body = sudo_cmd.split(" ", maxsplit=1)
    no_recurse_cmd = " ".join((head, "-nrc", body))
    await bot.send_message(chat_id=sudo_acc, text=no_recurse_cmd, disable_preview=True)
