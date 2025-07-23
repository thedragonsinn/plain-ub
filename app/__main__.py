import sys

from app import LOGGER, Config, bot

if Config.CMD_TRIGGER == Config.SUDO_TRIGGER:
    LOGGER.error("CMD_TRIGGER e SUDO_TRIGGER não podem ser iguais")
    sys.exit(1)


if __name__ == "__main__":
    bot.run(bot.boot())
else:
    LOGGER.error("Comando de inicialização errado.\nUse 'python -m app'")

