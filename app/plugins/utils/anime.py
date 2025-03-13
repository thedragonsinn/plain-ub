from app import bot
import requests

@bot.add_cmd(cmd="anime")
async def fetch_anime_wallpaper(bot, message):
    """
    Fetches a random anime wallpaper using the waifu.pics API.
    """
    try:
        # Define the API URL
        api_url = "https://api.waifu.pics/sfw/waifu"

        # Make a request to the API
        response = requests.get(api_url)
        response.raise_for_status()

        # Extract the image URL from the response
        data = response.json()
        image_url = data.get("url")

        # Send the image to Telegram
        if image_url:
            await message.reply_photo(
                image_url,
                caption="Here's a random anime wallpaper for you!"
            )
        else:
            await message.reply_text("Could not fetch an anime wallpaper. Please try again.")
    except requests.RequestException as e:
        await message.reply_text(f"Failed to fetch an anime wallpaper. Error: {e}")
