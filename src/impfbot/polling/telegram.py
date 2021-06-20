
import logging
import typing as t
from telegram import Bot, TelegramError, ParseMode

from impfbot import model
from impfbot.utils.locale import get as _
from . import api

logger = logging.getLogger(__name__)


class TelegramAvailabilityDispatcher(api.IDataReceiver):

  def __init__(self,
    bot: Bot,
    session: model.ISessionProvider,
    avail: model.IAvailabilityStore,
    users: model.IUSerStore
  ) -> None:

    self._session = session
    self._bot = bot
    self._avail = avail
    self._users = users

  def on_availability_info_ready(self,
    center: api.IVaccinationCenter,
    vaccine_round: model.VaccineRound,
    data: model.AvailabilityInfo
  ) -> None:

    if not data.dates:
      return

    vcenter = center.get_metadata()
    logger.info('Dispatching availability for %s at %s.', vaccine_round, vcenter.id)

    with self._session:
      for user in self._users.get_users_subscribed_to(vcenter.id, vaccine_round):
        try:
          self._bot.send_message(
            chat_id=user.chat_id,
            text=_('notification.immediate',
              vaccine_name=vaccine_round.to_text(),
              link=vcenter.url,
              name=vcenter.name,
              dates=', '.join(d.strftime('%Y-%m-%d') for d in data.dates)),
            parse_mode=ParseMode.HTML,
          )
        except TelegramError as exc:
          logger.exception('An error occurred when sending message to chat_id %s', user.chat_id)


class TelegramAvailabilityRecorder(api.IDataReceiver):

  def __init__(self,
    session: model.ISessionProvider,
    avail: model.IAvailabilityStore,
    dispatch_on_change: api.IDataReceiver
  ) -> None:

    self._session = session
    self._avail = avail
    self._dispatch_on_change = dispatch_on_change

  def on_vaccination_center(self, center: api.IVaccinationCenter) -> None:
    with self._session:
      self._avail.upsert_vaccination_center(center.get_metadata())

  def on_availability_info_ready(self,
    center: api.IVaccinationCenter,
    vaccine_round: model.VaccineRound,
    data: model.AvailabilityInfo
  ) -> None:

    vcenter = center.get_metadata()

    with self._session:
      # If the dates changed significantly, (i.e. new dates became available, we ignore if
      # old dates are no longer available), we continue to dispatch.
      last_data = self._avail.get_availability(vcenter.id, vaccine_round)
      self._avail.set_availability(vcenter.id, vaccine_round, data)

    if not set(data.dates).issubset(set(last_data.dates)):
      try:
        self._dispatch_on_change.on_availability_info_ready(center, vaccine_round, data)
      except Exception:
        logger.exception('An unexpected error occurred during dispatch.')
