
import contextlib
import typing as t
import datetime
from .api import AvailabilityInfo, VaccineRound, VaccineType
from sqlalchemy import create_engine, Boolean, Column, Date, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import ForeignKeyConstraint

engine = None
Base = declarative_base()

CURRENT_VERSION = 2


def init_engine(spec: str) -> None:
  global engine
  engine = create_engine(spec, echo=False, future=True)
  Base.metadata.create_all(engine)

  with session() as s:
    version = SchemaVersion.get(s)
    if version < CURRENT_VERSION:
      raise RuntimeError(f'Current database schema version ({version}) does not match '
        f'the required schema version ({CURRENT_VERSION})')


@contextlib.contextmanager
def session() -> t.Iterator[Session]:
  s = Session(bind=engine)
  with s.begin():
    yield s


class SchemaVersion(Base):
  __tablename__ = 'schema_version'
  version = Column(Integer, primary_key=True)

  @staticmethod
  def get(session: Session) -> int:
    versions = list(session.query(SchemaVersion).all())
    if not versions:
      if not all(map(list, (
        session.query(UserRegistration).all(),
        session.query(VaccinationCenterByType).all(),
        session.query(AvailableDay).all(),
      ))):
        session.add(SchemaVersion(version=CURRENT_VERSION))
        return CURRENT_VERSION  # Fresh install
      return 1  # That's when we didn't store the schema version
    elif len(versions) == 1:
      return versions[0].version
    else:
      raise RuntimeError('found multiple schema versions: ' + str(versions))


class UserRegistration(Base):
  __tablename__ = 'user_registration'
  id = Column(Integer, primary_key=True)
  chat_id = Column(Integer, nullable=False)
  first_name = Column(String, nullable=False)
  subscription_active = Column(Boolean, nullable=False)
  registered_at = Column(DateTime, nullable=True)


class VaccinationCenterByType(Base):
  __tablename__ = 'vaccination_center_by_type'
  id = Column(String, primary_key=True)
  vaccine_type = Column(String, primary_key=True)
  vaccine_round = Column(Integer, nullable=True, primary_key=True)
  updated_availability_at = Column(DateTime)
  num_available_dates = Column(Integer, default=0)
  not_available_until = Column(Date)
  available_dates: t.Iterable['AvailableDay'] = relationship('AvailableDay', back_populates='vaccination_center')

  def set_available_dates(self, dates: t.Sequence[datetime.date]) -> None:
    session = Session.object_session(self)
    for slot in self.available_dates:
      session.delete(slot)
    for date in dates:
      session.add(AvailableDay(  # type: ignore
        vaccination_center_id=self.id,
        vaccine_type=self.vaccine_type,
        vaccine_round=self.vaccine_round,
        date=date))
    self.num_available_dates = len(dates)

  def set_availability(self, info: AvailabilityInfo) -> None:
    self.set_available_dates(info.dates)
    self.not_available_until = info.not_available_until

  @classmethod
  def save(cls, session: Session, id: str, vaccine_round: VaccineRound, info: AvailabilityInfo) -> bool:
    """ Returns True if the information changed, False if it's the same. """

    vaccine_type, round_num = vaccine_round[0].name, vaccine_round[1]
    obj = session.query(cls).get((id, vaccine_type, round_num)) or cls(id=id, vaccine_type=vaccine_type, vaccine_round=round_num)

    info.dates.sort()
    if obj.availability_info()[1] == info:
      return False

    session.add(obj)
    obj.set_availability(info)
    return True

  def get_vaccine_round(self) -> VaccineRound:
    return VaccineType[self.vaccine_type], self.vaccine_round

  def availability_info(self) -> t.Tuple[VaccineRound, AvailabilityInfo]:
    info = AvailabilityInfo([], self.not_available_until)
    for date in self.available_dates:
      info.dates.append(date.date)
    info.dates.sort()
    return self.get_vaccine_round(), info


class AvailableDay(Base):
  __tablename__ = 'available_day'
  vaccination_center_id = Column(String, primary_key=True)
  vaccine_type = Column(String, primary_key=True)
  vaccine_round = Column(Integer, nullable=True, primary_key=True)
  date = Column(Date, primary_key=True)
  __table_args__ = (
    ForeignKeyConstraint(
      ['vaccination_center_id', 'vaccine_type'],
      ['vaccination_center_by_type.id', 'vaccination_center_by_type.vaccine_type']),
  )
  vaccination_center = relationship(
    'VaccinationCenterByType',
    back_populates='available_dates')
