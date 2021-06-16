
import contextlib
import typing as t
import datetime
from .api import AvailabilityInfo, VaccineType
from sqlalchemy import create_engine, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.orm.session import Session, SessionTransaction
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.schema import ForeignKey, ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.sql.sqltypes import Date

engine = None
Base = declarative_base()


def init_engine(spec: str) -> None:
  global engine
  engine = create_engine(spec, echo=False, future=True)
  Base.metadata.create_all(engine)


@contextlib.contextmanager
def session() -> t.Iterator[Session]:
  s = Session(bind=engine)
  with s.begin():
    yield s


class UserRegistration(Base):
  __tablename__ = 'user_registration'
  id = Column(Integer, primary_key=True)
  first_name = Column(String)
  chat_id = Column(Integer, nullable=False)


class VaccinationCenterByType(Base):
  __tablename__ = 'vaccination_center_by_type'
  id = Column(String, primary_key=True)
  vaccine_type = Column(String, primary_key=True)
  updated_availability_at = Column(DateTime)
  num_available_dates = Column(Integer, default=0)
  not_available_until = Column(Date)
  available_dates = relationship('AvailableDay', back_populates='vaccination_center')

  def set_available_dates(self, dates: t.Sequence[datetime.date]) -> None:
    session = Session.object_session(self)
    for slot in self.available_dates:
      session.delete(slot)
    for date in dates:
      session.add(AvailableDay(vaccination_center_id=self.id, vaccine_type=self.vaccine_type, date=date))
    self.num_available_dates = len(dates)

  def set_availability(self, info: AvailabilityInfo) -> None:
    self.set_available_dates(info.dates)
    self.not_available_until = info.not_available_until

  @classmethod
  def save(cls, session: Session, id: str, vaccine_type: VaccineType, info: AvailabilityInfo) -> bool:
    """ Returns True if the information changed, False if it's the same. """

    obj = session.query(cls).get((id, vaccine_type.name)) or cls(id=id, vaccine_type=vaccine_type.name)

    info.dates.sort()
    if obj.availability_info()[1] == info:
      return False

    session.add(obj)
    obj.set_availability(info)
    return True

  def availability_info(self) -> t.Tuple[VaccineType, AvailabilityInfo]:
    info = AvailabilityInfo([], self.not_available_until)
    for date in self.available_dates:
      info.dates.append(date.date)
    info.dates.sort()
    return VaccineType[self.vaccine_type], info


class AvailableDay(Base):
  __tablename__ = 'available_day'
  vaccination_center_id = Column(String)
  vaccine_type = Column(String)
  date = Column(Date)
  __table_args__ = (
    ForeignKeyConstraint(
      ['vaccination_center_id', 'vaccine_type'],
      ['vaccination_center_by_type.id', 'vaccination_center_by_type.vaccine_type']),
  )
  PrimaryKeyConstraint(vaccination_center_id, vaccine_type, date)
  vaccination_center = relationship(
    'VaccinationCenterByType',
    back_populates='available_dates')
