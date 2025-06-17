import asyncio
import json
import os
from collections import defaultdict
from functools import wraps

import aiohttp
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from pyrogram.enums import ParseMode
from ub_core import BOT, Config, CustomDB, Message
from ub_core.utils import Download, get_tg_media_details, progress

DB = CustomDB["COMMON_SETTINGS"]

INSTRUCTIONS = """
Step 1 - Get credentials.json from:
https://developers.google.com/workspace/drive/api/quickstart/python


Step 2 - Run this to generate a token.json:
(make sure to keep credentials.json in the same directory)
```
import json

from google_auth_oauthlib.flow import InstalledAppFlow

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", ["https://www.googleapis.com/auth/drive"])
flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

auth_url, state = flow.authorization_url(prompt="consent")
print("Please go to this URL and authorize:")
print(auth_url)

code = input("Enter the authorization code here: ")
flow.fetch_token(code=code)

creds = flow.credentials

with open("token.json", "w") as token_file:
    json.dump(creds.to_json(), token_file, indent=4)
print("Credentials successfully saved to token.json!")

```

Step 3:
Copy the contents of token.json and save them to db using:
.agcreds <data>
"""


class Drive:
    URL_TEMPLATE = "https://drive.google.com/file/d/{_id}/view?usp=sharing"
    FOLDER_MIME = "application/vnd.google-apps.folder"
    SHORTCUT_MIME = "application/vnd.google-apps.shortcut"
    DRIVE_ROOT = os.getenv("DRIVE_ROOT_ID", "root")

    def __init__(self):
        self._aiohttp_session = None
        self._progress_store: dict[str, dict[str, str | int | asyncio.Task]] = defaultdict(dict)
        self._creds: Credentials | None = None
        self.service = None
        self.files = None
        self.is_authenticated = False

    async def async_init(self):
        if self._aiohttp_session is None:
            self._aiohttp_session = aiohttp.ClientSession()
            Config.EXIT_TASKS.append(self._aiohttp_session.close)
        await self.set_creds()

    @property
    def creds(self):
        if (
            isinstance(self._creds, Credentials)
            and self._creds.expired
            and self._creds.refresh_token
        ):
            self._creds.refresh(Request())
            await DB.add_data({"_id": "drive_creds", "creds": json.loads(creds.to_json())})
        return self._creds

    @creds.setter
    def creds(self, creds):
        self._creds = creds

    async def set_creds(self):
        cred_data = await DB.find_one({"_id": "drive_creds"})
        if not cred_data:
            self.is_authenticated = False
            return

        self.creds = Credentials.from_authorized_user_info(
            info=cred_data["creds"], scopes=["https://www.googleapis.com/auth/drive"]
        )
        self.service = build(
            serviceName="drive", version="v3", credentials=self.creds, cache_discovery=False
        )
        self.files = self.service.files()
        self.is_authenticated = True

    def ensure_creds(self, func):
        @wraps(func)
        async def inner(bot: BOT, message: Message):
            if not self.is_authenticated:
                await message.reply(INSTRUCTIONS)
            else:
                await func(bot, message)

        return inner

    async def list_contents(
        self,
        _id: bool = False,
        limit: int = 10,
        file_only: bool = False,
        folder_only: bool = False,
        search_param: str | None = None,
    ) -> list[dict[str, str | int]]:
        """
        :param _id: The ID of the folder to list files from.
        :param limit: Number of results to fetch.
        :param file_only: If True, only list files.
        :param folder_only: If True, only list folders.
        :param search_param: A string to search for in file/folder names.
        :return: A list of dictionaries containing file/folder id, name and mimeType.
        """
        return await asyncio.to_thread(self._list, _id, limit, file_only, folder_only, search_param)

    async def upload_from_url(
        self,
        file_url: str,
        is_encoded: bool = False,
        folder_id: str = None,
        message_to_edit: Message = None,
    ):
        try:
            file_id = await self._upload_from_url(file_url, is_encoded, folder_id, message_to_edit)
            if file_id is not None:
                return self.URL_TEMPLATE.format(_id=file_id)
        except Exception as e:
            return f"Error:\n{e}"
        finally:
            store = self._progress_store.pop(file_url, {})
            store["done"] = True
            task = store.get("edit_task")
            if isinstance(task, asyncio.Task):
                task.cancel()

    async def upload_from_telegram(
        self, media_message: Message, message_to_edit: Message = None, folder_id: str = None
    ):
        try:
            file_id = await self._upload_from_telegram(media_message, message_to_edit, folder_id)
            if file_id is not None:
                return self.URL_TEMPLATE.format(_id=file_id)
        except Exception as e:
            return f"Error:\n{e}"
        finally:
            store = self._progress_store.pop(message_to_edit.task_id, {})
            store["done"] = True
            task = store.get("edit_task")
            if isinstance(task, asyncio.Task):
                task.cancel()

    def _list(
        self,
        _id: bool = False,
        limit: int = 10,
        file_only: bool = False,
        folder_only: bool = False,
        search_param: str | None = None,
    ) -> list[dict[str, str | int]]:

        query_params = ["trashed=false"]

        if folder_only:
            query_params.append(f"mimeType = '{self.FOLDER_MIME}'")
        elif file_only:
            query_params.append(f"mimeType != '{self.FOLDER_MIME}'")

        if search_param is not None:
            if _id:
                query_params.append(f"'{search_param}' in parents")
            else:
                query_params.append(f"name contains '{search_param}'")
        else:
            query_params.append(f"'{self.DRIVE_ROOT}' in parents")

        query = " and ".join(query_params)

        files = []

        fields = "nextPageToken, files(id, name, mimeType, shortcutDetails)"
        result = self.files.list(q=query, pageSize=limit, fields=fields).execute()
        files.extend(result.get("files", []))

        while next_token := result.get("nextPageToken"):
            if len(files) >= limit:
                break
            else:
                file_limit = limit - len(files)
            result = self.files.list(
                q=query, pageSize=file_limit, fields=fields, pageToken=next_token
            ).execute()
            files.extend(result.get("files", []))

        return files[0:limit]

    async def create_file(self, file_name: str, folder_id: str = None) -> str:
        """
        :return: An url pointing to a location in drive.
        """
        headers = {
            "Authorization": f"Bearer {self.creds.token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "application/octet-stream",
        }
        async with self._aiohttp_session.post(
            url="https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
            json={"name": file_name, "parents": [folder_id or self.DRIVE_ROOT]},
            headers=headers,
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Initiate failed: {text}")
            return resp.headers["Location"]

    async def upload_chunk(self, location, headers, chunk) -> str | None:
        async with self._aiohttp_session.put(location, headers=headers, data=chunk) as put:
            if put.status == 308:
                # Chunk accepted, not finished yet
                return None
            elif put.status in (200, 201):
                # File finished
                file = await put.json()
                return file["id"]
            else:
                text = await put.text()
                raise Exception(f"Chunk upload failed with {put.status}: {text}")

    async def _upload_from_url(
        self,
        file_url: str,
        is_encoded: bool = False,
        folder_id: str = None,
        message_to_edit: Message = None,
    ):
        async with Download(url=file_url, dir="", is_encoded_url=is_encoded) as downloader:
            store = self._progress_store[file_url]
            store["size"] = downloader.size_bytes
            store["done"] = False
            store["uploaded_size"] = 0
            store["edit_task"] = asyncio.create_task(
                self.progress_worker(store, message_to_edit), name="url_drive_up_prog"
            )

            file_session = downloader.file_response_session
            file_session.raise_for_status()
            drive_location = await self.create_file(downloader.file_name, folder_id)
            start = 0
            buffer = b""
            chunk_size = 524288

            async for chunk in file_session.content.iter_chunked(chunk_size):
                buffer += chunk
                if len(buffer) < chunk_size:
                    continue
                else:
                    chunk = buffer[:chunk_size]
                    end = start + len(chunk) - 1
                    put_headers = {
                        "Content-Range": f"bytes {start}-{end}/{downloader.size_bytes}",
                        "Authorization": f"Bearer {self.creds.token}",
                    }
                    file_id = await self.upload_chunk(drive_location, put_headers, chunk)
                    start += len(chunk)
                    store["uploaded_size"] += len(chunk)
                    buffer = buffer[chunk_size:]

            if buffer:
                end = start + len(buffer) - 1
                put_headers = {
                    "Content-Range": f"bytes {start}-{end}/{downloader.size_bytes}",
                    "Authorization": f"Bearer {self.creds.token}",
                }
                file_id = await self.upload_chunk(drive_location, put_headers, buffer)
                start = end + 1
                store["uploaded_size"] = start
                buffer = b""

        store["done"] = True
        return file_id

    async def _upload_from_telegram(
        self, media_message: Message, message_to_edit: Message = None, folder_id: str = None
    ):
        media = get_tg_media_details(media_message)

        store = self._progress_store[message_to_edit.task_id]
        store["size"] = getattr(media, "file_size", 0)
        store["done"] = False
        store["uploaded_size"] = 0
        store["edit_task"] = asyncio.create_task(
            self.progress_worker(store, message_to_edit), name="tg_drive_up_prog"
        )

        start = 0
        drive_location = await self.create_file(getattr(media, "file_name"), folder_id)
        file_id = None
        # noinspection PyTypeChecker
        async for chunk in message_to_edit._client.stream_media(message=media_message):
            end = start + len(chunk) - 1
            headers = {
                "Content-Range": f"bytes {start}-{end}/{getattr(media, "file_size", 0)}",
                "Authorization": f"Bearer {self.creds.token}",
            }
            file_id = await self.upload_chunk(drive_location, headers, chunk)
            start = end + 1
            store["uploaded_size"] = end + 1

        return file_id

    @staticmethod
    async def progress_worker(store: dict, message: Message):
        if not isinstance(message, Message):
            return

        while not store["done"]:
            await progress(
                current_size=store["uploaded_size"],
                total_size=store["size"] or 1,
                response=message,
                action_str="Uploading to Drive...",
                file_path="",
            )
            await asyncio.sleep(5)


drive = Drive()


async def init_task():
    await drive.async_init()


@BOT.add_cmd("agcreds")
async def set_drive_creds(bot: BOT, message: Message):
    """
    CMD: AGCREDS
    INFO: Add your O-Auth Creds Json to bot.
    USAGE: .agcreds {data}
    """
    if "-r" in message.flags:
        await drive.set_creds()
        await message.reply("Creds added...")
        return

    creds = message.input.strip()
    if not creds:
        await message.reply("Enter Creds!!!")
        return

    try:
        creds_json = json.loads(creds)
        creds = Credentials.from_authorized_user_info(info=creds_json)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        await DB.add_data({"_id": "drive_creds", "creds": json.loads(creds.to_json())})
        await drive.set_creds()
        await message.reply("Creds added...")
    except Exception as e:
        await message.reply(e)


@BOT.add_cmd("rgcreds")
async def remove_drive_creds(bot: BOT, message: Message):
    response = await message.reply(
        "Are you sure you want to delete drive creds?\nreply with y to continue"
    )

    resp = await response.get_response(from_user=message.from_user.id)
    if not (resp and resp.text in ("y", "Y")):
        await response.edit("Aborted!!!")
        return

    drive.is_authenticated = False
    await DB.delete_data({"_id": "drive_creds"})
    await response.edit("Creds Deleted Successfully!")


@BOT.add_cmd("gls")
@drive.ensure_creds
async def list_drive(bot: BOT, message: Message):
    """
    CMD: GLS
    INFO: List Files/Folders from Drive
    FLAGS:
        -f: list files only
        -d: list dirs only
        -id: list via folder id
        -l: limit of results (10 by default)

    USAGE:
        .gls [-f|-d]
        .gls [-f|-d] abc (lists files/folders matching abc in name)
        .gls -id <folder id>
        .gls [-f|-d] -l 20 (lists 20 results)
        .gls -l 20 abc (tries to list 20 results containing abc in name)
    """
    response = await message.reply("Listing...")
    flags = message.flags
    filtered_input_chunks = message.filtered_input.split(maxsplit=1)

    kwargs = {
        "_id": False,
        "limit": 10,
        "folder_only": False,
        "file_only": False,
        "search_param": None,
    }

    # Search by ID
    if "-id" in flags:
        kwargs["_id"] = True
    # list folders
    if "-d" in flags:
        kwargs["folder_only"] = True
    # list files
    if "-f" in flags:
        kwargs["file_only"] = True

    # limit total number of results
    if "-l" in flags:
        kwargs["limit"] = int(filtered_input_chunks[0])
        # search for specific files/dirs
        if len(filtered_input_chunks) == 2:
            kwargs["search_param"] = filtered_input_chunks[1]
    else:
        # search for specific files/dirs
        kwargs["search_param"] = message.filtered_input.strip() or None

    remote_files = await drive.list_contents(**kwargs)

    if not remote_files:
        await response.edit("No results found.")
        return

    folders = []
    files = [""]
    shortcuts = [""]

    for file in remote_files:
        url = drive.URL_TEMPLATE.format(_id=file["id"])
        mime = file["mimeType"]
        if mime == drive.FOLDER_MIME:
            folders.append(f"📁 <a href={url}>{file["name"]}</a>")
        elif mime == drive.SHORTCUT_MIME:
            shortcut_details = file.get("shortcutDetails", {})
            target_id = shortcut_details.get("targetId")
            if target_id:
                url = drive.URL_TEMPLATE.format(_id=target_id)
            shortcuts.append(f"🔗 <a href={url}>{file["name"]}</a>")
        else:
            files.append(f"📄 <a href={url}>{file["name"]}</a>")

    list_str = "Results:\n\n" + "\n".join(folders + shortcuts + files)

    await response.edit(list_str, parse_mode=ParseMode.HTML)


@BOT.add_cmd(cmd="gup")
@drive.ensure_creds
async def upload_to_drive(bot: BOT, message: Message):
    """
    CMD: GUP
    INFO: Upload file to drive
    FLAGS:
        -id: folder id
        -e: if the url is encoded
    USAGE:
        .gup [reply to a message | url]
        .gup -id <folder id> [reply to a message | url]
    """
    reply = message.replied
    response = await message.reply("Checking Input...")

    if reply and reply.media:
        folder_id = message.filtered_input if "-id" in message.flags else None
        upload_coro = drive.upload_from_telegram(reply, response, folder_id=folder_id)

    elif message.filtered_input.startswith("http"):
        if "-id" in message.flags:
            folder_id, file_url = message.filtered_input.split(maxsplit=1)
        else:
            folder_id = None
            file_url = message.filtered_input

        upload_coro = drive.upload_from_url(
            file_url=file_url,
            is_encoded="-e" in message.flags,
            folder_id=folder_id,
            message_to_edit=response,
        )

    else:
        await response.edit("Invalid Input!!!")
        return

    await response.edit(await upload_coro)
