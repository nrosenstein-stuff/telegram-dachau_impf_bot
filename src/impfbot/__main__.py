
import logging

import telegram

from impfbot.logger import TelegramBotLoggingHandler

from . import model
from .main.bot import Impfbot
from .main.config import Config
from .utils import locale


def setup_telegram_logger(bot: telegram.Bot, chat_id: int, level: int, fmt: str) -> None:
  handler = TelegramBotLoggingHandler(bot, chat_id, level)
  handler.setFormatter(logging.Formatter(fmt))
  logging.root.addHandler(handler)


def main():
  config = Config.load('config.yml')
  logging.basicConfig(level=logging.INFO, format=config.log_format)
  model.db.init_database(config.database_spec)
  locale.load('src/locale/de.yml')
  bot = Impfbot(config)

  if config.telegram_logger_chat_id is not None:
    setup_telegram_logger(
      bot.bot,
      config.telegram_logger_chat_id,
      getattr(logging, config.telegram_logger_level),
      config.log_format)

  bot.mainloop()


if __name__ == '__main__':
  main()
