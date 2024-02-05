import asyncio
import os
import shutil
from functools import cached_property

import aiofiles
import aiohttp
from pyrogram.types import Message as Msg

from app.core.types.message import Message
from app.utils import Str
from app.utils.helpers import progress
from app.utils.media_helper import (bytes_to_mb, get_filename_from_headers,
                                    get_filename_from_url, get_type)


class DownloadedFile(Str):
    def __init__(
            self,
            name: str,
            path: str,
            full_path: str,
            size: int | float):
        self.name = name
        self.path = path
        self.full_path = full_path
        self.size = size
        self.type = get_type(path=name)


class Download(Str):
    """Download a file in async using aiohttp.

    Attributes:
        url (str):
            file url.
        path (str):
            download path without file name.
        message_to_edit:
            response message to edit for progress.
        custom_file_name:
            override the file name.

    Returns:
        ON success a DownloadedFile object is returned.

    Methods:
        dl_obj = await Download.setup(
            url="https....",
            path="downloads",
            message_to_edit=response,
        )
        file = await dl_obj.download()
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
        custom_file_name: str | None = None,
        message_to_edit: Message | Msg | None = None,
    ):
        self.url: str = url
        self.path: str = path
        self.headers: aiohttp.ClientResponse.headers = headers
        self.custom_file_name: str = custom_file_name
        self.file_session: aiohttp.ClientResponse = file_session
        self.session: aiohttp.ClientSession = session
        self.message_to_edit: Message | Msg | None = message_to_edit
        self.raw_completed_size: int = 0
        self.has_started: bool = False
        self.is_done: bool = False
        os.makedirs(name=path, exist_ok=True)

    @classmethod
    async def setup(
        cls,
        url: str,
        path: str = "downloads",
        message_to_edit: Message | None = None,
        custom_file_name: str | None = None,
    ) -> "Download":
        session = aiohttp.ClientSession()
        file_session = await session.get(url=url)
        headers = file_session.headers
        cls_object = cls(
            url=url,
            path=path,
            file_session=file_session,
            session=session,
            headers=headers,
            message_to_edit=message_to_edit,
            custom_file_name=custom_file_name,
        )
        await asyncio.gather(
            cls_object.check_disk_space(), cls_object.check_duplicates()
        )
        return cls_object

    async def check_disk_space(self):
        if shutil.disk_usage(self.path).free < self.raw_size:
            await self.close()
            raise MemoryError(
                f"Not enough space in {self.path} to download {self.size}mb."
            )

    async def check_duplicates(self):
        if os.path.isfile(self.full_path):
            await self.close()
            raise self.DuplicateDownload(self.full_path)

    @property
    def completed_size(self):
        """Size in MB"""
        return bytes_to_mb(self.raw_completed_size)

    @cached_property
    def file_name(self):
        if self.custom_file_name:
            return self.custom_file_name
        return get_filename_from_headers(
            self.headers) or get_filename_from_url(
            self.url)

    @cached_property
    def full_path(self):
        return os.path.join(self.path, self.file_name)

    @cached_property
    def raw_size(self):
        # File Size in Bytes
        return int(self.headers.get("Content-Length", 0))

    @cached_property
    def size(self):
        """File size in MBs"""
        return bytes_to_mb(self.raw_size)

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
                await progress(
                    current=self.raw_completed_size,
                    total=self.raw_size,
                    response=self.message_to_edit,
                    action="Downloading...",
                    file_name=self.file_name,
                    file_path=self.full_path,
                )
        self.is_done = True
        await self.close()
        return self.return_file()

    def return_file(self) -> DownloadedFile:
        if os.path.isfile(self.full_path):
            return DownloadedFile(
                name=self.file_name,
                path=self.path,
                full_path=self.full_path,
                size=self.size,
            )
