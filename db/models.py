from sqlalchemy import Column, String, Float, Integer, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session
from settings import get_settings


class Base(DeclarativeBase):
    pass


class Receipt(Base):
    __tablename__ = "receipts"

    id = Column(String, primary_key=True)  # store:receipt_id
    store = Column(String, nullable=False)  # lidl|albert|penny
    receipt_id = Column(String, nullable=False)
    date = Column(String)
    total_czk = Column(Float)
    raw_json = Column(Text)


class ReceiptItem(Base):
    __tablename__ = "receipt_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_pk = Column(String, nullable=False)  # FK to receipts.id
    name = Column(String)
    quantity = Column(Float)
    unit_price_czk = Column(Float)
    total_price_czk = Column(Float)


class StoreToken(Base):
    __tablename__ = "store_tokens"

    store = Column(String, primary_key=True)  # e.g. "albert"
    access_token = Column(Text)
    refresh_token = Column(String)


def get_engine():
    return create_engine(get_settings().db_url)


def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session(engine=None) -> Session:
    if engine is None:
        engine = get_engine()
    return Session(engine)
