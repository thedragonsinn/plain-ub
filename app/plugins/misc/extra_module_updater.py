from ub_core.utils import run_shell_cmd

from app import BOT, Message, bot


@bot.add_cmd(cmd="supdate", allow_sudo=False)
async def social_dl_update(bot: BOT, message: Message):
    output = await run_shell_cmd(
        cmd="cd app/modules && git pull", timeout=10, ret_val=0
    )
    await message.reply(output)
