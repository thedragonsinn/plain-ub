from ub_core.utils import run_shell_cmd

from app import BOT, Message


@BOT.add_cmd(cmd="extupdate", allow_sudo=False)
async def extra_modules_updater(bot: BOT, message: Message):
    """
    CMD: EXT UPDATE
    INFO: Updates external modules if installed
    """

    output = await run_shell_cmd(cmd="cd app/modules && git pull", timeout=10)

    await message.reply(f"<pre language=shell>{output}</pre>")

    if output.strip() != "Already up to date.":
        bot.raise_sigint()
