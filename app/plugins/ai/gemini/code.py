import asyncio
import io
import pathlib
import sysconfig

from ub_core import BOT, Message
from ub_core.utils.helpers import wrap_in_block_quote

from app.plugins.ai.gemini import Models, async_client, configs, response
from app.plugins.ai.gemini.code_sync import get_codebase_store
from app.plugins.ai.gemini.utils import create_prompts, run_basic_check

SITE_PACKAGES = pathlib.Path(sysconfig.get_path("purelib")).resolve()


REPLY_NOTICE = "\n**>Reply to this message to make changes...<**\n**>Reply with q to stop.<**"


@BOT.add_cmd("acode")
@run_basic_check
async def create_plugin(bot: BOT, message: Message, history=None):
    """
    CMD: AI CODE
    INFO: Generates code for the userbot based on existing codebase
    USAGE: .aicode create a plugin ...
    """
    if not get_codebase_store().active_documents_count:
        await message.reply("Codebase store not synced!\nCheck .help csync")
        return

    chat = async_client.chats.create(model=Models.CODE_MODEL, config=configs.AIConfig.CODE_GENERATION, history=history)
    prompts = await create_prompts(message, is_chat=False)

    async with bot.Convo(
        chat_id=message.chat.id, client=bot, from_user=message.from_user.id, reply_to_user_id=bot.me.id, timeout=300
    ) as tg_convo:
        name = None
        try:
            while True:
                ai_response = await response.loop_until_sent(chat=chat, parts=prompts, tg_convo=tg_convo)

                if ai_response.function_call:
                    ai_response = await response.execute_and_send_function_call(chat, tg_convo, ai_response)

                data = configs.CodeResponseSchema.model_validate_json(ai_response.text)

                if data.file_name and data.file_content:
                    name = data.file_name
                    file = io.BytesIO(data.file_content.encode())
                    file.name = name
                    await tg_convo.send_document(file, caption=REPLY_NOTICE)

                text = ""

                if data.error_text:
                    text += wrap_in_block_quote(data.error_text, expandable=True)

                if data.response_text:
                    text += wrap_in_block_quote(data.response_text, expandable=True)

                if text:
                    await tg_convo.send_message(text=text + REPLY_NOTICE)

                try:
                    user_response: Message = await tg_convo.get_response()
                except TimeoutError:
                    break

                if user_response.content.lower() in ("q", "exit", "quit"):
                    await user_response.reply("Exited...")
                    break

                prompts = await create_prompts(message=user_response, is_chat=True)

                await asyncio.sleep(10)

        finally:
            await response.export_history(
                chat=chat, message=message, name=f"{name}_chat_history.pkl", caption=name or "acode"
            )


@configs.declare_in_tool(tools_list=[configs.Tools.CODE_FUNCTION_DECLARATIONS.function_declarations])
async def get_site_package_tree(module: str = None, recursive: bool = False) -> str:
    """
    Returns a string of site-packages or a module's file tree

    params:
        module: optional param to get tree for a specific module
        recursive: if true get all files else get top level files and dir tree
    examples:
        get_site_package_tree("requests", recursive=True) # get full tree for requests module
        get_site_package_tree(recursive=False) # get list of installed packages in site-packages
    """
    path = SITE_PACKAGES / module if module else SITE_PACKAGES
    tree = path.rglob("*") if recursive else path.glob("*")
    filtered = filter(lambda p: "__pycache__" not in p.as_posix(), tree)
    return "\n".join(str(t.relative_to(SITE_PACKAGES)) for t in filtered)


@configs.declare_in_tool(tools_list=[configs.Tools.CODE_FUNCTION_DECLARATIONS.function_declarations])
async def get_site_package_contents(file_paths: list[str]) -> str:
    """
    Reads contents of one or more site-package files and returns data (merged if multiple paths)

    params:
        file_paths: list of absolute unix paths i.e (site-package/module...) to read from

    """
    file_paths = [pathlib.Path(f).resolve() for f in file_paths]

    contents = []

    for file in file_paths:
        contents.append(f"\n ### {file.as_posix()} ### \n")

        if file.is_relative_to(SITE_PACKAGES):
            contents.append(shrink_file(file, comments=True, de_indent=False))
        else:
            contents.append(
                f"Error: path {file.as_posix()} is not relative to {SITE_PACKAGES.as_posix()}: Access denied."
            )

    return "".join(contents)


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
