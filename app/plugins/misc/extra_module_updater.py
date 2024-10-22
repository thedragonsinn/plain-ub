from ub_core.utils import run_shell_cmd

from app import BOT, Message


@BOT.add_cmd(cmd="extupdate", allow_sudo=False)
async def extra_modules_updater(bot: BOT, message: Message):
    output = await run_shell_cmd(
        cmd="cd app/modules && git pull", timeout=10, ret_val="0"
    )

    await message.reply(output)

    if output.strip() != "Already up to date.":
        bot.raise_sigint()
