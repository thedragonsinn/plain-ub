import logging

from google.genai import types
from ub_core import CustomDB

logging.getLogger("google_genai.models").setLevel(logging.WARNING)

DB_SETTINGS = CustomDB["COMMON_SETTINGS"]


async def init_task():
    model_info = await DB_SETTINGS.find_one({"_id": "gemini_model_info"}) or {}
    if model_name := model_info.get("model_name"):
        AIConfig.TEXT_MODEL = model_name
    if image_model := model_info.get("image_model_name"):
        AIConfig.IMAGE_MODEL = image_model


SAFETY_SETTINGS = [
    # SafetySetting(category="HARM_CATEGORY_UNSPECIFIED", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
]

SEARCH_TOOL = types.Tool(
    google_search=types.GoogleSearchRetrieval(
        dynamic_retrieval_config=types.DynamicRetrievalConfig(dynamic_threshold=0.3)
    )
)

SYSTEM_INSTRUCTION = (
    "Answer precisely and in short unless specifically instructed otherwise."
    "\nIF asked related to code, do not comment the code and do not explain the code unless instructed."
)

MALE_SPEECH_CONFIG = types.SpeechConfig(
    voice_config=types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
    )
)

FEMALE_SPEECH_CONFIG = types.SpeechConfig(
    voice_config=types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")
    )
)


MULTI_SPEECH_CONFIG = types.SpeechConfig(
    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=[
            types.SpeakerVoiceConfig(
                speaker="John",
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore",
                    )
                ),
            ),
            types.SpeakerVoiceConfig(
                speaker="Jane",
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Puck",
                    )
                ),
            ),
        ]
    )
)


class AIConfig:
    TEXT_MODEL = "gemini-2.0-flash"

    TEXT_CONFIG = types.GenerateContentConfig(
        candidate_count=1,
        # max_output_tokens=1024,
        response_modalities=["Text"],
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.69,
        tools=[],
    )

    IMAGE_MODEL = "gemini-2.0-flash-exp"

    IMAGE_CONFIG = types.GenerateContentConfig(
        candidate_count=1,
        # max_output_tokens=1024,
        response_modalities=["Text", "Image"],
        # system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.99,
    )

    AUDIO_MODEL = "gemini-2.5-flash-preview-tts"
    AUDIO_CONFIG = types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=FEMALE_SPEECH_CONFIG,
    )

    @staticmethod
    def get_kwargs(flags: list[str]) -> dict:
        if "-i" in flags:
            return {"model": AIConfig.IMAGE_MODEL, "config": AIConfig.IMAGE_CONFIG}

        if "-a" in flags:
            audio_config = AIConfig.AUDIO_CONFIG

            if "-m" in flags:
                audio_config.speech_config = MALE_SPEECH_CONFIG
            else:
                audio_config.speech_config = FEMALE_SPEECH_CONFIG

            return {"model": AIConfig.AUDIO_MODEL, "config": audio_config}

        if "-sp" in flags:
            AIConfig.AUDIO_CONFIG.speech_config = MULTI_SPEECH_CONFIG
            return {"model": AIConfig.AUDIO_MODEL, "config": AIConfig.AUDIO_CONFIG}

        tools = AIConfig.TEXT_CONFIG.tools

        use_search = "-s" in flags

        if not use_search and SEARCH_TOOL in tools:
            tools.remove(SEARCH_TOOL)

        if use_search and SEARCH_TOOL not in tools:
            tools.append(SEARCH_TOOL)

        return {"model": AIConfig.TEXT_MODEL, "config": AIConfig.TEXT_CONFIG}
