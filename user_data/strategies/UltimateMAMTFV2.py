import numpy as np
import pandas as pd
from freqtrade.strategy import (
    IStrategy,
    CategoricalParameter,
    IntParameter,
    DecimalParameter
)
from pandas import DataFrame

class UltimateMAMTFV2(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '1h'
    stoploss = -0.10

    minimal_roi = {
        "0": 0.05,
        "30": 0.03,
        "60": 0.01,
        "120": 0
    }

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # --- Hyperoptable parameters for MA1 and MA2, including T3 factor ---
    ma1_type = CategoricalParameter(['sma', 'ema', 'wma', 'hull', 'vwma', 'rma', 'tema', 't3'], default='ema', space='buy', optimize=True)
    ma1_len = IntParameter(5, 100, default=20, space='buy', optimize=True)
    ma1_t3_factor = DecimalParameter(0.1, 1.0, default=0.7, decimals=2, space='buy', optimize=True)

    ma2_type = CategoricalParameter(['sma', 'ema', 'wma', 'hull', 'vwma', 'rma', 'tema', 't3'], default='sma', space='buy', optimize=True)
    ma2_len = IntParameter(5, 100, default=50, space='buy', optimize=True)
    ma2_t3_factor = DecimalParameter(0.1, 1.0, default=0.7, decimals=2, space='buy', optimize=True)

    # Hyperoptable: which crossover style to use
    crossover_type = CategoricalParameter(['price_ma1', 'ma1_ma2'], default='ma1_ma2', space='buy', optimize=True)

    use_ma2 = True  # Enable MA2 for cross signals

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ma1'] = self._ma(
            dataframe,
            self.ma1_type.value,
            self.ma1_len.value,
            self.ma1_t3_factor.value
        )
        if self.use_ma2 or (self.crossover_type.value == 'ma1_ma2'):
            dataframe['ma2'] = self._ma(
                dataframe,
                self.ma2_type.value,
                self.ma2_len.value,
                self.ma2_t3_factor.value
            )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.crossover_type.value == 'ma1_ma2' and self.use_ma2:
            # Entry LONG: MA1 crosses above MA2
            dataframe.loc[
                (
                    (dataframe['ma1'] > dataframe['ma2']) &
                    (dataframe['ma1'].shift(1) <= dataframe['ma2'].shift(1))
                ),
                'entry_long'
            ] = 1
            # Entry SHORT: MA1 crosses below MA2
            dataframe.loc[
                (
                    (dataframe['ma1'] < dataframe['ma2']) &
                    (dataframe['ma1'].shift(1) >= dataframe['ma2'].shift(1))
                ),
                'entry_short'
            ] = 1
        else:
            # price / MA1 crossover
            dataframe.loc[
                (
                    (dataframe['close'] > dataframe['ma1']) &
                    (dataframe['close'].shift(1) <= dataframe['ma1'].shift(1))
                ),
                'entry_long'
            ] = 1
            dataframe.loc[
                (
                    (dataframe['close'] < dataframe['ma1']) &
                    (dataframe['close'].shift(1) >= dataframe['ma1'].shift(1))
                ),
                'entry_short'
            ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        if self.crossover_type.value == 'ma1_ma2' and self.use_ma2:
            # Exit LONG: MA1 crosses below MA2
            dataframe.loc[
                (
                    (dataframe['ma1'] < dataframe['ma2']) &
                    (dataframe['ma1'].shift(1) >= dataframe['ma2'].shift(1))
                ),
                'exit_long'
            ] = 1
            # Exit SHORT: MA1 crosses above MA2
            dataframe.loc[
                (
                    (dataframe['ma1'] > dataframe['ma2']) &
                    (dataframe['ma1'].shift(1) <= dataframe['ma2'].shift(1))
                ),
                'exit_short'
            ] = 1
        else:
            # price / MA1 crossover
            dataframe.loc[
                (
                    (dataframe['close'] < dataframe['ma1']) &
                    (dataframe['close'].shift(1) >= dataframe['ma1'].shift(1))
                ),
                'exit_long'
            ] = 1
            dataframe.loc[
                (
                    (dataframe['close'] > dataframe['ma1']) &
                    (dataframe['close'].shift(1) <= dataframe['ma1'].shift(1))
                ),
                'exit_short'
            ] = 1
        return dataframe

    def _ma(self, dataframe: DataFrame, ma_type: str, length: int, t3_factor: float):
        if ma_type == 'sma':
            return dataframe['close'].rolling(length).mean()
        elif ma_type == 'ema':
            return dataframe['close'].ewm(span=length, adjust=False).mean()
        elif ma_type == 'wma':
            weights = np.arange(1, length + 1)
            return dataframe['close'].rolling(length).apply(
                lambda prices: np.dot(prices, weights)/weights.sum(), raw=True)
        elif ma_type == 'hull':
            half_length = int(length / 2)
            sqrt_length = int(np.sqrt(length))
            wma1 = dataframe['close'].rolling(half_length).apply(
                lambda x: np.dot(x, np.arange(1, half_length+1)) / np.arange(1, half_length+1).sum(), raw=True)
            wma2 = dataframe['close'].rolling(length).apply(
                lambda x: np.dot(x, np.arange(1, length+1)) / np.arange(1, length+1).sum(), raw=True)
            hull = 2 * wma1 - wma2
            return hull.rolling(sqrt_length).mean()
        elif ma_type == 'vwma':
            v = dataframe['volume']
            p = dataframe['close']
            vwma = (p * v).rolling(length).sum() / v.rolling(length).sum()
            return vwma
        elif ma_type == 'rma':
            return dataframe['close'].ewm(alpha=1/length, adjust=False).mean()
        elif ma_type == 'tema':
            ema1 = dataframe['close'].ewm(span=length, adjust=False).mean()
            ema2 = ema1.ewm(span=length, adjust=False).mean()
            ema3 = ema2.ewm(span=length, adjust=False).mean()
            return 3 * (ema1 - ema2) + ema3
        elif ma_type == 't3':
            def _gd(series, length, factor):
                ema1 = series.ewm(span=length, adjust=False).mean()
                ema2 = ema1.ewm(span=length, adjust=False).mean()
                return ema1 * (1 + factor) - ema2 * factor
            factor = t3_factor
            gd1 = _gd(dataframe['close'], length, factor)
            gd2 = _gd(gd1, length, factor)
            gd3 = _gd(gd2, length, factor)
            return gd3
        else:
            return dataframe['close'].rolling(length).mean()