from app import BOT, bot, Message
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import re

@bot.bot.on_message()  # Registering only for the bot
@bot.add_cmd(cmd=["buttons"])
async def edit_channel_post(bot: BOT, message: Message):
    """
    CMD: BUTTON
    INFO: Add buttons to an existing channel post.
    USAGE:
        .buttons <channel_id>/<message_id>
        .buttons <post_url>

    Example:
        .buttons https://t.me/c/2188529816/65
        Example - https://example.com
        Example2 - https://example.org:same
        Example3 - https://example.in
    """
    if not message.text:
        return  # Ignore empty messages

    # Detect userbot (.) or bot sudo (?)
    if not (message.text.startswith(".button") or message.text.startswith("?button")):
        return

    try:
        lines = message.text.split("\n")
        if len(lines) < 2:
            await message.reply("❌ Usage: `.button <channel_id>/<message_id>` OR `.button <post_url>` followed by buttons.")
            return

        post_reference = lines[0].split(" ", 1)[1].strip()  # Extract post ID or URL

        # Detect Telegram post URL (private/public)
        match = re.search(r"(?:https://t\.me/(c/)?([\w\d_]+)/(\d+))", post_reference)
        if match:
            is_private = match.group(1) == "c/"
            channel_ref = match.group(2)  # Channel username or numeric ID
            message_id = int(match.group(3))

            if is_private:
                channel_id = f"-100{channel_ref}"  # Private channels require -100 prefix
            else:
                chat = await bot.get_chat(channel_ref)  # Get chat ID for public channels
                channel_id = chat.id

        else:
            # Handle direct channel_id/message_id input
            if "/" not in post_reference:
                await message.reply("❌ Invalid format! Use `.button <channel_id>/<message_id>` or `.button <post_url>`")
                return

            channel_id, message_id = post_reference.split("/")
            channel_id = int(channel_id)
            message_id = int(message_id)

        # Ensure the bot has met the channel before interacting
        try:
            await bot.get_chat(channel_id)
        except Exception as e:
            await message.reply("❌ Bot has not interacted with this channel. Ensure it is an admin and has sent a message before.")
            return

        # Parse button definitions
        button_lines = lines[1:]  
        keyboard = []
        current_row = []

        for line in button_lines:
            parts = line.split(" - ", 1)
            if len(parts) != 2:
                continue  # Skip invalid lines

            button_text = parts[0].strip()
            url_parts = parts[1].split(":same")  # Check for `:same` flag
            button_url = url_parts[0].strip()
            same_line = len(url_parts) > 1  

            button = InlineKeyboardButton(button_text, url=button_url)

            if same_line:
                current_row.append(button)  # Add to the same row
            else:
                if current_row:
                    keyboard.append(current_row)  # Add previous row
                current_row = [button]  # Start new row

        if current_row:
            keyboard.append(current_row)  

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Ensure modification is needed
        existing_message = await bot.get_messages(channel_id, message_id)
        if existing_message.reply_markup == reply_markup:
            await message.reply("⚠️ The message already contains the same buttons. No changes were made.")
            return

        # Edit the message
        await bot.edit_message_reply_markup(int(channel_id), message_id, reply_markup=reply_markup)
        await message.reply("✅ Buttons added successfully to the channel post!")

    except Exception as e:
        await message.reply(f"❌ An error occurred: {str(e)}")
