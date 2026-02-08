from freqtrade.strategy.interface import IStrategy
from pandas import DataFrame
from freqtrade.strategy import IntParameter, DecimalParameter
import talib.abstract as ta

class OBVBBStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "15m"
    can_short = True

    # Hyperoptable parameters
    obv_ma_length = IntParameter(5, 30, default=12, space="buy")
    bb_length = IntParameter(5, 30, default=12, space="buy")
    bb_std = DecimalParameter(1.0, 3.0, default=2.0, space="buy")
    minimal_roi = {
        "0": 0.01,
    }
    stoploss = -0.10  # Must be a float, not a Parameter!

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # OBV
        dataframe['obv'] = ta.OBV(dataframe)
        # OBV_MA
        dataframe['obv_ma'] = ta.SMA(dataframe['obv'], timeperiod=int(self.obv_ma_length.value))
        # Bollinger Bands on OBV (returns tuple, not dict!)
        upperband, middleband, lowerband = ta.BBANDS(
            dataframe['obv'],
            timeperiod=int(self.bb_length.value),
            nbdevup=float(self.bb_std.value),
            nbdevdn=float(self.bb_std.value),
            matype=0
        )
        dataframe['bb_obv_upper'] = upperband
        dataframe['bb_obv_middle'] = middleband
        dataframe['bb_obv_lower'] = lowerband
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long Entry: OBV crosses above upper BB
        dataframe['enter_long'] = (
            (dataframe['obv'] > dataframe['bb_obv_upper']) &
            (dataframe['obv'].shift(1) <= dataframe['bb_obv_upper'].shift(1))
        ).astype('int')

        # Short Entry: OBV crosses below lower BB
        dataframe['enter_short'] = (
            (dataframe['obv'] < dataframe['bb_obv_lower']) &
            (dataframe['obv'].shift(1) >= dataframe['bb_obv_lower'].shift(1))
        ).astype('int')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Long Exit: OBV crosses below middle BB
        dataframe['exit_long'] = (
            (dataframe['obv'] < dataframe['bb_obv_middle']) &
            (dataframe['obv'].shift(1) >= dataframe['bb_obv_middle'].shift(1))
        ).astype('int')

        # Short Exit: OBV crosses above middle BB
        dataframe['exit_short'] = (
            (dataframe['obv'] > dataframe['bb_obv_middle']) &
            (dataframe['obv'].shift(1) <= dataframe['bb_obv_middle'].shift(1))
        ).astype('int')

        return dataframe