import pandas as pd
from freqtrade.strategy import IStrategy
from freqtrade.strategy import IntParameter, RealParameter
from pandas import DataFrame
import numpy as np

class HASKAUStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = '15m'
    minimal_roi = {"0": 0.02}
    stoploss = -0.10
    position_adjustment_enable = True

    slow_ema_period = IntParameter(5, 50, default=20, space="buy")
    kaufman_length = IntParameter(2, 20, default=5, space="buy")
    kaufman_fastend = RealParameter(1.5, 5.0, default=2.5, space="buy")
    kaufman_slowend = IntParameter(10, 40, default=20, space="buy")

    @staticmethod
    def heikin_ashi(df: DataFrame) -> DataFrame:
        required_cols = ['open', 'high', 'low', 'close']
        ha_df = DataFrame(index=df.index)
        if df.empty or not all(col in df.columns for col in required_cols):
            ha_df['ha_close'] = np.nan
            ha_df['ha_open'] = np.nan
            ha_df['ha_high'] = np.nan
            ha_df['ha_low'] = np.nan
            return ha_df

        ha_df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open = [df['open'].iloc[0]]
        for i in range(1, len(df)):
            ha_open.append((ha_open[i-1] + ha_df['ha_close'].iloc[i-1]) / 2)
        ha_df['ha_open'] = ha_open

        ha_high = pd.DataFrame({
            'ha_open': ha_df['ha_open'],
            'ha_close': ha_df['ha_close'],
            'high': df['high']
        })
        ha_df['ha_high'] = ha_high.max(axis=1)

        ha_low = pd.DataFrame({
            'ha_open': ha_df['ha_open'],
            'ha_close': ha_df['ha_close'],
            'low': df['low']
        })
        ha_df['ha_low'] = ha_low.min(axis=1)

        return ha_df

    @staticmethod
    def kaufman_ama(source, length, fastend, slowend):
        nfastend = 2 / (fastend + 1)
        nslowend = 2 / (slowend + 1)
        ama = source.copy()
        ama.iloc[:length] = source.iloc[:length]
        for i in range(length, len(source)):
            nsignal = abs(source.iloc[i] - source.iloc[i - length])
            nnoise = np.sum(np.abs(source.iloc[i - length + 1:i + 1] - source.iloc[i - length:i]))
            nefratio = nsignal / nnoise if nnoise != 0 else 0
            nsmooth = (nefratio * (nfastend - nslowend) + nslowend) ** 2
            ama.iloc[i] = ama.iloc[i - 1] + nsmooth * (source.iloc[i] - ama.iloc[i - 1])
        return ama

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ha = self.heikin_ashi(dataframe)
        dataframe['ha_close'] = ha['ha_close']
        dataframe['kaufman'] = self.kaufman_ama(
            dataframe['ha_close'],
            int(self.kaufman_length.value),
            float(self.kaufman_fastend.value),
            int(self.kaufman_slowend.value)
        )
        dataframe['fma'] = dataframe['ha_close'].ewm(span=3, adjust=False).mean()
        dataframe['sma'] = dataframe['kaufman'].ewm(span=int(self.slow_ema_period.value), adjust=False).mean()
        dataframe['golong'] = (
            (dataframe['fma'] > dataframe['sma']) &
            (dataframe['fma'].shift(1) <= dataframe['sma'].shift(1))
        )
        dataframe['goshort'] = (
            (dataframe['fma'] < dataframe['sma']) &
            (dataframe['fma'].shift(1) >= dataframe['sma'].shift(1))
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe['golong'], 'enter_long'] = 1
        dataframe.loc[dataframe['goshort'], 'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[dataframe['goshort'], 'exit_long'] = 1
        dataframe.loc[dataframe['golong'], 'exit_short'] = 1
        return dataframe