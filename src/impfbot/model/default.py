
import datetime
import typing as t

from . import db
from .api import AvailabilityInfo, VaccineRound, IAvailabilityStore, IUSerStore, Subscription, User, VaccinationCenter, VaccineType


def dates_from_json(data: t.List[str]) -> t.List[datetime.date]:
  return [datetime.datetime.strptime(x, '%Y-%m-%d').date() for x in data]


def dates_to_json(dates: t.List[datetime.date]) -> t.List[str]:
  return [dt.strftime('%Y-%m-%d') for dt in dates]


class DefaultAvailabilityStore(IAvailabilityStore):
  """
  Stores details about vaccination centers and availability info in the database.

  # Arguments
  ttl (int): The time for availability data to stay alive. If availability for a vaccination
    center isn't refreshed within this time frame, it will be assumed that the center is not
    available anymore (the whole center, not just the availability info).
    availability. It will also be assumed that the vaccination center is not available anymore
  """

  def __init__(self, session: db.ISessionProvider, ttl: datetime.timedelta) -> None:
    self._session = session
    self._ttl = ttl

  def upsert_vaccination_center(self, vaccination_center: VaccinationCenter) -> None:
    db_obj = db.VaccinationCenterV1(
      id=vaccination_center.id,
      name=vaccination_center.name,
      url=vaccination_center.url,
      location=vaccination_center.location,
      expires=datetime.datetime.now() + self._ttl)
    self._session().merge(db_obj)

  def search_vaccination_centers(self,
    search_query: t.Optional[str],
    offset: t.Optional[int] = None,
    limit: t.Optional[int] = None,
  ) -> t.List[VaccinationCenter]:

    query = self._session().query(db.VaccinationCenterV1) \
      .filter(db.VaccinationCenterV1.expires > datetime.datetime.now()) \
      .order_by(db.VaccinationCenterV1.id) \
      .offset(offset)\
      .limit(limit)

    if search_query is not None:
      query = query.filter(
        db.VaccinationCenterV1.name.ilike('%' + search_query + '%') |
        db.VaccinationCenterV1.url.ilike('%' + search_query + '%') |
        db.VaccinationCenterV1.location.ilike('%' + search_query + '%'))

    result = []
    for db_obj in query:
      result.append(VaccinationCenter(db_obj.id, db_obj.name, db_obj.url, db_obj.location))
    return result

  def get_availability(self,
    vaccination_center_id: str,
    vaccine_round: t.Optional[VaccineRound]
  ) -> AvailabilityInfo:

    query = self._session().query(db.VaccinationCenterAvailabilityV1)\
      .filter(db.VaccinationCenterAvailabilityV1.vaccination_center_id == vaccination_center_id) \
      .filter(db.VaccinationCenterAvailabilityV1.expires > datetime.datetime.now())
    if vaccine_round is not None:
      query = query.filter(db.VaccinationCenterAvailabilityV1.vaccine_type == vaccine_round[0].name)
      if vaccine_round[0] is not None:
        query = query.filter(db.VaccinationCenterAvailabilityV1.vaccine_round == vaccine_round[1])
    dates: t.Set[datetime.date] = set()
    for result in query:
      dates.update(dates_from_json(t.cast(t.List[str], result.dates)))
    return AvailabilityInfo(dates=sorted(dates))

  def set_availability(self,
    vaccination_center_id: str,
    vaccine_round: VaccineRound,
    data: AvailabilityInfo
  ) -> None:

    center = self._session().query(db.VaccinationCenterV1).get(vaccination_center_id)
    if not center:
      raise ValueError(f'Unknown vaccination center id: {vaccination_center_id!r}')
    center.expires = datetime.datetime.now() + self._ttl
    db_obj = db.VaccinationCenterAvailabilityV1(
      vaccination_center_id=vaccination_center_id,
      vaccine_type=vaccine_round[0].name,
      vaccine_round=vaccine_round[1],
      dates=dates_to_json(data.dates),
      num_dates=len(data.dates),
      expires=center.expires,
    )
    self._session().merge(db_obj)


