
import datetime
import typing as t

from sqlalchemy.orm.query import Query

from . import db
from .api import AvailabilityInfo, VaccineRound, IAvailabilityStore, IUSerStore, Subscription, User, VaccinationCenter, VaccineType


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

  def delete_vaccination_center(self, vaccination_center_id: str) -> None:
    # TODO(NiklasRosenstein): Drop connected availability?
    obj = self._session().query(db.VaccinationCenterV1).get(vaccination_center_id)
    if obj:
      self._session().delete(obj)

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
      result.append(db_obj.to_api())
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
      dates.update(result.get_availability_info().dates)
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
      vaccine_round=vaccine_round,
      availability_info=data,
      expires=center.expires,
    )
    self._session().merge(db_obj)


class DefaultUserStore(IUSerStore):

  def __init__(self, session: db.ISessionProvider) -> None:
    self._session = session

  def _get_user(self, user_id: int) -> t.Tuple[t.Optional[User], bool]:
    userv1 = self._session().query(db.UserV1).get(user_id)
    if userv1 is not None:
      return userv1.to_api(), False
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
      result.append(user.to_api())
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
    for vaccine_round in subscription.vaccine_rounds:
      s.add(db.SubscriptionV1(
        user_id=user_id,
        type=db.SubscriptionV1.Type.VACCINE_TYPE_AND_ROUND.name,
        vaccine_type=vaccine_round[0].name,
        vaccine_round=vaccine_round[1],
      ))
    for vaccination_center_id in subscription.vaccination_center_ids:
      s.add(db.SubscriptionV1(
        user_id=user_id,
        type=db.SubscriptionV1.Type.VACCINATION_CENTER_ID.name,
        vaccination_center_id=vaccination_center_id,
      ))
    for vaccination_center_query in subscription.vaccination_center_queries:
      s.add(db.SubscriptionV1(
        user_id=user_id,
        type=db.SubscriptionV1.Type.VACCINATION_CENTER_QUERY.name,
        vaccination_center_query=vaccination_center_query,
      ))

  def unsubscribe_user(self, user_id: int) -> None:
    # Delete all existing subscriptions. We will re-populate them.
    self._session().query(db.SubscriptionV1).filter(db.SubscriptionV1.user_id == user_id).delete()

  def _subscription_query(self,
    vaccination_center_id: t.Optional[str] = None,
    vaccine_round: t.Optional[VaccineRound] = None,
    user_id: t.Optional[int] = None,
  ) -> Query:

    now = datetime.datetime.now()
    subs1 = db.aliased(db.SubscriptionV1)
    subs2 = db.aliased(db.SubscriptionV1)
    query = self._session().query(db.VaccinationCenterV1, db.UserV1)
    query = query.filter(db.VaccinationCenterV1.expires > now)
    if vaccination_center_id:
      query = query.filter(db.VaccinationCenterV1.id == vaccination_center_id)
    else:
      query = query.join(db.VaccinationCenterAvailabilityV1).add_entity(db.VaccinationCenterAvailabilityV1)
      query = query.filter(db.VaccinationCenterAvailabilityV1.expires > now)
      query = query.filter(db.VaccinationCenterAvailabilityV1.num_dates > 0)
    query = query.join(subs1, subs1.user_id == db.UserV1.id).join(subs2, subs2.user_id == db.UserV1.id)
    query = query.order_by(db.UserV1.id, db.VaccinationCenterV1.id, subs1.id, subs2.id)

    if user_id is not None:
      query = query.filter(db.UserV1.id == user_id)

    if vaccine_round is not None:
      vaccine_type_filter = vaccine_round[0].name
      if vaccine_round[1] == 0:
        vaccine_round_filter = True
      else:
        vaccine_round_filter = (subs1.vaccine_round == vaccine_round[1])
    else:
      vaccine_type_filter = db.VaccinationCenterAvailabilityV1.vaccine_type
      vaccine_round_filter = subs1.vaccine_round == db.VaccinationCenterAvailabilityV1.vaccine_round
    query = query.filter(
      (subs1.type == subs1.Type.VACCINE_TYPE_AND_ROUND.name) &
      (subs1.vaccine_type == vaccine_type_filter) &
      vaccine_round_filter
    )

    if vaccination_center_id:
      vaccination_center_filter = vaccination_center_id
    else:
      vaccination_center_filter = db.VaccinationCenterV1.id
    query = query.filter((
        (subs2.type == subs2.Type.VACCINATION_CENTER_ID.name) &
        (subs2.vaccination_center_id == vaccination_center_filter)
      )|(
        (subs2.type == subs2.Type.VACCINATION_CENTER_QUERY.name) &
        (db.VaccinationCenterV1.construct_search_query(subs2.vaccination_center_query))
    ))

    return query

  def get_users_subscribed_to(self,
    vaccination_center_id: str,
    vaccine_round: VaccineRound,
    offset: t.Optional[int] = None,
    limit: t.Optional[int] = None,
  ) -> t.List[User]:

    query = self._subscription_query(vaccination_center_id, vaccine_round, None)
    query = query.offset(offset).limit(limit)
    result = []
    user: db.UserV1
    for _vcenter, user in query:
      result.append(user.to_api())
    return result

  def get_relevant_availability_for_user(self, user_id: int,
  ) -> t.List[t.Tuple[VaccinationCenter, VaccineRound, AvailabilityInfo]]:

    query = self._subscription_query(None, None, user_id)
    result = []
    vcenter: db.VaccinationCenterV1
    availability: db.VaccinationCenterAvailabilityV1
    for vcenter, _user, availability in query:
      result.append((vcenter.to_api(), availability.get_vaccine_round(), availability.get_availability_info()))
    return result
