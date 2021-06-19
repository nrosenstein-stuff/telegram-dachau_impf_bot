
import cachetools
import enum
import hashlib
import typing as t
from dataclasses import dataclass
from databind.json import from_str, to_str
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.callbackquery import CallbackQuery
from telegram.message import Message
from telegram.user import User

from impfbot.model import IAvailabilityStore, IUSerStore
from impfbot.model import db
from impfbot.model.api import Subscription, VaccineRound, VaccineType


KNOWN_ROUNDS = [
  VaccineRound(VaccineType.BIONTECH, 1),
  VaccineRound(VaccineType.BIONTECH, 2),
  VaccineRound(VaccineType.ASTRA_ZENECA, 1),
  VaccineRound(VaccineType.ASTRA_ZENECA, 2),
  VaccineRound(VaccineType.JOHNSON_AND_JOHNSON, 0),
]


class Page(enum.Enum):
  ROOT = enum.auto()
  MODIFY_IDS = enum.auto()
  MODIFY_VACCINES = enum.auto()
  MODIFY_VACCINE_ROUNDS = enum.auto()


class Action(enum.Enum):
  GOTO_ROOT = enum.auto()
  GOTO_CONFIGURE_CENTERS = enum.auto()
  GOTO_VACCINE_TYPES = enum.auto()
  TOGGLE_VACCINATION_CENTER_ID = enum.auto()
  TOGGLE_VACCINE_TYPE = enum.auto()
  UNSUB_ALL = enum.auto()


@dataclass
class Payload:
  type: str
  data: t.Dict[str, t.Any]

  def json(self) -> str:
    return to_str(self, Payload)

  @staticmethod
  def load(data: str) -> 'Payload':
    return from_str(Payload, data)


class ActionCacheMissError(Exception): pass


