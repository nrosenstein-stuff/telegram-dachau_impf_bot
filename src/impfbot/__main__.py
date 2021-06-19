
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
from impfbot import api, model
from impfbot.text import Text
from telegram.parsemode import ParseMode

logger = logging.getLogger(__name__)


@dataclass
class Config:
  token: str
  admin_chat_id: int = 56970700  # Niklas R. <-> impfbot Bot
  database_spec: str = 'sqlite+pysqlite:///impfbot.db'
  check_period: int = 20  # minutes
  log_format: str = '[%(asctime)s - %(levelname)s - %(name)s]: %(message)s'

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
    self._updater.dispatcher.bot_data
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('status', self._status))
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('start', self._register))
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('anmelden', self._register))
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('abmelden', self._unregister))
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

  def _dispatch(self,
    name: str,
    url: str,
    vaccine_round: api.VaccineRound,
    dates: t.List[datetime.date],
    recipient_chat_id: t.Optional[int] = None,
    is_retro: bool = False
  ) -> None:

    with model.session() as session:
      if recipient_chat_id is not None:
        chat_ids: t.Iterable[int] = [recipient_chat_id]
      else:
        chat_ids = (x.chat_id for x in session.query(model.UserRegistration) if x.subscription_active)
      for chat_id in chat_ids:
        try:
          self._updater.bot.send_message(
            chat_id=chat_id,
            text=(Text.SLOT_AVAILABLE_RETRO if is_retro else Text.SLOT_AVAILABLE)(
              vaccine_name=Text.of_vaccine_round(vaccine_round),
              link=url,
              location=name,
              dates=', '.join(d.strftime('%Y-%m-%d') for d in dates)),
            parse_mode=ParseMode.HTML,
          )
        except telegram.error.TelegramError as exc:
          logger.exception('An error occurred when sending message to chat_id %s', chat_id)

  def _check_availability_worker(self) -> None:
    while True:
      try:
        for vaccination_center in self._centers:
          logger.info('Checking availability of %s (%s)', vaccination_center.uid, vaccination_center.name)
          try:
            availability = vaccination_center.check_availability()
          except Exception:
            logger.exception('Error while checking availability of %s', vaccination_center.uid)
            self._dispatch_to_admin(f'Error in {vaccination_center.uid}', code=traceback.format_exc())
          else:
            if availability:
              logger.info('Detected availability for %s: %s', vaccination_center.name, vaccination_center.check_availability())
            with model.session() as session:
              self._save_available_dates_and_dispatch(session, vaccination_center, availability)
        self._last_check_at = datetime.datetime.now()
      except:
        logger.exception('Error in _check_availability_worker')
        self._dispatch_to_admin('Error in _check_availability_worker', code=traceback.format_exc())
      time.sleep(60 * self._config.check_period)  # Run every five minutes

  def _save_available_dates_and_dispatch(self,
    session: model.Session,
    vaccination_center: api.IVaccinationCenter,
    availability: t.Dict[api.VaccineRound, api.AvailabilityInfo]
  ) -> None:

    known_rounds: t.Set[api.VaccineRound] = set()
    for center in session.query(model.VaccinationCenterByType).all():
      known_rounds.add(center.get_vaccine_round())
    known_rounds.update(availability.keys())

    for vaccine_round in known_rounds:
      info = availability.get(vaccine_round, api.AvailabilityInfo())
      changed = model.VaccinationCenterByType.save(session, vaccination_center.uid, vaccine_round, info)
      if changed and info.dates:
        self._dispatch(vaccination_center.name, vaccination_center.url, vaccine_round, info.dates)
      elif not changed and info.dates:
        logger.info('Skipped sending notification because the dates did not change.')

  def _status(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    assert update.message
    at_least_one_result = False
    with model.session() as session:
      for center in session.query(model.VaccinationCenterByType):
        if center.num_available_dates <= 0: continue
        if not at_least_one_result:
          update.message.reply_markdown(Text.AVAILABLE_SLOTS_HEADER())
        at_least_one_result = True
        vaccine_type, info = center.availability_info()
        center_data = next((x for x in self._centers if x.uid == center.id), None)
        if not center_data:
          logger.warn('Could not find name for center with id %s', center.id)
          continue
        self._dispatch(
          center_data.name,
          center_data.url,
          vaccine_type,
          info.dates,
          recipient_chat_id=update.message.chat_id,
          is_retro=True)
    if not at_least_one_result:
      update.message.reply_markdown(Text.NO_SLOTS_AVAILABLE())

  def _register(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    assert update.message
    user = update.message.from_user
    assert user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if has_user and has_user.subscription_active:
        update.message.reply_markdown(Text.SUBSCRIBE_DUPLICATE(first_name=user.first_name))
        return
      if has_user:
        has_user.subscription_active = True
      else:
        session.add(model.UserRegistration(
          id=user.id,
          first_name=user.first_name,
          chat_id=update.message.chat_id,
          subscription_active=True,
          registered_at=datetime.datetime.now()))
      session.commit()
      update.message.reply_markdown(Text.SUBSCRIBE_OK(first_name=user.first_name))
      self._status(update, context)

  def _unregister(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    assert update.message
    user = update.message.from_user
    assert user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if not has_user:
        update.message.reply_markdown(Text.UNSUBSCRIBE_ENOENT(first_name=user.first_name))
        return
      has_user.subscription_active = False
      session.commit()
      update.message.reply_markdown(Text.UNSUBSCRIBE_OK(first_name=user.first_name))

  def main(self):
    thread = threading.Thread(target=self._check_availability_worker, daemon=True)
    thread.start()
    self._updater.start_polling()
    self._updater.idle()


def main():
  config = Config.load('config.yml')
  logging.basicConfig(level=logging.INFO, format=config.log_format)
  model.init_engine(config.database_spec)
  bot = Impfbot(config)
  bot.main()


if __name__ == '__main__':
  main()
