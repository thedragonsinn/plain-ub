import json
import os
import re
import shutil
from functools import cached_property

import aiofiles
import aiohttp
from pyrogram.types import Message as Msg

from app.core.types.message import Message
from app.utils.aiohttp_tools import get_filename, get_type

RECENT_LINKS = []


class DownloadedFile:
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.full_path = os.path.join(name, path)
        self.type = get_type(path=name)

    def __str__(self):
        return json.dumps(self.__dict__, indent=4, ensure_ascii=False, default=str)


class Download:
    class DuplicateDownload(Exception):
        def __init__(self, url: str | None = None):
            text = "Download already started"
            if url:
                text += f" for the url: {url}"
            super().__init__(text)

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
        self.edit_pass_count: int = 0
        self.is_done = False

    @cached_property
    def file_name(self):
        content_disposition = self.headers.get("Content-Disposition", "")
        filename_match = re.search(r'filename="(.+)"', content_disposition)
        if filename_match:
            return filename_match.group(1)
        return get_filename(self.url)

    @cached_property
    def raw_size(self):
        # File Size in Bytes
        return int(self.headers.get("Content-Length", 0))

    @cached_property
    def size(self):
        # File size in MBs
        return self.raw_size / 1048576

    @cached_property
    def check_disk_space(self):
        if shutil.disk_usage(self.path).free < self.raw_size:
            self.close()
            raise MemoryError(
                f"Not enough space in {self.path} to download {self.size}mb."
            )

    @property
    def completed_size(self):
        return round(self.raw_completed_size / 1048576)

    def close(self):
        if not self.session.closed:
            self.session.close()
        if not self.file_session.closed:
            self.file_session.close()

    async def download(self) -> DownloadedFile | None:
        if self.session.closed:
            return
        async with aiofiles.open(
            os.path.join(self.path, self.file_name), "wb"
        ) as async_file:
            while file_chunk := (await self.file_session.content.read(1048576)):  # NOQA
                await async_file.write(file_chunk)
                self.raw_completed_size += 1048576
                self.edit_pass_count += 1
                if self.edit_pass_count >= 8:
                    self.edit_pass_count = 0
                    await self.edit_progress_message()
        self.is_done = True
        self.close()
        return

    async def edit_progress_message(self):
        if not self.message:
            return
        await self.message.edit(
            f"Downloading..."
            f"\n<pre language=bash>"
            f"\nfile = {self.file_name}"
            f"\nsize={self.size}"
            f"\ncompleted={self.completed_size}</pre>"
        )

    def return_file(self) -> DownloadedFile:
        return DownloadedFile(name=self.file_name, path=self.path)

    @classmethod
    async def setup(cls, url: str, path: str = "downloads", message=None) -> "Download":
        session = aiohttp.ClientSession()
        file_session = await session.get(url=url)
        headers = file_session.headers
        os.makedirs(name=path, exist_ok=True)
        return cls(
            url=url,
            path=path,
            file_session=file_session,
            session=session,
            headers=headers,
            message=message,
        )
