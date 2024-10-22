from app import BOT, Config, CustomDB, Message

DB = CustomDB("SUDO_CMD_LIST")


async def init_task():
    async for sudo_cmd in DB.find():
        cmd_object = Config.CMD_DICT.get(sudo_cmd["_id"])
        if cmd_object:
            cmd_object.loaded = True


@BOT.add_cmd(cmd="addscmd", allow_sudo=False)
async def add_scmd(bot: BOT, message: Message):
    """
    CMD: ADDSCMD
    INFO: Add Sudo Commands.
    FLAGS: -all to instantly add all Commands.
    USAGE:
        .addscmd ping | .addscmd -all
    """
    if "-all" in message.flags:
        cmds = []

        for cmd_name, cmd_object in Config.CMD_DICT.items():
            if cmd_object.sudo:
                cmd_object.loaded = True
                cmds.append({"_id": cmd_name})

        await DB.drop()
        await DB.insert_many(cmds)

        await (await message.reply("All Commands Added to Sudo!")).log()
        return

    cmd_name = message.filtered_input
    cmd_object = Config.CMD_DICT.get(cmd_name)

    response = await message.reply(f"Adding <b>{cmd_name}</b> to sudo....")

    if not cmd_object:
        await response.edit(text=f"<b>{cmd_name}</b> not a valid command.", del_in=10)
        return

    elif not cmd_object.sudo:
        await response.edit(
            text=f"<b>{cmd_name}</b> is disabled for sudo users.", del_in=10
        )
        return

    elif cmd_object.loaded:
        await response.edit(text=f"<b>{cmd_name}</b> already in Sudo!", del_in=10)
        return

    resp_str = f"#SUDO\n<b>{cmd_name}</b> added to Sudo!"

    if "-temp" in message.flags:
        resp_str += "\nTemp: True"
    else:
        await DB.add_data(data={"_id": cmd_name})

    cmd_object.loaded = True

    await (await response.edit(resp_str)).log()


@BOT.add_cmd(cmd="delscmd", allow_sudo=False)
async def del_scmd(bot: BOT, message: Message):
    """
    CMD: DELSCMD
    INFO: Remove Sudo Commands.
    FLAGS: -all to instantly remove all Commands.
    USAGE:
        .delscmd ping | .delscmd -all
    """
    if "-all" in message.flags:

        for cmd_object in Config.CMD_DICT.values():
            cmd_object.loaded = False

        await DB.drop()
        await (await message.reply("All Commands Removed from Sudo!")).log()
        return

    cmd_name = message.filtered_input
    cmd_object = Config.CMD_DICT.get(cmd_name)

    if not cmd_object:
        return

    response = await message.reply(f"Removing <b>{cmd_name}</b> from sudo....")

    if not cmd_object.loaded:
        await response.edit(f"<b>{cmd_name}</b> not in Sudo!")
        return

    cmd_object.loaded = False
    resp_str = f"#SUDO\n<b>{cmd_name}</b> removed from Sudo!"

    if "-temp" in message.flags:
        resp_str += "\nTemp: True"
    else:
        await DB.delete_data(cmd_name)

    await (await response.edit(resp_str)).log()


@BOT.add_cmd(cmd="vscmd")
async def view_sudo_cmd(bot: BOT, message: Message):
    cmds = [cmd_name for cmd_name, cmd_obj in Config.CMD_DICT.items() if cmd_obj.loaded]

    if not cmds:
        await message.reply("No Commands in SUDO!")
        return

    await message.reply(
        text=f"List of <b>{len(cmds)}</b>:\n <pre language=json>{cmds}</pre>",
        del_in=30,
        block=False,
    )
