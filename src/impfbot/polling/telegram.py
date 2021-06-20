
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

    with self._session:
      vcenter = center.get_metadata()
      for user in self._users.get_users_subscribed_to(vcenter.id, vaccine_round):
        try:
          self._bot.send_message(
            chat_id=user.chat_id,
            text=_('availability.single.long',
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
    self._recorded_vaccination_center_ids: t.Set[str] = set()

  # def begin_polling(self) -> None:
  #   self._recorded_vaccination_center_ids.clear()

  # def end_polling_vaccination_centers(self) -> None:
  #   # Remove any vaccination centers that we have not received metadata for.
  #   with self._session:
  #     for center in self._avail.search_vaccination_centers(None):
  #       if center.id not in self._recorded_vaccination_center_ids:
  #         self._avail.delete_vaccination_center(center.id)
  #   self._recorded_vaccination_center_ids.clear()

  def on_vaccination_center(self, center: api.IVaccinationCenter) -> None:
    self._recorded_vaccination_center_ids.add(center.get_metadata().id)
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

    # TODO(NiklasRosenstein): Check if we ever sent this user a notiication for this
    #   center/vaccine_round before. If we haven't, we want to dispatch the notification
    #   anyway.
    if not set(data.dates).issubset(set(last_data.dates)):
      try:
        self._dispatch_on_change.on_availability_info_ready(center, vaccine_round, data)
      except Exception:
        logger.exception('An unexpected error occurred during dispatch.')
