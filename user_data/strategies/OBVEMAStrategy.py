import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta

class OBVEMAStrategy(IStrategy):
    """
    Freqtrade strategy using only OBV and OBV_EMA (hyperoptable period).
    Long: OBV crosses above its EMA.
    Short: OBV crosses below its EMA (can_short = True).
    """

    INTERFACE_VERSION = 3
    can_short: bool = True
    timeframe = "5m"
    minimal_roi = {"0": 0.02}
    stoploss = -0.10
    trailing_stop = False
    process_only_new_candles = True
    startup_candle_count: int = 50

    # Hyperoptable parameter for OBV_EMA period
    obv_ema_period = IntParameter(5, 50, default=20, space="buy", optimize=True, load=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # On-Balance Volume (OBV)
        dataframe["obv"] = ta.OBV(dataframe)
        # OBV EMA (hyperoptable period)
        dataframe["obv_ema"] = dataframe["obv"].ewm(span=self.obv_ema_period.value, adjust=False).mean()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long: OBV crosses above its EMA
        dataframe.loc[
            (dataframe["obv"] > dataframe["obv_ema"]) &
            (dataframe["obv"].shift(1) <= dataframe["obv_ema"].shift(1)) &
            (dataframe["volume"] > 0),
            "enter_long"
        ] = 1

        # Short: OBV crosses below its EMA (if shorts enabled)
        dataframe.loc[
            (dataframe["obv"] < dataframe["obv_ema"]) &
            (dataframe["obv"].shift(1) >= dataframe["obv_ema"].shift(1)) &
            (dataframe["volume"] > 0),
            "enter_short"
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit long: OBV crosses below its EMA
        dataframe.loc[
            (dataframe["obv"] < dataframe["obv_ema"]) &
            (dataframe["obv"].shift(1) >= dataframe["obv_ema"].shift(1)) &
            (dataframe["volume"] > 0),
            "exit_long"
        ] = 1

        # Exit short: OBV crosses above its EMA
        dataframe.loc[
            (dataframe["obv"] > dataframe["obv_ema"]) &
            (dataframe["obv"].shift(1) <= dataframe["obv_ema"].shift(1)) &
            (dataframe["volume"] > 0),
            "exit_short"
        ] = 1

        return dataframe