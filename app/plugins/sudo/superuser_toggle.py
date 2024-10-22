from pyrogram import filters

from app import BOT, Config, Message, bot
from app.plugins.sudo.users import SUDO_USERS


@BOT.add_cmd(cmd="disable_su", allow_sudo=False)
async def disable_su(bot: BOT, message: Message):
    u_id = message.from_user.id

    if u_id in Config.DISABLED_SUPERUSERS:
        return

    Config.DISABLED_SUPERUSERS.append(u_id)

    await SUDO_USERS.add_data({"_id": u_id, "disabled": True})

    await message.reply(
        text="Your <b>SuperUser</b> Access is now <code>Disabled</code>.", del_in=10
    )


@bot.on_message(
    filters=filters.command(commands="enable_su", prefixes=Config.SUDO_TRIGGER)
    & filters.create(
        lambda _, __, m: m.from_user and m.from_user.id in Config.DISABLED_SUPERUSERS
    ),
    group=1,
    is_command=True,
    filters_edited=True,
    check_for_reactions=True,
)
async def enable_su(bot: BOT, message: Message):
    u_id = message.from_user.id

    Config.DISABLED_SUPERUSERS.remove(u_id)

    await SUDO_USERS.add_data({"_id": u_id, "disabled": False})

    await message.reply(
        text="Your <b>SuperUser</b> Access is now <code>Enabled</code>.", del_in=10
    )
