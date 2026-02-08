from freqtrade.strategy import IStrategy, merge_informative_pair, IntParameter, DecimalParameter
from pandas import DataFrame
import numpy as np
import talib.abstract as ta

class VolatilityGaussianBandsStrategy(IStrategy):
    INTERFACE_VERSION = 3
    can_short = False

    gaussian_length = IntParameter(5, 60, default=20, space="buy", optimize=True)
    band_distance   = DecimalParameter(0.5, 3.0, decimals=2, default=1.0, space="buy", optimize=True)

    minimal_roi = { "0": 0.03 }
    stoploss = -0.10

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    timeframe = '5m'

    @property
    def leverage(self) -> float:
        return 3.0

    def gaussian_filter(self, src: np.ndarray, length: int, sigma: float = 10) -> np.ndarray:
        x = np.arange(length)
        center = (length - 1) / 2
        weights = np.exp(-0.5 * ((x - center) / sigma) ** 2)
        weights /= np.sum(weights)
        return np.convolve(src, weights, mode='same')

    def multi_trend(self, df: DataFrame, price_col: str = 'close', period: int = 20, mode: str = 'AVG', band_distance: float = 1.0):
        src = df[price_col].values
        g_values = []
        for step in range(21):
            length = period + step
            if length > len(src):
                break
            filtered = self.gaussian_filter(src, length)
            g_values.append(filtered)
        g_values = np.vstack(g_values)
        if mode == 'AVG':
            value = np.mean(g_values, axis=0)
        elif mode == 'MEADIAN':
            value = np.median(g_values, axis=0)
        elif mode == 'MODE':
            value = np.median(g_values, axis=0)
        else:
            value = np.mean(g_values, axis=0)
        volatility = ta.SMA(df['high'] - df['low'], timeperiod=100)
        lower_band = value - volatility * band_distance
        upper_band = value + volatility * band_distance
        close = df[price_col]
        trend = (close > upper_band).astype(int) - (close < lower_band).astype(int)
        score = (close - value) / (volatility + 1e-8)
        trend_line = np.where(trend > 0, lower_band, upper_band)
        return value, lower_band, upper_band, trend, score, trend_line

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        avg, lower, upper, trend, score, trend_line = self.multi_trend(
            dataframe,
            price_col='close',
            period=self.gaussian_length.value,
            mode='AVG',
            band_distance=self.band_distance.value
        )
        dataframe['vgb_avg'] = avg
        dataframe['vgb_lower'] = lower
        dataframe['vgb_upper'] = upper
        dataframe['vgb_trend'] = trend
        dataframe['vgb_score'] = score
        dataframe['vgb_trend_line'] = trend_line
        dataframe['vgb_crossup'] = (dataframe['close'] > trend_line) & (dataframe['close'].shift(1) <= trend_line)
        dataframe['vgb_crossdn'] = (dataframe['close'] < trend_line) & (dataframe['close'].shift(1) >= trend_line)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # LONG ENTRY
        dataframe.loc[
            (
                (dataframe['vgb_crossup']) &
                (dataframe['vgb_trend'] > 0) &
                (dataframe['volume'] > 0)
            ),
            ['enter_long', 'enter_tag']
        ] = (1, 'vgb_long')

        # SHORT ENTRY
        dataframe.loc[
            (
                (dataframe['vgb_crossdn']) &
                (dataframe['vgb_trend'] < 0) &
                (dataframe['volume'] > 0)
            ),
            ['enter_short', 'enter_tag']
        ] = (1, 'vgb_short')

        print("Long signals:", dataframe['enter_long'].sum())
        print("Short signals:", dataframe['enter_short'].sum())

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # LONG EXIT
        dataframe.loc[
            (
                (dataframe['vgb_crossdn']) &
                (dataframe['vgb_trend'] < 0) &
                (dataframe['volume'] > 0)
            ),
            ['exit_long', 'exit_tag']
        ] = (1, 'vgb_exit_long')

        # SHORT EXIT
        dataframe.loc[
            (
                (dataframe['vgb_crossup']) &
                (dataframe['vgb_trend'] > 0) &
                (dataframe['volume'] > 0)
            ),
            ['exit_short', 'exit_tag']
        ] = (1, 'vgb_exit_short')

        # --- Debug print statements ---
        print("Long exits:", dataframe['exit_long'].sum())
        print("Short exits:", dataframe['exit_short'].sum())

        return dataframe