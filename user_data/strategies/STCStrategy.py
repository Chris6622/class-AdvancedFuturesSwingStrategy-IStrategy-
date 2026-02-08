import pandas as pd
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter


class SchaffTrendCycleStrategy(IStrategy):
    """
    Strategy using Schaff Trend Cycle (STC) for buy/sell signals, including shorting.
    """

    INTERFACE_VERSION = 3

    can_short: bool = True  # Enable shorting

    minimal_roi = {
        "60": 0.01,
        "30": 0.02,
        "0": 0.04,
    }

    stoploss = -0.10
    timeframe = "15m"
    process_only_new_candles = True
    startup_candle_count: int = 200

    # Hyperoptable parameters for Schaff Trend Cycle (Buy)
    fast_length_buy = IntParameter(10, 50, default=23, space="buy", optimize=True)
    slow_length_buy = IntParameter(20, 100, default=50, space="buy", optimize=True)
    cycle_length_buy = IntParameter(5, 20, default=10, space="buy", optimize=True)
    d1_length_buy = IntParameter(1, 10, default=3, space="buy", optimize=True)
    d2_length_buy = IntParameter(1, 10, default=3, space="buy", optimize=True)
    upper_band_buy = DecimalParameter(50, 100, default=75, space="buy", optimize=True)
    lower_band_buy = DecimalParameter(0, 50, default=25, space="buy", optimize=True)

    # Hyperoptable parameters for Schaff Trend Cycle (Sell)
    fast_length_sell = IntParameter(10, 50, default=23, space="sell", optimize=True)
    slow_length_sell = IntParameter(20, 100, default=50, space="sell", optimize=True)
    cycle_length_sell = IntParameter(5, 20, default=10, space="sell", optimize=True)
    d1_length_sell = IntParameter(1, 10, default=3, space="sell", optimize=True)
    d2_length_sell = IntParameter(1, 10, default=3, space="sell", optimize=True)
    upper_band_sell = DecimalParameter(50, 100, default=75, space="sell", optimize=True)
    lower_band_sell = DecimalParameter(0, 50, default=25, space="sell", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Adds Schaff Trend Cycle (STC) and other indicators to the dataframe.
        """

        # Ensure the 'close' column is a Pandas Series
        close = dataframe["close"]

        # MACD calculation for Buy using Pandas
        ema_fast_buy = close.ewm(span=self.fast_length_buy.value, adjust=False).mean()
        ema_slow_buy = close.ewm(span=self.slow_length_buy.value, adjust=False).mean()
        dataframe["macd_buy"] = ema_fast_buy - ema_slow_buy

        # First Stochastic calculation for Buy
        high_k_buy = dataframe["macd_buy"].rolling(window=self.cycle_length_buy.value).max()
        low_k_buy = dataframe["macd_buy"].rolling(window=self.cycle_length_buy.value).min()
        dataframe["k_buy"] = 100 * (dataframe["macd_buy"] - low_k_buy) / (high_k_buy - low_k_buy)

        # First %D for Buy
        dataframe["d_buy"] = dataframe["k_buy"].ewm(span=self.d1_length_buy.value, adjust=False).mean()

        # Second stochastic calculation for Buy
        high_d_buy = dataframe["d_buy"].rolling(window=self.cycle_length_buy.value).max()
        low_d_buy = dataframe["d_buy"].rolling(window=self.cycle_length_buy.value).min()
        dataframe["kd_buy"] = 100 * (dataframe["d_buy"] - low_d_buy) / (high_d_buy - low_d_buy)

        # Final STC calculation for Buy
        dataframe["stc_buy"] = dataframe["kd_buy"].ewm(span=self.d2_length_buy.value, adjust=False).mean().clip(
            lower=0, upper=100
        )

        # MACD calculation for Sell using Pandas
        ema_fast_sell = close.ewm(span=self.fast_length_sell.value, adjust=False).mean()
        ema_slow_sell = close.ewm(span=self.slow_length_sell.value, adjust=False).mean()
        dataframe["macd_sell"] = ema_fast_sell - ema_slow_sell

        # First Stochastic calculation for Sell
        high_k_sell = dataframe["macd_sell"].rolling(window=self.cycle_length_sell.value).max()
        low_k_sell = dataframe["macd_sell"].rolling(window=self.cycle_length_sell.value).min()
        dataframe["k_sell"] = 100 * (dataframe["macd_sell"] - low_k_sell) / (high_k_sell - low_k_sell)

        # First %D for Sell
        dataframe["d_sell"] = dataframe["k_sell"].ewm(span=self.d1_length_sell.value, adjust=False).mean()

        # Second stochastic calculation for Sell
        high_d_sell = dataframe["d_sell"].rolling(window=self.cycle_length_sell.value).max()
        low_d_sell = dataframe["d_sell"].rolling(window=self.cycle_length_sell.value).min()
        dataframe["kd_sell"] = 100 * (dataframe["d_sell"] - low_d_sell) / (high_d_sell - low_d_sell)

        # Final STC calculation for Sell
        dataframe["stc_sell"] = dataframe["kd_sell"].ewm(span=self.d2_length_sell.value, adjust=False).mean().clip(
            lower=0, upper=100
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Defines entry signals based on STC for both long and short positions.
        """
        # Long Entry
        dataframe.loc[
            (
                (dataframe["stc_buy"] > self.lower_band_buy.value)
                & (dataframe["stc_buy"].shift(1) <= self.lower_band_buy.value)
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        # Short Entry
        dataframe.loc[
            (
                (dataframe["stc_sell"] < self.upper_band_sell.value)
                & (dataframe["stc_sell"].shift(1) >= self.upper_band_sell.value)
                & (dataframe["volume"] > 0)
            ),
            "enter_short",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Defines exit signals based on STC for both long and short positions.
        """
        # Long Exit
        dataframe.loc[
            (
                (dataframe["stc_buy"] < self.upper_band_buy.value)
                & (dataframe["stc_buy"].shift(1) >= self.upper_band_buy.value)
                & (dataframe["volume"] > 0)
            ),
            "exit_long",
        ] = 1

        # Short Exit
        dataframe.loc[
            (
                (dataframe["stc_sell"] > self.lower_band_sell.value)
                & (dataframe["stc_sell"].shift(1) <= self.lower_band_sell.value)
                & (dataframe["volume"] > 0)
            ),
            "exit_short",
        ] = 1

        return dataframe