# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy,
    BooleanParameter,
    CategoricalParameter,
    IntParameter,
)
import talib.abstract as ta
from technical import qtpylib

class SampleCategoricalStrategy(IStrategy):
    """
    Sample Freqtrade strategy with indicator sources as hyperoptable CategoricalParameters
    where possible. Indicators that require OHLCV (ADX, SAR, MFI) are always called with the full
    dataframe and are NOT hyperoptable for source.
    """

    INTERFACE_VERSION = 3
    can_short = False

    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04,
    }
    stoploss = -0.10
    trailing_stop = False
    timeframe = "5m"
    process_only_new_candles = True
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False
    startup_candle_count = 200

    # --- Hyperoptable Indicator Source Parameters (only for 1D price indicators) ---
    rsi_src = CategoricalParameter(['close', 'open', 'high', 'low'], default='close', space="buy", optimize=True, load=True)
    macd_src = CategoricalParameter(['close', 'open', 'high', 'low'], default='close', space="buy", optimize=True, load=True)
    tema_src = CategoricalParameter(['close', 'open', 'high', 'low'], default='close', space="buy", optimize=True, load=True)
    boll_src = CategoricalParameter(
        ['close', 'open', 'high', 'low', 'typical'], 
        default='typical', space="buy", optimize=True, load=True
    )
    ewo_src = CategoricalParameter(['close', 'open', 'high', 'low'], default='close', space="buy", optimize=True, load=True)

    # --- Other Hyperoptable Parameters ---
    buy_rsi = IntParameter(1, 50, default=30, space="buy", optimize=True, load=True)
    sell_rsi = IntParameter(50, 100, default=70, space="sell", optimize=True, load=True)
    short_rsi = IntParameter(51, 100, default=70, space="sell", optimize=True, load=True)
    exit_short_rsi = IntParameter(1, 50, default=30, space="buy", optimize=True, load=True)
    ewo_sma1 = IntParameter(2, 20, default=5, space="buy", optimize=True, load=True)
    ewo_sma2 = IntParameter(15, 60, default=35, space="buy", optimize=True, load=True)
    ewo_use_percent = BooleanParameter(default=True, space="buy", optimize=True, load=True)

    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }
    order_time_in_force = {"entry": "GTC", "exit": "GTC"}

    plot_config = {
        "main_plot": {
            "tema": {},
            "sar": {"color": "white"},
            "ewo": {"color": "green"},
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
        return []

    def get_src(self, dataframe: DataFrame, src: str):
        if src == 'typical':
            return qtpylib.typical_price(dataframe)
        return dataframe[src]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- INDICATORS WITH HYPEROPTABLE SOURCE ---
        rsi_src = self.get_src(dataframe, self.rsi_src.value)
        macd_src = self.get_src(dataframe, self.macd_src.value)
        tema_src = self.get_src(dataframe, self.tema_src.value)
        boll_src = self.get_src(dataframe, self.boll_src.value)
        ewo_src = self.get_src(dataframe, self.ewo_src.value)

        dataframe["rsi"] = ta.RSI(rsi_src)
        dataframe["tema"] = ta.TEMA(tema_src, timeperiod=9)
        # EWO
        sma1 = ta.SMA(ewo_src, timeperiod=self.ewo_sma1.value)
        sma2 = ta.SMA(ewo_src, timeperiod=self.ewo_sma2.value)
        if self.ewo_use_percent.value:
            dataframe["ewo"] = (sma1 - sma2) / ewo_src * 100
        else:
            dataframe["ewo"] = sma1 - sma2

        # --- MACD handling (robust to output types) ---
        macd = ta.MACD(macd_src)
        # MACD can return a DataFrame (preferred) or a tuple/list/array
        if isinstance(macd, pd.DataFrame):
            dataframe["macd"] = macd["macd"]
            dataframe["macdsignal"] = macd["macdsignal"]
            dataframe["macdhist"] = macd["macdhist"]
        elif isinstance(macd, (tuple, list, np.ndarray)):
            # MACD returns a tuple/list/array (macd, macdsignal, macdhist)
            dataframe["macd"] = macd[0]
            dataframe["macdsignal"] = macd[1]
            dataframe["macdhist"] = macd[2]
        else:
            # Fallback for dict
            dataframe["macd"] = macd.get("macd", np.nan)
            dataframe["macdsignal"] = macd.get("macdsignal", np.nan)
            dataframe["macdhist"] = macd.get("macdhist", np.nan)

        # --- INDICATORS THAT REQUIRE OHLCV (DO NOT HYPEROPT SOURCE) ---
        dataframe["adx"] = ta.ADX(dataframe)
        dataframe["sar"] = ta.SAR(dataframe)
        dataframe["mfi"] = ta.MFI(dataframe)

        # Bollinger Bands (window=20, stds=2) - source is hyperoptable!
        bollinger = qtpylib.bollinger_bands(boll_src, window=20, stds=2)
        dataframe["bb_lowerband"] = bollinger["lower"]
        dataframe["bb_middleband"] = bollinger["mid"]
        dataframe["bb_upperband"] = bollinger["upper"]
        dataframe["bb_percent"] = (dataframe["close"] - dataframe["bb_lowerband"]) / (
            dataframe["bb_upperband"] - dataframe["bb_lowerband"]
        )
        dataframe["bb_width"] = (dataframe["bb_upperband"] - dataframe["bb_lowerband"]) / dataframe["bb_middleband"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry: EWO crosses above 0
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe["ewo"], 0)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit: EWO crosses below 0
        dataframe.loc[
            (
                qtpylib.crossed_below(dataframe["ewo"], 0)
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1
        return dataframe