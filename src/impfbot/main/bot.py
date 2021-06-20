
import cachetools
import datetime
import threading
import typing as t
from telegram import Update
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
    update.message.reply_markdown_v2(_('welcome_mesage', first_name=user.first_name, bot_name=self.bot.name))
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
    return
    if not update.message or update.message.chat_id != self._config.admin_chat_id:
      return

    try:
      import argparse, shlex
      parser = argparse.ArgumentParser()
      parser.add_argument('--stats', action='store_true')
      # TODO: Capture parser output to stderr
      args = parser.parse_args(shlex.split(update.message.text.replace('—', '--'))[1:])
    except BaseException:
      self._dispatch_to_admin(f'Error executing {update.message.text}', traceback.format_exc())

    if args.stats:
      with model.session() as session:
        registered_users = session.query(model.UserRegistration).count()
        subscribed_users = session.query(model.UserRegistration).filter(model.UserRegistration.subscription_active == True).count()
      update.message.reply_text(f'Registered users: {registered_users}, subscribed: {subscribed_users}')
