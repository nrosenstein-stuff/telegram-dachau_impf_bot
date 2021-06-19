
import abc
import enum
import i18n
import datetime
import typing as t
from dataclasses import dataclass, field


@dataclass(frozen=True)
class VaccinationCenter:
  id: str
  name: str
  url: str
  location: str


class VaccineType(enum.Enum):
  BIONTECH = enum.auto()
  ASTRA_ZENECA = enum.auto()
  JOHNSON_AND_JOHNSON = enum.auto()


class VaccineRound(t.NamedTuple):
  """
  Represents a type of vaccine and possible a requirement for which round of vaccinations are
  accepted (e.g. 1st/2nd vaccination for mRNA vaccines). If the *round* is zero, it means that
  any rounds are accepted.
  """

  type: VaccineType
  round: int = 0

  def to_text(self) -> str:
    round_name = {1: 'one', 2: 'two', 0: 'any'}.get(self.round, 'any')
    return f'{i18n.t("vaccine_type." + self.type.name)} {i18n.t("vaccine_round." + round_name)}'


@dataclass(frozen=True)
class AvailabilityInfo:

  #: A list of dates that have at least one available slot.
  dates: t.List[datetime.date] = field(default_factory=list)


@dataclass(frozen=True)
class User:
  id: int
  chat_id: int
  first_name: str


@dataclass(frozen=True)
class Subscription:
  vaccine_rounds: t.List[VaccineRound] = field(default_factory=list)
  vaccination_center_ids: t.List[str] = field(default_factory=list)
  vaccination_center_queries: t.List[str] = field(default_factory=list)


class IAvailabilityStore(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def upsert_vaccination_center(self, vaccination_center: VaccinationCenter) -> None: ...

  @abc.abstractmethod
  def search_vaccination_centers(self,
    search_query: t.Optional[str],
    offset: t.Optional[int] = None,
    limit: t.Optional[int] = None) -> t.List[VaccinationCenter]: ...

  @abc.abstractmethod
  def get_availability(self,
    vaccination_center_id: str,
    vaccine_round: VaccineRound) -> AvailabilityInfo: ...

  @abc.abstractmethod
  def set_availability(self,
    vaccination_center_id: str,
    vaccine_round: VaccineRound,
    data: AvailabilityInfo) -> None: ...


class IUSerStore(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def register_user(self, user: User) -> None: ...

  @abc.abstractmethod
  def get_subscription(self, user_id: int) -> Subscription: ...

  @abc.abstractmethod
  def subscribe_user(self, user_id: int, subscription: Subscription) -> None: ...

  @abc.abstractmethod
  def unsubscribe_user(self, user_id: int) -> None: ...

  @abc.abstractmethod
  def get_users_subscribed_to(self,
    vaccination_center_id: str,
    vaccine_round: VaccineRound,
    offset: t.Optional[int] = None,
    limit: t.Optional[int] = None) -> t.List[User]:
    """
    Find all users that have a subscription for the specified vaccination center and vaccination
    round. If the round number in the *vaccine_round* is `None`, it will match even users that
    have subscribed to particular rounds.

    The *offset* can be used to re-run the same search but offset the results. This is useful to
    split the request into multiple calls, but you will need to count the number of already read
    results yourself.
    """
