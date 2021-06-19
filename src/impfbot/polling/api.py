
import abc
import logging
import pkg_resources
import typing as t

from impfbot import model

logger = logging.getLogger(__name__)


class IPlugin(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def get_vaccination_centers(self) -> t.Sequence['IVaccinationCenter']: ...

  @staticmethod
  def load_plugins() -> t.List['IPlugin']:
    result = []
    for ep in pkg_resources.iter_entry_points('impfbot.api.IPlugin'):
      result.append(ep.load()())
    return result


class IVaccinationCenter(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def get_metadata(self) -> model.VaccinationCenter: ...

  @abc.abstractmethod
  def check_availability(self) -> t.Dict[model.VaccineRound, model.AvailabilityInfo]: ...


class IDataReceiver(metaclass=abc.ABCMeta):

  def begin_polling(self) -> None: ...

  def end_polling(self) -> None: ...

  def on_vaccination_center(self, center: IVaccinationCenter) -> None: ...

  @abc.abstractmethod
  def on_availability_info_ready(self,
    center: IVaccinationCenter,
    vaccine_round: model.VaccineRound,
    data: model.AvailabilityInfo) -> None: ...

  Dispatcher: t.ClassVar[t.Type['_DataReceiverDispatcher']]


class _DataReceiverDispatcher(IDataReceiver):
  """
  Dispatches received events to other receivers. Logs errors that occur in the recievers instead
  of propagating them.
  """

  def __init__(self, delegates: t.List[IDataReceiver]) -> None:
    self._delegates = delegates

  def begin_polling(self) -> None:
    for delegate in self._delegates:
      try:
        delegate.begin_polling()
      except Exception:
        logger.exception('An unexpected error occurred during dispatching.')

  def end_polling(self) -> None:
    for delegate in self._delegates:
      try:
        delegate.end_polling()
      except Exception:
        logger.exception('An unexpected error occurred during dispatching.')

  def on_vaccination_center(self, center: IVaccinationCenter) -> None:
    for delegate in self._delegates:
      try:
        delegate.on_vaccination_center(center)
      except Exception:
        logger.exception('An unexpected error occurred during dispatching.')

  def on_availability_info_ready(self,
    center: IVaccinationCenter,
    vaccine_round: model.VaccineRound,
    data: model.AvailabilityInfo
  ) -> None:

    for delegate in self._delegates:
      try:
        delegate.on_availability_info_ready(center, vaccine_round, data)
      except Exception:
        logger.exception('An unexpected error occurred during dispatching.')


IDataReceiver.Dispatcher = _DataReceiverDispatcher
