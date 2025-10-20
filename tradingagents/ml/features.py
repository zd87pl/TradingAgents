"""
Feature Engineering for Options Trading ML Models

This module provides feature engineering functions for:
- Technical indicators
- Options-specific metrics (IV rank, Greeks, put/call ratio)
- Market microstructure features
- Sentiment indicators

Used by XGBoost, RL agents, and other ML models.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class OptionsFeatureEngineer:
    """
    Feature engineering for options trading strategies.

    Converts raw market data into ML-ready features.
    """

    def __init__(self):
        """Initialize feature engineer"""
        self.feature_names = []

    def create_technical_features(self, price_df: pd.DataFrame) -> pd.DataFrame:
        """
        Create technical indicator features from price data.

        Args:
            price_df: DataFrame with OHLCV data

        Returns:
            DataFrame with technical features
        """
        df = price_df.copy()

        # Price-based features
        df['returns'] = df['Close'].pct_change()
        df['log_returns'] = np.log(df['Close'] / df['Close'].shift(1))

        # Moving averages
        df['sma_10'] = df['Close'].rolling(window=10).mean()
        df['sma_20'] = df['Close'].rolling(window=20).mean()
        df['sma_50'] = df['Close'].rolling(window=50).mean()
        df['ema_10'] = df['Close'].ewm(span=10, adjust=False).mean()
        df['ema_20'] = df['Close'].ewm(span=20, adjust=False).mean()

        # Price relative to moving averages
        df['price_to_sma_10'] = df['Close'] / df['sma_10']
        df['price_to_sma_20'] = df['Close'] / df['sma_20']
        df['price_to_sma_50'] = df['Close'] / df['sma_50']

        # Volatility
        df['volatility_10'] = df['returns'].rolling(window=10).std()
        df['volatility_20'] = df['returns'].rolling(window=20).std()
        df['volatility_30'] = df['returns'].rolling(window=30).std()

        # ATR (Average True Range)
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        df['atr_14'] = true_range.rolling(window=14).mean()

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi_14'] = 100 - (100 / (1 + rs))

        # Volume features
        df['volume_sma_20'] = df['Volume'].rolling(window=20).mean()
        df['volume_ratio'] = df['Volume'] / df['volume_sma_20']

        return df

    def create_options_features(
        self,
        options_data: Dict[str, Any],
        price: float
    ) -> Dict[str, float]:
        """
        Create options-specific features.

        Args:
            options_data: Dictionary with options chain data
            price: Current stock price

        Returns:
            Dictionary of options features
        """
        features = {}

        # IV metrics
        if 'iv_rank' in options_data:
            features['iv_rank'] = options_data['iv_rank']
            features['iv_rank_squared'] = options_data['iv_rank'] ** 2
            features['iv_high'] = 1.0 if options_data['iv_rank'] > 75 else 0.0
            features['iv_low'] = 1.0 if options_data['iv_rank'] < 25 else 0.0

        if 'current_iv' in options_data:
            features['current_iv'] = options_data['current_iv']

        if 'historical_volatility' in options_data:
            features['historical_volatility'] = options_data['historical_volatility']

            # IV vs HV ratio
            if options_data.get('current_iv'):
                iv_hv_ratio = options_data['current_iv'] / (options_data['historical_volatility'] + 1e-6)
                features['iv_hv_ratio'] = iv_hv_ratio
                features['iv_expensive'] = 1.0 if iv_hv_ratio > 1.2 else 0.0
                features['iv_cheap'] = 1.0 if iv_hv_ratio < 0.8 else 0.0

        # Put/Call ratio
        if 'put_call_ratio' in options_data:
            features['put_call_ratio'] = options_data['put_call_ratio']
            features['put_call_high'] = 1.0 if options_data['put_call_ratio'] > 1.5 else 0.0
            features['put_call_low'] = 1.0 if options_data['put_call_ratio'] < 0.67 else 0.0

        # Volume and open interest
        if 'total_call_volume' in options_data and 'total_put_volume' in options_data:
            total_volume = options_data['total_call_volume'] + options_data['total_put_volume']
            features['total_options_volume'] = total_volume
            features['call_volume_pct'] = options_data['total_call_volume'] / (total_volume + 1)

        if 'total_call_oi' in options_data and 'total_put_oi' in options_data:
            total_oi = options_data['total_call_oi'] + options_data['total_put_oi']
            features['total_open_interest'] = total_oi

        # ATM option features
        if 'atm_call_price' in options_data:
            features['atm_call_price'] = options_data['atm_call_price']
            features['atm_call_pct'] = options_data['atm_call_price'] / (price + 1e-6)

        if 'atm_put_price' in options_data:
            features['atm_put_price'] = options_data['atm_put_price']
            features['atm_put_pct'] = options_data['atm_put_price'] / (price + 1e-6)

        return features

    def create_market_regime_features(
        self,
        price_df: pd.DataFrame,
        lookback: int = 60
    ) -> Dict[str, float]:
        """
        Detect market regime features.

        Args:
            price_df: Price DataFrame
            lookback: Lookback period

        Returns:
            Market regime features
        """
        features = {}

        if len(price_df) < lookback:
            return features

        recent_data = price_df.tail(lookback)

        # Trend strength
        returns = recent_data['Close'].pct_change()
        cumulative_return = (recent_data['Close'].iloc[-1] / recent_data['Close'].iloc[0]) - 1
        features['trend_strength'] = cumulative_return

        # Volatility regime
        volatility = returns.std() * np.sqrt(252)  # Annualized
        features['volatility_regime'] = volatility
        features['high_vol_regime'] = 1.0 if volatility > 0.30 else 0.0
        features['low_vol_regime'] = 1.0 if volatility < 0.15 else 0.0

        # Trend direction
        sma_20 = recent_data['Close'].rolling(window=20).mean()
        sma_50 = recent_data['Close'].rolling(window=50).mean()

        if len(sma_20) > 0 and len(sma_50) > 0:
            features['uptrend'] = 1.0 if sma_20.iloc[-1] > sma_50.iloc[-1] else 0.0
            features['downtrend'] = 1.0 if sma_20.iloc[-1] < sma_50.iloc[-1] else 0.0

        # Price position in range
        high_60 = recent_data['High'].max()
        low_60 = recent_data['Low'].min()
        current_price = recent_data['Close'].iloc[-1]

        if high_60 > low_60:
            features['price_position_in_range'] = (current_price - low_60) / (high_60 - low_60)

        return features

    def create_all_features(
        self,
        price_df: pd.DataFrame,
        options_data: Dict[str, Any],
        current_price: float
    ) -> pd.DataFrame:
        """
        Create all features for ML models.

        Args:
            price_df: Historical price data
            options_data: Options metrics
            current_price: Current stock price

        Returns:
            DataFrame with all features
        """
        # Technical features
        df = self.create_technical_features(price_df)

        # Options features (same for all rows, but we'll add to latest)
        options_features = self.create_options_features(options_data, current_price)

        # Add options features to the dataframe
        for key, value in options_features.items():
            df[key] = value

        # Market regime features
        regime_features = self.create_market_regime_features(price_df)
        for key, value in regime_features.items():
            df[key] = value

        # Store feature names
        self.feature_names = [col for col in df.columns if col not in ['Open', 'High', 'Low', 'Close', 'Volume']]

        return df

    def get_latest_features(
        self,
        price_df: pd.DataFrame,
        options_data: Dict[str, Any],
        current_price: float
    ) -> Dict[str, float]:
        """
        Get the most recent feature vector for inference.

        Args:
            price_df: Historical price data
            options_data: Options metrics
            current_price: Current stock price

        Returns:
            Dictionary of features for the latest data point
        """
        all_features_df = self.create_all_features(price_df, options_data, current_price)

        # Get the last row (most recent)
        latest_row = all_features_df.iloc[-1]

        # Convert to dictionary, dropping NaN values
        features_dict = {}
        for col in self.feature_names:
            if col in latest_row.index:
                value = latest_row[col]
                if pd.notna(value):
                    features_dict[col] = float(value)

        return features_dict


def extract_features_for_strategy_classification(
    symbol: str,
    price_data: pd.DataFrame,
    options_summary: Dict[str, Any]
) -> Dict[str, Any]:
    """
    High-level function to extract features for strategy classification.

    Args:
        symbol: Ticker symbol
        price_data: Historical price DataFrame
        options_summary: Options summary data

    Returns:
        Feature dictionary ready for ML model
    """
    engineer = OptionsFeatureEngineer()

    current_price = price_data['Close'].iloc[-1]

    features = engineer.get_latest_features(
        price_df=price_data,
        options_data=options_summary,
        current_price=current_price
    )

    # Add metadata
    features['symbol'] = symbol
    features['timestamp'] = datetime.now().isoformat()

    return features


# Example usage
if __name__ == "__main__":
    print("Options Feature Engineering Module")
    print("=" * 50)
    print("\nExample usage:")
    print("""
    from tradingagents.ml.features import OptionsFeatureEngineer

    engineer = OptionsFeatureEngineer()

    # Create features
    features_df = engineer.create_all_features(
        price_df=historical_prices,
        options_data=options_metrics,
        current_price=current_stock_price
    )

    # Get latest feature vector for inference
    latest_features = engineer.get_latest_features(
        price_df=historical_prices,
        options_data=options_metrics,
        current_price=current_stock_price
    )
    """)
