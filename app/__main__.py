import sys

from app import LOGGER, Config, bot

if Config.CMD_TRIGGER == Config.SUDO_TRIGGER:
    LOGGER.error("CMD_TRIGGER and SUDO_TRIGGER can't be the same")
    sys.exit(1)


if __name__ == "__main__":
    bot.run(bot.boot())
else:
    LOGGER.error("Wrong Start Command.\nUse 'python -m app'")
