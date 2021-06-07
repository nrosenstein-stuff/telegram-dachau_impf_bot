
import datetime
import html
import logging
import time
import telegram, telegram.ext
import threading
import traceback
import typing as t
from dataclasses import dataclass
from databind import yaml
from functools import reduce
from impfi import api, model
from telegram.parsemode import ParseMode

logger = logging.getLogger(__name__)


@dataclass
class Config:
  token: str
  admin_chat_id: int = 56970700  # Niklas R. <-> Impfi Bot
  database_spec: str = 'sqlite+pysqlite:///impfi.db'
  check_period: int = 20  # minutes

  @classmethod
  def load(cls, filename: str) -> 'Config':
    with open(filename) as fp:
      return yaml.from_stream(cls, fp)


class Impfbot:

  def __init__(self, config: Config) -> None:
    self._config = config
    self._centers = reduce(
      lambda a, b: a + list(b.get_vaccination_centers()), api.IPlugin.load_plugins(),
      t.cast(t.List[api.IVaccinationCenter], []))
    self._updater = telegram.ext.Updater(config.token)
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('status', self._status))
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('register', self._register))
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('unregister', self._unregister))
    self._last_check_at: t.Optional[datetime.datetime] = None

  def _dispatch_to_admin(self, message: str, code: t.Optional[str] = None) -> None:
    message = html.escape(message)
    if code is not None:
      message += f'\n\n<pre><code>{html.escape(code)}</code></pre>'
    self._updater.bot.send_message(
      chat_id=self._config.admin_chat_id,
      text=message,
      parse_mode=ParseMode.HTML
    )

  def _dispatch(self, name: str, url: str, vaccine_type: api.VaccineType, dates: t.List[datetime.date]) -> None:
    with model.session() as session:
      for reg in session.query(model.UserRegistration):
        self._updater.bot.send_message(
          chat_id=reg.chat_id,
          text=f'Slots for {vaccine_type.name} are available at <a href="{url}">{name}</a> '\
            'for the following dates: ' + ', '.join(d.strftime('%Y-%m-%d') for d in dates),
          parse_mode=ParseMode.HTML,
        )

  def _check_availability_worker(self):
    while True:
      try:
        for vaccination_center in self._centers:
          logger.info('Checking availability of %s (%s)', vaccination_center.uid, vaccination_center.name)
          try:
            availability = vaccination_center.check_availability()
          except Exception:
            logger.exception('Error while checking availability of %s', vaccination_center.uid)
            self._dispatch_to_admin(f'Error in {vaccination_center.uid}', code=traceback.print_exc())
          else:
            if availability:
              logger.info('Detected availability for %s: %s', vaccination_center.name, vaccination_center.check_availability())
            for vaccine_type, info in availability.items():
              self._dispatch(vaccination_center.name, vaccination_center.url, vaccine_type, availability.dates)
        self._last_check_at = datetime.datetime.now()
      except:
        logger.exception('Error in _check_availability_worker')
        self._dispatch_to_admin('Error in _check_availability_worker', code=traceback.format_exc())
      time.sleep(60 * self._config.check_period)  # Run every five minutes

  def _status(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    assert update.message
    update.message.reply_markdown(f'Last check at: {self._last_check_at}')

  def _register(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    assert update.message
    user = update.message.from_user
    assert user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if has_user:
        update.message.reply_markdown(f'You\'re already registered.')
        return
      session.add(model.UserRegistration(id=user.id, first_name=user.first_name, chat_id=update.message.chat_id))
      session.commit()
      update.message.reply_markdown(f'Hey **{user.first_name}**, welcome to the crew. 💉💪')

  def _unregister(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    assert update.message
    user = update.message.from_user
    assert user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if not has_user:
        update.message.reply_markdown(f'You\'re not currently registered.')
        return
      session.delete(has_user)
      session.commit()
      update.message.reply_markdown(f'Sorry to see you go. But that means you got fully vaccinated, right? 💉💪')

  def main(self):
    thread = threading.Thread(target=self._check_availability_worker, daemon=True)
    thread.start()
    self._updater.start_polling()
    self._updater.idle()


def main():
  logging.basicConfig(level=logging.INFO)
  config = Config.load('config.yml')
  model.init_engine(config.database_spec)
  bot = Impfbot(config)
  bot.main()


if __name__ == '__main__':
  main()
