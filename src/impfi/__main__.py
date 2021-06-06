
import html
import logging
import time
import threading
import traceback
import typing as t
import telegram, telegram.ext
from impfi import model
from impfi.slotchecker import DachauMedSlotChecker, SlotChecker, SlotResponse
from telegram.parsemode import ParseMode

logger = logging.getLogger(__name__)

class Impfbot:

  def __init__(self, token: str, slotcheckers: t.List[SlotChecker]) -> None:
    self._token = token
    self._slotcheckers = slotcheckers
    self._updater = telegram.ext.Updater(token)
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('register', self._register))
    self._updater.dispatcher.add_handler(telegram.ext.CommandHandler('unregister', self._unregister))

  def _register(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    user = update.message.from_user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if has_user:
        update.message.reply_markdown(f'You\'re already registered.')
        return
      session.add(model.UserRegistration(id=user.id, first_name=user.first_name, chat_id=update.message.chat_id))
      session.commit()
      update.message.reply_markdown(f'Hey **{user.first_name}**, welcome to the crew. 💉💪')

  def _unregister(self, update: telegram.Update, context: telegram.ext.CallbackContext) -> None:
    user = update.message.from_user
    with model.session() as session:
      has_user = session.query(model.UserRegistration).filter(model.UserRegistration.id == user.id).first()
      if not has_user:
        update.message.reply_markdown(f'You\'re not currently registered.')
        return
      session.delete(has_user)
      session.commit()
      update.message.reply_markdown(f'Sorry to see you go. But that means you got fully vaccinated, right? 💉💪')

  def _dispatch(self, name: str, slot: SlotResponse) -> None:
    print('@@@ dispatching', name, slot)
    with model.session() as session:
      for reg in session.query(model.UserRegistration):
        print(reg.id, reg.first_name, reg.chat_id)
        self._updater.bot.send_message(
          chat_id=reg.chat_id,
          text=f'{reg.first_name}, looks like I found an open slot for <b>{name}</b>.\n\n<pre><code>{html.escape(slot.content)}</code></pre>',
          parse_mode=ParseMode.HTML,
        )

  def _dispatch_exception(self) -> None:
    chat_id = 56970700
    self._updater.bot.send_message(
      chat_id=chat_id,
      text=f'<pre><code>{html.escape(traceback.format_exc())}</code></pre>',
      parse_mode=ParseMode.HTML
    )

  def _check_slots(self):
    logger.info('Begin slot checker thread')
    while True:
      for checker in self._slotcheckers:
        try:
          logger.info('Checking slots for %s', checker.get_description())
          slot = checker.check_available_slots()
        except Exception:
          logger.exception('Error when checking slots for %s', checker.get_description())
          self._dispatch_exception()
        else:
          if slot is not None:
            logger.info('Found open slot for %s', checker.get_description())
            self._dispatch(checker.get_description(), slot)
      time.sleep(60 * 5)  # Run every five minutes

  def main(self):
    thread = threading.Thread(target=self._check_slots)
    thread.start()
    self._updater.start_polling()
    self._updater.idle()


def main():
  logging.basicConfig(level=logging.INFO)
  with open('creds.txt') as fp:
    token = fp.read().strip()
  model.init_engine("sqlite+pysqlite:///test.db")
  bot = Impfbot(token, DachauMedSlotChecker.all_offices())
  bot.main()


if __name__ == '__main__':
  main()
