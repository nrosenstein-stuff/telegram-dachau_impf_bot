
import cachetools
import datetime
import logging
import threading
import typing as t
import uuid
from prometheus_client import start_http_server
from telegram import Update, ParseMode, TelegramError
from telegram.ext import CallbackContext, CommandHandler, Updater, CallbackQueryHandler
from telegram.message import Message
from nr.stream import Stream

from impfbot import __version__
from impfbot.model import ScopedSession, User
from impfbot.model.default import DefaultAvailabilityStore, DefaultUserStore
from impfbot.polling.api import IPlugin
from impfbot.polling.default import DefaultPoller
from impfbot.polling.telegram import TelegramAvailabilityDispatcher, TelegramAvailabilityRecorder
from impfbot.utils.locale import get as _
from impfbot.utils import tgui
from .config import Config
from .sub import SubscriptionManager
from . import metrics

logger = logging.getLogger(__name__)


class Impfbot:

  def __init__(self, config: Config) -> None:
    self.session = ScopedSession()
    self.config = config
    self.telegram_updater = Updater(config.token)
    self.bot = self.telegram_updater.bot
    self.poller = DefaultPoller(datetime.timedelta(seconds=config.check_period_in_s))
    self.poller.plugins += IPlugin.load_plugins()
    self.availability_store = DefaultAvailabilityStore(self.session, datetime.timedelta(hours=config.retention_period_in_h))
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

    @metrics.users_num_registered.set_function
    def _user_count() -> int:
      with self.session:
        return self.user_store.get_user_count(False)

    @metrics.users_num_subscribed.set_function
    def _user_subscribed_count() -> int:
      with self.session:
        return self.user_store.get_user_count(False)

    metrics.tgui_action_cache_size.set_function(lambda: len(self.tgui_action_store._cache))

  def add_command(self, name: str, handler_func: t.Callable) -> None:
    def wrapper(*args, **kwargs):
      with self.session:
        return handler_func(*args, **kwargs)
    self.telegram_updater.dispatcher.add_handler(CommandHandler(name, wrapper))

  def init_commands(self) -> None:
    self.add_command('start', self._command_start)
    self.add_command('einstellungen', self._command_config)
    self.add_command('termine', self._command_availability)
    self.add_command('info', self._command_info)
    self.add_command('adm', self._command_admin)
    self.add_command('broadcast', self._command_broadcast)
    self.add_command('broadcast4real', self._command_broadcast)
    self.telegram_updater.dispatcher.add_handler(CallbackQueryHandler(self._callback_query_handler))

  def mainloop(self) -> None:
    start_http_server(self.config.metrics_port)
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
    metrics.commands_executed.labels('/start').inc()
    if not update.message: return
    user = self._register_user_from_message(update.message)
    msg = _('conversation.start', first_name=user.first_name, bot_name=self.bot.name.replace('_', '\\_'))
    update.message.reply_markdown(msg)

  def _command_config(self, update: Update, context: CallbackContext) -> None:
    metrics.commands_executed.labels('/einstellungen').inc()
    if not update.message: return
    ctx = tgui.DefaultContext(self.tgui_action_store, update)
    self.subs.get_root_view(ctx.user_id()).respond(ctx)

  def _command_info(self, update: Update, context: CallbackContext) -> None:
    metrics.commands_executed.labels('/info').inc()
    if not update.message: return
    message = _('conversation.info_html', bot_name=self.bot.name[1:], version=__version__)
    update.message.reply_html(message, disable_web_page_preview =True)

  def _command_availability(self, update: Update, context: CallbackContext) -> None:
    metrics.commands_executed.labels('/termine').inc()
    if not update.message or not update.message.from_user: return
    user_id = update.message.from_user.id
    availability = self.user_store.get_relevant_availability_for_user(user_id)
    lines = []
    for vaccine_round, values in Stream(availability).groupby(lambda t: t[1]):
      lines.append(f'<b>{vaccine_round.to_text()}</b>')
      for vcenter, vaccine_round, data in values:
        dates = ', '.join(d.strftime('%Y-%m-%d') for d in data.dates)
        lines.append(f'• <a href="{vcenter.url}">{vcenter.name}</a>: {dates}')
      lines.append('')
    if lines:
      lines.insert(0, '')
      lines.insert(0, _('conversation.summary_header'))
    else:
      lines.append(_('conversation.no_availability'))
      if self.poller.last_poll:
        date = self.poller.last_poll.strftime(_('format.date'))
        time = self.poller.last_poll.strftime(_('format.time'))
        lines[-1] += ' ' + _('conversation.last_checked_on', date=date, time=time)
    update.message.reply_html('\n'.join(lines))

  def _callback_query_handler(self, update: Update, context: CallbackContext) -> None:
    with self.session:
      ctx = tgui.DefaultContext(self.tgui_action_store, update)
      tgui.dispatch(ctx)

  def _command_admin(self, update: Update, context: CallbackContext) -> None:
    if not update.message or not update.message.from_user: return
    if not update.message or update.message.from_user.id not in self.config.admin_user_ids:
      return

    def _stats(ctx: tgui.IContext, *a) -> tgui.View:
      assert update.message
      update.message.reply_text(
        f'Number of registered users: {self.user_store.get_user_count(False)}\n'
        f'Number of users with active subscriptions: {self.user_store.get_user_count(True)}')
      return view

    def _show_chat_id(ctx: tgui.IContext, *a) -> tgui.View:
      assert update.message
      update.message.reply_text(str(update.message.chat_id))
      return view

    view = tgui.View('Admin Interface')
    view.add_button('User Statistics').connect(_stats)
    view.add_button('Show Chat ID').connect(_show_chat_id)
    ctx = tgui.DefaultContext(self.tgui_action_store, update)
    view.respond(ctx)

  def _command_broadcast(self, update: Update, context: CallbackContext) -> None:
    if not update.message or not update.message.from_user or not update.message.text: return
    if update.message.from_user.id not in self.config.admin_user_ids: return

    prefix = '/broadcast'
    prefix_4_real = '/broadcast4real'
    for_real = update.message.text.startswith(prefix_4_real)
    assert for_real or update.message.text.startswith(prefix)
    text = update.message.text[len(prefix_4_real if for_real else prefix):]
    nonce = str(uuid.uuid4())
    text = text.replace('\n\n', nonce).replace('\n', ' ').replace(nonce, '\n\n')
    if not text:
      return

    if for_real:
      chat_ids = [x.chat_id for x in self.user_store.get_users()]
    else:
      chat_ids = [update.message.chat_id]

    for chat_id in chat_ids:
      try:
        self.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
        if not for_real:
          self.bot.send_message(chat_id=chat_id, text=f'Use {prefix_4_real} to actually send '
            f'the message to {self.user_store.get_user_count(False)} users.')
      except TelegramError:
        logger.exception('Could not send message to chat_id %s', chat_id)
