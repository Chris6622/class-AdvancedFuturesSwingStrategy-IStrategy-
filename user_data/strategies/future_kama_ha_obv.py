# --- Do not remove these libs ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy
from freqtrade.strategy import DecimalParameter, IntParameter
from functools import reduce

# --- Technical analysis library ---
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class FutureKamaHaObv(IStrategy):
    """
    Strategy: Adaptive Trend Confirmation
    Author: Gemini AI
    Version: 1.3 (Corrected column overlap issue by renaming HA columns)

    Description:
    This futures strategy uses a combination of KAMA, Heikin Ashi, and OBV.
    - KAMA defines the adaptive trend.
    - Heikin Ashi provides smooth momentum-based entry triggers.
    - OBV confirms that volume supports the trade direction.
    Exits are based on a reversal in the Heikin Ashi candle pattern.
    """

    # --- Strategy Configuration ---
    INTERFACE_VERSION = 3
    timeframe = '15m'
    can_short = True

    # --- Risk Management ---
    stoploss = -0.05  # 5% stop-loss. MUST be optimized.
    minimal_roi = {
        "0": 100 # Disable ROI, rely on Heikin Ashi exit signal
    }

    # --- Trailing Stop ---
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # --- Hyperparameters ---
    buy_kama_period = IntParameter(20, 80, default=60, space="buy")
    buy_obv_sma_period = IntParameter(10, 30, default=20, space="buy")
    
    sell_kama_period = IntParameter(20, 80, default=60, space="sell")
    sell_obv_sma_period = IntParameter(10, 30, default=20, space="sell")


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds all necessary indicators to the given DataFrame
        """
        # --- Heikin Ashi ---------------
        ha_df = qtpylib.heikinashi(dataframe)

        # First, rename the Heikin Ashi columns to avoid a name collision
        ha_df.rename(columns={'open': 'ha_open', 'high': 'ha_high', 'low': 'ha_low', 'close': 'ha_close'}, inplace=True)

        # Now, join the renamed Heikin Ashi dataframe to the main dataframe
        dataframe = dataframe.join(ha_df)


        # --- Trend Indicator: KAMA ---
        dataframe['kama_buy'] = ta.KAMA(dataframe, timeperiod=self.buy_kama_period.value)
        dataframe['kama_sell'] = ta.KAMA(dataframe, timeperiod=self.sell_kama_period.value)

        # --- Volume Confirmation: OBV ---
        dataframe['obv'] = ta.OBV(dataframe)
        dataframe['obv_sma_buy'] = ta.SMA(dataframe['obv'], timeperiod=self.buy_obv_sma_period.value)
        dataframe['obv_sma_sell'] = ta.SMA(dataframe['obv'], timeperiod=self.sell_obv_sma_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on the populated indicators, combines them to generate entry signals.
        """
        # --- Long Entry Conditions ---
        long_conditions = [
            # 1. Main Trend is UP (Price is above adaptive MA)
            (dataframe['close'] > dataframe['kama_buy']),
            # 2. Volume confirms bullish pressure (OBV is above its own SMA)
            (dataframe['obv'] > dataframe['obv_sma_buy']),
            # 3. Heikin Ashi momentum signal: A green candle appears
            (qtpylib.crossed_above(dataframe['ha_close'], dataframe['ha_open']))
        ]

        # --- Short Entry Conditions ---
        short_conditions = [
            # 1. Main Trend is DOWN (Price is below adaptive MA)
            (dataframe['close'] < dataframe['kama_sell']),
            # 2. Volume confirms bearish pressure (OBV is below its own SMA)
            (dataframe['obv'] < dataframe['obv_sma_sell']),
            # 3. Heikin Ashi momentum signal: A red candle appears
            (qtpylib.crossed_below(dataframe['ha_close'], dataframe['ha_open']))
        ]

        # Combine conditions with 'and'
        if long_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, long_conditions),
                'enter_long'] = 1

        if short_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, short_conditions),
                'enter_short'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on the populated indicators, generates custom exit signals.
        The exit is a reversal in the Heikin Ashi pattern.
        """
        # --- Long Exit Condition: A red HA candle appears ---
        long_exit_conditions = [
            qtpylib.crossed_below(dataframe['ha_close'], dataframe['ha_open'])
        ]

        # --- Short Exit Condition: A green HA candle appears ---
        short_exit_conditions = [
            qtpylib.crossed_above(dataframe['ha_close'], dataframe['ha_open'])
        ]
        
        # Combine conditions
        if long_exit_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, long_exit_conditions),
                'exit_long'] = 1

        if short_exit_conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, short_exit_conditions),
                'exit_short'] = 1

        return dataframe