class SubscriptionManager:
  """
  This class implements the state machine for the subscription configuration in Telegram.
  """

  def __init__(self, avail: IAvailabilityStore, users: IUSerStore) -> None:
    self.avail = avail
    self.users = users

    # Button callback_data can only contain up to 64 characters. We occassionally need to
    # store more information that is associated with a button, so we cache it at runtime.
    # This may result in some weird behaviour where some buttons work after a while if the
    # action is cached and available or not.
    self.action_cache: t.MutableMapping[str, Payload] = cachetools.TTLCache(maxsize=2**16, ttl=10 * 60)

  def encode_payload(self, type_: str, **data: t.Any) -> str:
    action = Payload(type_, data)
    hsum = hashlib.md5(action.json().encode('utf8')).hexdigest()
    self.action_cache[hsum] = action
    return hsum

  def get_payload(self, hsum: str) -> Payload:
    try:
      return self.action_cache[hsum]
    except KeyError:
      raise ActionCacheMissError

  def _unsub_all(self) -> InlineKeyboardButton:
    return InlineKeyboardButton('Benachrichtigungen abstellen', callback_data=self.encode_payload(
      Action.UNSUB_ALL.name))

  def _configure_centers(self) -> InlineKeyboardButton:
    return InlineKeyboardButton('Praxen wählen', callback_data=self.encode_payload(
      Action.GOTO_CONFIGURE_CENTERS.name))

  def _configure_vaccine_types(self) -> InlineKeyboardButton:
    return InlineKeyboardButton('Impstoffe wählen', callback_data=self.encode_payload(
      Action.GOTO_VACCINE_TYPES.name))

  def _back_to_root(self) -> InlineKeyboardButton:
    return InlineKeyboardButton('<< Zurück', callback_data=self.encode_payload(
      Action.GOTO_ROOT.name))

  def _toggle_vaccination_center_id(self, id: str, name: str, currently_active: bool) -> InlineKeyboardButton:
    if currently_active:
      name += ' ✅'
    return InlineKeyboardButton(name, callback_data=self.encode_payload(
      Action.TOGGLE_VACCINATION_CENTER_ID.name, id=id))

  def _toggle_vaccine_type(self, vaccine_round: VaccineRound, currently_active: bool) -> InlineKeyboardButton:
    name = vaccine_round.to_text()
    if currently_active:
      name += ' ✅'
    return InlineKeyboardButton(name, callback_data=self.encode_payload(
      Action.TOGGLE_VACCINE_TYPE.name, type=vaccine_round.type.name, round=vaccine_round.round))

  def respond(self, update: Update) -> bool:
    try:
      if update.message and update.message.from_user:
        return self._respond_to_message(update.message, update.message.from_user)
      elif update.callback_query and update.callback_query.from_user:
        return self._respond_to_callback(update.callback_query, update.callback_query.from_user)
      return False
    except Exception:
      if update.message:
        update.message.reply_text('Sorry, something went wrong.')
      elif update.callback_query:
        update.callback_query.edit_message_text('Sorry, something went wrong.')
      raise

  def _respond_to_message(self, message: Message, user: User) -> bool:
    message.reply_text(
      'Benachrichtigungen konfigurieren',
      reply_markup=self._render_root())
    return True

  def _respond_to_callback(self, query: CallbackQuery, user: User) -> bool:
    payload = self.get_payload(query.data or '')
    subscription = self.users.get_subscription(user.id)

    if payload.type == Action.GOTO_CONFIGURE_CENTERS.name:
      query.answer()
      query.edit_message_text(
        'Praxen wählen',
        reply_markup=self._render_centers_picker(subscription))
      return True

    elif payload.type == Action.GOTO_VACCINE_TYPES.name:
      query.answer()
      query.edit_message_text(
        'Impfstoffe wählen',
        reply_markup=self._render_vaccine_types_picker(subscription))
      return True

    elif payload.type == Action.GOTO_ROOT.name:
      query.answer()
      query.edit_message_text(
        'Benachrichtigungen konfigurieren',
        reply_markup=self._render_root())
      return True

    elif payload.type == Action.TOGGLE_VACCINATION_CENTER_ID.name:
      query.answer()
      center_id: str = payload.data['id']
      if center_id in subscription.vaccination_center_ids:
        subscription.vaccination_center_ids.remove(center_id)
      else:
        subscription.vaccination_center_ids.append(center_id)
      self.users.subscribe_user(user.id, subscription)
      query.edit_message_text(
        'Praxen wählen',
        reply_markup=self._render_centers_picker(subscription))
      return True

    elif payload.type == Action.TOGGLE_VACCINE_TYPE.name:
      query.answer()
      vaccine_round = VaccineRound(
        VaccineType[payload.data['type']],
        payload.data['round'])
      if vaccine_round in subscription.vaccine_rounds:
        subscription.vaccine_rounds.remove(vaccine_round)
      else:
        subscription.vaccine_rounds.append(vaccine_round)
      self.users.subscribe_user(user.id, subscription)
      query.edit_message_text(
        'Impstoffe wählen',
        reply_markup=self._render_vaccine_types_picker(subscription))
      return True

    elif payload.type == Action.UNSUB_ALL.name:
      query.answer()
      self.users.unsubscribe_user(user.id)
      query.edit_message_text('Ok, erhältst keine Benachrichtigungen mehr.')
      return True

    return False

  def _render_root(self) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        self._configure_centers(),
        self._configure_vaccine_types()],
        [self._unsub_all()]])

  def _render_centers_picker(self, subscription: Subscription) -> InlineKeyboardMarkup:
      buttons = [
        [self._toggle_vaccination_center_id(
          center.id,
          center.name,
          center.id in subscription.vaccination_center_ids)]
        for center in self.avail.search_vaccination_centers(None)
      ]
      buttons.append([self._back_to_root()])
      return InlineKeyboardMarkup(buttons)

  def _render_vaccine_types_picker(self, subscription: Subscription) -> InlineKeyboardMarkup:
      buttons = [
        [self._toggle_vaccine_type(r, r in subscription.vaccine_rounds)]
        for r in KNOWN_ROUNDS
      ]
      buttons.append([self._back_to_root()])
      return InlineKeyboardMarkup(buttons)
