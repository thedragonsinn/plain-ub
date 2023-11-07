import asyncio
import json
import os
import re
import shutil
from functools import cached_property

import aiofiles
import aiohttp
from async_lru import alru_cache
from pyrogram.types import Message as Msg

from app.core.types.message import Message
from app.utils.aiohttp_tools import get_filename, get_type


class DownloadedFile:
    def __init__(self, name: str, path: str, full_path: str, size: int):
        self.name = name
        self.path = path
        self.full_path = full_path
        self.size = size
        self.type = get_type(path=name)

    def __str__(self):
        return json.dumps(self.__dict__, indent=4, ensure_ascii=False, default=str)


class Download:
    """
    Example usage:
    dl_obj = await Download.setup(
        url="https....",
        path="downloads", # default is download
        message=response # optional
        )
    without message:
        file = await dl_obj.download()
        # only download the file
    with message:
        file = await dl_obj.start()
        # starts the download and edit the response message with progress

    On success both return a DownloadedFile class.

    if the file path exists raises Download.DuplicateDownload error.

    if not enough disk space in specified path raises MemoryError.
    """

    class DuplicateDownload(Exception):
        def __init__(self, path: str):
            super().__init__(f"path {path} already exists!")

    def __init__(
        self,
        url: str,
        path: str,
        file_session: aiohttp.ClientResponse,
        session: aiohttp.client,
        headers: aiohttp.ClientResponse.headers,
        message: Message | Msg | None = None,
    ):
        self.url: str = url
        self.path: str = path
        self.headers: aiohttp.ClientResponse.headers = headers
        self.file_session: aiohttp.ClientResponse = file_session
        self.session: aiohttp.ClientSession = session
        self.message: Message | Msg | None = message
        self.raw_completed_size: int = 0
        self.has_started: bool = False
        self.is_done: bool = False
        os.makedirs(name=path, exist_ok=True)

    @alru_cache()
    async def check_disk_space(self):
        if shutil.disk_usage(self.path).free < self.raw_size:
            await self.close()
            raise MemoryError(
                f"Not enough space in {self.path} to download {self.size}mb."
            )

    @alru_cache()
    async def check_duplicates(self):
        if os.path.isfile(self.full_path):
            await self.close()
            raise self.DuplicateDownload(self.full_path)

    @property
    def completed_size(self):
        return round(self.raw_completed_size / 1048576)

    @cached_property
    def file_name(self):
        content_disposition = self.headers.get("Content-Disposition", "")
        filename_match = re.search(r'filename="(.+)"', content_disposition)
        if filename_match:
            return filename_match.group(1)
        return get_filename(self.url)

    @cached_property
    def full_path(self):
        return os.path.join(self.path, self.file_name)

    @cached_property
    def raw_size(self):
        # File Size in Bytes
        return int(self.headers.get("Content-Length", 0))

    @cached_property
    def size(self):
        # File size in MBs
        return round(self.raw_size / 1048576)

    async def close(self):
        if not self.session.closed:
            await self.session.close()
        if not self.file_session.closed:
            self.file_session.close()

    async def download(self) -> DownloadedFile | None:
        if self.session.closed:
            return
        async with aiofiles.open(self.full_path, "wb") as async_file:
            self.has_started = True
            while file_chunk := (await self.file_session.content.read(1024)):  # NOQA
                await async_file.write(file_chunk)
                self.raw_completed_size += 1024
        self.is_done = True
        await self.close()
        return self.return_file()

    async def edit_progress_message(self):
        if not self.message:
            return
        sleep_for = 0
        while not self.is_done:
            await self.message.edit(
                f"Downloading..."
                f"\n<pre language=bash>"
                f"\nfile={self.file_name}"
                f"\nsize={self.size}mb"
                f"\ncompleted={self.completed_size}mb</pre>"
            )
            if sleep_for == 10:
                sleep_for = 1
            await asyncio.sleep(sleep_for)
            sleep_for += 1

    def return_file(self) -> DownloadedFile:
        if os.path.isfile(self.full_path):
            return DownloadedFile(
                name=self.file_name,
                path=self.path,
                full_path=self.full_path,
                size=self.size,
            )

    async def start(self) -> DownloadedFile:
        _, downloaded_file = await asyncio.gather(
            self.edit_progress_message(), self.download()
        )
        return downloaded_file

    @classmethod
    async def setup(cls, url: str, path: str = "downloads", message=None) -> "Download":
        session = aiohttp.ClientSession()
        file_session = await session.get(url=url)
        headers = file_session.headers
        return cls(
            url=url,
            path=path,
            file_session=file_session,
            session=session,
            headers=headers,
            message=message,
        )
