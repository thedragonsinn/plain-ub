# Uploads Xposed module info to telegram channel
#
# Author: Ryuk <@anonymousx97>
#
# Created: 2026-03-10
#
# Updated: 2026-03-10

import os
from datetime import datetime, timedelta

import bs4
from ub_core import BOT, LOGGER, CustomDB, Message, bot
from ub_core.utils import aio

POST_DB = CustomDB["COMMON_SETTINGS"]

POST_CHANNEL = -1002651613037

XPOSED_URL = "https://modules.lsposed.org/modules.json"


@BOT.register_worker(interval=10800, name="xposed-updates")
@BOT.add_cmd(cmd="cxu")
async def check_xposed_updates(bot: BOT = bot, message: Message = None):
    """
    CMD: CXU
    INFO: Fetches information about the latest Xposed module from LSPosed modules repository.
    USAGE: .cxu
    """
    modules_data = await aio.get_json(XPOSED_URL)

    if not modules_data:
        LOGGER.error("Failed to fetch Xposed module data or data is empty.")
        return

    modules_data.sort(key=lambda m: m.get("updatedAt", "1970-01-01T00:00:00Z"), reverse=True)

    latest_module = modules_data[0]

    is_new_post = await check_and_insert_to_db(latest_module)

    if not is_new_post:
        if message:
            await message.reply("No new update found.")
        return

    text_parts = []

    name = latest_module.get("description", "N/A")
    text_parts.append(f"<b>📦 Module</b>: {name}\n")

    description = latest_module.get("summary", "No description available.")
    text_parts.append(f"<b>✍️ Description</b>: {description}\n")

    version = latest_module.get("latestRelease", "N/A")
    release = latest_module.get("releases", [{}])[0]

    changelog_html = release.get("descriptionHTML")
    if changelog_html:
        soup = bs4.BeautifulSoup(changelog_html, "html.parser")
        text_parts.append(f"<b>📜 Changelog</b>: <code>{version}</code>")
        text_parts.append(f"<blockquote expandable=true>{soup.text}</blockquote>\n")

    text_parts.append(f"<b>🏷️ Version</b>: <code>{version}</code>")

    if release.get("isPrerelease"):
        text_parts.append("<b>🚧 Pre-Release</b>: <code>yes</code>")

    if release.get("isDraft"):
        text_parts.append("<b>✍🏻 Draft</b>: <code>yes</code>\n")

    source_url = latest_module.get("sourceUrl")
    release_url = release.get("url") or os.path.join(source_url, "releases")
    text_parts.append(f'📥  <a href="{release_url}">Download</a>  |  💻  <a href="{source_url}">Source</a>\n')

    text_parts.append("Join us:\n@XposedRepositoryChat\n@Xposed_Repository\n@Xposed_APK_repository")
    text_parts.append(
        "<blockquote>🔖Don't forget to read the <a href='https://t.me/Xposed_Repository/8'>Reduction of responsibility</a></blockquote>"
    )

    schedule_date = datetime.utcnow() + timedelta(seconds=10)

    await bot.send_message(
        chat_id=POST_CHANNEL,
        text="\n".join(text_parts),
        disable_preview=True,
        schedule_date=schedule_date,
    )


async def check_and_insert_to_db(module) -> bool:
    package_name = module.get("name")
    latest_release = module.get("latestRelease")

    last_post = await POST_DB.find_one({"_id": "last_updated_post"}) or {}
    old_package_name = last_post.get("name")
    old_release = last_post.get("latestRelease")

    # same post
    if package_name == old_package_name and latest_release == old_release:
        return False

    data = dict(
        package_name=package_name,
        latest_release=latest_release,
        _id="last_updated_post",
    )
    await POST_DB.add_data(data)
    return True
