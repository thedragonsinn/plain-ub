import asyncio
import traceback
from functools import wraps

from app import bot


def try_(func):
    if asyncio.iscoroutinefunction(func):

        @wraps(func)
        async def run_func(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                return result
            except asyncio.exceptions.CancelledError:
                text, type = f"<b>FUNC</b>: {func.__name__} Cancelled.", "info"
            except BaseException:
                text, type = (
                    f"<b>FUNC</b>: {func.__name__}"
                    f"\n</b>#TRACEBACK</b>:\n<pre language=python>{traceback.format_exc()}</pre>",
                    "error",
                )
            if text:
                await bot.log_text(text=text, name="traceback.txt", type=type)

    else:

        @wraps(func)
        def run_func(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                return result
            except asyncio.exceptions.CancelledError:
                text, type = f"<b>FUNC</b>: {func.__name__} Cancelled.", "info"
            except BaseException:
                text, type = (
                    f"<b>FUNC</b>: {func.__name__}"
                    f"\n</b>#TRACEBACK</b>:\n<pre language=python>{traceback.format_exc()}</pre>",
                    "error",
                )
            if text:
                asyncio.run_coroutine_threadsafe(
                    coro=bot.log_text(text=text, name="traceback.txt", type=type),
                    loop=bot.loop,
                )

    return run_func
