import asyncio
import io
import pickle
import wave
from collections.abc import Callable
from functools import cached_property

import numpy as np
from google.genai import types
from google.genai.chats import AsyncChat
from google.genai.errors import ClientError
from pyrogram.enums import ParseMode
from ub_core import LOGGER, CustomDB, Message, bot, utils

DB_SETTINGS = CustomDB["COMMON_SETTINGS"]

FUNCTION_CALL_MAP: dict[str, Callable] = {}


def wrap_in_quote(text: str, mode: ParseMode = ParseMode.MARKDOWN):
    _text = text.strip()
    match mode:
        case ParseMode.MARKDOWN:
            if "```" in _text:
                return _text
            else:
                return utils.wrap_in_block_quote(text=_text, quote_delimiter="**>", end_delimiter="<**")
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
        int(min(255,np.abs(samples[i : i + chunk_size]).mean() / (2 ** (8 * sample_width - 1)) * 255))
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

        for part in self.first_parts:
            if part.inline_data:
                self._inline_data = part.inline_data
                break
        else:
            self._inline_data = None

        self.is_empty = not self.first_parts
        self.failed_str = "`Error: Query Failed.`"

    @cached_property
    def text(self) -> str:
        return "\n".join(part.text for part in self.first_parts if isinstance(part.text, str))

    @property
    def image(self) -> bool:
        if self._inline_data and self._inline_data.mime_type:
            return "image" in self._inline_data.mime_type
        return False

    @property
    def image_file(self) -> io.BytesIO | None:
        inline_data = self._inline_data

        if inline_data:
            file = io.BytesIO(inline_data.data)
            file.name = "photo.png"
            return file

        return None

    @property
    def audio(self) -> bool:
        if self._inline_data and self._inline_data.mime_type:
            return "audio" in self._inline_data.mime_type
        return False

    @property
    def audio_file(self) -> io.BytesIO | None:
        inline_data = self._inline_data
        return save_wave_file(inline_data.data) if inline_data else None

    @property
    def function_call(self):
        return bool(self.first_part.function_call)

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
        call = self.first_part.function_call
        func_name = call.name

        LOGGER.info(call)

        if func_name in FUNCTION_CALL_MAP:
            try:
                result = await utils.run_unknown_callable(FUNCTION_CALL_MAP[func_name], **call.args)
            except Exception as e:
                LOGGER.error(e, exec_info=True)
                result = f"Error occurred while running function: {e}"

        else:
            result = "Error: Function not found in backend function map."

        return [self.first_part, types.Part.from_function_response(name=func_name, response={"result": result})]


async def send_message_with_retry_delay_guard(chat, response, parts, tg_convo) -> Response:
    max_calls = 0

    while max_calls < 10:
        try:
            if response and response.function_call:
                parts = await response.execute_function_call()

            response = Response(await chat.send_message(message=parts))

        except ClientError as e:
            delay = get_retry_delay(e.details)
            await tg_convo.send_message(f"Gemini API returned flood wait of {delay}s sleeping...")
            await asyncio.sleep(delay + 10)
            response = Response(await chat.send_message(message=parts))

        await asyncio.sleep(10)

        max_calls += 1

        if response.text:
            return response


def get_retry_delay(response_json: dict) -> float:
    error = response_json.get("error", {})
    details = error.get("details", [])
    for err in details:
        if err.get("@type").endswith("RetryInfo"):
            return float(err["retryDelay"].strip("s"))
    else:
        return 0


async def export_history(chat: AsyncChat, message: Message, name: str = None, caption: str = None):
    doc = io.BytesIO(pickle.dumps(chat.get_history(curated=True)))
    doc.name = name or "AI_Chat_History.pkl"
    if caption is None:
        Response(await chat.send_message("Summarize our Conversation into one line.")).quoted_text()
    await bot.send_document(chat_id=message.from_user.id, document=doc, caption=caption)
