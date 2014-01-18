# Copyright (c) 2013 Alan McIntyre

import cPickle
import datetime
import decimal
import os.path
import sqlite3
import threading
import time

import btceapi
from btceapi.public import Trade

from pymongo import MongoClient

# engine = create_engine('mysql://scott:tiger@localhost/test')
# session_factory = sessionmaker(bind=engine)
# Session = scoped_session(session_factory)



# Add support for conversion to/from decimal
def adapt_decimal(d):
    return int(d * decimal.Decimal("1e8"))


def convert_decimal(s):
    return decimal.Decimal(s) * decimal.Decimal("1e-8")


sqlite3.register_adapter(decimal.Decimal, adapt_decimal)
sqlite3.register_converter("DECIMAL", convert_decimal)


class MarketDatabase(object):
    def __init__(self, database_path):
        self.client = MongoClient('mongodb://192.168.1.102:27017/')
        self.db = self.client.tradebot
        create = not os.path.isfile(database_path)
        self.connection = sqlite3.connect(database_path)
        self.cursor = self.connection.cursor()
        if create:
            # The database is new, so create tables and populate the enumerations.
            self.createTables()

            # Pairs table
            pairs = zip(range(len(btceapi.all_pairs)), btceapi.all_pairs)
            self.cursor.executemany("INSERT INTO pairs VALUES(?, ?)", pairs)
            self.pair_to_index = dict((p, i) for i, p in pairs)
            self.index_to_pair = dict(pairs)

            # Trade types table
            trade_types = [(0, "bid"), (1, "ask")]
            self.cursor.executemany("INSERT INTO trade_types VALUES(?, ?)", trade_types)
            self.tradetype_to_index = dict((tt, i) for i, tt in trade_types)
            self.index_to_tradetype = dict(trade_types)

            self.connection.commit()

        else:
            # The database isn't new, so just retrieve enumerations from it.

            self.cursor.execute("SELECT id, name from pairs")
            self.index_to_pair = dict(self.cursor.fetchall())
            self.pair_to_index = dict((p, i) for i, p in self.index_to_pair.items())

            self.cursor.execute("SELECT id, name from trade_types")
            self.index_to_tradetype = dict(self.cursor.fetchall())
            self.tradetype_to_index = dict((p, i) for i, p in self.index_to_tradetype.items())

    def createTables(self):
        self.cursor.execute('''
            CREATE TABLE pairs(
                id INT PRIMARY KEY,
                name TEXT
            );''')

        self.cursor.execute('''
            CREATE TABLE trade_types(
                id INT PRIMARY KEY,
                name TEXT
            );''')

        self.cursor.execute('''
            CREATE TABLE trade_history(
                tid INT PRIMARY KEY,
                pair INT,
                trade_type INT,
                price REAL,
                amount REAL,
                date DATETIME,
                FOREIGN KEY(pair) REFERENCES pairs(id),
                FOREIGN KEY(trade_type) REFERENCES trade_types(id)
            );''')

        self.cursor.execute('''
            CREATE TABLE depth(
                date DATETIME,
                pair INT,
                asks BLOB,
                bids BLOB,
                FOREIGN KEY(pair) REFERENCES pairs(id)
            );''')

        self.cursor.execute('''
            CREATE TABLE ticks(
                date DATETIME,
                pair INT,
                updated DATETIME,
                server_time DATETIME,
                high_price REAL,
                low_price REAL,
                avg_price REAL,
                last_price REAL,
                buy_price REAL,
                sell_price REAL,
                volume REAL,
                current_volume REAL,
                FOREIGN KEY(pair) REFERENCES pairs(id)
        );''')

        self.connection.commit()

    def close(self):
        self.cursor = None
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def tupleFromTrade(self, t):
        return (t.tid,
                self.pair_to_index[t.pair],
                self.tradetype_to_index[t.trade_type],
                t.price,
                t.amount,
                t.date)

    def insertTradeHistory(self, trade_data):
        '''
        Add one or more trades to the trade history store.  If trade_data is a
        list, then it is assumed to be a list of multiple trades; if it is a tuple,
        or a btceapi.Trade object, it is assumed to represent a single trade.
        Tuples should be (trade id, pair id, trade type id, price, amount, date).
        '''
        if type(trade_data) is not list:
            trade_data = [trade_data]

        if type(trade_data[0]) is Trade:
            trade_data = map(self.tupleFromTrade, trade_data)

        self.cursor.executemany("INSERT OR IGNORE INTO trade_history VALUES(?, ?, ?, ?, ?, ?)", trade_data)
        self.connection.commit()

    def retrieveTradeHistory(self, start_date, end_date, pair):
        vars = ("tid", "trade_type", "price", "amount", "date", "pair", "trade_type")
        pair_index = self.pair_to_index[pair]
        sql = """select tid, trade_type, price, amount, date, pairs.name, trade_types.name
           from trade_history, pairs, trade_types
           where pair == ? and date >= ?
               and date <= ?
               and trade_history.pair == pairs.id
               and trade_history.trade_type == trade_types.id
           order by date"""

        for row in self.cursor.execute(sql, (pair_index, start_date, end_date)):
            row = dict(zip(vars, row))
            yield Trade(**row)

    def insertTick(self, time, pair, tick):
        tick_hash = {"time": time, "pair": pair, "updated": tick.updated, "server_time": tick.server_time,
                     "high": float(tick.high), "low": float(tick.low), "avg": float(tick.avg), "last": float(tick.last),
                     "buy": float(tick.buy), "sell": float(tick.sell), "vol": float(tick.vol),
                     "vol_cur": float(tick.vol_cur)}
        self.db.ticks.insert(tick_hash)

    def retrieveTicks(self, pair, start_time, end_time):
        pair_index = self.pair_to_index[pair]
        sql = """select date, pair, updated, server_time, high_price, low_price, avg_price, last_price, buy_price, sell_price, volume, current_volume from ticks where pair == ? and date >= ? and date <= ?"""
        ticks = []
        for date, pair, updated, server_time, high_price, low_price, avg_price, last_price, buy_price, sell_price, volume, current_volume in self.cursor.execute(sql, (pair_index, start_time, end_time)):
            ticks.append((datetime.datetime.strptime(date, '%Y-%m-%d %H:%M:%S.%f'), self.index_to_pair[pair], updated, server_time, high_price, low_price, avg_price, last_price, buy_price, sell_price, volume, current_volume))
        return ticks

    def insertDepth(self, dt, pair, asks, bids):
        depth_data = (dt,
                      self.pair_to_index[pair],
                      cPickle.dumps(asks),
                      cPickle.dumps(bids))
        self.cursor.execute("INSERT INTO depth VALUES(?, ?, ?, ?)", depth_data)
        self.connection.commit()

    def retrieveDepth(self, start_date, end_date, pair):
        pair_index = self.pair_to_index[pair]
        sql = """select date, asks, bids
                 from depth, pairs
                 where pair == ? 
                     and date >= ?
                     and date <= ?
                     and depth.pair == pairs.id
                 order by date"""

        depth = []
        for d, asks, bids in self.cursor.execute(sql, (pair_index, start_date, end_date)):
            dt, frac = d.split(".")
            # TODO: refactor this somewhere
            d = datetime.datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
            asks = cPickle.loads(str(asks))
            bids = cPickle.loads(str(bids))
            yield d, asks, bids
