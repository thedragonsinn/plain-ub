import ast
import io
import pathlib

from google.genai.types import File
from ub_core import BOT, LOGGER, Message, ub_core_dirname
from ub_core.utils import MediaExtensions, bytes_to_mb

from app import extra_config
from app.plugins.ai.gemini import async_client, utils


CODEBASE_PATHS = [pathlib.Path(ub_core_dirname).resolve(), pathlib.Path("app").resolve()]
EXTRA_MODULES = pathlib.Path("app/modules").resolve()

if extra_config.INDEX_EXTRA_MODULES:
    CODEBASE_PATHS.append(EXTRA_MODULES)

CODEBASE_INDEX_FILE = None


def shrink_file(file: pathlib.Path, strip_comments: bool = False) -> str:
    """Read a file and return its content with blank lines removed."""
    parts = []
    for line in file.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if strip_comments and stripped.startswith("#"):
            continue

        parts.append(line.rstrip())

    return "\n".join(parts)


def extract_and_strip_imports(code: str) -> tuple[str, list]:
    """
    Strips top-level imports from a file and returns the clean code
    along with a list of the imports found.
    Handles both single-line and multi-line parenthesis imports.
    """
    lines = code.splitlines()
    output = []
    imports = []

    in_import_parens = False
    current_import = []

    for line in lines:
        if in_import_parens:
            current_import.append(line)
            if ")" in line.split("#")[0]:
                in_import_parens = False
                imports.append("\n".join(current_import))
                current_import = []
            continue

        if line.startswith("import ") or line.startswith("from "):
            code_part = line.split("#")[0]
            if "(" in code_part and ")" not in code_part:
                in_import_parens = True
                current_import.append(line)
            else:
                imports.append(line)
            continue

        output.append(line)

    return "\n".join(output), imports


def merge_imports(imports_list: set) -> str:
    """
    Parses a set of import statements and merges them by module.
    e.g. `from X import A` and `from X import B` becomes `from X import (A, B)`.
    """
    source = "\n".join(imports_list)
    try:
        tree = ast.parse(source)
    except Exception:
        return "\n".join(sorted(imports_list))

    import_modules = set()
    from_imports = {}

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if alias.asname:
                    name += f" as {alias.asname}"
                import_modules.add(name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level > 0:
                module = "." * node.level + module

            if module not in from_imports:
                from_imports[module] = set()

            for alias in node.names:
                name = alias.name
                if alias.asname:
                    name += f" as {alias.asname}"
                from_imports[module].add(name)

    output_lines = []

    for mod in sorted(import_modules):
        output_lines.append(f"import {mod}")

    for mod, names in sorted(from_imports.items()):
        sorted_names = sorted(names)
        if "*" in sorted_names:
            output_lines.append(f"from {mod} import *")
            continue

        if len(sorted_names) == 1:
            output_lines.append(f"from {mod} import {sorted_names[0]}")
        else:
            names_str = ",\n    ".join(sorted_names)
            output_lines.append(f"from {mod} import (\n    {names_str}\n)")

    return "\n".join(output_lines)


def build_codebase_index() -> str:
    """
    Builds a structured codebase index string with XML tags per file
    and deduplicated global imports at the top.
    """
    global_imports = set()
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
                    rel_path = str(file.relative_to(root))
                except ValueError:
                    rel_path = file.name

                codebase_parts.append(f'<file path="{rel_path}">\n')

                try:
                    raw_content = shrink_file(file)
                    clean_content, file_imports = extract_and_strip_imports(raw_content)

                    global_imports.update(file_imports)
                    codebase_parts.append(clean_content)

                except Exception as e:
                    codebase_parts.append(f"Error reading file: {e}")

                codebase_parts.append("\n</file>\n\n")

    joined_global_imports = merge_imports(global_imports)

    return (
        "### Global Project Imports ###\n"
        f"{joined_global_imports}\n\n\n"
        "### Codebase Context ###\n"
        f"{''.join(codebase_parts)}"
    )


async def upload_codebase(refresh: bool = False) -> File:
    """
    info:
        Build structured codebase index and upload to file storage
    args:
        refresh: set to True to force re-upload of context.
    returns:
        uploaded file
    """
    global CODEBASE_INDEX_FILE

    if CODEBASE_INDEX_FILE and not refresh:
        try:
            await async_client.files.get(name=CODEBASE_INDEX_FILE.name)
            return CODEBASE_INDEX_FILE
        except Exception as e:
            LOGGER.error(f"Error accessing uploaded codebase file: {e}\nAuto Refreshing...")

    joined_codebase = build_codebase_index()

    codebase = io.BytesIO(bytes(joined_codebase, encoding="utf-8"))
    codebase.name = "codebase_index.txt"

    CODEBASE_INDEX_FILE = await utils.upload_file(codebase, codebase.name)

    LOGGER.info(
        f"Codebase indexed successfully: [{bytes_to_mb(len(codebase.getvalue()))} MBs] [{len(joined_codebase)} chars]"
    )
    return CODEBASE_INDEX_FILE


@BOT.add_cmd("ucb")
async def upload_codebase_cmd(bot: BOT, message: Message):
    """
    CMD: UCB
    INFO: Indexes the codebase and uploads it directly to the current Telegram chat.
    Does not use Gemini Files API.
    """
    edit_msg = await message.reply("`Indexing codebase...`")

    final_output = build_codebase_index()

    codebase = io.BytesIO(bytes(final_output, encoding="utf-8"))
    codebase.name = "codebase_index.txt"

    await message.reply_document(
        document=codebase,
        caption=f"**Codebase Index Executed**\n"
        f"Size: `{bytes_to_mb(len(codebase.getvalue()))} MB`\n"
        f"Chars: `{len(final_output)}` output",
    )
    await edit_msg.delete()
    LOGGER.info(f"Codebase indexed successfully and sent to {message.chat.id}")
