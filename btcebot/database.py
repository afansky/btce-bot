# Copyright (c) 2013 Alan McIntyre

import decimal
from pymongo import MongoClient


# Add support for conversion to/from decimal
def adapt_decimal(d):
    return int(d * decimal.Decimal("1e8"))


def convert_decimal(s):
    return decimal.Decimal(s) * decimal.Decimal("1e-8")


class MarketDatabase(object):
    def __init__(self):
        self.client = MongoClient('mongodb://192.168.1.102:27017/')
        self.db = self.client.tradebot

    def close(self):
        self.client.close()

    def insert_trade_history(self, trade_data):
        pass

    def retrieve_trade_history(self, start_date, end_date, pair):
        pass

    def insert_tick(self, time, pair, tick):
        tick_hash = {"time": time, "pair": pair, "updated": tick.updated, "server_time": tick.server_time,
                     "high": float(tick.high), "low": float(tick.low), "avg": float(tick.avg), "last": float(tick.last),
                     "buy": float(tick.buy), "sell": float(tick.sell), "vol": float(tick.vol),
                     "vol_cur": float(tick.vol_cur)}
        self.db.ticks.insert(tick_hash)

    def retrieve_ticks(self, pair, start_time, end_time):
        ticks = self.db.ticks.find({"pair": pair, "time": {"$gte": start_time, "$lte": end_time}})
        return list(ticks)

    def insert_depth(self, dt, pair, asks, bids):
        pass

    def retrieve_depth(self, start_date, end_date, pair):
        pass
