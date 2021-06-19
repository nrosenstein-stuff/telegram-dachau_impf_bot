
import collections
import enum

from impfbot.api import VaccineRound, VaccineType


class Template(str):

  def __call__(self, **params: str) -> str:
    return self.format_map(collections.defaultdict(lambda: '<?>', params))


class Text(enum.Enum):
  SUBSCRIBE_OK = enum.auto()
  SUBSCRIBE_DUPLICATE = enum.auto()
  UNSUBSCRIBE_OK = enum.auto()
  UNSUBSCRIBE_ENOENT = enum.auto()
  SLOT_AVAILABLE = enum.auto()
  SLOT_AVAILABLE_RETRO = enum.auto()
  AVAILABLE_SLOTS_HEADER = enum.auto()
  NO_SLOTS_AVAILABLE = enum.auto()
  ROUND_ANY = enum.auto()
  ROUND_1 = enum.auto()
  ROUND_2 = enum.auto()

  def load(self) -> Template:
    return Template(GERMAN[self])

  def __call__(self, **params: str) -> str:
    return self.load()(**params)

  @staticmethod
  def of_vaccine_type(vaccine_type: VaccineType) -> str:
    return GERMAN[vaccine_type]

  @staticmethod
  def of_vaccine_round(vaccine_round: VaccineRound) -> str:
    vaccine_type, round_num = vaccine_round
    round_text = {None: Text.ROUND_ANY, 1: Text.ROUND_1, 2: Text.ROUND_2}.get(round_num)
    round_str = round_text() if isinstance(round_text, Text) else str(round_num)
    return f'{Text.of_vaccine_type(vaccine_type)} {round_str}'


GERMAN = {
  Text.SUBSCRIBE_OK: 'Hallo {first_name}, ich werde dir Bescheid geben sobald Impftermine verfügbar sind. Sende mir eine Nachricht mit "/abmelden" um keine Benachrichtigungen mehr zu erhalten.',
  Text.SUBSCRIBE_DUPLICATE: 'Du bist bereits angemeldet.',
  Text.UNSUBSCRIBE_OK: '{first_name}, ich werde dir keine Benachrichtigungen mehr senden.',
  Text.UNSUBSCRIBE_ENOENT: 'Du bist bereits abgemeldet or warst nie angemeldet.',
  Text.SLOT_AVAILABLE: 'Ich habe soeben folgende Termine für <b>{vaccine_name}</b> bei <a href="{link}">{location}</a> gefunden:\n\n{dates}',
  Text.SLOT_AVAILABLE_RETRO: '<b>{vaccine_name}</b> bei <a href="{link}">{location}</a>:{dates}',
  Text.AVAILABLE_SLOTS_HEADER: 'Zuletzt bekannte Impftermine (Verfügbarkeit kann sich in der Zwischenzeit geändert haben): {dates}',
  Text.NO_SLOTS_AVAILABLE: 'Momentan sind keine Impftermine verfügbar.',
  Text.ROUND_ANY: '(allg. Impfung)',
  Text.ROUND_1: '1. Impfung',
  Text.ROUND_2: '2. Impfung',
  VaccineType.Biontech: 'BioNTech',
  VaccineType.AstraZeneca: 'AstraZeneca',
  VaccineType.JohnsonAndJohnson: 'Johnson+Johnson',
}
