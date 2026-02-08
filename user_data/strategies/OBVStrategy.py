import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

import talib.abstract as ta
from technical import qtpylib

class OBVStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short: bool = True

    minimal_roi = {
        "0": 0.068,
        "63": 0.045,
        "106": 0.015,
        "375": 0
    }

    stoploss = -0.294

    trailing_stop = True
    trailing_only_offset_is_reached = False
    trailing_stop_positive = 0.122
    trailing_stop_positive_offset = 0.176

    timeframe = "5m"
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    buy_rsi = IntParameter(1, 50, default=30, space="buy", optimize=True, load=True)
    sell_rsi = IntParameter(50, 100, default=70, space="sell", optimize=True, load=True)
    short_rsi = IntParameter(51, 100, default=70, space="sell", optimize=True, load=True)
    exit_short_rsi = IntParameter(1, 50, default=30, space="buy", optimize=True, load=True)
    obv_sma_window = IntParameter(5, 30, default=12, space="buy", optimize=True, load=True)

    startup_candle_count: int = 200

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    plot_config = {
        "main_plot": {
            "tema": {},
            "sar": {"color": "white"},
        },
        "subplots": {
            "MACD": {
                "macd": {"color": "blue"},
                "macdsignal": {"color": "orange"},
            },
            "RSI": {
                "rsi": {"color": "red"},
            },
        },
    }

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe)
        dataframe["obv"] = ta.OBV(dataframe)
        dataframe["obv_SMA"] = dataframe["obv"].rolling(window=self.obv_sma_window.value).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value) &
                qtpylib.crossed_above(dataframe["obv"], dataframe["obv_SMA"])
            ),
            'enter_long'
        ] = 1

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["rsi"], self.short_rsi.value) &
                qtpylib.crossed_below(dataframe["obv"], dataframe["obv_SMA"])
            ),
            'enter_short'
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0

        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value) &
                qtpylib.crossed_below(dataframe["obv"], dataframe["obv_SMA"])
            ),
            'exit_long'
        ] = 1

        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe["rsi"], self.exit_short_rsi.value) &
                qtpylib.crossed_above(dataframe["obv"], dataframe["obv_SMA"])
            ),
            'exit_short'
        ] = 1

        return dataframe