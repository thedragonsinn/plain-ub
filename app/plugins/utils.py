import asyncio
import os

from git import Repo
from pyrogram.enums import ChatType

from app import Config, bot
from app.core import Message


@bot.add_cmd(cmd="help")
async def cmd_list(bot: bot, message: Message) -> None:
    commands: str = "\n".join(
        [f"<code>{Config.TRIGGER}{i}</code>" for i in Config.CMD_DICT.keys()]
    )
    await message.reply(f"<b>Available Commands:</b>\n\n{commands}", del_in=30)


@bot.add_cmd(cmd="restart")
async def restart(bot: bot, message: Message, u_resp: Message | None = None) -> None:
    reply: Message = u_resp or await message.reply("restarting....")
    if reply.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
        os.environ["RESTART_MSG"] = str(reply.id)
        os.environ["RESTART_CHAT"] = str(reply.chat.id)
    await bot.restart(hard="-h" in message.flags)


@bot.add_cmd(cmd="repo")
async def sauce(bot: bot, message: Message) -> None:
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"<a href='{Config.UPSTREAM_REPO}'>Plain-UB.</a>",
        reply_to_message_id=message.reply_id or message.id,
        disable_web_page_preview=True,
    )


@bot.add_cmd(cmd="update")
async def updater(bot: bot, message: Message) -> None | Message:
    reply: Message = await message.reply("Checking for Updates....")
    repo: Repo = Repo()
    repo.git.fetch()
    commits: str = ""
    limit: int = 0
    for commit in repo.iter_commits("HEAD..origin/main"):
        commits += f"""
<b>#{commit.count()}</b> <a href='{Config.UPSTREAM_REPO}/commit/{commit}'>{commit.summary}</a> By <i>{commit.author}</i>
"""
        limit += 1
        if limit > 50:
            break
    if not commits:
        return await reply.edit("Already Up To Date.", del_in=5)
    if "-pull" not in message.flags:
        return await reply.edit(
            f"<b>Update Available:</b>\n\n{commits}", disable_web_page_preview=True
        )
    repo.git.reset("--hard")
    repo.git.pull(Config.UPSTREAM_REPO, "--rebase=true")
    await asyncio.gather(
        bot.log(text=f"#Updater\nPulled:\n\n{commits}", disable_web_page_preview=True),
        reply.edit("<b>Update Found</b>\n<i>Pulling....</i>"),
    )
    await restart(bot, message, reply)
