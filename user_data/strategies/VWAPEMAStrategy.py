# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from pandas import DataFrame
from typing import Optional, Union

from freqtrade.strategy import (
    IStrategy,
    Trade,
    Order,
    PairLocks,
    informative,  # @informative decorator
    # Hyperopt Parameters
    BooleanParameter,
    CategoricalParameter,
    DecimalParameter,
    IntParameter,
    RealParameter,
    # timeframe helpers
    timeframe_to_minutes,
    timeframe_to_next_date,
    timeframe_to_prev_date,
    # Strategy helper functions
    merge_informative_pair,
    stoploss_from_absolute,
    stoploss_from_open,
)

# --------------------------------
# Add your lib to import here
import talib.abstract as ta
from technical import qtpylib


# This class is a sample. Feel free to customize it.
class VWAPEMAStrategy(IStrategy):
    """
    This is a sample strategy to inspire you.
    More information in https://www.freqtrade.io/en/latest/strategy-customization/

    You can:
        :return: a Dataframe with all mandatory indicators for the strategies
    - Rename the class name (Do not forget to update class_name)
    - Add any methods you want to build your strategy
    - Add any lib you need to build your strategy

    You must keep:
    - the lib in the section "Do not remove these libs"
    - the methods: populate_indicators, populate_entry_trend, populate_exit_trend
    You should keep:
    - timeframe, minimal_roi, stoploss, trailing_*
    """

    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        # "120": 0.0,  # exit after 120 minutes at break even
        "60": 0.01,
        "30": 0.02,
        "0": 0.04,
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.10

    # Trailing stoploss
    trailing_stop = False
    # trailing_only_offset_is_reached = False
    # trailing_stop_positive = 0.01
    # trailing_stop_positive_offset = 0.0  # Disabled / not configured

    # Optimal timeframe for the strategy.
    timeframe = "5m"

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Hyperoptable parameters
    buy_rsi = IntParameter(low=20, high=70, default=30, space="buy", optimize=True, load=True)
    sell_rsi = IntParameter(low=50, high=100, default=70, space="sell", optimize=True, load=True)
    short_rsi = IntParameter(low=51, high=100, default=70, space="sell", optimize=True, load=True)
    exit_short_rsi = IntParameter(low=1, high=50, default=30, space="buy", optimize=True, load=True)

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # Optional order type mapping.
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    # Optional order time in force.
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    plot_config = {
        "main_plot": {
            "tema": {},
            "sar": {"color": "white"},
        },
        "subplots": {
            "MACD": {
                "macd": {"color": "blue"},
                "macdsignal": {"color": "orange"},
            },
            "RSI": {
                "rsi": {"color": "red"},
            },
        },
    }

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds several different TA indicators to the given DataFrame

        Performance Note: For the best performance be frugal on the number of indicators
        you are using. Let uncomment only the indicator you are using in your strategies
        or your hyperopt configuration, otherwise you will waste your memory and CPU usage.
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe)
        
        
        # EMA
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=5)
        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=20)
        
        #VWAP
        dataframe['typical_price'] = (dataframe['high'] + dataframe['low'] + dataframe['close']) / 3
        dataframe['cumulative_price_volume'] = (dataframe['typical_price'] * dataframe['volume']).cumsum()
        dataframe['cumulative_volume'] = dataframe['volume'].cumsum()
        dataframe['vwap'] = dataframe['cumulative_price_volume'] / dataframe['cumulative_volume']
       

        """
        # first check if dataprovider is available
        if self.dp:
            if self.dp.runmode.value in ('live', 'dry_run'):
                ob = self.dp.orderbook(metadata['pair'], 1)
                dataframe['best_bid'] = ob['bids'][0][0]
                dataframe['best_ask'] = ob['asks'][0][0]
        """

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (
                # Signal: RSI crosses above 30
                (qtpylib.crossed_above(dataframe["rsi"], self.buy_rsi.value))
                & (dataframe["ema5"] >= dataframe["ema20"])  # Guard: tema below BB middle
                & (dataframe["close"] > dataframe["vwap"]) # Guard: tema is raising
                & (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            "enter_long",
        ] = 1

        dataframe.loc[
            (
                # Signal: RSI crosses above 70
                (qtpylib.crossed_above(dataframe["rsi"], self.short_rsi.value))
                & (dataframe["ema5"] < dataframe["ema20"])  # Guard: tema above BB middle
                & (dataframe["close"] < dataframe["vwap"])  # Guard: tema is falling
                & (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[
            (
                # Signal: RSI crosses above 70
                (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi.value))
                & (dataframe["ema5"] < dataframe["ema20"]) # Guard: tema above BB middle
                & (dataframe["close"] < dataframe["vwap"])  # Guard: tema is falling
                & (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            "exit_long",
        ] = 1

        dataframe.loc[
            (
                # Signal: RSI crosses above 30
                (qtpylib.crossed_above(dataframe["rsi"], self.exit_short_rsi.value))
                & (dataframe["ema5"] >= dataframe["ema20"])  # Guard: tema below BB middle
                & (dataframe["close"] > dataframe["vwap"]) # Guard: tema is raising
                & (dataframe["volume"] > 0)  # Make sure Volume is not 0
            ),
            "exit_short",
        ] = 1

        return dataframe
