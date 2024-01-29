import asyncio

from pyrogram.filters import Filter
from pyrogram.types import Message

from app.utils import Str


class Conversation(Str):
    CONVO_DICT: dict[int, "Conversation"] = {}

    class DuplicateConvo(Exception):
        def __init__(self, chat: str | int):
            super().__init__(f"Conversation already started with {chat} ")

    def __init__(
        self,
        client,
        chat_id: int | str,
        filters: Filter | None = None,
        timeout: int = 10,
    ):
        self.chat_id = chat_id
        self._client = client
        self.filters = filters
        self.response = None
        self.responses: list = []
        self.timeout = timeout
        self.set_future()

    async def __aenter__(self) -> "Conversation":
        if isinstance(self.chat_id, str):
            self.chat_id = (await self._client.get_chat(self.chat_id)).id
        if self.chat_id in Conversation.CONVO_DICT.keys():
            raise self.DuplicateConvo(self.chat_id)
        Conversation.CONVO_DICT[self.chat_id] = self
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        Conversation.CONVO_DICT.pop(self.chat_id, None)
        if not self.response.done():
            self.response.cancel()

    @classmethod
    async def get_resp(cls, client, *args, **kwargs) -> Message | None:
        try:
            async with cls(*args, client=client, **kwargs) as convo:
                response: Message | None = await convo.get_response()
                return response
        except TimeoutError:
            return

    def set_future(self, *args, **kwargs):
        future = asyncio.Future()
        future.add_done_callback(self.set_future)
        self.response = future

    async def get_response(self, timeout: int | None = None) -> Message | None:
        try:
            resp_future: asyncio.Future.result = await asyncio.wait_for(
                fut=self.response, timeout=timeout or self.timeout
            )
            return resp_future
        except asyncio.TimeoutError:
            raise TimeoutError("Conversation Timeout")

    async def send_message(
        self,
        text: str,
        timeout=0,
        get_response=False,
        **kwargs,
    ) -> Message | tuple[Message, Message]:
        message = await self._client.send_message(
            chat_id=self.chat_id, text=text, **kwargs
        )
        if get_response:
            response = await self.get_response(timeout=timeout or self.timeout)
            return message, response
        return message

    async def send_document(
        self,
        document,
        caption="",
        timeout=0,
        get_response=False,
        **kwargs,
    ) -> Message | tuple[Message, Message]:
        message = await self._client.send_document(
            chat_id=self.chat_id,
            document=document,
            caption=caption,
            force_document=True,
            **kwargs,
        )
        if get_response:
            response = await self.get_response(timeout=timeout or self.timeout)
            return message, response
        return message
