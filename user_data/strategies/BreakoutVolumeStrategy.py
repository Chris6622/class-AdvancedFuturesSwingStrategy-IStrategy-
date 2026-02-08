from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import pandas as pd

class BreakoutVolumeStrategy(IStrategy):
    breakout_lookback = IntParameter(10, 50, default=20, space="buy", optimize=True)
    volume_multiplier = DecimalParameter(1.1, 3.0, decimals=2, default=1.5, space="buy", optimize=True)
    stoploss_param = DecimalParameter(-0.10, -0.01, decimals=3, default=-0.02, space="sell", optimize=True)
    roi_param = DecimalParameter(0.02, 0.10, decimals=3, default=0.04, space="sell", optimize=True)

    timeframe = '4h'
    startup_candle_count: int = 50
    stoploss = -0.02
    minimal_roi = {"0": 0.04}
    can_short = True

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        length = int(self.breakout_lookback.value)
        dataframe['highest_high'] = dataframe['high'].rolling(window=length, min_periods=1).max().shift(1)
        dataframe['lowest_low'] = dataframe['low'].rolling(window=length, min_periods=1).min().shift(1)
        dataframe['avg_volume'] = dataframe['volume'].rolling(window=length, min_periods=1).mean().shift(1)
        dataframe['volume_spike'] = dataframe['volume'] > (self.volume_multiplier.value * dataframe['avg_volume'])
        dataframe['is_breakout'] = dataframe['close'] > dataframe['highest_high']
        dataframe['is_breakdown'] = dataframe['close'] < dataframe['lowest_low']
        dataframe['long_condition'] = dataframe['is_breakout'] & dataframe['volume_spike']
        dataframe['short_condition'] = dataframe['is_breakdown'] & dataframe['volume_spike']
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[dataframe['long_condition'], 'enter_long'] = 1
        dataframe.loc[dataframe['short_condition'], 'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):
        return float(self.stoploss_param.value)

    def custom_exit(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):
        roi = float(self.roi_param.value)
        if trade.is_short:
            if current_profit <= -roi:
                return "take_profit"
        else:
            if current_profit >= roi:
                return "take_profit"
        return None