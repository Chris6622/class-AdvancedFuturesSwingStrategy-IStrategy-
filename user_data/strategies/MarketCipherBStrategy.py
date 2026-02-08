# --- Do not remove these libs ---
from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import IntParameter, DecimalParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class MarketCipherBStrategy(IStrategy):
    INTERFACE_VERSION = 3

    # --- Hyperopt / Strategy Parameters ---
    minimal_roi = {
        "0": 0.03,
    }
    stoploss = -0.10
    timeframe = '1h'

    # --- Trailing stop (hyperoptable) ---
    trailing_stop = True
    trailing_stop_positive = DecimalParameter(0.005, 0.05, default=0.02, decimals=3, space="sell")
    trailing_stop_positive_offset = DecimalParameter(0.01, 0.1, default=0.03, decimals=3, space="sell")
    trailing_only_offset_is_reached = True

    # --- Hyperoptable thresholds (long) ---
    wt1_oversold = IntParameter(-60, -10, default=-20, space="buy")
    money_flow_min = DecimalParameter(-10, 2, default=0, decimals=2, space="buy")
    wt1_overbought = IntParameter(10, 80, default=60, space="sell")
    money_flow_max = DecimalParameter(-5, 5, default=0, decimals=2, space="sell")

    # --- Hyperoptable thresholds (short) ---
    wt1_overbought_short = IntParameter(10, 80, default=53, space="short")
    money_flow_max_short = DecimalParameter(-5, 5, default=0, decimals=2, space="short")
    wt1_oversold_short = IntParameter(-60, -10, default=-53, space="short")
    money_flow_min_short = DecimalParameter(-10, 2, default=0, decimals=2, space="short")

    # --- Hyperoptable indicator parameters ---
    n1 = IntParameter(6, 16, default=9, space="buy")
    n2 = IntParameter(10, 30, default=21, space="buy")
    moneyFlowPeriod = IntParameter(5, 16, default=9, space="buy")
    moneyFlowMultiplier = DecimalParameter(1, 10, default=5, decimals=2, space="buy")
    moneyFlowPeriodSlow = IntParameter(6, 20, default=10, space="buy")
    moneyFlowMultiplierSlow = DecimalParameter(1, 10, default=5, decimals=2, space="buy")

    # --- Main Indicator Calculation ---
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ap = dataframe['close']
        esa = ta.EMA(ap, timeperiod=self.n1.value)
        d = ta.EMA(np.abs(ap - esa), timeperiod=self.n1.value)
        ci = (ap - esa) / (0.015 * d)
        tci = ta.EMA(ci, timeperiod=self.n2.value)
        wt1 = tci
        wt2 = ta.SMA(wt1, timeperiod=2)

        dataframe['wt1'] = wt1
        dataframe['wt2'] = wt2

        # Money Flow
        hlc3 = (dataframe['high'] + dataframe['low'] + dataframe['close']) / 3
        sma_hlc3 = ta.SMA(hlc3, timeperiod=self.moneyFlowPeriod.value)
        sma_hl = ta.SMA(dataframe['high'] - dataframe['low'], timeperiod=self.moneyFlowPeriod.value)
        rawMoneyFlow = (2 * ta.SMA(hlc3 - sma_hlc3, timeperiod=self.moneyFlowPeriod.value)) / sma_hl
        moneyFlow = rawMoneyFlow * self.moneyFlowMultiplier.value
        dataframe['money_flow'] = moneyFlow

        # Slow Money Flow
        sma_hlc3_slow = ta.SMA(hlc3, timeperiod=self.moneyFlowPeriodSlow.value)
        sma_hl_slow = ta.SMA(dataframe['high'] - dataframe['low'], timeperiod=self.moneyFlowPeriodSlow.value)
        rawMoneyFlowSlow = (2 * ta.SMA(hlc3 - sma_hlc3_slow, timeperiod=self.moneyFlowPeriodSlow.value)) / sma_hl_slow
        moneyFlowSlow = rawMoneyFlowSlow * self.moneyFlowMultiplierSlow.value
        dataframe['money_flow_slow'] = moneyFlowSlow

        # Bullish/Bearish WT Cross
        dataframe['bullish_cross'] = (dataframe['wt1'] > dataframe['wt2']) & (dataframe['wt1'].shift(1) <= dataframe['wt2'].shift(1))
        dataframe['bearish_cross'] = (dataframe['wt1'] < dataframe['wt2']) & (dataframe['wt1'].shift(1) >= dataframe['wt2'].shift(1))
        return dataframe

    # --- Long Entry Logic ---
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['bullish_cross']) &
                (dataframe['wt1'] < self.wt1_oversold.value) &
                (dataframe['money_flow'] > self.money_flow_min.value)
            ),
            'enter_long'
        ] = 1
        return dataframe

    # --- Long Exit Logic ---
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['bearish_cross']) &
                (dataframe['wt1'] > self.wt1_overbought.value) &
                (dataframe['money_flow'] < self.money_flow_max.value)
            ),
            'exit_long'
        ] = 1
        return dataframe

    # --- Short Entry Logic ---
    def populate_entry_trend_short(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['bearish_cross']) &
                (dataframe['wt1'] > self.wt1_overbought_short.value) &
                (dataframe['money_flow'] < self.money_flow_max_short.value)
            ),
            'enter_short'
        ] = 1
        return dataframe

    # --- Short Exit Logic ---
    def populate_exit_trend_short(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['bullish_cross']) &
                (dataframe['wt1'] < self.wt1_oversold_short.value) &
                (dataframe['money_flow'] > self.money_flow_min_short.value)
            ),
            'exit_short'
        ] = 1
        return dataframe