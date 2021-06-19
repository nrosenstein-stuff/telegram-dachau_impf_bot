
import enum
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

from impfbot.model import IAvailabilityStore, IUSerStore


class State(enum.Enum):
  ROOT_DIALOG = enum.auto()
  MODIFY_QUERIES = enum.auto()
  MODIFY_IDS = enum.auto()
  MODIFY_VACCINES = enum.auto()
  MODIFY_VACCINE_ROUNDS = enum.auto()


class Action(enum.Enum):
  PICK_CENTER = enum.auto()
  PICK_VACCINE_TYPE = enum.auto()


class SubscriptionManager:

  def __init__(self, avail: IAvailabilityStore, users: IUSerStore) -> None:
    self.avail = avail
    self.users = users

  def respond(self, update: Update) -> bool:
    if update.message:
      buttons = InlineKeyboardMarkup([[
        InlineKeyboardButton("Praxis auswählen", callback_data=Action.PICK_CENTER.name),
        InlineKeyboardButton("Impfstoff auswählen", callback_data=Action.PICK_VACCINE_TYPE.name),
      ]])
      update.message.reply_text(
        'Benachrichtigungen konfigurieren',
        reply_markup=buttons)
      return True
    elif update.callback_query and update.callback_query.data == Action.PICK_CENTER.name:
      update.callback_query.answer()
      update.callback_query.edit_message_text('Praxis auswählen')
      return True
    return False
