from pyrogram.types import User

from app import DB, Config, bot
from app.core import Message
from app.plugins.fbans import _User
from app.utils.db_utils import add_data, delete_data
from app.utils.helpers import extract_user_data, get_name


@bot.add_cmd(cmd="sudo")
async def sudo(bot: bot, message: Message):
    if "-c" in message.flags:
        await message.reply(text=f"Sudo is enabled: <b>{Config.SUDO}</b> .", del_in=8)
        return
    value = not Config.SUDO
    Config.SUDO = value
    await add_data(collection=DB.SUDO, id="sudo_switch", data={"value": value})
    await message.reply(text=f"Sudo is enabled: <b>{value}</b>!", del_in=8)


@bot.add_cmd(cmd="addsudo")
async def add_sudo(bot: bot, message: Message) -> Message | None:
    response = await message.reply("Extracting User info...")
    user, _ = await message.extract_user_n_reason()
    if isinstance(user, str):
        await response.edit(user)
        return
    if not isinstance(user, User):
        user: _User = _User(id=message.text_list[1])
    if user.id in Config.SUDO_USERS:
        await response.edit(text=f"{get_name(user)} already in Sudo!", del_in=5)
        return
    response_str = f"{user.mention} added to Sudo List."
    Config.SUDO_USERS.append(user.id)
    if "-temp" not in message.flags:
        await add_data(
            collection=DB.SUDO_USERS, id=user.id, data=extract_user_data(user)
        )
        response_str += "\n<b>Temporary</b>: True"
    await response.edit(text=response_str, del_in=5)
    await bot.log(text=response_str)


@bot.add_cmd(cmd="delsudo")
async def remove_sudo(bot: bot, message: Message) -> Message | None:
    response = await message.reply("Extracting User info...")
    user, _ = await message.extract_user_n_reason()
    if isinstance(user, str):
        await response.edit(user)
        return
    if not isinstance(user, User):
        user: _User = _User(id=message.text_list[1])

    if user.id not in Config.SUDO_USERS:
        await response.edit(text=f"{get_name(user)} not in Sudo!", del_in=5)
        return
    Config.SUDO_USERS.remove(user.id)
    response_str = f"{user.mention} removed from Sudo List."
    if "-temp" not in message.flags:
        await delete_data(collection=DB.SUDO_USERS, id=user.id)
        response_str += "\n<b>Temporary</b>: True"
    await response.edit(text=response_str, del_in=5)
    await bot.log(text=response_str)


@bot.add_cmd(cmd="vsudo")
async def sudo_list(bot: bot, message: Message):
    output: str = ""
    total = 0
    async for user in DB.SUDO_USERS.find():
        output += f'<b>• {user["name"]}</b>\n'
        if "-id" in message.flags:
            output += f'  <code>{user["_id"]}</code>\n'
        total += 1
    if not total:
        await message.reply("You don't have any SUDO USERS.")
        return
    output: str = f"List of <b>{total}</b> SUDO USERS:\n\n{output}"
    await message.reply(output, del_in=30, block=False)


@bot.add_cmd(cmd="addscmd")
async def add_scmd(bot: bot, message: Message):
    if "-all" in message.flags:
        cmds = [{"_id": cmd} for cmd in Config.CMD_DICT.keys()]
        Config.SUDO_CMD_LIST = list(Config.CMD_DICT.keys())
        await DB.SUDO_CMD_LIST.drop()
        await DB.SUDO_CMD_LIST.insert_many(cmds)
        await message.reply("All Commands Added to Sudo!")
        await bot.log(text="All Commands Added to Sudo!")
        return
    cmd = message.flt_input
    response = await message.reply(f"Adding <b>{cmd}</b> to sudo....")
    if cmd in Config.SUDO_CMD_LIST:
        await response.edit(f"<b>{cmd}</b> already in Sudo!")
        return
    await DB.SUDO_CMD_LIST.insert_one({"_id": cmd})
    Config.SUDO_CMD_LIST.append(cmd)
    await response.edit(f"<b>{cmd}</b> added to Sudo!")
    await bot.log(f"<b>{cmd}</b> added to Sudo!")


@bot.add_cmd(cmd="delscmd")
async def del_scmd(bot: bot, message: Message):
    if "-all" in message.flags:
        Config.SUDO_CMD_LIST = []
        await DB.SUDO_CMD_LIST.drop()
        await message.reply("All Commands Removed from Sudo!")
        await bot.log(text="All Commands Removed from Sudo!")
        return
    cmd = message.flt_input
    response = await message.reply(f"Removing <b>{cmd}</b> from sudo....")
    if cmd not in Config.SUDO_CMD_LIST:
        await response.edit(f"<b>{cmd}</b> not in Sudo!")
        return
    await DB.SUDO_CMD_LIST.delete_one({"_id": cmd})
    Config.SUDO_CMD_LIST.remove(cmd)
    await response.edit(f"<b>{cmd}</b> removed from Sudo!")
    await bot.log(f"<b>{cmd}</b> removed from Sudo!")


@bot.add_cmd(cmd="vscmd")
async def view_sudo_cmd(bot: bot, message: Message):
    cmds = " ".join(Config.SUDO_CMD_LIST)
    if not cmds:
        await message.reply("No Commands in SUDO!")
        return
    await message.reply(
        f"List of <b>{len(Config.SUDO_CMD_LIST)}</b> SUDO CMDS:\n\n{cmds}",
        del_in=30,
        block=False,
    )
