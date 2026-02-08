# --- Do not remove these libs ---
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional
from freqtrade.strategy import IStrategy
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

# --- Main Strategy Class ---
class GmmaFutures(IStrategy):
    """
    A futures trading strategy based on the GMMA, with a fixed 2x leverage.
    """

    # --- Strategy Configuration ---
    timeframe = '1h'
    can_short = True
    stoploss = -0.10
    minimal_roi = {"0": 100} # Let the exit signal close the trade
    trailing_stop = False

    # --- Leverage Method ---
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, entry_tag: Optional[str],
                 side: str, **kwargs) -> float:
        """
        Sets a fixed leverage of 2.0 for all trades.
        This will override the leverage setting in your config file for this strategy.
        """
        return 2.0

    # --- Static Indicator Definitions ---
    # Guppy EMA periods are hard-coded
    short_ema_periods = [3, 5, 8, 10, 12, 15]
    long_ema_periods = [30, 35, 40, 45, 50, 60]

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Adds all necessary indicators to the given DataFrame
        """
        # Calculate all short-term EMAs
        for period in self.short_ema_periods:
            dataframe[f'ema_short_{period}'] = ta.EMA(dataframe, timeperiod=period)

        # Calculate all long-term EMAs
        for period in self.long_ema_periods:
            dataframe[f'ema_long_{period}'] = ta.EMA(dataframe, timeperiod=period)
        
        # To simplify logic, create a 'boundary' for each group.
        short_ema_cols = [f'ema_short_{p}' for p in self.short_ema_periods]
        dataframe['short_ema_min'] = dataframe[short_ema_cols].min(axis=1)
        dataframe['short_ema_max'] = dataframe[short_ema_cols].max(axis=1)

        long_ema_cols = [f'ema_long_{p}' for p in self.long_ema_periods]
        dataframe['long_ema_min'] = dataframe[long_ema_cols].min(axis=1)
        dataframe['long_ema_max'] = dataframe[long_ema_cols].max(axis=1)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Based on TA indicators, populates the entry signal for long and short positions.
        """
        # --- LONG ENTRY ---
        enter_long_condition = (
            qtpylib.crossed_above(dataframe['short_ema_min'], dataframe['long_ema_max'])
        )

        # --- SHORT ENTRY ---
        enter_short_condition = (
            qtpylib.crossed_below(dataframe['short_ema_max'], dataframe['long_ema_min'])
        )

        # Populate the enter signals
        dataframe.loc[enter_long_condition, 'enter_long'] = 1
        dataframe.loc[enter_short_condition, 'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        """
        Based on TA indicators, populates the exit signal for long and short positions.
        """
        # --- LONG EXIT ---
        exit_long_condition = (
            qtpylib.crossed_below(dataframe['short_ema_max'], dataframe['long_ema_min'])
        )

        # --- SHORT EXIT ---
        exit_short_condition = (
            qtpylib.crossed_above(dataframe['short_ema_min'], dataframe['long_ema_max'])
        )

        # Populate the exit signals
        dataframe.loc[exit_long_condition, 'exit_long'] = 1
        dataframe.loc[exit_short_condition, 'exit_short'] = 1

        return dataframe