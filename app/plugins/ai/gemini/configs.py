import logging
import platform
from collections.abc import Callable

import pyrogram
from google.genai import types

from app.plugins.ai.gemini.models import Models
from app.plugins.ai.gemini.response import FUNCTION_CALL_MAP

logging.getLogger("google_genai.models").setLevel(logging.WARNING)


SYSTEM_INSTRUCTION = """Be concise and precise by default. Answer briefly unless the user explicitly asks for more detail.
When the user requests code:
    - output only the requested code. Do not add comments, explanations, or surrounding prose unless explicitly asked.
    - if codebase index of ub-core and plain-ub is present in context use that as reference for output.
Avoid greetings, filler, or opinionated language. Follow the user's requested format exactly."""

CODE_INSTRUCTION = f"""You are a Python code-generation assistant for a Telegram bot project built with Pyrogram.

ENVIRONMENT

- Python version: {platform.python_version()}.
- Installed Pyrogram version: {pyrogram.__version__}.

CONTEXT ACQUISITION RULES

- On the initial user message, a codebase file will be provided.
- Treat the resolved codebase contents as definitive for:
  - file structure and module layout
  - naming conventions
  - import ordering
  - typing and annotation style
  - docstring and comment style
  - async vs sync patterns
  - error handling and logging conventions

PYROGRAM RULES

- If the installed Pyrogram version is newer than your training cutoff or you are uncertain about any API detail, call get_pyro_file_contents() before generating code.
- Request only the specific Pyrogram source files required for the exact methods or classes you will use.
- File requests must use the exact absolute paths defined in the Pyrogram path section of the codebase file.
- Do not construct, infer, normalize, or convert paths.
- Do not use relative paths.
- Do not request entire modules or unrelated files.
- Use retrieved source only to verify method signatures, parameter names, return types, and correct usage patterns.

CODE GENERATION RULES

- Reuse existing project abstractions and helpers where appropriate.
- Match the project’s formatting and structural patterns exactly.
- Produce only valid, runnable Python code compatible with the installed Python and Pyrogram versions.
- Include comments only if they match the project’s existing comment style and are necessary.
- Do not include:
  - explanations
  - markdown or HTML wrappers
  - code fences
  - metadata
  - logs
  - tool outputs
  - debug traces
  - any surrounding commentary
- Telegram message formatting (e.g., Markdown or HTML) is allowed only inside Python string literals where required by the bot logic.

OUTPUT FORMAT (STRICT)

- Line 1: filename in snake_case
- Line 2 onward: complete Python file contents
- No extra text before or after
- No blank line before the filename
- No excessive comments
- No trailing commentary after the file content
- No markdown or external formatting wrappers

OPERATIONAL CONSTRAINTS

- All reasoning and tool usage must remain internal.
- The assistant must interpret the codebase from the supplied file.
- If required API or context details are missing, call the appropriate tool(s) before emitting code.
- If required context is missing, do not guess the codebase structure.
- If the request cannot be satisfied under these constraints, return exactly:
  ERROR: <reason>
- If the codebase file is missing, return exactly:
  ERROR: <reason>
"""

SAFETY_SETTINGS = [
    # SafetySetting(category="HARM_CATEGORY_UNSPECIFIED", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
    types.SafetySetting(category="HARM_CATEGORY_CIVIC_INTEGRITY", threshold="BLOCK_NONE"),
]

MALE_SPEECH_CONFIG = types.SpeechConfig(
    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck"))
)

FEMALE_SPEECH_CONFIG = types.SpeechConfig(
    voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore"))
)


MULTI_SPEECH_CONFIG = types.SpeechConfig(
    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
        speaker_voice_configs=[
            types.SpeakerVoiceConfig(
                speaker="John",
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Kore")),
            ),
            types.SpeakerVoiceConfig(
                speaker="Jane",
                voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")),
            ),
        ]
    )
)

SEARCH_TOOLS = [types.Tool(google_search=types.GoogleSearch()), types.Tool(url_context=types.UrlContext())]


class AIConfig:
    TEXT_CONFIG = types.GenerateContentConfig(
        candidate_count=1,
        # max_output_tokens=1024,
        response_modalities=["Text"],
        system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.69,
        tools=[],
    )

    IMAGE_CONFIG = types.GenerateContentConfig(
        candidate_count=1,
        # max_output_tokens=1024,
        response_modalities=["Text", "Image"],
        # system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.99,
    )

    AUDIO_CONFIG = types.GenerateContentConfig(
        temperature=1, response_modalities=["audio"], speech_config=FEMALE_SPEECH_CONFIG
    )

    CODE_CONFIG = types.GenerateContentConfig(
        candidate_count=1,
        response_modalities=["Text"],
        system_instruction=CODE_INSTRUCTION,
        temperature=0.69,
        tools=[],
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="AUTO")),
    )


def get_model_config(flags: list[str]) -> dict:
    if "-i" in flags:
        return {"model": Models.IMAGE_MODEL, "config": AIConfig.IMAGE_CONFIG}

    if "-a" in flags:
        audio_config = AIConfig.AUDIO_CONFIG

        if "-m" in flags:
            audio_config.speech_config = MALE_SPEECH_CONFIG
        else:
            audio_config.speech_config = FEMALE_SPEECH_CONFIG

        return {"model": Models.AUDIO_MODEL, "config": audio_config}

    if "-sp" in flags:
        AIConfig.AUDIO_CONFIG.speech_config = MULTI_SPEECH_CONFIG
        return {"model": Models.AUDIO_MODEL, "config": AIConfig.AUDIO_CONFIG}

    update_search_tools_in_place(add="-s" in flags, config_tools=AIConfig.TEXT_CONFIG.tools)

    return {"model": Models.TEXT_MODEL, "config": AIConfig.TEXT_CONFIG}


def update_search_tools_in_place(add: bool, config_tools: list):
    for tool in SEARCH_TOOLS:
        if add:
            if tool not in config_tools:
                config_tools.append(tool)
        elif tool in config_tools:
            config_tools.remove(tool)


def declare_in_tools(tools_list: list[list]):
    def declare(func: Callable):
        FUNCTION_CALL_MAP[func.__name__] = func
        func_tool = types.FunctionDeclaration.from_callable_with_api_option(api_option="GEMINI_API", callable=func)

        for tools in tools_list:
            if func_tool not in tools:
                tools.append(types.Tool(function_declarations=[func_tool]))

        return func

    return declare
