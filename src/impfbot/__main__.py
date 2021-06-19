
import logging

from . import model
from .main.bot import Impfbot
from .main.config import Config
from .utils import locale


def main():
  config = Config.load('config.yml')
  logging.basicConfig(level=logging.INFO, format=config.log_format)
  model.db.init_database(config.database_spec)
  locale.load('src/locale/de.yml')
  bot = Impfbot(config)
  bot.mainloop()


if __name__ == '__main__':
  main()
