import asyncio
import io
import os
import pathlib

import pyrogram
from google.genai.types import File, Part
from ub_core import BOT, LOGGER, Message, ub_core_dirname
from ub_core.utils import MediaExtensions

from app import extra_config
from app.plugins.ai.gemini import (
    AIConfig,
    Models,
    async_client,
    declare_in_tools,
    export_history,
    send_message_with_retry_delay_guard,
    utils,
)

PYRO_PATH = pathlib.Path(os.path.dirname(pyrogram.__file__)).resolve()

CODEBASE_PATHS = [pathlib.Path(ub_core_dirname).resolve(), pathlib.Path("app").resolve()]
EXTRA_MODULES = pathlib.Path("app/modules").resolve()

if extra_config.INDEX_EXTRA_MODULES:
    CODEBASE_PATHS.append(EXTRA_MODULES)

CODEBASE_INDEX_FILE = None


def replace_indents(line: str, char: str = "@") -> str:
    de_indented_line = line.lstrip(" ")
    total_indents = len(line) - len(de_indented_line)
    return char * total_indents + de_indented_line.rstrip()


def shrink_indents(line: str, size: int = 4, char="@") -> str:
    indents = len(line) - len(line.lstrip(" "))
    if indents == 0:
        return line.strip()
    depth = (indents + size - 1) // size
    return char * depth + line.strip()


def shrink_file(
    file: pathlib.Path,
    comments: bool = False,
    de_indent: bool = False,
    indent_size: int = 4,
    replace_indent: bool = True,
) -> str:
    parts = []
    for line in file.read_text(encoding="utf-8", errors="ignore").splitlines():
        _line = line.strip()

        if not _line:
            continue

        if comments and _line.startswith("#"):
            continue

        if de_indent:
            line = shrink_indents(line, size=indent_size)
        elif replace_indent:
            line = replace_indents(line)

        parts.append(line)

    return "\n".join(parts)


@declare_in_tools(tools_list=[AIConfig.CODE_CONFIG.tools])
def get_pyro_file_contents(file_paths: list[str]) -> str:
    """
    Reads the contents of multiple pyrogram files and returns their combined contents as a single string.

    params:
        file_paths: a list of absolute paths to pyrogram installation dir.
    """

    file_paths = [pathlib.Path(file_path).resolve() for file_path in file_paths]
    contents = []

    for file in file_paths:
        if file.is_relative_to(PYRO_PATH):
            contents.append(shrink_file(file, comments=True, de_indent=True))
        else:
            contents.append(f"Error: path {file} is not relative to {PYRO_PATH}: Access denied.")
        contents.append(f"\n ### {file.name} ### \n")

    return "".join(contents)


async def upload_codebase(refresh: bool = False) -> File:
    """
    info:
        Upload project context to file storage
    args:
        refresh: set to True to force re-upload of context.
    returns:
        uploaded file
    """
    global CODEBASE_INDEX_FILE

    if CODEBASE_INDEX_FILE and not refresh:
        return CODEBASE_INDEX_FILE

    codebase_parts = []

    for root in CODEBASE_PATHS:
        for file in sorted(root.rglob("*")):
            file = file.resolve()

            if not file.is_file():
                continue

            if not extra_config.INDEX_EXTRA_MODULES and file.is_relative_to(EXTRA_MODULES):
                continue

            if file.suffix in MediaExtensions.CODE:
                try:
                    codebase_parts.append(shrink_file(file))
                except Exception as e:
                    codebase_parts.append(str(e))

                codebase_parts.append(f"\n##### {file} #####\n")

    codebase_parts.append(f"\n\n\nPyrogram file path tree:\n{sorted(PYRO_PATH.rglob('*py'))}")

    joined_codebase = "".join(codebase_parts)

    codebase = io.BytesIO(bytes(joined_codebase, encoding="utf-8"))
    codebase.name = "codebase_index.txt"

    CODEBASE_INDEX_FILE = await utils.upload_file(codebase, codebase.name)

    LOGGER.info(f"Codebase indexed successfully: {len(joined_codebase)}")
    return CODEBASE_INDEX_FILE


@BOT.add_cmd("acode")
@utils.run_basic_check
async def create_plugin(bot: BOT, message: Message, history=None):
    """
    CMD: AI CODE
    INFO: Generates code for the userbot based on existing codebase
    USAGE: .aicode create a plugin ...
    """
    chat = async_client.chats.create(model=Models.CODE_MODEL, config=AIConfig.CODE_CONFIG, history=history)
    prompts = await utils.create_prompts(message, is_chat=True)

    if history is None:
        await message.reply("`Generating plugin...`")
        context_file = await upload_codebase()
        prompts.append(Part.from_uri(file_uri=context_file.uri, mime_type=context_file.mime_type))

    async with bot.Convo(
        chat_id=message.chat.id, client=bot, from_user=message.from_user.id, reply_to_user_id=bot.me.id, timeout=300
    ) as tg_convo:
        name = ai_response = None
        try:
            while True:
                ai_response = await send_message_with_retry_delay_guard(chat, ai_response, prompts, tg_convo)

                if ai_response.text.startswith("ERROR:"):
                    await tg_convo.send_message(
                        f"{ai_response.quoted_text()}"
                        f"\n**>Reply to this message to make changes...<**"
                        f"\n**>Reply with `q` to stop.<**"
                    )

                else:
                    name, code = ai_response.text.split("\n", maxsplit=1)
                    file = io.BytesIO(bytes(code, encoding="utf-8"))
                    file.name = name
                    await tg_convo.send_document(
                        file, caption="**>Reply to this message to make changes...<**\n**>Reply with q to stop.<**"
                    )

                try:
                    user_response: Message = await tg_convo.get_response()
                except TimeoutError:
                    break

                user_response_text = user_response.content

                if user_response_text and user_response_text.lower() in ("q", "exit", "quit"):
                    await user_response.reply("Exited...")
                    break

                prompts = []

                if user_response.media:
                    uploaded_file = await utils.upload_tg_file(message=message)
                    prompts.append(Part.from_uri(file_uri=uploaded_file.uri, mime_type=uploaded_file.mime_type))

                if user_response.text:
                    prompts.append(Part.from_text(text=str(user_response_text)))

                await asyncio.sleep(15)

        finally:
            await export_history(chat=chat, message=message, name=f"{name}_chat_history.pkl", caption=name)
