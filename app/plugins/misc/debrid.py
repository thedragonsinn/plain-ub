# AllDebrid API plugin By Ryuk

import os

from app import BOT, Message, bot
from app.utils.aiohttp_tools import aio
from app.utils.helpers import post_to_telegraph as post_tgh


# Get response from api and return json or the error
async def get_json(endpoint: str, query: dict, key=os.environ.get("DEBRID_TOKEN")):
    if not key:
        return "API key not found."
    api = "https://api.alldebrid.com/v4" + endpoint
    params = {"agent": "bot", "apikey": key, **query}
    async with aio.session.get(url=api, params=params) as ses:
        try:
            json = await ses.json()
            return json
        except Exception as e:
            return str(e)


# Unlock Links or magnets
@bot.add_cmd("unrestrict")
async def debrid(bot: BOT, message: Message):
    if not message.flt_input:
        return await message.reply("Give a magnet or link to unrestrict.")
    for i in message.text_list[1:]:
        link = i
        if link.startswith("http"):
            if "-save" not in message.flags:
                endpoint = "/link/unlock"
                query = {"link": link}
            else:
                endpoint = "/user/links/save"
                query = {"links[]": link}
        else:
            endpoint = "/magnet/upload"
            query = {"magnets[]": link}
        unrestrict = await get_json(endpoint=endpoint, query=query)
        if not isinstance(unrestrict, dict) or "error" in unrestrict:
            await message.reply(unrestrict)
            continue
        if "-save" in message.flags:
            await message.reply("Link Successfully Saved.")
            continue
        if not link.startswith("http"):
            data = unrestrict["data"]["magnets"][0]
        else:
            data = unrestrict["data"]
        name = data.get("filename", data.get("name", ""))
        id = data.get("id")
        size = round(int(data.get("size", data.get("filesize", 0))) / 1000000)
        ready = data.get("ready", "True")
        ret_str = (
            f"""Name: **{name}**\nID: `{id}`\nSize: **{size} mb**\nReady: __{ready}__"""
        )
        await message.reply(ret_str)


# Get Status via id or Last 5 torrents
@bot.add_cmd("torrents")
async def torrents(bot: BOT, message: Message):
    endpoint = "/magnet/status"
    query = {}

    if "-s" in message.flags and "-l" in message.flags:
        return await message.reply("can't use two flags at once")

    if "-s" in message.flags:
        if not (input_ := message.flt_input):
            return await message.reply("ID required with -s flag")
        query = {"id": input_}

    json = await get_json(endpoint=endpoint, query=query)

    if not isinstance(json, dict) or "error" in json:
        return await message.reply(json)

    data = json["data"]["magnets"]

    if not isinstance(data, list):
        data = [data]

    ret_str_list = []
    limit = 1
    if "-l" in message.flags:
        limit = int(message.flt_input)

    for i in data[0:limit]:
        status = i.get("status")
        name = i.get("filename")
        id = i.get("id")
        downloaded = ""
        uptobox = ""
        if status == "Downloading":
            downloaded = f"""<i>{round(int(i.get("downloaded",0))/1000000)}</i>/"""
        size = f"""{downloaded}<i>{round(int(i.get("size",0))/1000000)}</i> mb"""
        if link := i.get("links"):
            uptobox = (
                "<i>UptoBox</i>: \n[ "
                + "\n".join(
                    [
                        f"""<a href={z.get("link","")}>{z.get("filename","")}</a>"""
                        for z in link
                    ]
                )
                + " ]"
            )
        ret_str_list.append(
            f"\n<b>Name</b>: <i>{name}</i>"
            f"\nStatus: <i>{status}</i>"
            f"\nID: {id}"
            f"\nSize: {size}"
            f"\n{uptobox}"
        )

    ret_str = "<br>".join(ret_str_list)
    if len(ret_str) < 4096:
        await message.reply(ret_str)
    else:
        await message.reply(
            (await post_tgh("Magnets", ret_str.replace("\n", "<br>"))),
            disable_web_page_preview=True,
        )


# Delete a Magnet
@bot.add_cmd("del_t")
async def delete_torrent(bot: BOT, message: Message):
    endpoint = "/magnet/delete"
    if not (id := message.flt_input):
        return await message.reply("Enter an ID to delete")
    for i in message.text_list[1:]:
        json = await get_json(endpoint=endpoint, query={"id": i})
        await message.reply(str(json))
