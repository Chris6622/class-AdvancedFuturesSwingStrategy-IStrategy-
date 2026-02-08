# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame
import talib.abstract as ta
import numpy as np
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime
from freqtrade.persistence import Trade
from typing import Any

# --- Import Strategy Parameters ---
from freqtrade.strategy import (
    DecimalParameter,
    IntParameter,
    RealParameter,
)

# --------------------------------

class BlackflagEWOFutures(IStrategy):
    """
    Final, robust version of the futures strategy with fully hyperoptable parameters.
    """
    # Strategy interface version - Required
    INTERFACE_VERSION = 3

    # --- Order Type Configuration ---
    order_types = {
        'entry': 'market',
        'exit': 'market',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # --- Hyperoptable Parameters (defined inline) ---
    leverage_opt = RealParameter(1.0, 5.0, default=1.4, step=0.1, space="buy", optimize=True)
    stoploss_opt = RealParameter(-0.15, -0.05, default=-0.10, space="stoploss", optimize=True)

    # ROI table parameters
    roi_t1 = IntParameter(10, 240, default=120, space="roi", optimize=True)
    roi_t2 = IntParameter(240, 720, default=480, space="roi", optimize=True)
    roi_p1 = DecimalParameter(0.01, 0.10, default=0.05, decimals=2, space="roi", optimize=True)
    roi_p2 = DecimalParameter(0.01, 0.05, default=0.02, decimals=2, space="roi", optimize=True)

    # Indicator Parameters
    bf_atr_period = IntParameter(10, 50, default=27, space="buy", optimize=True)
    bf_multiplier = DecimalParameter(2.0, 7.0, default=2.4, decimals=1, space="buy", optimize=True)
    ewo_fast_ma = IntParameter(3, 10, default=10, space="buy", optimize=True)
    ewo_slow_ma = IntParameter(20, 50, default=38, space="buy", optimize=True)
    adx_period = IntParameter(10, 30, default=19, space="buy", optimize=True)
    adx_threshold = IntParameter(15, 35, default=22, space="buy", optimize=True)
    entry_pullback_pct = DecimalParameter(0.005, 0.03, default=0.03, decimals=3, space="buy", optimize=True)

    # --- Static Strategy Settings (will be overridden by hyperopt values at runtime) ---
    timeframe = '1h'
    stoploss = -0.299
    minimal_roi = {
        "0": 0.551,
        "445": 0.156,
        "590": 0.052,
        "1391": 0
    }

    # Trailing stop:
    trailing_stop = True
    trailing_stop_positive = 0.243
    trailing_stop_positive_offset = 0.272
    trailing_only_offset_is_reached = False
    
    # --- Dynamic Leverage Method ---
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                 proposed_leverage: float, max_leverage: float, side: str,
                 **kwargs) -> float:
        """
        Calculate leverage for a trade.
        """
        return self.leverage_opt.value

    def bot_loop_start(self, **kwargs) -> None:
        """
        Called once at startup.
        Assigns hyperopt values to core strategy attributes.
        """
        super().bot_loop_start(**kwargs)
        self.stoploss = self.stoploss_opt.value

        # --- FIX: Use integers for ROI dictionary keys ---
        self.minimal_roi = {
            0: self.roi_p1.value + self.roi_p2.value,
            self.roi_t2.value: self.roi_p1.value,
            self.roi_t1.value + self.roi_t2.value: 0
        }

    # --- Strategy Logic ---
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['bf_atr'] = ta.ATR(dataframe, timeperiod=self.bf_atr_period.value)
        dataframe['bf_midline'] = ta.SMA(
            (dataframe['high'] + dataframe['low']) / 2,
            timeperiod=self.bf_atr_period.value
        )
        dataframe['bf_upperband'] = dataframe['bf_midline'] + (self.bf_multiplier.value * dataframe['bf_atr'])
        dataframe['bf_lowerband'] = dataframe['bf_midline'] - (self.bf_multiplier.value * dataframe['bf_atr'])
        dataframe['bf_trend'] = 0
        dataframe['bf_support'] = np.nan
        dataframe['bf_resistance'] = np.nan
        for i in range(1, len(dataframe)):
            if dataframe.loc[i-1, 'bf_trend'] == 1:
                if dataframe.loc[i, 'close'] < dataframe.loc[i-1, 'bf_lowerband']:
                    dataframe.loc[i, 'bf_trend'] = -1
                else:
                    dataframe.loc[i, 'bf_trend'] = 1
            elif dataframe.loc[i-1, 'bf_trend'] == -1:
                if dataframe.loc[i, 'close'] > dataframe.loc[i-1, 'bf_upperband']:
                    dataframe.loc[i, 'bf_trend'] = 1
                else:
                    dataframe.loc[i, 'bf_trend'] = -1
            else:
                if dataframe.loc[i, 'close'] > dataframe.loc[i-1, 'bf_midline']:
                    dataframe.loc[i, 'bf_trend'] = 1
                else:
                    dataframe.loc[i, 'bf_trend'] = -1

            if dataframe.loc[i, 'bf_trend'] == 1:
                dataframe.loc[i, 'bf_support'] = dataframe.loc[i, 'bf_lowerband']
            else:
                dataframe.loc[i, 'bf_resistance'] = dataframe.loc[i, 'bf_upperband']

        dataframe['ewo'] = ta.EMA(dataframe, timeperiod=self.ewo_fast_ma.value) - \
                         ta.EMA(dataframe, timeperiod=self.ewo_slow_ma.value)
        
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        long_pullback_zone = dataframe['bf_support'] * (1 + self.entry_pullback_pct.value)
        short_pullback_zone = dataframe['bf_resistance'] * (1 - self.entry_pullback_pct.value)

        dataframe.loc[
            (
                (dataframe['adx'] > self.adx_threshold.value) &
                (dataframe['bf_trend'] == 1) &
                (dataframe['ewo'] > 0) &
                (dataframe['low'] <= long_pullback_zone) &
                (dataframe['close'] > dataframe['open']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        dataframe.loc[
            (
                (dataframe['adx'] > self.adx_threshold.value) &
                (dataframe['bf_trend'] == -1) &
                (dataframe['ewo'] < 0) &
                (dataframe['high'] >= short_pullback_zone) &
                (dataframe['close'] < dataframe['open']) &
                (dataframe['volume'] > 0)
            ),
            'enter_short'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (qtpylib.crossed_below(dataframe['ewo'], 0)),
            'exit_long'] = 1

        dataframe.loc[
            (qtpylib.crossed_above(dataframe['ewo'], 0)),
            'exit_short'] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: Trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs: Any) -> float:
        
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()

        if trade.is_long:
            support_level = last_candle['bf_support']
            if support_level and support_level > 0:
                return (current_rate - support_level) / current_rate
        
        elif not trade.is_long:
            resistance_level = last_candle['bf_resistance']
            if resistance_level and resistance_level > 0:
                return (resistance_level - current_rate) / current_rate
        
        return 1