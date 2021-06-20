
import cachetools
import datetime
import logging
import threading
import typing as t
from telegram import Update, ParseMode, TelegramError
from telegram.ext import CallbackContext, CommandHandler, Updater, CallbackQueryHandler
from telegram.message import Message

from impfbot.model import ScopedSession, User
from impfbot.model.default import DefaultAvailabilityStore, DefaultUserStore
from impfbot.polling.api import IPlugin
from impfbot.polling.default import DefaultPoller
from impfbot.polling.telegram import TelegramAvailabilityDispatcher, TelegramAvailabilityRecorder
from impfbot.utils.locale import get as _
from impfbot.utils import tgui
from .config import Config
from .sub import SubscriptionManager

logger = logging.getLogger(__name__)


class Impfbot:

  def __init__(self, config: Config) -> None:
    self.session = ScopedSession()
    self.config = config
    self.telegram_updater = Updater(config.token)
    self.bot = self.telegram_updater.bot
    self.poller = DefaultPoller(datetime.timedelta(seconds=config.check_period))
    self.poller.plugins += IPlugin.load_plugins()
    self.availability_store = DefaultAvailabilityStore(self.session, datetime.timedelta(hours=72))
    self.user_store = DefaultUserStore(self.session)
    self.poller.receivers.append(
      TelegramAvailabilityRecorder(
        self.session,
        self.availability_store,
        TelegramAvailabilityDispatcher(
          self.telegram_updater.bot,
          self.session,
          self.availability_store,
          self.user_store
        )
      )
    )
    self.subs = SubscriptionManager(self.availability_store, self.user_store)
    self.tgui_action_store = tgui.DefaultActionStore(cachetools.TTLCache(2**16, ttl=3600 * 24))
    self.init_commands()

  def add_command(self, name: str, handler_func: t.Callable) -> None:
    def wrapper(*args, **kwargs):
      with self.session:
        return handler_func(*args, **kwargs)
    self.telegram_updater.dispatcher.add_handler(CommandHandler(name, wrapper))

  def init_commands(self) -> None:
    self.add_command('start', self._command_start)
    self.add_command('einstellungen', self._command_config)
    self.add_command('adm', self._command_admin)
    self.add_command('broadcast', self._command_broadcast)
    self.telegram_updater.dispatcher.add_handler(CallbackQueryHandler(self._callback_query_handler))

  def mainloop(self) -> None:
    threading.Thread(target=self.poller.mainloop, daemon=True).start()
    self.telegram_updater.start_polling()
    self.telegram_updater.idle()

  def _register_user_from_message(self, message: Message) -> User:
    assert message.from_user
    from_user = message.from_user
    user = User(from_user.id, message.chat_id, from_user.first_name)
    self.user_store.register_user(user)
    return user

  def _command_start(self, update: Update, context: CallbackContext) -> None:
    if not update.message: return
    user = self._register_user_from_message(update.message)
    update.message.reply_markdown(_('welcome_mesage', first_name=user.first_name, bot_name=self.bot.name))
    self._command_config(update, context)

  def _command_config(self, update: Update, context: CallbackContext) -> None:
    if not update.message: return
    ctx = tgui.DefaultContext(self.tgui_action_store, update)
    self.subs.get_root_view(ctx.user_id()).respond(ctx)

  def _callback_query_handler(self, update: Update, context: CallbackContext) -> None:
    with self.session:
      ctx = tgui.DefaultContext(self.tgui_action_store, update)
      tgui.dispatch(ctx)

  def _command_admin(self, update: Update, context: CallbackContext) -> None:
    if not update.message or update.message.chat_id != self.config.admin_chat_id:
      return

    try:
      import argparse, shlex
      parser = argparse.ArgumentParser()
      parser.add_argument('--stats', action='store_true')
      # TODO: Capture parser output to stderr
      args = parser.parse_args(shlex.split((update.message.text or '').replace('—', '--'))[1:])
    except BaseException:
      logger.exception('Error executing admin command %r', update.message.text)

    if args.stats:
      update.message.reply_text(\
        f'Number of registered users: {self.user_store.get_user_count(False)}\n'
        f'NUmber of users with active subscriptions: {self.user_store.get_user_count(True)}')

  def _command_broadcast(self, update: Update, context: CallbackContext) -> None:
    if not update.message or not update.message.text: return
    if update.message.chat_id != self.config.admin_chat_id: return

    prefix = '/broadcast'
    assert update.message.text.startswith(prefix)
    text = update.message.text[len(prefix):].strip().replace('.', '\\.').replace('!', '\\!')

    for user in self.user_store.get_users():
      try:
        self.bot.send_message(chat_id=user.chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
      except TelegramError:
        logger.exception('Could not send message to chat_id %s', user.chat_id)