class DefaultUserStore(IUSerStore):

  def __init__(self, session: db.ISessionProvider) -> None:
    self._session = session

  def _get_user(self, user_id: int) -> t.Tuple[t.Optional[User], bool]:
    userv1 = self._session().query(db.UserV1).get(user_id)
    if userv1 is not None:
      return User(userv1.id, userv1.chat_id, userv1.first_name), False
    return None, False

  def get_user_count(self, with_subscription_only: bool) -> int:
    query = self._session().query(db.UserV1)
    if with_subscription_only:
      query = query.join(db.SubscriptionV1).filter(db.SubscriptionV1.id != None)
    return query.distinct(db.UserV1.id).count()

  def get_users(self, offset: t.Optional[int] = None, limit: t.Optional[int] = None) -> t.List[User]:
    query = self._session().query(db.UserV1).order_by(db.UserV1.id).offset(offset).limit(limit)
    result = []
    for user in query:
      result.append(User(user.id, user.chat_id, user.first_name))
    return result

  def register_user(self, user: User) -> None:
    has_user, in_old_table = self._get_user(user.id)
    if not has_user or in_old_table or has_user != user:
      self._session().merge(db.UserV1(
        id=user.id,
        chat_id=user.chat_id,
        first_name=user.first_name,
        registered_at=datetime.datetime.now()
      ))

  def get_subscription(self, user_id: int) -> Subscription:
    result = Subscription()
    for sub in self._session().query(db.SubscriptionV1).filter(db.SubscriptionV1.user_id == user_id):
      if sub.type == db.SubscriptionV1.Type.VACCINE_TYPE_AND_ROUND.name:
        assert sub.vaccine_type is not None
        assert sub.vaccine_round is not None
        result.vaccine_rounds.append(VaccineRound(VaccineType[sub.vaccine_type], sub.vaccine_round))
      elif sub.type == db.SubscriptionV1.Type.VACCINATION_CENTER_ID.name:
        assert sub.vaccination_center_id is not None
        result.vaccination_center_ids.append(sub.vaccination_center_id)
      elif sub.type == db.SubscriptionV1.Type.VACCINATION_CENTER_QUERY.name:
        assert sub.vaccination_center_query is not None
        result.vaccination_center_queries.append(sub.vaccination_center_query)
      else:
        raise RuntimeError(f'unhandled subscription type: {sub.type}')
    return result

  def subscribe_user(self, user_id: int, subscription: Subscription) -> None:
    self.unsubscribe_user(user_id)
    # Re-create all the subscription details.
    s = self._session()
    for vaccine_round in subscription.vaccine_rounds or []:
      s.add(db.SubscriptionV1(
        user_id=user_id,
        type=db.SubscriptionV1.Type.VACCINE_TYPE_AND_ROUND.name,
        vaccine_type=vaccine_round[0].name,
        vaccine_round=vaccine_round[1],
      ))
    for vaccination_center_id in subscription.vaccination_center_ids or []:
      s.add(db.SubscriptionV1(
        user_id=user_id,
        type=db.SubscriptionV1.Type.VACCINATION_CENTER_ID.name,
        vaccination_center_id=vaccination_center_id,
      ))
    for vaccination_center_query in subscription.vaccination_center_queries or []:
      s.add(db.SubscriptionV1(
        user_id=user_id,
        type=db.SubscriptionV1.Type.VACCINATION_CENTER_QUERY.name,
        vaccination_center_query=vaccination_center_query,
      ))

  def unsubscribe_user(self, user_id: int) -> None:
    # Delete all existing subscriptions. We will re-populate them.
    self._session().query(db.SubscriptionV1).filter(db.SubscriptionV1.user_id == user_id).delete()

  def get_users_subscribed_to(self,
    vaccination_center_id: str,
    vaccine_round: VaccineRound,
    offset: t.Optional[int] = None,
    limit: t.Optional[int] = None,
  ) -> t.List[User]:

    if vaccine_round[1] == 0:
      vaccine_round_filter = True
    else:
      vaccine_round_filter = (db.SubscriptionV1.vaccine_round == vaccine_round[1])

    query = self._session().query(db.VaccinationCenterV1, db.UserV1)\
      .filter(db.VaccinationCenterV1.id == vaccination_center_id)\
      .join(db.SubscriptionV1)\
      .filter(
        ( (db.SubscriptionV1.type == db.SubscriptionV1.Type.VACCINE_TYPE_AND_ROUND.name) &
          (db.SubscriptionV1.vaccine_type == vaccine_round[0].name) &
          vaccine_round_filter) |
        ( (db.SubscriptionV1.type == db.SubscriptionV1.Type.VACCINATION_CENTER_ID.name) &
          (db.SubscriptionV1.vaccination_center_id == vaccination_center_id)) |
        ( (db.SubscriptionV1.type == db.SubscriptionV1.Type.VACCINATION_CENTER_QUERY.name) &
          (db.VaccinationCenterV1.construct_search_query(db.SubscriptionV1.vaccination_center_query)) )
      )\
      .offset(offset)\
      .limit(offset)

    user: db.UserV1
    result = []
    for _vcenter, user in query:
      result.append(User(user.id, user.chat_id, user.first_name))

    return result
