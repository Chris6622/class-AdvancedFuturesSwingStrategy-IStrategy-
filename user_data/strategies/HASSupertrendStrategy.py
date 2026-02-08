from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
import pandas as pd
import numpy as np
import talib.abstract as ta

class HASSupertrendStrategy(IStrategy):
    # Hyperoptable Supertrend factor (buy param)
    st_factor = DecimalParameter(0.5, 5.0, default=4.79, space="buy", optimize=True, decimals=2)

    # Hyperoptable RSI/EMA thresholds for exit
    rsi_exit_threshold = IntParameter(35, 55, default=45, space="sell", optimize=True)
    ema_exit_period = IntParameter(10, 50, default=20, space="sell", optimize=True)

    timeframe = "15m"
    can_short = True

    # Trailing stop settings (static)
    trailing_stop = True
    trailing_stop_positive = 0.011
    trailing_stop_positive_offset = 0.107
    trailing_only_offset_is_reached = True

    # Stoploss (static)
    stoploss = -0.15

    # ROI table (static)
    minimal_roi = {
        "0": 0.232,
        "120": 0.159,
        "264": 0.056,
        "614": 0
    }

    def heikin_ashi(self, df):
        ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open = df['open'].copy()
        ha_open.iloc[0] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2
        for i in range(1, len(df)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        ha_high = pd.concat([df['high'], ha_open, ha_close], axis=1).max(axis=1)
        ha_low = pd.concat([df['low'], ha_open, ha_close], axis=1).min(axis=1)
        return pd.DataFrame({
            'ha_open': ha_open,
            'ha_high': ha_high,
            'ha_low': ha_low,
            'ha_close': ha_close
        })

    def average_true_range(self, high, low, close, period=14):
        high = high.values
        low = low.values
        close = close.values
        tr = [np.nan]
        for i in range(1, len(high)):
            tr.append(max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1])))
        atr = pd.Series(tr).rolling(period, min_periods=1).mean()
        return atr

    def supertrend_signal(self, ha_df, st_factor):
        hl2 = (ha_df['ha_high'] + ha_df['ha_low']) / 2
        atr = self.average_true_range(ha_df['ha_high'], ha_df['ha_low'], ha_df['ha_close'])
        up = hl2 - (st_factor * atr)
        dn = hl2 + (st_factor * atr)

        trend_up = [np.nan]
        trend_down = [np.nan]
        for i in range(1, len(ha_df)):
            prev_trend_up = trend_up[-1]
            prev_trend_down = trend_down[-1]
            prev_close = ha_df['ha_close'].iloc[i-1]
            if not np.isnan(prev_trend_up) and prev_close > prev_trend_up:
                trend_up.append(max(up.iloc[i], prev_trend_up))
            else:
                trend_up.append(up.iloc[i])
            if not np.isnan(prev_trend_down) and prev_close < prev_trend_down:
                trend_down.append(min(dn.iloc[i], prev_trend_down))
            else:
                trend_down.append(dn.iloc[i])

        signal = [0]
        last = 0
        for i in range(1, len(ha_df)):
            if ha_df['ha_close'].iloc[i] > trend_down[i-1]:
                tr = 1
                last = tr
            elif ha_df['ha_close'].iloc[i] < trend_up[i-1]:
                tr = -1
                last = tr
            else:
                tr = last
            signal.append(tr)
        return pd.Series(signal, index=ha_df.index)

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        ha = self.heikin_ashi(dataframe)
        dataframe['ha_open'] = ha['ha_open']
        dataframe['ha_high'] = ha['ha_high']
        dataframe['ha_low'] = ha['ha_low']
        dataframe['ha_close'] = ha['ha_close']
        dataframe['trend_signal'] = self.supertrend_signal(dataframe, self.st_factor.value)
        dataframe['entry_long_signal'] = (dataframe['trend_signal'].shift(1) == -1) & (dataframe['trend_signal'] == 1)
        dataframe['entry_short_signal'] = (dataframe['trend_signal'].shift(1) == 1) & (dataframe['trend_signal'] == -1)
        dataframe['exit_long_signal'] = (dataframe['trend_signal'] == -1)
        dataframe['exit_short_signal'] = (dataframe['trend_signal'] == 1)

        # Add EMA and RSI for exit logic
        dataframe['ema_exit'] = ta.EMA(dataframe, timeperiod=self.ema_exit_period.value)
        dataframe['rsi_exit'] = ta.RSI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe['enter_long'] = dataframe['entry_long_signal'].astype(bool)
        dataframe['enter_short'] = dataframe['entry_short_signal'].astype(bool)
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # Exit long: Supertrend exit signal AND RSI below threshold AND price below EMA
        dataframe['exit_long'] = (
            dataframe['exit_long_signal'] &
            (dataframe['rsi_exit'] < self.rsi_exit_threshold.value) &
            (dataframe['close'] < dataframe['ema_exit'])
        )
        # Exit short: Supertrend exit signal AND RSI above (100 - threshold) AND price above EMA
        dataframe['exit_short'] = (
            dataframe['exit_short_signal'] &
            (dataframe['rsi_exit'] > (100 - self.rsi_exit_threshold.value)) &
            (dataframe['close'] > dataframe['ema_exit'])
        )
        return dataframe