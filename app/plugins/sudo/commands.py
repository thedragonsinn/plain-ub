from app import DB, Config, bot
from app.core import Message


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
        text=f"List of <b>{len(Config.SUDO_CMD_LIST)}</b> SUDO CMDS:\n\n{cmds}",
        del_in=30,
        block=False,
    )
