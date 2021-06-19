
import abc
import enum
import typing as t
from sqlalchemy import create_engine, Column, DateTime, Integer, String, ForeignKey, JSON
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from impfbot.utils.local import LocalList

__all__ = [
  'ISessionProvider',
  'ScopedSession',
  'VaccinationCenterV1',
  'UserV1',
  'SubscriptionV1',
]

engine: t.Optional[Engine] = None
Base = declarative_base()


class ISessionProvider(metaclass=abc.ABCMeta):

  @abc.abstractmethod
  def __call__(self) -> Session: ...

  @abc.abstractmethod
  def __enter__(self) -> Session: ...

  @abc.abstractmethod
  def __exit__(self, exc_type, exc_value, exc_tb) -> None: ...


class ScopedSession(ISessionProvider):

  def __init__(self) -> None:
    self._local = LocalList[Session]()

  def __enter__(self) -> 'Session':
    assert engine is not None
    session = Session(bind=engine)
    self._local.append(session)
    return session

  def __exit__(self, exc_t, exc_v, exc_tb) -> None:
    session = self._local.pop()
    if exc_tb is None:
      session.commit()
    else:
      session.rollback()

  def __call__(self) -> Session:
    try:
      return self._local.last()
    except IndexError:
      raise RuntimeError('No active ScopedSession in current thread.')


class SchemaVersion(Base):
  """
  A helper table to store the current schema version of the database.
  """

  __tablename__ = 'schema_version'

  EXPECTED_SCHEMA_VERSION = 1

  version = Column(Integer, primary_key=True)

  @staticmethod
  def get(session: Session) -> int:
    versions = list(session.query(SchemaVersion).all())
    if not versions:
      session.add(SchemaVersion(version=SchemaVersion.EXPECTED_SCHEMA_VERSION))
      return SchemaVersion.EXPECTED_SCHEMA_VERSION
    elif len(versions) == 1:
      return versions[0].version
    else:
      raise RuntimeError('found multiple schema versions: ' + str(versions))

  @staticmethod
  def validate() -> None:
    with ScopedSession() as session:
      version = SchemaVersion.get(session)
      if version != SchemaVersion.EXPECTED_SCHEMA_VERSION:
        raise RuntimeError(f'Current database schema version ({version}) does not match '
          f'the required schema version ({SchemaVersion.EXPECTED_SCHEMA_VERSION})')


class VaccinationCenterV1(Base):
  __tablename__ = 'vaccc_v1'

  id = Column(String, primary_key=True)
  name = Column(String, nullable=False)
  url = Column(String, nullable=False)
  location = Column(String, nullable=False)
  expires = Column(DateTime, nullable=False)

  @staticmethod
  def construct_search_query(query_col):
    query_col = '%' + query_col + '%'
    return VaccinationCenterV1.name.ilike(query_col) | \
           VaccinationCenterV1.location.ilike(query_col) | \
           VaccinationCenterV1.url.ilike(query_col)


class VaccinationCenterAvailabilityV1(Base):
  __tablename__ = 'vav_v1'

  vaccination_center_id = Column(String, primary_key=True)
  vaccine_type = Column(String, primary_key=True)
  vaccine_round = Column(Integer, primary_key=True, nullable=True)
  dates = Column(JSON, nullable=False)
  num_dates = Column(Integer, nullable=False)
  expires = Column(DateTime, nullable=False)


class UserV1(Base):
  __tablename__ = 'user_v1'

  id = Column(Integer, primary_key=True)
  chat_id = Column(Integer, nullable=False)
  first_name = Column(String, nullable=False)
  registered_at = Column(DateTime, nullable=False)


class SubscriptionV1(Base):
  __tablename__ = 'sub_v1'

  class Type(enum.Enum):
    VACCINE_TYPE_AND_ROUND = enum.auto()
    VACCINATION_CENTER_ID = enum.auto()
    VACCINATION_CENTER_QUERY = enum.auto()

  id = Column(Integer, primary_key=True, autoincrement=True)
  user_id = Column(Integer, ForeignKey(UserV1.id), nullable=False)
  type = Column(String, nullable=False)
  vaccine_type = Column(String, nullable=True)
  vaccine_round = Column(Integer, nullable=True)
  vaccination_center_id = Column(String, nullable=True)
  vaccination_center_query = Column(String, nullable=True)


def init_database(spec: str) -> None:
  """
  Initializes the database according to the SqlAlchemy database connection URL string *spec*.
  """

  global engine
  engine = create_engine(spec, echo=False, future=True)
  Base.metadata.create_all(engine)
  SchemaVersion.validate()
