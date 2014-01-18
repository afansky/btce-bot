from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Pair(Base):
    __tablename__ = 'pairs'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __repr__(self):
        return "<Pair(id='%s', name='%s')>" % (self.id, self.name)


class TradeType(Base):
    __tabname__ = 'trade_types'

    id = Column(Integer, primary_key=True)
    name = Column(String)

    def __repr__(self):
        return "<TradeType(id='%s', name='%s')>" % (self.id, self.name)


class TradeHistory(Base):
    __tabname__ = 'trade_history'


