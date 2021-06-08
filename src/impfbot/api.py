
import abc
import enum
import datetime
import pkg_resources
import typing as t
from dataclasses import dataclass


class VaccineType(enum.Enum):
  Biontech = enum.auto()
  AstraZeneca = enum.auto()
  JohnsonAndJohnson = enum.auto()


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

  uid: str
  name: str
  location: str
  url: str

  @abc.abstractmethod
  def check_availability(self) -> t.Dict[VaccineType, 'AvailabilityInfo']: ...


@dataclass
class AvailabilityInfo:

  #: A list of dates that have at least one available slot.
  dates: t.List[datetime.date]

  #: A date for which new appointments may be available again soon.
  not_available_until: t.Optional[datetime.date]
