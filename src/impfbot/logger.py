
import logging
from telegram import Bot, ParseMode


class TelegramBotLoggingHandler(logging.Handler):
  """
  A handler class which dispatches log events to a Telegram chat.
  """

  def __init__(self, bot: Bot, chat_id: int, level: int = logging.NOTSET) -> None:
    super().__init__(level)
    self.bot = bot
    self.chat_id = chat_id

  def emit(self, record: logging.LogRecord) -> None:
    self.bot.send_message(
      chat_id=self.chat_id,
      text=f'<code>{self.format(record)}</code>',
      parse_mode=ParseMode.HTML)
