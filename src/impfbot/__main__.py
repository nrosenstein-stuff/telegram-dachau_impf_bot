
import logging
import telegram

from locale import setlocale, LC_ALL
from impfbot import model
from impfbot.logger import TelegramBotLoggingHandler
from impfbot.main.bot import Impfbot
from impfbot.main.config import Config
from impfbot.utils import locale


def setup_telegram_logger(bot: telegram.Bot, chat_id: int, level: int, fmt: str) -> None:
  handler = TelegramBotLoggingHandler(bot, chat_id, level)
  handler.setFormatter(logging.Formatter(fmt))
  logging.root.addHandler(handler)


def main():
  config = Config.load('config.yml')
  setlocale(LC_ALL, config.locale)

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
