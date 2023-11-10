import asyncio

from git import Repo

from app import Config, bot
from app.core import Message
from app.plugins.utils.restart import restart


def get_commits(repo: Repo) -> str:
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
    return commits


async def pull_commits(repo: Repo) -> None:
    repo.git.reset("--hard")
    async with asyncio.timeout(10):
        await asyncio.to_thread(repo.git.pull, Config.UPSTREAM_REPO, "--rebase=true")


@bot.add_cmd(cmd="update")
async def updater(bot: bot, message: Message) -> None | Message:
    reply: Message = await message.reply("Checking for Updates....")
    repo: Repo = Repo()
    commits: str = await asyncio.to_thread(get_commits, repo)
    if not commits:
        await reply.edit("Already Up To Date.", del_in=5)
        return
    if "-pull" not in message.flags:
        await reply.edit(
            f"<b>Update Available:</b>\n\n{commits}", disable_web_page_preview=True
        )
        return
    try:
        await pull_commits(repo)
    except TimeoutError:
        await reply.edit("Timeout...try again.")
        return
    await asyncio.gather(
        bot.log(text=f"#Updater\nPulled:\n\n{commits}", disable_web_page_preview=True),
        reply.edit("<b>Update Found</b>\n<i>Pulling....</i>"),
    )
    await restart(bot, message, reply)
