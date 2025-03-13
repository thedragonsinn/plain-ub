from pyrogram import filters
from pyrogram.errors import PeerIdInvalid, UserNotMutualContact, FloodWait
from app import BOT, Message
import asyncio

@BOT.add_cmd(cmd="invite")
async def invite_user(bot: BOT, message: Message):
    args = message.text.split()[1:] 
    if not args:
        await message.reply("Usage: .invite @username or user_id")
        return

    user_input = args[0]

    try:
        if user_input.isdigit():
            user_id = int(user_input)
        elif user_input.startswith("@"):
            user = await bot.get_users(user_input)
            user_id = user.id
        else:
            await message.reply("Invalid input. Use @username or user_id.")
            return

        await bot.add_chat_members(chat_id=message.chat.id, user_ids=[user_id])
        await message.reply(f"Successfully invited {user_input} to the group.")

    except PeerIdInvalid:
        await message.reply("Invalid username or user ID.")
    except UserNotMutualContact:
        await message.reply("Cannot add user. They must be a mutual contact.")
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await invite_user(bot, message)
    except Exception as e:
        await message.reply(f"Error: {str(e)}")
