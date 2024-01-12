import asyncio

from pyrogram.types import User

from app import BOT, Config, CustomDB, Message, bot
from app.plugins.admin.fbans import _User
from app.utils.helpers import extract_user_data, get_name

SUDO = CustomDB("SUDO")
SUDO_USERS = CustomDB("SUDO_USERS")


async def init_task():
    sudo = await SUDO.find_one({"_id": "sudo_switch"})
    if sudo:
        Config.SUDO = sudo["value"]
    Config.SUDO_USERS = [sudo_user["_id"] async for sudo_user in SUDO_USERS.find()]


@bot.add_cmd(cmd="sudo")
async def sudo(bot: BOT, message: Message):
    """
    CMD: SUDO
    INFO: Enable/Disable sudo..
    FLAGS: -c to check sudo status.
    USAGE:
        .sudo | .sudo -c
    """
    if "-c" in message.flags:
        await message.reply(text=f"Sudo is enabled: <b>{Config.SUDO}</b> .", del_in=8)
        return
    value = not Config.SUDO
    Config.SUDO = value
    await asyncio.gather(
        SUDO.add_data({"_id": "sudo_switch", "value": value}),
        message.reply(text=f"Sudo is enabled: <b>{value}</b>!", del_in=8),
    )


@bot.add_cmd(cmd="addsudo")
async def add_sudo(bot: BOT, message: Message) -> Message | None:
    """
    CMD: ADDSUDO
    INFO: Add Sudo User.
    FLAGS: -temp to temporarily add until bot restarts.
    USAGE:
        .addsudo [-temp] [ UID | @ | Reply to Message ]
    """
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
        await SUDO_USERS.add_data({"_id": user.id, **extract_user_data(user)})
    else:
        response_str += "\n<b>Temporary</b>: True"
    await response.edit(text=response_str, del_in=5)
    await response.log()


@bot.add_cmd(cmd="delsudo")
async def remove_sudo(bot: BOT, message: Message) -> Message | None:
    """
    CMD: DELSUDO
    INFO: Add Remove User.
    FLAGS: -temp to temporarily remove until bot restarts.
    USAGE:
        .delsudo [-temp] [ UID | @ | Reply to Message ]
    """
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
        await SUDO_USERS.delete_data(id=user.id)
    else:
        response_str += "\n<b>Temporary</b>: True"
    await response.edit(text=response_str, del_in=5)
    await response.log()


@bot.add_cmd(cmd="vsudo")
async def sudo_list(bot: BOT, message: Message):
    """
    CMD: VSUDO
    INFO: View Sudo Users.
    FLAGS: -id to get UIDs
    USAGE:
        .vsudo | .vsudo -id
    """
    output: str = ""
    total = 0
    async for user in SUDO_USERS.SUDO_USERS.find():
        output += f'<b>• {user["name"]}</b>\n'
        if "-id" in message.flags:
            output += f'  <code>{user["_id"]}</code>\n'
        total += 1
    if not total:
        await message.reply("You don't have any SUDO USERS.")
        return
    output: str = f"List of <b>{total}</b> SUDO USERS:\n\n{output}"
    await message.reply(output, del_in=30, block=False)
