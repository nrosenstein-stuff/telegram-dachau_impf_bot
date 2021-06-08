
from sqlalchemy import create_engine, Column, Integer, String  # type: ignore
from sqlalchemy.orm import declarative_base, Session  # type: ignore

engine = None
Base = declarative_base()


def init_engine(spec: str) -> None:
  global engine
  engine = create_engine(spec, echo=False, future=True)
  Base.metadata.create_all(engine)


def session() -> Session:
  return Session(bind=engine)


class UserRegistration(Base):
  __tablename__ = 'user_registration'
  id = Column(Integer, primary_key=True)
  first_name = Column(String)
  chat_id = Column(Integer)
