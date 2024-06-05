## PLAIN UB

![Header Image](assets/dark.png#gh-dark-mode-only)
![Header Image](assets/light.png#gh-light-mode-only)

A simple Telegram User-Bot.

> Made for my personal use

## Example Plugins:

<details>

<summary></summary>
 
* Basic Plugin:
```python
from app import BOT, bot, Message

@bot.add_cmd(cmd="test")
async def test_function(bot: BOT, message: Message):
    await message.reply("Testing....")
    """Your rest of the code."""
    
```

* Plugin with Multiple Commands:    
Instead of stacking @add_cmd you can pass in a list of command triggers.
```python
from app import BOT, bot, Message

@bot.add_cmd(cmd=["cmd1", "cmd2"])
async def test_function(bot: BOT, message: Message):
    if message.cmd=="cmd1":
        await message.reply("cmd1 triggered function")
    """Your rest of the code."""
    
```

* Plugin with DB access:

```python
from app import BOT, bot, Message, CustomDB

TEST_COLLECTION = CustomDB("TEST_COLLECTION")

@bot.add_cmd(cmd="add_data")
async def test_function(bot: BOT, message: Message):
    async for data in TEST_COLLECTION.find():
        """Your rest of the code."""
    # OR
    await TEST_COLLECTION.add_data(data={"_id":"test", "data":"some_data"})
    await TEST_COLLECTION.delete_data(id="test")
```

* Conversational Plugin:
    * Bound Method
        ```python
        from pyrogram import filters
        from app import BOT, bot, Message
        @bot.add_cmd(cmd="test")
        async def test_function(bot: BOT, message: Message):
            response = await message.get_response(
                filters=filters.text&filters.user([1234]), 
                timeout=10,
            )
            # Will return First text it receives in chat where cmd was ran
            """ rest of the code """
               
        ```
    * Conversational
        
        ```python
        from app import BOT, bot, Message, Convo
        from pyrogram import filters
      
        @bot.add_cmd(cmd="test")
        async def test_function(bot: BOT, message: Message):
            async with Convo(
                client=bot, 
                chat_id=1234, 
                filters=filters.text, 
                timeout=10
            ) as convo:
                await convo.get_response(timeout=10)
                await convo.send_message(text="abc", get_response=True, timeout=8)
                # and so on
            
        ```
</details>