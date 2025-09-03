import io
import logging
import wave

import numpy as np
from google.genai.client import AsyncClient, Client
from google.genai.types import GenerateContentResponse
from pyrogram.enums import ParseMode

from app import CustomDB, extra_config

logging.getLogger("google_genai.models").setLevel(logging.WARNING)

DB_SETTINGS = CustomDB["COMMON_SETTINGS"]

try:
    client: Client | None = Client(api_key=extra_config.GEMINI_API_KEY)
    async_client: AsyncClient | None = client.aio
except:
    client = async_client = None


class Response:
    def __init__(self, ai_response: GenerateContentResponse):
        self._ai_response = ai_response

        self.first_candidate = None
        self.first_content = None
        self.first_parts = []

        if ai_response.candidates:
            self.first_candidate = ai_response.candidates[0]
            if self.first_candidate.content:
                self.first_content = self.first_candidate.content
                if self.first_content.parts:
                    self.first_parts = self.first_content.parts

        for part in self.first_parts:
            if part.inline_data:
                self._inline_data = part.inline_data
                break
        else:
            self._inline_data = None

        self.is_empty = not self.first_parts
        self.failed_str = "`Error: Query Failed.`"

    def wrap_in_quote(self, text: str, mode: ParseMode = ParseMode.MARKDOWN):
        _text = text.strip()
        match mode:
            case ParseMode.MARKDOWN:
                return _text if "```" in _text else f"**>\n{_text}<**"
            case ParseMode.HTML:
                return f"<blockquote expandable=true>{_text}</blockquote>"
            case _:
                return _text

    @property
    def _text(self) -> str:
        return "\n".join(part.text for part in self.first_parts if isinstance(part.text, str))

    def text(self, quote_mode: ParseMode | None = ParseMode.MARKDOWN) -> str:
        if self.is_empty:
            return self.failed_str
        return self.wrap_in_quote(text=self._text, mode=quote_mode)

    def text_with_sources(self, quote_mode: ParseMode = ParseMode.MARKDOWN) -> str:
        if self.is_empty:
            return self.failed_str

        try:
            chunks = self.first_candidate.grounding_metadata.grounding_chunks
        except (AttributeError, TypeError):
            return self.text(quote_mode=quote_mode)

        hrefs = [f"[{chunk.web.title}]({chunk.web.uri})" for chunk in chunks]
        sources = "\n\nSources: " + " | ".join(hrefs)
        final_text = self._text.strip() + sources
        return self.wrap_in_quote(text=final_text, mode=quote_mode)

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

    @staticmethod
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

        waveform = bytes(
            [
                int(
                    min(
                        255,
                        np.abs(samples[i : i + chunk_size]).mean()
                        / (2 ** (8 * sample_width - 1))
                        * 255,
                    )
                )
                for i in range(0, len(samples), chunk_size)
            ]
        )

        waveform = waveform[:80]
        file.name = "audio.ogg"
        file.waveform = waveform
        file.duration = round(duration)

        return file

    @property
    def audio(self) -> bool:
        if self._inline_data and self._inline_data.mime_type:
            return "audio" in self._inline_data.mime_type
        return False

    @property
    def audio_file(self) -> io.BytesIO | None:
        inline_data = self._inline_data
        return self.save_wave_file(inline_data.data) if inline_data else None
