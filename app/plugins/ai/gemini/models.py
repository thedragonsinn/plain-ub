import asyncio

from app import BOT, CustomDB, Message
from app.plugins.ai.gemini.client import async_client

DB_SETTINGS = CustomDB["COMMON_SETTINGS"]


class Models:
    CODE_MODEL = "gemini-2.5-flash"
    TEXT_MODEL = "gemini-2.5-flash"
    IMAGE_MODEL = "gemini-pro-latest"
    AUDIO_MODEL = "gemini-2.5-flash-preview-tts"


MODEL_FLAG_MAP = {
    "-c": {"local_key": "CODE_MODEL", "db_key": "code_model_name"},
    "-t": {"local_key": "TEXT_MODEL", "db_key": "text_model_name"},
    "-i": {"local_key": "IMAGE_MODEL", "db_key": "image_model_name"},
    "-a": {"local_key": "AUDIO_MODEL", "db_key": "audio_model_name"},
}


async def init_task():
    saved_models = await DB_SETTINGS.find_one({"_id": "gemini_model_info"}) or {}
    for model_info in MODEL_FLAG_MAP.values():
        if model := saved_models.get(model_info["db_key"]):
            setattr(Models, model_info["local_key"], model)


async def get_models_list():
    return [
        model.name.lstrip("models/")
        async for model in await async_client.models.list(config={"query_base": True})
        if "generateContent" in model.supported_actions
    ]


@BOT.add_cmd(cmd="llms")
async def list_ai_models(bot: BOT, message: Message):
    """
    CMD: LIST MODELS
    INFO: List and change Gemini Models.
    FLAGS:
        -i: to change image model
        -c to change code model
        -a: to change audio model
        -t: to change text model [default no flag behaviour]
    USAGE:
        .llms [changes default text model]
        .llms -i | -c | -a
    """
    models = await get_models_list()

    flag = message.flags[0] if message.flags else None

    model_info = MODEL_FLAG_MAP.get(flag) or MODEL_FLAG_MAP["-t"]

    reply = await message.reply(
        f"<b>Current Model</b>: <code>{getattr(Models, model_info['local_key'])}</code>"
        f"\n\n<blockquote expandable=True><pre language=text>{'\n\n'.join(models)}</pre></blockquote>"
        "\n\nReply to this message with the <code>model name</code> to change to a different model."
    )

    new_model_name, _ = await reply.get_response(
        timeout=60, reply_to_message_id=reply.id, from_user=message.from_user.id, quote=True
    )

    if not new_model_name:
        await reply.delete()
        return

    if new_model_name not in models:
        await reply.edit("<code>Invalid Model... Try again</code>")
        return

    setattr(Models, model_info["local_key"], new_model_name)

    confirmation = f"{new_model_name} saved as model."

    await asyncio.gather(
        DB_SETTINGS.add_data({"_id": "gemini_model_info", model_info["db_key"]: new_model_name}),
        reply.edit(confirmation),
        bot.log_text(text=confirmation, type=f"ai_{model_info['db_key']}"),
    )
