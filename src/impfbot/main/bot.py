
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
from .config import Config
from .sub import SubscriptionManager



class Impfbot:

  def __init__(self, config: Config) -> None:
    self.session = ScopedSession()
    self.config = config
    self.telegram_updater = Updater(config.token)
    self.poller = DefaultPoller(datetime.timedelta(seconds=config.check_period))
    self.poller.plugins += IPlugin.load_plugins()
    self.availability_store = DefaultAvailabilityStore(self.session, datetime.timedelta(hours=1))
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
    self.init_commands()

  def add_command(self, name: str, handler_func: t.Callable) -> None:
    def wrapper(*args, **kwargs):
      with self.session:
        return handler_func(*args, **kwargs)
    self.telegram_updater.dispatcher.add_handler(CommandHandler(name, wrapper))

  def init_commands(self) -> None:
    self.add_command('start', self._command_start)
    self.add_command('status', self._command_status)
    self.add_command('anmelden', self._command_subscribe)
    self.add_command('abmelden', self._command_unsubscribe)
    self.add_command('adm', self._command_admin)
    self.telegram_updater.dispatcher.add_handler(CallbackQueryHandler(self._callback_query_handler))

  def mainloop(self) -> None:
    #threading.Thread(target=self.poller.mainloop, daemon=True).start()
    self.telegram_updater.start_polling()
    self.telegram_updater.idle()

  def _register_user_from_message(self, message: Message) -> None:
    if not message.from_user: return
    from_user = message.from_user
    self.user_store.register_user(User(from_user.id, message.chat_id, from_user.first_name))

  def _command_start(self, update: Update, context: CallbackContext) -> None:
    if not update.message: return
    self._register_user_from_message(update.message)

  def _command_status(self, update: Update, context: CallbackContext) -> None:
    if not update.message: return

    """
    at_least_one_result = False
    with model.session() as session:
      for center in session.query(model.VaccinationCenterByType):
        if center.num_available_dates <= 0: continue
        if not at_least_one_result:
          update.message.reply_markdown(Text.AVAILABLE_SLOTS_HEADER())
        at_least_one_result = True
        vaccine_type, info = center.availability_info()
        center_data = next((x for x in self._centers if x.uid == center.id), None)
        if not center_data:
          logger.warn('Could not find name for center with id %s', center.id)
          continue
        self._dispatch(
          center_data.name,
          center_data.url,
          vaccine_type,
          info.dates,
          recipient_chat_id=update.message.chat_id,
          is_retro=True)
    if not at_least_one_result:
      update.message.reply_markdown(Text.NO_SLOTS_AVAILABLE())
    """

  def _command_subscribe(self, update: Update, context: CallbackContext) -> None:
    if not update.message: return
    self._register_user_from_message(update.message)
    self.subs.respond(update)

  def _callback_query_handler(self, update: Update, context: CallbackContext) -> None:
    self.subs.respond(update)

    """
    user = update.message.from_user
    assert user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if has_user and has_user.subscription_active:
        update.message.reply_markdown(Text.SUBSCRIBE_DUPLICATE(first_name=user.first_name))
        return
      if has_user:
        has_user.subscription_active = True
      else:
        session.add(model.UserRegistration(
          id=user.id,
          first_name=user.first_name,
          chat_id=update.message.chat_id,
          subscription_active=True,
          registered_at=datetime.datetime.now()))
      session.commit()
      update.message.reply_markdown(Text.SUBSCRIBE_OK(first_name=user.first_name))
      self._status(update, context)
      """

  def _command_unsubscribe(self, update: Update, context: CallbackContext) -> None:
    return
    assert update.message
    user = update.message.from_user
    assert user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if not has_user:
        update.message.reply_markdown(Text.UNSUBSCRIBE_ENOENT(first_name=user.first_name))
        return
      has_user.subscription_active = False
      session.commit()
      update.message.reply_markdown(Text.UNSUBSCRIBE_OK(first_name=user.first_name))

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
