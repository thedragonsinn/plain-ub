import asyncio
import pathlib
from functools import partial

import pathspec
from google.genai import types
from ub_core import BOT, LOGGER, Config, Message, ub_core_dir, utils

from app.plugins.ai.gemini import async_client, configs
from app.plugins.ai.gemini.file_store import delete_files, get_stores, upload_file_to_store

APP = Config.WORKING_DIR
CUR_DIR = pathlib.Path(".").resolve()

STORE_NAME = "App-and-UBCore-Codebase"
CODEBASE_FILES_STORE: types.FileSearchStore | None = None

ALLOWED_EXT = tuple(utils.MediaExtensions.CODE)


def get_codebase_store():
    global CODEBASE_FILES_STORE
    return CODEBASE_FILES_STORE


async def init_task():
    async for store in get_stores():
        if store.display_name == STORE_NAME:
            _store = store
            break
    else:
        _store = await async_client.file_search_stores.create(
            config=types.CreateFileSearchStoreConfig(display_name=STORE_NAME)
        )

    global CODEBASE_FILES_STORE
    CODEBASE_FILES_STORE = _store
    configs.Tools.CODE.file_search = types.FileSearch(file_search_store_names=[_store.name])


@BOT.add_cmd("csync")
async def sync_codebase(bot: BOT, message: Message):
    """
    CMD: CODEBASE SYNC [code files only]
    INFO: uploads specified file or dir to gemini file store
    FLAGS:
        -c to sync core
        -nf don't filter .gitignore or filename filters
    USAGE:
        .csync app/ [syncs everything in app/]
        .csync app/plugins/files/download.py [syncs only this file]
        .csync scripts/ [syncs everything in ./scripts]
        .csync -c [syncs core]

    NOTE: Recomended to sync core first then app
    """
    global CODEBASE_FILES_STORE

    if "-c" in message.flags:
        path = ub_core_dir
    else:
        path_str = message.input.strip()

        if not path_str:
            await message.reply("Give a valid path to sync.")
            return

        path = pathlib.Path(path_str).resolve()

        if not path.exists() or path.stat().st_size == 0:
            await message.reply(f"Path: `{path_str}` doesn't exist or is empty!")
            return

    reply = await message.reply("`Scanning input...`")

    total = 0

    if path.is_dir():
        total_files = await get_files_to_sync(path, "-nf" not in message.flags)
        _files = "\n".join([f.relative_to(path.parent).as_posix() for f in total_files])

        await reply.edit(f"Found {len(total_files)} files.\n<pre language=sh>{_files}</pre>")
        await message.reply("Reply `y` to continue...")

        choice, _ = await message.get_response(from_user=message.from_user.id, quote=True, lower=True, timeout=30)

        if choice != "y":
            await reply.edit("`Aborted...`")
            return

        await message.reply("`Pruning old files from cloud...`")

        await delete_files(store=CODEBASE_FILES_STORE, file_filter=partial(path_filter, path=path))

        await message.reply("`Starting upload... this will take a while...`")

        for chunk in utils.helpers.create_chunks(total_files, chunk_size=20):
            total += sum(1 for _ in await asyncio.gather(*[sync_file(f) for f in chunk]) if _ is not None)
    else:
        if await sync_file(path):
            total += 1

    await message.reply(f"`Synced {total} file(s).`")

    async for store in get_stores():
        if store.display_name == STORE_NAME:
            CODEBASE_FILES_STORE = store
            break


def path_filter(file: types.Document, path: pathlib.Path):
    if not file.custom_metadata:
        return False
    metadata = file.custom_metadata
    for data in metadata:
        if data.key == "full_path":
            file_path = pathlib.Path(data.string_value)
            return file_path.is_relative_to(path)


@BOT.make_async
def get_files_to_sync(root: pathlib.Path, filter_paths: bool = True):
    total_files = []
    specs: list[tuple[pathlib.Path, pathspec.GitIgnoreSpec]] = []

    def is_ignored(p: pathlib.Path):
        should_ignore = False
        for root, spec in specs:
            try:
                rel = p.relative_to(root).as_posix()

                if p.is_dir():
                    rel += "/"

                if spec.match_file(file=rel):
                    should_ignore = True

            except ValueError:
                continue

        return should_ignore

    for cwd, dirs, files in root.walk():
        if filter_paths:
            if ".gitignore" in files:
                with open(cwd / ".gitignore") as f:
                    rules = filter(lambda line: line.strip() != "" and not line.startswith("#"), f.readlines())
                    spec = pathspec.GitIgnoreSpec.from_lines(list(rules))
                    specs.append((cwd, spec))

                dirs[:] = list(filter(lambda x: not is_ignored(cwd / x), dirs))
                files = filter(lambda x: not is_ignored(cwd / x), files)

        total_files.extend([cwd / f for f in files if f.endswith(ALLOWED_EXT)])

    total_files.sort()
    return total_files


async def sync_file(file: pathlib.Path):
    if not file.is_file() or file.stat().st_size == 0:
        LOGGER.warn(f"Skipping uploading: {file.as_posix()}")
        return

    for parent in (ub_core_dir, APP, CUR_DIR):
        if file.is_relative_to(parent):
            rel_path = file.relative_to(parent)
            sep = "." if file.name.endswith(".py") else "/"
            file_name = sep.join([parent.name, *rel_path.parts])
            break
    else:
        file_name = file.name
    try:
        return await upload_file_to_store(
            store=CODEBASE_FILES_STORE,
            file=file,
            file_name=file_name,
            custom_metadata=[types.CustomMetadata(key="full_path", string_value=file.as_posix())],
        )
    except Exception as e:
        LOGGER.warning(f"Error uploading file: {file.as_posix()}\n{e}")
