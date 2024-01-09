from app import BOT, Config, CustomDB, Message, bot

DB = CustomDB("SUDO_CMD_LIST")


async def init_task():
    Config.SUDO_CMD_LIST = [sudo_cmd["_id"] async for sudo_cmd in DB.find()]


@bot.add_cmd(cmd="addscmd")
async def add_scmd(bot: BOT, message: Message):
    """
    CMD: ADDSCMD
    INFO: Add Sudo Commands.
    FLAGS: -all to instantly add all Commands.
    USAGE:
        .addscmd ping | .addscmd -all
    """
    if "-all" in message.flags:
        cmds = [{"_id": cmd} for cmd in Config.CMD_DICT.keys()]
        Config.SUDO_CMD_LIST = list(Config.CMD_DICT.keys())
        await DB.drop()
        await DB.insert_many(cmds)
        await (await message.reply("All Commands Added to Sudo!")).log()
        return
    cmd = message.flt_input
    response = await message.reply(f"Adding <b>{cmd}</b> to sudo....")
    if cmd in Config.SUDO_CMD_LIST:
        await response.edit(f"<b>{cmd}</b> already in Sudo!")
        return
    resp_str = f"<b>{cmd}</b> added to Sudo!"
    if "-temp" in message.flags:
        resp_str += "\nTemp: True"
    else:
        await DB.add_data(data={"_id": cmd})
    Config.SUDO_CMD_LIST.append(cmd)
    await (await response.edit(resp_str)).log()


@bot.add_cmd(cmd="delscmd")
async def del_scmd(bot: BOT, message: Message):
    """
    CMD: DELSCMD
    INFO: Remove Sudo Commands.
    FLAGS: -all to instantly remove all Commands.
    USAGE:
        .delscmd ping | .delscmd -all
    """
    if "-all" in message.flags:
        Config.SUDO_CMD_LIST = []
        await DB.drop()
        await (await message.reply("All Commands Removed from Sudo!")).log()
        return
    cmd = message.flt_input
    response = await message.reply(f"Removing <b>{cmd}</b> from sudo....")
    if cmd not in Config.SUDO_CMD_LIST:
        await response.edit(f"<b>{cmd}</b> not in Sudo!")
        return
    Config.SUDO_CMD_LIST.remove(cmd)
    resp_str = f"<b>{cmd}</b> removed from Sudo!"
    if "-temp" in message.flags:
        resp_str += "\nTemp: True"
    else:
        await DB.delete_data(cmd)
    await (await response.edit(resp_str)).log()


@bot.add_cmd(cmd="vscmd")
async def view_sudo_cmd(bot: BOT, message: Message):
    cmds = " ".join(Config.SUDO_CMD_LIST)
    if not cmds:
        await message.reply("No Commands in SUDO!")
        return
    await message.reply(
        text=f"List of <b>{len(Config.SUDO_CMD_LIST)}</b> SUDO CMDS:\n\n{cmds}",
        del_in=30,
        block=False,
    )
