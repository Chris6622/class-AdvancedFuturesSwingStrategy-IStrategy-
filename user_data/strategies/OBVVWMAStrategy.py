from freqtrade.strategy.interface import IStrategy
from freqtrade.strategy import IntParameter, DecimalParameter
import talib
import pandas as pd

class OBV_VWMA_Futures(IStrategy):
    can_short: bool = True

    # Hyperoptable parameters
    vwma_length = IntParameter(10, 50, default=21, space="buy")
    atr_length = IntParameter(7, 28, default=14, space="buy")
    atr_multiplier = DecimalParameter(1.0, 4.0, default=2.0, space="buy")
    risk_per_trade = DecimalParameter(0.005, 0.05, default=0.01, space="buy")
    leverage = IntParameter(1, 20, default=5, space="buy")
    roi_0 = DecimalParameter(0.01, 0.10, default=0.03, space="buy")
    roi_10 = DecimalParameter(0.0, 0.05, default=0.01, space="buy")

    stoploss = -0.99
    timeframe = '5m'
    startup_candle_count: int = 50

    minimal_roi = {
        "0": 0.03,
        "10": 0.01,
        "30": 0
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set minimal_roi from parameters
        self.minimal_roi = {
            "0": self.roi_0.value,
            "10": self.roi_10.value,
            "30": 0
        }

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe['obv'] = talib.OBV(dataframe['close'], dataframe['volume'])
        dataframe['obv_vwma'] = (
            (dataframe['obv'] * dataframe['volume']).rolling(window=self.vwma_length.value).sum() /
            dataframe['volume'].rolling(window=self.vwma_length.value).sum()
        )
        dataframe['atr'] = talib.ATR(
            dataframe['high'], dataframe['low'], dataframe['close'], timeperiod=self.atr_length.value
        )
        return dataframe

    def custom_stoploss(self, pair: str, trade, current_time, current_rate, current_profit, **kwargs):
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        entry_idx = dataframe[dataframe['date'] == trade.open_date_utc].index
        if len(entry_idx) == 0:
            return 1  # No data, disable stoploss
        entry_idx = entry_idx[0]
        atr = dataframe.at[entry_idx, 'atr']
        if trade.is_short:
            stoploss_rate = trade.open_rate + atr * self.atr_multiplier.value
        else:
            stoploss_rate = trade.open_rate - atr * self.atr_multiplier.value
        stoploss_pct = (stoploss_rate - trade.open_rate) / trade.open_rate
        return stoploss_pct

    def custom_entry_position_size(self, pair: str, current_price: float, entry_tag: str, **kwargs) -> float:
        balance = self.wallets.get_total('USDT')  # adjust quote currency if needed
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        atr = dataframe['atr'].iloc[-1]
        stoploss_distance = atr * self.atr_multiplier.value
        risk_amount = balance * self.risk_per_trade.value
        position_size = risk_amount / (stoploss_distance * self.leverage.value)
        min_trade_size = 0.001  # adjust for your market
        return max(position_size, min_trade_size)

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (
                (dataframe['obv'] > dataframe['obv_vwma']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'
        ] = 1
        dataframe.loc[
            (
                (dataframe['obv'] < dataframe['obv_vwma']) &
                (dataframe['volume'] > 0)
            ),
            'enter_short'
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe.loc[
            (dataframe['obv'] < dataframe['obv_vwma']),
            'exit_long'
        ] = 1
        dataframe.loc[
            (dataframe['obv'] > dataframe['obv_vwma']),
            'exit_short'
        ] = 1
        return dataframe