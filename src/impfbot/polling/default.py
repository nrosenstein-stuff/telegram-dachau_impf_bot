
import datetime
import logging
import time
import typing as t
from . import api

logger = logging.getLogger(__name__)


class DefaultPoller:

  def __init__(self, frequency: datetime.timedelta) -> None:
    self._frequency = frequency
    self.receivers: t.List[api.IDataReceiver] = []
    self.plugins: t.List[api.IPlugin] = []
    self.last_poll: t.Optional[datetime.datetime] = None

  def mainloop(self) -> None:
    while True:
      try:
        self.poll_once()
      except Exception:
        logger.exception('An unexpected error occurred during polling.')
      time.sleep(self._frequency.total_seconds())

  def poll_once(self) -> None:
    self.last_poll = datetime.datetime.now()
    dispatcher = api.IDataReceiver.Dispatcher(self.receivers)
    dispatcher.begin_polling()
    try:
      centers: t.List[api.IVaccinationCenter] = []
      for plugin in self.plugins:
        plugin_id = type(plugin).__module__ + '.' + type(plugin).__qualname__
        logger.info('Polling vaccination centers for %s', plugin_id)
        try:
          centers += plugin.get_vaccination_centers()
        except Exception:
          logger.exception('An unexpected error occurred while polling vaccination '
            'centers for %s.', plugin_id)
          continue
      for center in centers:
        dispatcher.on_vaccination_center(center)
      for center in centers:
        logger.info('Polling availability for %s', center.get_metadata().id)
        try:
          availability = center.check_availability()
        except Exception:
          logger.exception('An unexpected error occurred while checking the availability of %s',
            center.get_metadata())
        else:
          for vaccine_round, data in availability.items():
            dispatcher.on_availability_info_ready(center, vaccine_round, data)
    finally:
      dispatcher.end_polling()
