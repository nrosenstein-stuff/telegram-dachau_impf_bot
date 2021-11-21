
import enum
import typing as t
from dataclasses import dataclass
from databind.json import from_str, to_str

from impfbot.model import IAvailabilityStore, IUSerStore
from impfbot.model.api import Subscription, VaccineRound, VaccineType
from impfbot.utils import tgui
from impfbot.utils.locale import get as _


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

  def _toggle_vaccine_type_filter(self, user_id: int, vaccine_round: VaccineRound) -> tgui.View:
    subscription = self.users.get_subscription(user_id)
    if vaccine_round in subscription.vaccine_rounds:
      subscription.vaccine_rounds.remove(vaccine_round)
    else:
      subscription.vaccine_rounds.append(vaccine_round)
    self.users.subscribe_user(user_id, subscription)
    return self._get_vaccine_type_picker_view(user_id, subscription)

  def _get_vaccine_type_picker_view(self, user_id: int, subscription: t.Optional[Subscription] = None) -> tgui.View:
    subscription = subscription or self.users.get_subscription(user_id)
    view = tgui.View(_('subscriptions.dialog.choose_vaccine_rounds.message'))

    # Fetch all known rounds from the availability store.
    all_rounds = set()
    for center in self.avail.search_vaccination_centers(None):
      vaccine_rounds = [vaccine_round for vaccine_round, availability
                        in self.avail.get_per_vaccine_round_availability(center.id)
                        if availability.dates]
      all_rounds.update(vaccine_rounds)

    # Create the UI.
    for vaccine_round in all_rounds:
      name = vaccine_round.to_text()
      if vaccine_round in subscription.vaccine_rounds:
        name += ' ✅'
      view.add_button(name, {'vaccine_round': vaccine_round}).connect(
        lambda ctx, btn: self._toggle_vaccine_type_filter(ctx.user_id(), btn.args['vaccine_round']))
    view.add_button(_('subscriptions.dialog.general.back')).connect(lambda ctx, btn: self.get_root_view(ctx.user_id()))

    return view

  def _toggle_match_all(self, user_id: int) -> tgui.View:
    subscription = self.users.get_subscription(user_id)
    if '%' in subscription.vaccination_center_queries:
      subscription.vaccination_center_queries.remove('%')
    else:
      subscription.vaccination_center_queries.append('%')
    self.users.subscribe_user(user_id, subscription)
    return self._get_vaccination_center_picker_view(user_id, subscription)

  def _toggle_vaccination_center_id(self, user_id: int, center_id: str) -> tgui.View:
    subscription = self.users.get_subscription(user_id)
    if center_id in subscription.vaccination_center_ids:
      subscription.vaccination_center_ids.remove(center_id)
    else:
      subscription.vaccination_center_ids.append(center_id)
    self.users.subscribe_user(user_id, subscription)
    return self._get_vaccination_center_picker_view(user_id, subscription)

  def _get_vaccination_center_picker_view(self, user_id, subscription: t.Optional[Subscription] = None) -> tgui.View:
    subscription = subscription or self.users.get_subscription(user_id)
    view = tgui.View(_('subscriptions.dialog.choose_vaccination_centers.message'))

    all_enabled = '%' in subscription.vaccination_center_queries
    name = _('subscriptions.dialog.general.all')
    if all_enabled:
      name += ' ' + _('emoji.enabled')
    view.add_button(name).connect(lambda ctx, btn: self._toggle_match_all(ctx.user_id()))

    for center in self.avail.search_vaccination_centers(None):
      name = center.name
      if all_enabled:
        name += ' ' + _('emoji.enabled_implicit')
      if center.id in subscription.vaccination_center_ids:
        name += ' ' + _('emoji.enabled')
      view.add_button(name, {'id': center.id}).connect(
        lambda ctx, btn: self._toggle_vaccination_center_id(ctx.user_id(), btn.args['id']))
    view.add_button(_('subscriptions.dialog.general.back')).connect(lambda ctx, btn: self.get_root_view(ctx.user_id()))
    return view

  def _unsubscribe(self, user_id) -> tgui.View:
    self.users.unsubscribe_user(user_id)
    return tgui.View(_('subscriptions.dialog.responses.unsubscribed'))

  def get_root_view(self, user_id: int) -> tgui.View:
    subscription = self.users.get_subscription(user_id)

    # Let the user know when they have a partial subscription.
    msg = _('subscriptions.dialog.main.message')
    if subscription.is_partial():
      msg += '\n\n' + _('subscriptions.dialog.main.warning') + ': '
      msg += _('subscriptions.dialog.main.partial_subscription_warning')

    view = tgui.View(msg)
    view.add_buttons(
      tgui.Button(_('subscriptions.dialog.main.choose_vaccination_centers')).connect(
        lambda ctx, _b: self._get_vaccination_center_picker_view(ctx.user_id())),
      tgui.Button(_('subscriptions.dialog.main.choose_vaccine_rounds')).connect(
        lambda ctx, btn: self._get_vaccine_type_picker_view(ctx.user_id()))
    )
    if subscription:
      view.add_button(_('subscriptions.dialog.main.unsubscribe_all')).connect(
        lambda ctx, btn: self._unsubscribe(ctx.user_id()))
    view.add_button(_('subscriptions.dialog.main.close_dialog')).connect(lambda ctx, btn: None)
    return view
