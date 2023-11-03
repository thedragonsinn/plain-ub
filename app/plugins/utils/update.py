import asyncio

from git import Repo

from app import Config, bot
from app.core import Message


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
