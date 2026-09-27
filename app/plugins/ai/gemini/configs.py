import logging
import platform
import sysconfig
from collections.abc import Callable

import pyrogram
from google.genai import types
from pydantic import BaseModel, Field
from ub_core.version import __version__

from app.plugins.ai.gemini.models import Models
from app.plugins.ai.gemini.response import FUNCTION_CALL_MAP

logging.getLogger("google_genai.models").setLevel(logging.WARNING)


class Instructions:
    SYSTEM = """\
- Be concise and precise by default. Answer briefly unless the user explicitly asks for more details.
- Avoid greetings, filler, or opinionated language. Follow the user's requested format exactly.
"""

    CODE_QUERY = """\
ENVIRONMENT
- Python: {platform.python_version()}
- ub_core: {__version__}

PRE CODE GENERATION STEPS:
    CODEBASE FILE STORE:
    - Ensure it's present and has files in it otherwise error out early and instruct user to check '.help csync'.
    - if ub_core version in system prompt > ub_core version from FILE_STORE: instruct user to run '.csync -c' 
    - Study all files from ub_core in depth to understand code structure, functions and usage.
    - When possible prefer using existing structures over creating new code. 
    - app is the bot i,e the main entry point. it is based on ub_core.
    - study app/plugins roughly to understand how ub_ore is actually used in real world.
    - you will be generating code for a new plugin in app/plugins.

CODE OUTPUT CONSTRAINTS:
- Only valid Python code
- No comments
- No explanations
- No markdown
- No extra text
- No excessive error handling
"""

    CODE_GENERATION = f"""\
You generate Python code for a Telegram bot project built on ub_core over pyrotgfork (a pyrogram fork).

ENVIRONMENT
- Python: {platform.python_version()}
- pyrotgfork: {pyrogram.__version__}
- ub_core: {__version__}
- site-packages: {sysconfig.get_path("purelib")}

PRE CODE GENERATION STEPS:
    CODEBASE FILE STORE:
        - Ensure it's present and has files in it otherwise error out early.
        - if ub_core version in system prompt > ub_core version from FILE_STORE: instruct user to run '.csync -c' 
        - Study all files from ub_core in depth to understand code structure, functions and usage.
        - When possible prefer using existing structures over creating new code. 
        - app is the bot i,e the main entry point. it is based on ub_core.
        - study app/plugins roughly to understand how ub_ore is actually used in real world.
        - you will be generating code for a new plugin in app/plugins.
        - do not include app/plugins in final file name.

    FUNCTIONS: get_site_package_tree and get_site_package_content
        - DO NOT call the functions for app and ub_core.
        - Call these ONLY when user requests you to study potential site-packages.

CODE OUTPUT CONSTRAINTS
- Only valid Python code
- No comments
- No explanations
- No markdown
- No extra text
- No excessive error handling
"""


SAFETY_SETTINGS = [
    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
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


class CodeResponseSchema(BaseModel):
    file_name: str = Field(description="full name with extension of the generated file ", default=None)
    file_content: str = Field(description="data to be written to file", default=None)
    response_text: str = Field(description="any non code text to be sent back on user request", default=None)
    error_text: str = Field(description="'Error: reason' incase of failure complying user-request", default=None)

    # python_code_to_exec: str = Field(description="[Optional] python code to run live in current env.", default=None)
    # shell_code_to_exec: str = Field(description="[Optional] shell code to run in ub_core.utils.run_shell_cmd", default=None)


class Tools:
    TEXT = types.Tool()
    SEARCH = dict(google_search=types.GoogleSearch(), url_context=types.UrlContext())
    CODE_FUNCTION_DECLARATIONS = types.Tool(function_declarations=[])
    CODE = types.Tool()


class AIConfig:
    TEXT = types.GenerateContentConfig(
        candidate_count=1,
        # max_output_tokens=1024,
        response_modalities=["Text"],
        system_instruction=Instructions.SYSTEM,
        temperature=0.69,
        tools=[Tools.TEXT],
    )

    IMAGE = types.GenerateContentConfig(
        candidate_count=1,
        # max_output_tokens=1024,
        response_modalities=["Text", "Image"],
        # system_instruction=SYSTEM_INSTRUCTION,
        temperature=0.99,
    )

    AUDIO = types.GenerateContentConfig(
        temperature=1, response_modalities=["audio"], speech_config=FEMALE_SPEECH_CONFIG
    )

    CODE = types.GenerateContentConfig(
        candidate_count=1,
        # max_output_tokens=1024,
        response_modalities=["Text"],
        system_instruction=Instructions.CODE_QUERY,
        temperature=0.69,
        tools=[Tools.CODE],
    )

    CODE_GENERATION = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        candidate_count=1,
        response_schema=CodeResponseSchema,
        response_mime_type="application/json",
        response_modalities=["Text"],
        system_instruction=Instructions.CODE_GENERATION,
        temperature=1,
        tools=[Tools.CODE, Tools.CODE_FUNCTION_DECLARATIONS],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="VALIDATED"),
            include_server_side_tool_invocations=True,
        ),
    )


def get_model_config(flags: list[str]) -> dict:
    if "-i" in flags:
        return {"model": Models.IMAGE_MODEL, "config": AIConfig.IMAGE}

    if "-a" in flags:
        audio_config = AIConfig.AUDIO

        if "-m" in flags:
            audio_config.speech_config = MALE_SPEECH_CONFIG
        else:
            audio_config.speech_config = FEMALE_SPEECH_CONFIG

        return {"model": Models.AUDIO_MODEL, "config": audio_config}

    if "-sp" in flags:
        AIConfig.AUDIO.speech_config = MULTI_SPEECH_CONFIG
        return {"model": Models.AUDIO_MODEL, "config": AIConfig.AUDIO}

    for k, v in Tools.SEARCH.items():
        if "-s" in flags:
            setattr(Tools.TEXT, k, v)
        else:
            setattr(Tools.TEXT, k, None)

    return {"model": Models.TEXT_MODEL, "config": AIConfig.TEXT}


def declare_in_tool(tools_list: list[list]):

    def drop_old_declaration(defs: list, fdef: types.FunctionDeclaration):
        defs[:] = [f for f in defs if isinstance(f, types.FunctionDeclaration) and f.name != fdef.name]

    def declare(func: Callable):
        FUNCTION_CALL_MAP[func.__name__] = func

        declaration = types.FunctionDeclaration.from_callable_with_api_option(api_option="GEMINI_API", callable=func)

        for func_defs in tools_list:
            drop_old_declaration(func_defs, declaration)
            func_defs.append(declaration)

        return func

    return declare
