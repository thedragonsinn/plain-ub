from app import BOT, bot, Message, Convo
from pyrogram import filters
import asyncio
import time
import json
import requests

DATABASE_CHANNEL_ID = -1002373174689
USER_ID = 89031402
QUOTE_API = "https://zenquotes.io/api/random"
STATE_FILE = "bio_state.json"

async def fetch_quote():
    try:
        response = requests.get(QUOTE_API)
        if response.status_code == 200:
            data = response.json()
            quote = data[0].get("q", "Keep pushing forward.")
            if len(quote) > 30:
                quote = quote[:71] + "..."
            return quote
    except Exception as e:
        print(f"Error fetching quote: {e}")
    return "Keep moving forward."

async def save_state(state, quote):
    try:
        await bot.send_message(DATABASE_CHANNEL_ID, quote)
        await bot.send_message(DATABASE_CHANNEL_ID, json.dumps(state))
    except Exception as e:
        print(f"Error saving state: {e}")

async def load_state():
    try:
        async for msg in bot.get_chat_history(DATABASE_CHANNEL_ID, limit=2):
            if msg.text.startswith("{"):
                return json.loads(msg.text)
    except Exception as e:
        print(f"Error loading state: {e}")
    return {"last_updated": 0, "quote_no": 1}

async def update_bio():
    state = await load_state()
    while True:
        current_time = int(time.time())
        if current_time - state["last_updated"] >= 86400:
            quote = await fetch_quote()
            new_bio = f"{quote} #{state['quote_no']}"
            try:
                await bot.update_profile(bio=new_bio)
                state["last_updated"] = current_time
                state["quote_no"] += 1
                await save_state(state, quote)
            except Exception as e:
                print(f"Error updating bio: {e}")
        await asyncio.sleep(3600)  # Check every hour

@bot.add_cmd(cmd="nextbio")
async def check_next_bio(bot: BOT, message: Message):
    state = await load_state()
    next_update_in = max(0, 86400 - (int(time.time()) - state["last_updated"]))
    await message.reply_text(f"Next bio change in {next_update_in // 3600}h {(next_update_in % 3600) // 60}m")

@bot.add_cmd(cmd="forcebio")
async def force_update_bio(bot: BOT, message: Message):
    state = await load_state()
    quote = await fetch_quote()
    new_bio = f"{quote} #{state['quote_no']}"
    try:
        await bot.update_profile(bio=new_bio)
        state["last_updated"] = int(time.time())
        state["quote_no"] += 1
        await save_state(state, quote)
        await message.reply_text("Bio updated manually!")
    except Exception as e:
        await message.reply_text(f"Failed to update bio: {e}")

bot.loop.create_task(update_bio())
