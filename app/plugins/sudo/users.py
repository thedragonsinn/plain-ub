from pyrogram.types import User
from ub_core.utils.helpers import extract_user_data, get_name

from app import BOT, Config, CustomDB, Message

SUDO = CustomDB["COMMON_SETTINGS"]
SUDO_USERS = CustomDB["SUDO_USERS"]


async def init_task():
    sudo = await SUDO.find_one({"_id": "sudo_switch"}) or {}
    Config.SUDO = sudo.get("value", False)

    async for sudo_user in SUDO_USERS.find():
        config = Config.SUPERUSERS if sudo_user.get("super") else Config.SUDO_USERS
        config.add(sudo_user["_id"])

        if sudo_user.get("disabled"):
            Config.DISABLED_SUPERUSERS.add(sudo_user["_id"])


@BOT.add_cmd(cmd="sudo", allow_sudo=False)
async def sudo(bot: BOT, message: Message):
    """
    CMD: SUDO
    INFO: Enable/Disable sudo.
    FLAGS: -c to check sudo status.
    USAGE:
        .sudo | .sudo -c
    """
    if "-c" in message.flags:
        await message.reply(text=f"Sudo is enabled: <b>{Config.SUDO}</b>!", del_in=8)
        return

    value = not Config.SUDO

    Config.SUDO = value

    await SUDO.add_data({"_id": "sudo_switch", "value": value})

    await (await message.reply(text=f"Sudo is enabled: <b>{value}</b>!", del_in=8)).log()


@BOT.add_cmd(cmd="addsudo", allow_sudo=False)
async def add_sudo(bot: BOT, message: Message) -> Message | None:
    """
    CMD: ADDSUDO
    INFO: Add Sudo User.
    FLAGS:
        -temp: to temporarily add until bot restarts.
        -su: to give SuperUser[Owner level] access.
    USAGE:
        .addsudo [-temp | -su] [ UID | @ | Reply to Message ]
    """
    response = await message.reply("Extracting User info...")

    user, _ = await message.extract_user_n_reason()

    if not isinstance(user, User):
        await response.edit("unable to extract user info.")
        return

    if "-su" in message.flags:
        set_to_add, set_to_remove = Config.SUPERUSERS, Config.SUDO_USERS
        text = "Super Users"
    else:
        set_to_add, set_to_remove = Config.SUDO_USERS, Config.SUPERUSERS
        text = "Sudo Users"

    if user.id in set_to_add:
        await response.edit(text=f"{get_name(user)} already in Sudo with same privileges!", del_in=5)
        return

    response_str = f"#SUDO\n{user.mention} added to {text} List."

    set_to_add.add(user.id)
    set_to_remove.discard(user.id)

    if "-temp" not in message.flags:
        await SUDO_USERS.add_data(
            {
                "_id": user.id,
                **extract_user_data(user),
                "disabled": False,
                "super": "-su" in message.flags,
            }
        )
    else:
        response_str += "\n<b>Temporary</b>: True"

    await response.edit(text=response_str, del_in=5)
    await response.log()


@BOT.add_cmd(cmd="delsudo", allow_sudo=False)
async def remove_sudo(bot: BOT, message: Message) -> Message | None:
    """
    CMD: DELSUDO
    INFO: Add Remove User.
    FLAGS:
        -temp: to temporarily remove until bot restarts.
        -su: to Remove SuperUser Access.
        -f: force rm an id
    USAGE:
        .delsudo [-temp] [ UID | @ | Reply to Message ]
    """

    if "-f" in message.flags:
        await SUDO_USERS.delete_data(id=int(message.filtered_input))
        await message.reply(f"Forcefully deleted {message.filtered_input} from sudo users.")
        return

    response = await message.reply("Extracting User info...")
    user, _ = await message.extract_user_n_reason()

    if isinstance(user, str):
        await response.edit(user)
        return

    if not isinstance(user, User):
        await response.edit("unable to extract user info.")
        return

    if user.id not in {*Config.SUDO_USERS, *Config.SUPERUSERS}:
        await response.edit(text=f"{get_name(user)} not in Sudo!", del_in=5)
        return

    if "-su" in message.flags:
        response_str = f"{user.mention}'s Super User access is revoked to Sudo only."
        Config.SUDO_USERS.add(user.id)
        Config.SUPERUSERS.discard(user.id)
    else:
        Config.SUPERUSERS.discard(user.id)
        Config.SUDO_USERS.discard(user.id)
        response_str = f"{user.mention}'s access to bot has been removed."

    if "-temp" not in message.flags:
        if "-su" in message.flags:
            await SUDO_USERS.add_data({"_id": user.id, "super": False})
        else:
            await SUDO_USERS.delete_data(id=user.id)

    else:
        response_str += "\n<b>Temporary</b>: True"

    await response.edit(text=response_str, del_in=5)
    await response.log()


@BOT.add_cmd(cmd="vsudo")
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

    async for user in SUDO_USERS.find():
        output += f"\n<b>• {user['name']}</b>"

        if "-id" in message.flags:
            output += f"\n  ID: <code>{user['_id']}</code>"

        output += f"\n  Super: <b>{user.get('super', False)}</b>"

        output += f"\n  Disabled: <b>{user.get('disabled', False)}</b>\n"

        total += 1

    if not total:
        await message.reply("You don't have any SUDO USERS.")
        return

    output: str = f"List of <b>{total}</b> SUDO USERS:\n{output}"
    await message.reply(output, del_in=30, block=True)
