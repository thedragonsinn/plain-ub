from sys import version_info

from pyrogram import __version__ as pyro_version
from pyrogram import filters
from pyrogram.raw.types.messages import BotResults
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultAnimation,
    InlineQueryResultPhoto,
    ReplyParameters,
)
from ub_core.utils import MediaType, get_type
from ub_core.version import __version__ as core_version

from app import BOT, Config, Message, bot, extra_config

PY_VERSION = f"{version_info.major}.{version_info.minor}.{version_info.micro}"


@bot.add_cmd(cmd="alive")
async def alive(bot: BOT, message: Message):
    # Inline Alive if Dual Mode
    if bot.is_user and getattr(bot, "has_bot", False):
        inline_result: BotResults = await bot.get_inline_bot_results(
            bot=bot.bot.me.username, query="inline_alive"
        )
        await bot.send_inline_bot_result(
            chat_id=message.chat.id,
            result_id=inline_result.results[0].id,
            query_id=inline_result.query_id,
        )
        return

    kwargs = dict(
        chat_id=message.chat.id,
        caption=await get_alive_text(),
        reply_markup=get_alive_buttons(client=bot),
        reply_parameters=ReplyParameters(message_id=message.reply_id or message.id),
    )

    if get_type(url=extra_config.ALIVE_MEDIA) == MediaType.PHOTO:
        await bot.send_photo(photo=extra_config.ALIVE_MEDIA, **kwargs)
    else:
        await bot.send_animation(
            animation=extra_config.ALIVE_MEDIA, unsave=True, **kwargs
        )


_bot = getattr(bot, "bot", bot)
if _bot.is_bot:

    @_bot.on_inline_query(filters=filters.regex("^inline_alive$"), group=2)
    async def return_inline_alive_results(client: BOT, inline_query: InlineQuery):
        kwargs = dict(
            title=f"Send Alive Media.",
            caption=await get_alive_text(),
            reply_markup=get_alive_buttons(client),
        )

        if get_type(url=extra_config.ALIVE_MEDIA) == MediaType.PHOTO:
            result_type = InlineQueryResultPhoto(
                photo_url=extra_config.ALIVE_MEDIA, **kwargs
            )
        else:
            result_type = InlineQueryResultAnimation(
                animation_url=extra_config.ALIVE_MEDIA, **kwargs
            )

        await inline_query.answer(results=[result_type], cache_time=300)


async def get_alive_text() -> str:
    user_info = await bot.get_users(user_ids=Config.OWNER_ID)
    return (
        f"<b><a href='{Config.UPSTREAM_REPO}'>Plain-UB</a></b>, "
        f"A simple Telegram User-Bot by Meliodas.\n"
        f"\n › User            :   <code>{user_info.first_name}</code>"
        f"\n › Python        :   <code>v{PY_VERSION}</code>"
        f"\n › Pyrogram   :   <code>v{pyro_version}</code>"
        f"\n › Core            :   <code>v{core_version}</code>"
    )


def get_alive_buttons(client: BOT):
    if not client.is_bot:
        return
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(text=f"UB-Core", url=Config.UPDATE_REPO)],
            [InlineKeyboardButton(text=f"Support Group", url="t.me/plainub")],
        ]
    )
