
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

  def mainloop(self) -> None:
    while True:
      try:
        self.poll_once()
      except Exception:
        logger.exception('An unexpected error occurred during polling.')
      time.sleep(self._frequency.total_seconds())

  def poll_once(self) -> None:
    dispatcher = api.IDataReceiver.Dispatcher(self.receivers)
    dispatcher.begin_polling()
    centers = []
    try:
      for plugin in self.plugins:
        logger.info('Polling vaccination centers for %s', plugin)
        try:
          centers += plugin.get_vaccination_centers()
        except Exception:
          logger.exception('An unexpected error occurred while retrieving the vaccination '
            'centers provided via %s.', plugin)
          continue
      logger.info('Dispatching vaccination centers (count: %s)', len(centers))
      for center in centers:
        dispatcher.on_vaccination_center(center)
      dispatcher.end_polling_vaccination_centers()
      for center in centers:
        logger.info('Checking availability of %s', center.get_metadata())
        try:
          availability = center.check_availability()
        except Exception:
          logger.exception('An unexpected error occurred while checking the availability of %s',
            center.get_metadata())
        else:
          logger.info('  Result: %s', availability)
          for vaccine_round, data in availability.items():
            dispatcher.on_availability_info_ready(center, vaccine_round, data)
    finally:
      dispatcher.end_polling()
