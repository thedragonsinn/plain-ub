from functools import wraps

from pyrogram.raw.types.messages import BotResults
from ub_core import BOT, Message


def run_with_timeout_guard(func):
    @wraps(func)
    async def inner(bot: BOT, message: Message):
        try:
            query_id, result_id, error = await func(bot, message)

            if error:
                await message.reply(error)
                return

            await bot.send_inline_bot_result(
                chat_id=message.chat.id, query_id=query_id, result_id=result_id
            )

        except Exception as e:
            await message.reply(str(e), del_in=10)

    return inner


@BOT.add_cmd("ln")
@run_with_timeout_guard
async def last_fm_now(bot: BOT, message: Message):
    """
    CMD: LN
    INFO: Check LastFM Status
    USAGE: .ln
    """

    result: BotResults = await bot.get_inline_bot_results(bot="lastfmrobot")

    if not result.results:
        return None, None, "No results found."

    return result.query_id, result.results[0].id, ""


@BOT.add_cmd("sn")
@run_with_timeout_guard
async def spotipie_now(bot: BOT, message: Message):
    """
    CMD: SN
    INFO: Check Spotipie Now
    USAGE: .sn
    """

    result: BotResults = await bot.get_inline_bot_results(bot="spotipiebot")

    if not result.results:
        return None, None, "No results found."

    return result.query_id, result.results[0].id, ""
