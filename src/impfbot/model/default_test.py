
import datetime
import typing as t
from unittest import TestCase
from impfbot.contrib.de.bavaria.dachau import ASTRA_2_URL

from impfbot.model.api import AvailabilityInfo, VaccineRound, VaccineType, Subscription, User, VaccinationCenter
from . import db
from .default import DefaultAvailabilityStore, DefaultUserStore


class DefaultTest(TestCase):

  def setUp(self) -> None:
    db.init_database('sqlite:///:memory:')
    self.scoped_session = db.ScopedSession()
    self.avail = DefaultAvailabilityStore(self.scoped_session, datetime.timedelta(1))
    self.users = DefaultUserStore(self.scoped_session)

  def setup_test_centers(self) -> None:
    with self.scoped_session:
      self.abc = VaccinationCenter('abc', 'ABC Vacc', 'https://abc.vacc', 'Vaccheim')
      self.xyz = VaccinationCenter('xyz', 'XYZ Vacc', 'https://xyz.vacc', 'Defheim')
      self.avail.upsert_vaccination_center(self.abc)
      self.avail.upsert_vaccination_center(self.xyz)

  def test_search_vaccination_centers(self) -> None:
    self.setup_test_centers()
    with self.scoped_session:
      assert set(self.avail.search_vaccination_centers(None)) == set([self.abc, self.xyz])
      assert set(self.avail.search_vaccination_centers('abc')) == set([self.abc])
      assert set(self.avail.search_vaccination_centers('XyZ')) == set([self.xyz])
      assert set(self.avail.search_vaccination_centers('.vacc')) == set([self.abc, self.xyz])

  def setup_test_users(self) -> None:
    with self.scoped_session:

      # Subscribing to just a vaccine round doesn't match you with any availabilities.
      self.u1 = User(1, 1, 'u1')
      self.users.register_user(self.u1)
      self.users.subscribe_user(self.u1.id, Subscription(
        vaccine_rounds=[VaccineRound(VaccineType.BIONTECH, 1)]))

      # Subscribing to just a vaccination center doesn't match you with any availabilities.
      self.u2 = User(2, 2, 'u2')
      self.users.register_user(self.u2)
      self.users.subscribe_user(self.u2.id, Subscription(
        vaccination_center_ids=['xyz']))

      self.u3 = User(3, 3, 'u3')
      self.users.register_user(self.u3)
      self.users.subscribe_user(self.u3.id, Subscription(
        vaccine_rounds=[VaccineRound(VaccineType.BIONTECH, 1)],
        vaccination_center_queries=['heim']))

      self.u4 = User(4, 4, 'u4')
      self.users.register_user(self.u4)
      self.users.subscribe_user(self.u4.id, Subscription(
        vaccine_rounds=[VaccineRound(VaccineType.JOHNSON_AND_JOHNSON, 0)],
        vaccination_center_ids=['xyz']))

  def test_subscriptions(self) -> None:
    self.setup_test_users()
    with self.scoped_session:
      assert self.users.get_subscription(self.u1.id) == Subscription(
        vaccine_rounds=[VaccineRound(VaccineType.BIONTECH, 1)])

  def test_get_users_subscribed_to(self) -> None:
    self.setup_test_centers()
    self.setup_test_users()
    with self.scoped_session:
      assert set(self.users.get_users_subscribed_to(
        'abc', VaccineRound(VaccineType.BIONTECH, 0))) == set([self.u3])
      assert set(self.users.get_users_subscribed_to(
        'xyz', VaccineRound(VaccineType.ASTRA_ZENECA, 1))) == set([])
      assert set(self.users.get_users_subscribed_to(
        'xyz', VaccineRound(VaccineType.JOHNSON_AND_JOHNSON, 0))) == set([self.u4])

  def setup_test_availability(self) -> None:
    def _register(v: t.Tuple[VaccinationCenter, VaccineRound, AvailabilityInfo]) -> None:
      self.avail.set_availability(v[0].id, v[1], v[2])
    with self.scoped_session:
      self.avail1 = (
        self.abc,
        VaccineRound(VaccineType.BIONTECH, 1),
        AvailabilityInfo(dates=[datetime.date(2021, 6, 21), datetime.date(2021, 6, 22)]))
      _register(self.avail1)

      self.avail2 = (
        self.abc,
        VaccineRound(VaccineType.BIONTECH, 2),
        AvailabilityInfo(dates=[datetime.date(2021, 6, 28)]))
      _register(self.avail2)

      self.avail3 = (
        self.abc,
        VaccineRound(VaccineType.JOHNSON_AND_JOHNSON, 0),
        AvailabilityInfo(dates=[datetime.date(2021, 6, 22), datetime.date(2021, 6, 23)]))
      _register(self.avail3)

      self.avail4 = (
        self.xyz,
        VaccineRound(VaccineType.BIONTECH, 1),
        AvailabilityInfo(dates=[datetime.date(2021, 7, 2)]))
      _register(self.avail4)

      self.avail5 = (
        self.xyz,
        VaccineRound(VaccineType.JOHNSON_AND_JOHNSON, 0),
        AvailabilityInfo(dates=[]))
      _register(self.avail5)

  def test_get_relevant_availability_for_user(self) -> None:
    self.setup_test_centers()
    self.setup_test_users()
    self.setup_test_availability()
    with self.scoped_session:
      assert self.users.get_relevant_availability_for_user(self.u1.id) == []
      assert self.users.get_relevant_availability_for_user(self.u2.id) == []
      assert self.users.get_relevant_availability_for_user(self.u3.id) == [self.avail1, self.avail4]
      assert self.users.get_relevant_availability_for_user(self.u4.id) == []  # Does not match avail5 because it has no dates
