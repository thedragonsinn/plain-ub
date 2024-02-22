import os

from app import BOT, Config, Message, bot


@bot.add_cmd(cmd="ci")
async def cmd_info(bot: BOT, message: Message):
    """
    CMD: CI (CMD INFO)
    INFO: Get Github File URL of a Command.
    USAGE: .ci ci
    """
    cmd = message.filtered_input
    if not cmd or cmd not in Config.CMD_DICT.keys():
        await message.reply("Give a valid cmd.", del_in=5)
        return
    cmd_path = Config.CMD_DICT[cmd].cmd_path
    plugin_path = os.path.relpath(cmd_path, os.curdir)
    repo = Config.REPO.remotes.origin.url
    branch = Config.REPO.active_branch
    remote_url = os.path.join(str(repo), "blob", str(branch), plugin_path)
    resp_str = (
        f"<pre language=css>Command: {cmd}"
        f"\nPath: {cmd_path}</pre>"
        f"\nLink: <a href='{remote_url}'>Github</a>"
    )
    await message.reply(resp_str, disable_web_page_preview=True)


@bot.add_cmd(cmd="s")
async def search(bot: BOT, message: Message):
    search_str = message.input

    if not search_str:
        await message.reply("Give some input to search commands.")
        return

    cmds = [cmd for cmd in Config.CMD_DICT.keys() if search_str in cmd]
    await message.reply(f"<pre language=json>{cmds}</pre>")
