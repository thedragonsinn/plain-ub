import asyncio
from functools import cached_property

from motor.core import AgnosticCollection
from pyrogram import filters
from pyrogram.types import Chat, User

from app import DB, Config, bot
from app.core import Message
from app.utils.db_utils import add_data, delete_data

FEDS: AgnosticCollection = DB.FED_LIST
FILTERS: filters.Filter = filters.user([609517172, 2059887769])
FBAN_REGEX: filters.Filter = filters.regex(
    r"(New FedBan|starting a federation ban|Starting a federation ban|start a federation ban|FedBan Reason update|FedBan reason updated|Would you like to update this reason)"
)


class _User(User):
    def __init__(self, id):
        super().__init__(id=id)

    @cached_property
    def mention(self) -> str:
        return f"<a href='tg://user?id={self.id}'>{self.id}</a>"


@bot.add_cmd(cmd="addf")
async def add_fed(bot: bot, message: Message):
    data = dict(name=message.input or message.chat.title, type=str(message.chat.type))
    await add_data(collection=FEDS, id=message.chat.id, data=data)
    await message.reply(
        f"<b>{data['name']}</b> added to FED LIST.", del_in=5, block=False
    )
    await bot.log(
        text=f"#FBANS\n<b>{data['name']}</b> <code>{message.chat.id}</code> added to FED LIST."
    )


@bot.add_cmd(cmd="delf")
async def remove_fed(bot: bot, message: Message):
    if "-all" in message.flags:
        await FEDS.drop()
        await message.reply("FED LIST cleared.")
        return
    chat: int | str | Chat = message.input or message.chat
    name = ""
    if isinstance(chat, Chat):
        name = f"Chat: {chat.title}\n"
        chat = chat.id
    elif chat.lstrip("-").isdigit():
        chat = int(chat)
    deleted: bool | None = await delete_data(collection=FEDS, id=chat)
    if deleted:
        await message.reply(
            f"<b>{name}</b><code>{chat}</code> removed from FED LIST.",
            del_in=8,
            block=False,
        )
        await bot.log(
            text=f"#FBANS\n<b>{name}</b><code>{chat}</code> removed from FED LIST."
        )
    else:
        await message.reply(f"<b>{name or chat}</b> not in FED LIST.", del_in=8)


@bot.add_cmd(cmd=["fban", "fbanp"])
async def fed_ban(bot: bot, message: Message):
    await message.delete()
    progress: Message = await message.reply("❯")
    user, reason = await message.extract_user_n_reason()
    if isinstance(user, str):
        await progress.edit(user)
        return
    if not isinstance(user, User):
        user = _User(id=message.text_list[1])
    if user.id in Config.USERS:
        await progress.edit("Cannot Fban Owner/Sudo users.")
        return
    proof_str: str = ""
    if message.cmd == "fbanp":
        if not message.replied:
            await message.reply("Reply to a proof")
        proof = await message.replied.forward(Config.FBAN_LOG_CHANNEL)
        proof_str = "".join(["{ ", proof.link, " }"])

    await progress.edit("❯❯")
    total: int = 0
    failed: list[str] = []
    cmd: str = f"/fban {user.mention} {reason}\n{proof_str}"
    async for fed in FEDS.find():
        chat_id = int(fed["_id"])
        total += 1
        cmd: Message = await bot.send_message(
            chat_id=chat_id, text=cmd, disable_web_page_preview=True
        )
        response: Message | None = await cmd.get_response(filters=(FILTERS), timeout=8)
        if not response or not (await FBAN_REGEX(bot, response)):
            failed.append(fed["name"])
        elif "Would you like to update this reason" in response.text:
            await response.click("Update reason")
        await asyncio.sleep(0.8)
    if not total:
        await progress.edit("You Don't have any feds connected!")
        return
    resp_str = f"❯❯❯ <b>FBanned {user.mention}\nID: {user.id}\nReason: {reason}\n"
    if failed:
        resp_str += f"Failed in: {len(failed)}/{total}\n• " + "\n• ".join(failed)
    else:
        resp_str += f"Success! Fbanned in {total} feds."
    await bot.send_message(chat_id=Config.FBAN_LOG_CHANNEL, text=resp_str)
    await progress.edit(
        text=resp_str, del_in=8, block=False, disable_web_page_preview=True
    )


@bot.add_cmd(cmd="unfban")
async def un_fban(bot: bot, message: Message):
    ...


@bot.add_cmd(cmd="listf")
async def fed_list(bot: bot, message: Message):
    output: str = "List of <b>{}</b> Connected Feds:\n\n"
    total = 0
    async for fed in DB.FED_LIST.find():
        output += f'<b>• {fed["name"]}</b>\n'
        if "-id" in message.flags:
            output += f'  <code>{fed["_id"]}</code>\n'
        total += 1
    if not total:
        await message.reply("You don't have any Feds Connected.")
        return
    await message.reply(output.format(total), del_in=30, block=False)
