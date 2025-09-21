from asyncio import sleep

from pyrogram import raw, types, utils
from ub_core import BOT, Message, bot


async def get_folder() -> raw.types.DialogFilter | int:
    dialog_filters: raw.types.messages.DialogFilters = await bot.invoke(
        raw.functions.messages.GetDialogFilters()
    )
    folder_ids = set()

    for filter in dialog_filters.filters:
        if not isinstance(filter, raw.types.DialogFilter | raw.types.DialogFilterChatlist):
            continue
        if filter.title.text == "Admin":
            return filter
        folder_ids.add(filter.id)

    for i in range(2, 256):
        if i not in folder_ids:
            folder_id = i
            break
    else:
        raise ValueError("No Folder ID available.")

    return folder_id


async def update_folder(
    folder_id,
    included_peers: list = None,
    excluded_peers: list = None,
    pinned_peers: list = None,
    folder=None,
) -> bool:
    filter = folder or raw.types.DialogFilter(
        id=folder_id,
        title=raw.types.TextWithEntities(text="Admin", entities=[]),
        pinned_peers=[] if pinned_peers is None else pinned_peers,
        include_peers=[] if included_peers is None else included_peers,
        exclude_peers=[] if excluded_peers is None else excluded_peers,
    )
    return await bot.invoke(
        raw.functions.messages.UpdateDialogFilter(
            id=folder_id,
            filter=filter,
        )
    )


async def get_dialogs():
    current = 0
    total = (1 << 31) - 1
    request_limit = min(100, total)

    offset_date = 0
    offset_id = 0
    offset_peer = raw.types.InputPeerEmpty()

    seen_dialog_ids = set()

    while True:
        r = await bot.invoke(
            raw.functions.messages.GetDialogs(
                offset_date=offset_date,
                offset_id=offset_id,
                offset_peer=offset_peer,
                limit=request_limit,
                hash=0,
                exclude_pinned=False,
                folder_id=0,
            ),
            sleep_threshold=60,
        )

        users = {i.id: i for i in r.users}
        chats = {i.id: i for i in r.chats}

        messages = {}

        for message in r.messages:
            if isinstance(message, raw.types.MessageEmpty):
                continue
            chat_id = utils.get_peer_id(message.peer_id)
            messages[chat_id] = message

        dialogs = []

        for dialog in r.dialogs:
            if not isinstance(dialog, raw.types.Dialog):
                continue

            parsed = types.Dialog._parse(bot, dialog, messages, users, chats)

            if parsed is None:
                continue

            if parsed.chat is None:
                continue

            if parsed.chat.id in seen_dialog_ids:
                continue

            seen_dialog_ids.add(parsed.chat.id)
            dialogs.append(parsed)

        if not dialogs:
            return

        last = dialogs[-1]

        if last.top_message is None:
            return

        offset_id = last.top_message.id
        offset_date = last.top_message.date
        offset_peer = await bot.resolve_peer(last.chat.id)

        for dialog in dialogs:
            await sleep(0)
            yield dialog
            current += 1
            if current >= total:
                return


def create_link(d: types.Dialog) -> str:
    link_chunks = ["https://t.me"]
    if d.chat.username:
        link_chunks.append(d.chat.username)
    else:
        link_chunks.append(f"c/{d.chat._raw.id}")
        if d.top_message.reply_to:
            link_chunks.append(str(d.top_message.reply_to.reply_to_msg_id))
        link_chunks.append(str(d.top_message.id or -1))
    return "/".join(link_chunks)


@BOT.add_cmd("caf")
async def create_admin_folder(bot: BOT, message: Message):
    """
    CMD: Create Admin Folder
    INFO: Creates a folder containing admin chats/channels
    FLAGS:
        -y: Automatically confirm adding chat to folder.
    USAGE:
        .caf
        .caf -y
    """
    resp = await message.reply("`Initiating...`")
    cleanup_ids: set[int] = {resp.id}

    folder = await get_folder()
    included_peers = []
    excluded_peers = []
    pinned_peers = []

    if isinstance(folder, raw.types.DialogFilter):
        included_peers.extend(folder.include_peers)
        excluded_peers.extend(folder.exclude_peers)
        pinned_peers.extend(pinned_peers)
        folder_id = folder.id
    else:
        folder_id = folder

    existing_hashes = {x.access_hash for x in [*included_peers, *excluded_peers, *pinned_peers]}

    await resp.edit("`Fetching Admin Chats and Channels...`")
    new = 0
    async with bot.Convo(
        chat_id=message.chat.id, client=bot, from_user=message.from_user.id
    ) as convo:
        async for d in get_dialogs():
            if not d.chat.admin_privileges or d.chat._raw.access_hash in existing_hashes:
                continue

            if "-y" not in message.flags:
                await sleep(1)
                prompt = await convo.send_message(
                    text=f"Add <a href='{create_link(d)}'>{d.chat.title}</a> to admin folder?\nReply: `[y, n]`"
                )
                cleanup_ids.add(prompt.id)
                try:
                    confirmation, _ = await convo.get_quote_or_text(lower=True)
                except TimeoutError:
                    confirmation = None

                if confirmation != "y":
                    await prompt.edit(text=prompt.text + "\n\n**Aborted.. continuing**")
                    await sleep(2)
                    continue

            included_peers.append(await bot.resolve_peer(d.chat.id))
            new += 1

    success = await update_folder(folder_id, included_peers, excluded_peers, pinned_peers)
    resp_text = (
        f"<pre language=java>Admin folder created/updated: {success}"
        f"\nIncluded: {len(included_peers)} | Excluded: {len(excluded_peers)} | Pinned: {len(pinned_peers)} | New: {new}</pre>"
    )
    await message.reply(resp_text)
    await bot.log_text(text=resp_text, type="info")
    await bot.delete_messages(chat_id=message.chat.id, message_ids=cleanup_ids)


@BOT.add_cmd("raf")
async def refresh_admin_folder(bot: BOT, message: Message):
    """
    INFO: Refresh Admins Folder.
    """
    folder = await get_folder()

    if not isinstance(folder, raw.types.DialogFilter):
        await message.reply("No Folder named Admin.")
        return

    resp = await message.reply("`Cleaning Non-Admin Chats and Channels in admin folder...`")

    chats = await bot.invoke(raw.functions.channels.GetChannels(id=folder.include_peers))
    to_delete_hash = [chat.access_hash for chat in chats.chats if not chat.admin_rights]

    folder.include_peers = list(
        filter(lambda x: x.access_hash not in to_delete_hash, folder.include_peers)
    )

    success = await update_folder(folder_id=folder.id, folder=folder)
    resp_text = f"Admin folder updated: {success}\nDeleted: {len(to_delete_hash)}"
    await resp.edit(resp_text)
    await bot.log_text(text=resp_text, type="info")
