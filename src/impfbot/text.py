
import collections
import enum


class Text(enum.Enum):
  SUBSCRIBE_OK = enum.auto()
  SUBSCRIBE_DUPLICATE = enum.auto()
  UNSUBSCRIBE_OK = enum.auto()
  UNSUBSCRIBE_ENOENT = enum.auto()
  SLOT_AVAILABLE = enum.auto()
  NO_SLOTS_AVAILABLE = enum.auto()

  def __call__(self, **params: str) -> str:
    return GERMAN[self].format_map(collections.defaultdict(lambda: '<?>', params))


GERMAN = {
  Text.SUBSCRIBE_OK: 'Hallo {first_name}, ich werde dir Bescheid geben sobald Impftermine verfügbar sind. Sende mir eine Nachricht mit "/abmelden" um keine Benachrichtigungen mehr zu erhalten.',
  Text.SUBSCRIBE_DUPLICATE: 'Du bist bereits angemeldet.',
  Text.UNSUBSCRIBE_OK: '{first_name}, ich werde dir keine Benachrichtigungen mehr senden.',
  Text.UNSUBSCRIBE_ENOENT: 'Du bist bereits abgemeldet or warst nie angemeldet.',
  Text.SLOT_AVAILABLE: 'Ich habe verfügbare <b>{vaccine_name}</b> Impftermine bei <a href="{link}">{location}</a> für die folgenden Daten gefunden: {dates}',
  Text.NO_SLOTS_AVAILABLE: 'Momentan sind keine Impftermine verfügbar.'
}
