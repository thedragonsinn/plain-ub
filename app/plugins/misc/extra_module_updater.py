from ub_core.default_plugins.restart import restart
from ub_core.utils import run_shell_cmd

from app import BOT, Message, bot


@bot.add_cmd(cmd="supdate", allow_sudo=False)
async def social_dl_update(bot: BOT, message: Message):
    output = await run_shell_cmd(
        cmd="cd app/modules && git pull", timeout=10, ret_val=0
    )
    update_notif = await message.reply(output)
    if output and output != "Already up to date.":
        await restart(bot, message, update_notif)
