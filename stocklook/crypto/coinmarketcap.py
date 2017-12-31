"""
MIT License

Copyright (c) 2017 Zeke Barge

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Some code on this page was copied from:
https://github.com/mrsmn/coinmarketcap

Copyright 2014-2017 Martin Simon

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
import os
import json
import requests
import pandas as pd
import requests_cache
from stocklook.config import config, DATA_DIRECTORY
from stocklook.utils.database import (db_map_dict_to_alchemy_object,
                                      db_get_python_dtypes,
                                      db_describe_dict)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import (String, Boolean, DateTime, Float,
                        Integer, BigInteger, Column, ForeignKey, Table, Enum,
                        UniqueConstraint, TIMESTAMP, create_engine, func)


class CoinMCAPI(object):

    _session = None
    __DEFAULT_BASE_URL = 'https://api.coinmarketcap.com/v1/'
    __DEFAULT_TIMEOUT = 120

    def __init__(self, base_url = __DEFAULT_BASE_URL, request_timeout = __DEFAULT_TIMEOUT):
        self.base_url = base_url
        self.request_timeout = request_timeout

    @property
    def session(self):
        if not self._session:
            self._session = requests_cache.core.CachedSession(
                cache_name='coinmarketcap_cache', 
                backend='sqlite', 
                expire_after=120)
            c = {
                'Content-Type': 'application/json',
                'User-agent': 'coinmarketcap - python wrapper'
                              'around coinmarketcap.com '
                              '(github.com/zbarge/stocklook)'}
            self._session.headers.update(c)
        return self._session

    def __request(self, endpoint, params):
        response_object = self.session.get(
            self.base_url + endpoint,
            params=params,
            timeout=self.request_timeout)

        if response_object.status_code != 200:
            raise Exception('An error occured, please try again.')
        try:
            response = json.loads(response_object.text)
            if isinstance(response, list):
                response = [dict(item, **{u'cached':response_object.from_cache})
                            for item in response]
            if isinstance(response, dict):
                response[u'cached'] = response_object.from_cache
        except requests.exceptions.RequestException as e:
            return e

        return response

    def ticker(self, currency="", **kwargs):
        """
        Returns a dict containing one/all the currencies
        Optional parameters:
        (int) limit - only returns the top limit results.
        (string) convert - return price, 24h volume, and market cap in terms of another currency. Valid values are:
        "AUD", "BRL", "CAD", "CHF", "CNY", "EUR", "GBP", "HKD", "IDR", "INR", "JPY", "KRW", "MXN", "RUB"
        """

        params = {}
        params.update(kwargs)
        response = self.__request('ticker/' + currency, params)
        return response

    def stats(self, **kwargs):
        """
        Returns a dict containing cryptocurrency statistics.
        Optional parameters:
        (string) convert - return 24h volume, and market cap in terms of another currency. Valid values are:
        "AUD", "BRL", "CAD", "CHF", "CNY", "EUR", "GBP", "HKD", "IDR", "INR", "JPY", "KRW", "MXN", "RUB"
        """

        params = {}
        params.update(kwargs)
        response = self.__request('global/', params)
        return response


COINMC_COLUMN_RENAME_MAP = {
    '24h_volume_usd': '_24h_volume_usd',
}
SQLCoinMCBase = declarative_base()


class SQLCoinMCSnapshot(SQLCoinMCBase):
    __tablename__ = 'coinmc_snapshots'
    shot_id = Column(Integer, primary_key=True)

    _24h_volume_usd = Column(Integer)
    available_supply = Column(Integer)
    cached = Column(Boolean)
    id = Column(String(255))
    last_updated = Column(Integer)
    market_cap_usd = Column(Integer)
    max_supply = Column(Integer)
    name = Column(String(255))
    percent_change_1h = Column(Float)
    percent_change_24h = Column(Float)
    percent_change_7d = Column(Float)
    price_btc = Column(Float)
    price_usd = Column(Float)
    rank = Column(Integer)
    symbol = Column(String(255))
    total_supply = Column(Integer)

    def __repr__(self):
        return "SQLCoinMCSnapshot(" \
               "symbol='{}'," \
               "price_btc='{}'," \
               "price_usd='{}'," \
               "rank='{}'" \
               "percent_change_24h='{}'," \
               "percent_change_7d='{}')".format(
                self.symbol, self.price_btc,
                self.price_usd, self.rank,
                self.percent_change_24h,
                self.percent_change_7d)


class SQLCoinMCStat(SQLCoinMCBase):
    __tablename__ = 'coinmc_stats'
    stat_id = Column(Integer, primary_key=True)

    active_assets = Column(Integer)
    active_currencies = Column(Integer)
    active_markets = Column(Integer)
    bitcoin_percentage_of_market_cap = Column(Float)
    cached = Column(Boolean)
    last_updated = Column(Integer)
    total_24h_volume_usd = Column(Float)
    total_market_cap_usd = Column(Float)

    def __repr__(self):
        return "SQLCoinMCStat(" \
               "active_assets='{}'," \
               "total_24h_volume_usd='{}'" \
               "total_market_cap_usd='{}'" \
               "last_updated='{}')".format(
                self.active_assets, self.total_24h_volume_usd,
                self.total_market_cap_usd, self.last_updated)


DB_COINMC_SNAPSHOT_DTYPES = db_get_python_dtypes(SQLCoinMCSnapshot, include_str=True)
DB_COINMC_SNAPSHOT_DTYPES_ITEMS = DB_COINMC_SNAPSHOT_DTYPES.items()

DB_COINMC_STATS_DTYPES = db_get_python_dtypes(SQLCoinMCStat, include_str=True)
DB_COINMC_STATS_DTYPES_ITEMS = DB_COINMC_STATS_DTYPES.items()

DB_COINMC_TABLE_DTYPE_MAP = {
    SQLCoinMCStat.__tablename__: DB_COINMC_STATS_DTYPES_ITEMS,
    SQLCoinMCSnapshot.__tablename__: DB_COINMC_SNAPSHOT_DTYPES_ITEMS,
}

class CoinMCDatabase:
    def __init__(self, engine=None, api=None, session_maker=None):
        if api is None:
            api = CoinMCAPI()
        self._engine = engine
        self._api = api
        self._session_maker = session_maker

    @property
    def engine(self):
        if self._engine is None:
            db_path = 'sqlite:///' + os.path.join(
                config[DATA_DIRECTORY], 'coinmc.sqlite3')
            self._engine = create_engine(db_path)
            SQLCoinMCBase.metadata.create_all(bind=self._engine)

        return self._engine

    @property
    def api(self):
        return self._api

    def get_session(self):
        if self._session_maker is None:
            self._session_maker = sessionmaker(bind=self.engine)
        return self._session_maker()

    def get_sql_object(self, obj, data_dict):
        data_dict = {COINMC_COLUMN_RENAME_MAP.get(k, k): v
                     for k, v in data_dict.items()}
        return db_map_dict_to_alchemy_object(
            data_dict,
            obj,
            DB_COINMC_TABLE_DTYPE_MAP[obj.__tablename__],
            raise_on_error=False)

    def get_last_updated_time(self, session, table_obj=None):
        if table_obj is None:
            table_obj = SQLCoinMCSnapshot
        return session.query(func.max(table_obj.last_updated)).first()

    def get_snapshots_frame(self, coin_symbols=None):
        df = pd.read_sql("SELECT * FROM {}".format(SQLCoinMCSnapshot.__tablename__),
                         self.engine,
                         coerce_float=False, )
        if coin_symbols:
            return df.loc[df['symbol'].isin(coin_symbols), :]

        return df

    def sync_data(self, session):
        stats = self.api.stats()
        stats_obj = self.get_sql_object(SQLCoinMCStat, stats)

        tickers = self.api.ticker()
        ticker_objs = [self.get_sql_object(SQLCoinMCSnapshot, t)
                       for t in tickers]

        session.add_all(ticker_objs + [stats_obj])
        session.commit()

        return stats_obj, ticker_objs




if __name__ == '__main__':
    db = CoinMCDatabase()
    session = db.get_session()
    stats, ticks = db.sync_data(session)

    print(stats)
    for t in ticks:
        print(t)
    