
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm.session import Session, SessionTransaction
from sqlalchemy.ext.declarative import declarative_base

engine = None
Base = declarative_base()


def init_engine(spec: str) -> None:
  global engine
  engine = create_engine(spec, echo=False, future=True)
  Base.metadata.create_all(engine)


def session() -> SessionTransaction:
  return Session(bind=engine).begin()


class UserRegistration(Base):
  __tablename__ = 'user_registration'
  id = Column(Integer, primary_key=True)
  first_name = Column(String)
  chat_id = Column(Integer)
