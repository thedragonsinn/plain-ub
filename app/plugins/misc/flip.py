import random

from app import BOT, Message
from app.core.db.models import CoinFlips
from ub_core.utils import reply_and_delete


@BOT.add_cmd(cmd="flip")
async def flip(bot: BOT, message: Message):
    """
    CMD: FLIP
    INFO: Flips a coin.
    USAGE: .flip
    """
    sides = ["Heads", "Tails"]
    result = random.choice(sides)
    await CoinFlips.create(user_id=message.from_user.id, choice=result)
    await reply_and_delete(message, f"The coin landed on **{result}**.")


@BOT.add_cmd(cmd="flips")
async def flips(bot: BOT, message: Message):
    """
    CMD: FLIPS
    INFO: Shows your flip history.
    USAGE: .flips
    """
    flips = (
        await CoinFlips.filter(user_id=message.from_user.id).order_by("-id").limit(10)
    )
    if not flips:
        await reply_and_delete(message, "You haven't flipped a coin yet.")
        return

    text = "Your last 10 coin flips:\n\n"
    for i, flip in enumerate(flips):
        text += f"{i+1}. {flip.choice}\n"

    await reply_and_delete(message, text)