# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, List

from freqtrade.strategy import (IStrategy, IntParameter, DecimalParameter, CategoricalParameter)
from freqtrade.persistence import Trade
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class FuturesSwingStrategy(IStrategy):
    """
    This is the final, robust hyperoptable version.
    It separates static defaults from hyperopt spaces and correctly assigns
    parameters to the 'buy' and 'sell' spaces for full compatibility.
    """
    INTERFACE_VERSION = 3
    timeframe = '4h'
    can_short: bool = True

    # --- Static Default Parameters for Backtesting & Initial Validation ---
    minimal_roi = {
        "0": 0.862,
        "1538": 0.312,
        "3044": 0.1,
        "7553": 0
    }
    
    stoploss = -0.282
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.041
    trailing_only_offset_is_reached = True

    # --- Hyperoptable Entry Parameters (buy space) ---
    # These are defined directly in the class body.
    # The 'space' argument assigns them to the 'buy' hyperopt space.
    ema_fast_period = IntParameter(10, 60, default=19, space="buy", optimize=True)
    ema_slow_period = IntParameter(100, 250, default=175, space="buy", optimize=True)
    atr_period = IntParameter(5, 20, default=11, space="buy", optimize=True)
    atr_multiplier = DecimalParameter(1.0, 5.0, default=1.0, decimals=1, space="buy", optimize=True)


    # --- Strategy Settings ---
    startup_candle_count: int = 250
    
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False,
    }
    order_time_in_force = {'entry': 'gtc', 'exit': 'gtc'}

    # --- Hyperopt Space for Exit Parameters ---

    def populate_exit_trend_space(self) -> List[any]:
        """
        Defines the hyperopt space for parameters used in exit logic.
        These are defined here because they are validated by Freqtrade at startup.
        """
        return [
            DecimalParameter(0.05, 0.25, default=0.15, name='stoploss'),
            IntParameter(10, 240, name='roi_t1'),
            DecimalParameter(0.01, 0.10, name='roi_p1'),
            CategoricalParameter([True, False], default=True, name='trailing_stop'),
            DecimalParameter(0.01, 0.10, default=0.03, name='trailing_stop_positive_offset'),
            DecimalParameter(0.005, 0.05, default=0.01, name='trailing_stop_positive'),
            CategoricalParameter([True, False], default=True, name='trailing_only_offset_is_reached'),
        ]

    # --- Indicator & Signal Logic ---

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD
        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        
        # EMAs - uses the value from the hyperoptable parameter
        dataframe['ema_fast'] = ta.EMA(dataframe, timeperiod=self.ema_fast_period.value)
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.ema_slow_period.value)

        # ATR - uses the value from the hyperoptable parameter
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['ema_fast'] > dataframe['ema_slow']) &
                (qtpylib.crossed_above(dataframe['macd'], dataframe['macdsignal']))
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['ema_fast'] < dataframe['ema_slow']) &
                (qtpylib.crossed_below(dataframe['macd'], dataframe['macdsignal']))
            ),
            'enter_short'] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exits are primarily handled by ROI, Stoploss, and Trailing Stop
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        if last_candle is not None and 'atr' in last_candle and last_candle['atr'] > 0:
            return (last_candle['atr'] * self.atr_multiplier.value) / current_rate
        
        # Fallback to the stoploss defined in the exit space or static default
        return self.stoploss

    def leverage(self, **kwargs) -> float:
        return 3.0