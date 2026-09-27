import asyncio
import io
import pickle
import wave
from collections.abc import Callable, Generator
from functools import cached_property

import numpy as np
from google.genai import types
from google.genai.chats import AsyncChat
from google.genai.errors import ClientError
from pyrogram.enums import ParseMode
from ub_core import LOGGER, Message
from ub_core.utils import run_unknown_callable, wrap_in_block_quote

FUNCTION_CALL_MAP: dict[str, Callable] = {}


def wrap_in_quote(text: str, mode: ParseMode = ParseMode.MARKDOWN):
    _text = text.strip()
    match mode:
        case ParseMode.MARKDOWN:
            if "```" in _text:
                return _text
            else:
                return wrap_in_block_quote(text=_text, expandable=True)
        case ParseMode.HTML:
            return f"<blockquote expandable=true>{_text}</blockquote>"
        case _:
            return _text


def save_wave_file(pcm, channels=1, rate=24000, sample_width=2) -> io.BytesIO:
    file = io.BytesIO()

    with wave.open(file, mode="wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

    n_samples = len(pcm) // (sample_width * channels)
    duration = n_samples / rate

    dtype = {1: np.int8, 2: np.int16, 4: np.int32}[sample_width]
    samples = np.frombuffer(pcm, dtype=dtype)

    chunk_size = max(1, len(samples) // 80)

    # fmt: off
    data = [
        int(min(255, np.abs(samples[i: i + chunk_size]).mean() / (2 ** (8 * sample_width - 1)) * 255))
        for i in range(0, len(samples), chunk_size)
    ]
    # fmt: on

    file.name = "audio.ogg"
    file.waveform = bytes(data)[:80]
    file.duration = round(duration)

    return file


class Response:
    def __init__(self, ai_response: types.GenerateContentResponse):
        self._ai_response = ai_response

        self.first_candidate = None
        self.first_content = None
        self.first_parts = []
        self.first_part = None

        if ai_response.candidates:
            self.first_candidate = ai_response.candidates[0]
            if self.first_candidate.content:
                self.first_content = self.first_candidate.content
                if self.first_content.parts:
                    self.first_parts = self.first_content.parts
                    self.first_part = self.first_parts[0]

        self.is_empty = not self.first_parts
        self.failed_str = "`Error: Query Failed.`"

    @cached_property
    def text(self) -> str:
        return "\n".join(part.text for part in self.first_parts if isinstance(part.text, str))

    @cached_property
    def image(self) -> bool:
        for part in self.first_parts:
            if part.inline_data and "image" in part.inline_data.mime_type:
                return True

    @cached_property
    def image_file(self) -> io.BytesIO | None:
        if not self.image:
            return

        for part in self.first_parts:
            if part.inline_data and "image" in part.inline_data.mime_type:
                file = io.BytesIO(part.inline_data.data)
                file.name = "photo.png"
                return file

    @property
    def all_image_files(self) -> Generator[io.BytesIO, None, None]:
        for part in self.first_parts:
            if part.inline_data and "image" in part.inline_data.mime_type:
                file = io.BytesIO(part.inline_data.data)
                file.name = "photo.png"
                yield file
        return None

    @cached_property
    def audio(self) -> bool:
        for part in self.first_parts:
            if part.inline_data and "audio" in part.inline_data.mime_type:
                return True

    @cached_property
    def audio_file(self) -> io.BytesIO | None:
        if not self.audio:
            return

        for part in self.first_parts:
            if part.inline_data and "audio" in part.inline_data.mime_type:
                return save_wave_file(part.inline_data.data)

    @property
    def all_audio_files(self) -> Generator[io.BytesIO, None, None]:
        for part in self.first_parts:
            if part.inline_data and "audio" in part.inline_data.mime_type:
                yield save_wave_file(part.inline_data.data)
        return None

    @cached_property
    def function_call(self) -> bool:
        for part in self.first_parts:
            if part.function_call:
                return True
        else:
            return False

    @cached_property
    def thought_signature_part(self) -> types.Part:
        for part in self.first_parts:
            if part.thought_signature is not None:
                return part

    def quoted_text(self, quote_mode: ParseMode | None = ParseMode.MARKDOWN) -> str:
        if self.is_empty:
            return self.failed_str
        return wrap_in_quote(text=self.text, mode=quote_mode)

    def text_with_sources(self, quote_mode: ParseMode = ParseMode.MARKDOWN) -> str:
        if self.is_empty:
            return self.failed_str

        try:
            if chunks := self.first_candidate.grounding_metadata.grounding_chunks:
                hrefs = [f"[{chunk.web.title}]({chunk.web.uri})" for chunk in chunks]
                sources = "\n\nSources: " + " | ".join(hrefs)
                final_text = self.text.strip() + sources
                return wrap_in_quote(text=final_text, mode=quote_mode)

            else:
                return self.quoted_text(quote_mode=quote_mode)

        except (AttributeError, TypeError):
            return self.quoted_text(quote_mode=quote_mode)

    async def execute_function_call(self):
        if not self.function_call:
            return []

        function_responses = []

        # if self.thought_signature_part:
        #    function_responses.append(self.thought_signature_part)

        for part in self.first_parts:
            if part.function_call is None:
                continue

            call = part.function_call
            LOGGER.info(call)

            if call.name in FUNCTION_CALL_MAP:
                try:
                    function = FUNCTION_CALL_MAP[call.name]
                    output = await run_unknown_callable(function, **call.args)
                    result = {"output": output}
                except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
                    raise
                except Exception as e:
                    LOGGER.error(e, exc_info=True)
                    result = {"error": f"Error occurred while running function: {e}"}

            else:
                result = {"error": "Error: Function not found in backend function maps."}

            function_response = types.FunctionResponse(id=call.id, name=call.name, response=result)
            function_responses.append(types.Part(function_response=function_response))

        return function_responses


def get_retry_delay(response_json: dict) -> float:
    error = response_json.get("error", {})
    details = error.get("details", [])
    for err in details:
        if err.get("@type").endswith("RetryInfo"):
            return float(err["retryDelay"].strip("s"))
    else:
        return 0


async def loop_until_sent(chat, parts: list[types.Part], tg_convo, max_retries: int = 10):
    retries = 0
    while retries < max_retries:
        try:
            return Response(await chat.send_message(message=parts))
        except ClientError as e:
            delay = get_retry_delay(e.details)
            if not delay:
                raise
            await tg_convo.send_message(f"Gemini API returned flood wait of {delay}s sleeping...")
            await asyncio.sleep(delay + 10)
        retries += 1
    else:
        raise OverflowError(f"Max number of retries reached: {retries}")


async def execute_and_send_function_call(chat, tg_convo, ai_response):
    total_function_calls = 0

    while ai_response.function_call and total_function_calls < 10:
        parts = await ai_response.execute_function_call()

        ai_response = await loop_until_sent(chat=chat, parts=parts, tg_convo=tg_convo)

        if not ai_response.function_call and ai_response.first_candidate.finish_reason:
            return ai_response

        total_function_calls += 1

        LOGGER.info(f"{total_function_calls=}")
    else:
        raise OverflowError(f"Max number of function calls reached: {total_function_calls}")


async def export_history(chat: AsyncChat, message: Message, name: str = None, caption: str = None):
    doc = io.BytesIO(pickle.dumps(chat.get_history(curated=True)))
    doc.name = name or "AI_Chat_History.pkl"
    if caption is None:
        Response(await chat.send_message("Summarize our Conversation into one line.")).quoted_text()
    await message._client.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
