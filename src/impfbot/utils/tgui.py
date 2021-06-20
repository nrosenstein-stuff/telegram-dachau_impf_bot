
"""
Helpers to build navigable Telegram UIs.
"""

import abc
import enum
import logging
import typing as t
from dataclasses import dataclass, field
from telegram import InlineKeyboardButton, Update, Message, CallbackQuery, User
from telegram.inline.inlinekeyboardmarkup import InlineKeyboardMarkup
from telegram.parsemode import ParseMode

logger = logging.getLogger(__name__)


class IActionStore(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def save_action(self, action: 'Action') -> str: ...

  @abc.abstractmethod
  def get_action(self, action_id: str) -> 'Action': ...


class IContext(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def get_action_store(self) -> IActionStore: ...

  @abc.abstractmethod
  def get_current_action(self) -> t.Optional['Action']: ...

  @abc.abstractmethod
  def user_id(self) -> int: ...

  @abc.abstractmethod
  def message_id(self) -> int: ...

  @abc.abstractmethod
  def acknowledge(self) -> None: ...

  @abc.abstractmethod
  def reply_markdown(self, text: str, markup: InlineKeyboardMarkup = None) -> None: ...

  @abc.abstractmethod
  def reply_text(self, text: str, markup: InlineKeyboardMarkup = None) -> None: ...

  @abc.abstractmethod
  def delete_message(self) -> None: ...


class DefaultActionStore(IActionStore):

  # TODO(NiklasRosenstein): This should be combined with a cache that can drop all
  #   previously stored actions when a message view has been replaced with new
  #   actions to a memory leak.

  def __init__(self, cache: t.MutableMapping) -> None:
    self._cache = cache

  def save_action(self, action: 'Action') -> str:
    k = str(id(action))
    self._cache[k] = action
    return k

  def get_action(self, action_id: str) -> 'Action':
    return self._cache[action_id]


class DefaultContext(IContext):

  def __init__(self, store: IActionStore, update: Update) -> None:
    self._store = store
    assert update.callback_query or update.message
    self._update = update
    if update.callback_query:
      assert update.callback_query.message
      assert update.callback_query.message.message_id
      self._user_id = update.callback_query.from_user.id
      self._message_id = update.callback_query.message.message_id
    elif update.message:
      assert update.message.from_user and update.message.message_id
      self._user_id = update.message.from_user.id
      self._message_id = update.message.message_id
    else:
      assert False, 'expected Message or CallbackQuery in Update'

  def get_action_store(self) -> IActionStore:
    return self._store

  def get_current_action(self) -> t.Optional['Action']:
    if self._update.callback_query:
      return self._store.get_action(self._update.callback_query.data or '')
    return None

  def user_id(self) -> int:
    return self._user_id

  def message_id(self) -> int:
    return self._message_id

  def acknowledge(self) -> None:
    if self._update.callback_query:
      self._update.callback_query.answer()

  def reply_markdown(self, text: str, markup: InlineKeyboardMarkup = None) -> None:
    if self._update.message:
      self._update.message.reply_markdown(text, reply_markup=markup)
    elif self._update.callback_query:
      self._update.callback_query.edit_message_text(
        text, parse_mode=ParseMode.MARKDOWN, reply_markup=markup)
    else:
      assert False

  def reply_text(self, text: str, markup: InlineKeyboardMarkup = None) -> None:
    if self._update.message:
      self._update.message.reply_text(text, reply_markup=markup)
    elif self._update.callback_query:
      self._update.callback_query.edit_message_text(text, reply_markup=markup)
    else:
      assert False

  def delete_message(self) -> None:
    if self._update.message:
      self._update.message.delete()
    elif self._update.callback_query:
      self._update.callback_query.delete_message()
    else:
      assert False


class ActionType(enum.Enum):
  BUTTON_CLICK = enum.auto()


@dataclass
class Action:
  type: ActionType
  args: t.Dict[str, t.Any]

  def __init__(self, type_: ActionType, **args) -> None:
    self.type = type_
    self.args = args


class IResponder(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def respond(self, ctx: IContext) -> None: ...


@dataclass
class Button:
  _ClickFn = t.Callable[[IContext, 'Button'], t.Optional[IResponder]]

  text: str
  args: t.Dict[str, t.Any] = field(default_factory=dict)
  on_click: t.Optional[_ClickFn] = None

  def connect(self, handler: _ClickFn) -> 'Button':
    self.on_click = handler
    return self

  def to_telegram(self, store: IActionStore) -> InlineKeyboardButton:
    action = Action(ActionType.BUTTON_CLICK, button=self)
    return InlineKeyboardButton(self.text, callback_data=store.save_action(action))


@dataclass
class View(IResponder):
  """
  Represents a telegram inline keyboard view.
  """

  message: str
  message_is_markdown: bool = True
  buttons: t.List[t.List[Button]] = field(default_factory=list)

  def add_button(self, text: str, data: t.Dict[str, t.Any] = None) -> Button:
    btn = Button(text, data or {})
    self.buttons.append([btn])
    return btn

  def add_buttons(self, *buttons: Button) -> None:
    self.buttons.append(list(buttons))

  def respond(self, ctx: IContext) -> None:
    """
    Responds with the view to the specified *update*.
    """

    action_store = ctx.get_action_store()
    markup = InlineKeyboardMarkup([[btn.to_telegram(action_store) for btn in line] for line in self.buttons])
    (ctx.reply_markdown if self.message_is_markdown else ctx.reply_text)(self.message, markup)


def dispatch(ctx: IContext) -> None:
  try:
    action = ctx.get_current_action()
  except KeyError:
    # TODO(NiklasRosenstein): Customize behaviour / show error message to user?
    ctx.delete_message()
    return
  if action and action.type == ActionType.BUTTON_CLICK:
    ctx.acknowledge()
    button: Button = action.args['button']
    if button.on_click:
      next_view = button.on_click(ctx, button)
      if next_view:
        next_view.respond(ctx)
      else:
        ctx.delete_message()
  elif action:
    logger.warn('Unhandled action: %s', action)
