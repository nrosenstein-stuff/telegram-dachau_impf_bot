
import atexit
import logging
import queue
import threading
import typing as t
from telegram import Bot, ParseMode


class TelegramBotLoggingHandler(logging.Handler):
  """
  A handler class which dispatches log events to a Telegram chat. Dispatches messages in a
  separate thread to avoid blocking the caller thread.
  """

  def __init__(self, bot: Bot, chat_id: int, level: int = logging.NOTSET) -> None:
    super().__init__(level)
    self.bot = bot
    self.chat_id = chat_id
    self.queue: 'queue.Queue[t.Optional[logging.LogRecord]]' = queue.Queue(1024)
    threading.Thread(target=self._dispatcher).start()
    atexit.register(lambda: self.queue.put(None))

  def _dispatcher(self) -> None:
    while True:
      record = self.queue.get()
      if not record:
        break
      self.bot.send_message(
        chat_id=self.chat_id,
        text=f'<code>{self.format(record)}</code>',
        parse_mode=ParseMode.HTML)

  def emit(self, record: logging.LogRecord) -> None:
    self.queue.put_nowait(record)
