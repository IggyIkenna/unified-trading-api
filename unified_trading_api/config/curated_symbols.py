"""Curated symbol config for the trading terminal watchlist and batch candle reader.

Only symbols with confirmed GCS market data are included.
Each entry has enough metadata to construct the GCS blob path and display in the watchlist.
"""

from __future__ import annotations

# Key: asset group → list of symbol config dicts
# Fields per symbol:
#   venue: GCS venue name (uppercase, e.g. "BINANCE-FUTURES")
#   symbol: GCS symbol name (e.g. "BTCUSDT", "BTC", "ES")
#   display_name: human-readable label for the watchlist
#   instrument_type: GCS instrument_type partition value (lowercase)
#   data_type: GCS data_type partition value (e.g. "trades", "ohlcv_1m", "oracle_prices")
#   base, quote: asset identifiers
#   chain: (DEFI only) blockchain name for chain= partition (e.g. "ethereum")
CURATED_SYMBOLS: dict[str, list[dict[str, str]]] = {
    "cefi": [
        {
            "venue": "BINANCE-FUTURES",
            "symbol": "BTCUSDT",
            "display_name": "BTC/USDT Perp",
            "instrument_type": "perpetual",
            "data_type": "trades",
            "base": "BTC",
            "quote": "USDT",
        },
        {
            "venue": "BINANCE-FUTURES",
            "symbol": "ETHUSDT",
            "display_name": "ETH/USDT Perp",
            "instrument_type": "perpetual",
            "data_type": "trades",
            "base": "ETH",
            "quote": "USDT",
        },
        {
            "venue": "BINANCE-FUTURES",
            "symbol": "SOLUSDT",
            "display_name": "SOL/USDT Perp",
            "instrument_type": "perpetual",
            "data_type": "trades",
            "base": "SOL",
            "quote": "USDT",
        },
        {
            "venue": "HYPERLIQUID",
            "symbol": "BTC",
            "display_name": "BTC-PERP",
            "instrument_type": "perpetual",
            "data_type": "trades",
            "base": "BTC",
            "quote": "USD",
        },
        {
            "venue": "HYPERLIQUID",
            "symbol": "ETH",
            "display_name": "ETH-PERP",
            "instrument_type": "perpetual",
            "data_type": "trades",
            "base": "ETH",
            "quote": "USD",
        },
        {
            "venue": "DERIBIT",
            "symbol": "BTC-PERPETUAL",
            "display_name": "BTC-PERPETUAL",
            "instrument_type": "perpetual",
            "data_type": "trades",
            "base": "BTC",
            "quote": "USD",
        },
        {
            "venue": "COINBASE-SPOT",
            "symbol": "BTC-USD",
            "display_name": "BTC/USD",
            "instrument_type": "spot",
            "data_type": "trades",
            "base": "BTC",
            "quote": "USD",
        },
    ],
    "tradfi": [
        {
            "venue": "CME",
            "symbol": "ES",
            "display_name": "S&P 500 Futures",
            "instrument_type": "future",
            "data_type": "ohlcv_1m",
            "base": "ES",
            "quote": "USD",
        },
        {
            "venue": "CME",
            "symbol": "NQ",
            "display_name": "Nasdaq 100 Futures",
            "instrument_type": "future",
            "data_type": "ohlcv_1m",
            "base": "NQ",
            "quote": "USD",
        },
        {
            "venue": "CME",
            "symbol": "CL",
            "display_name": "Crude Oil Futures",
            "instrument_type": "future",
            "data_type": "ohlcv_1m",
            "base": "CL",
            "quote": "USD",
        },
        {
            "venue": "NASDAQ",
            "symbol": "AAPL",
            "display_name": "Apple Inc.",
            "instrument_type": "equity",
            "data_type": "ohlcv_1m",
            "base": "AAPL",
            "quote": "USD",
        },
        {
            "venue": "NASDAQ",
            "symbol": "MSFT",
            "display_name": "Microsoft Corp.",
            "instrument_type": "equity",
            "data_type": "ohlcv_1m",
            "base": "MSFT",
            "quote": "USD",
        },
        {
            "venue": "NASDAQ",
            "symbol": "GOOGL",
            "display_name": "Alphabet Inc. (Class A)",
            "instrument_type": "equity",
            "data_type": "ohlcv_1m",
            "base": "GOOGL",
            "quote": "USD",
        },
        {
            "venue": "NYSE",
            "symbol": "JPM",
            "display_name": "JPMorgan Chase & Co.",
            "instrument_type": "equity",
            "data_type": "ohlcv_1m",
            "base": "JPM",
            "quote": "USD",
        },
    ],
    "defi": [
        {
            "venue": "UNISWAP_V3-ETHEREUM",
            "symbol": "WETH-USDC-500",
            "display_name": "WETH/USDC (0.05%)",
            "instrument_type": "lp_pool",
            "data_type": "oracle_prices",
            "base": "WETH",
            "quote": "USDC",
            "chain": "ethereum",
        },
        {
            "venue": "UNISWAP_V3-ETHEREUM",
            "symbol": "WETH-USDT-500",
            "display_name": "WETH/USDT (0.05%)",
            "instrument_type": "lp_pool",
            "data_type": "oracle_prices",
            "base": "WETH",
            "quote": "USDT",
            "chain": "ethereum",
        },
        {
            "venue": "AAVE_V3-ETHEREUM",
            "symbol": "WETH",
            "display_name": "AAVE WETH Lending",
            "instrument_type": "lending_pool",
            "data_type": "oracle_prices",
            "base": "WETH",
            "quote": "USD",
            "chain": "ethereum",
        },
        {
            "venue": "LIDO-ETHEREUM",
            "symbol": "stETH",
            "display_name": "Lido Staked ETH",
            "instrument_type": "liquid_staking",
            "data_type": "oracle_prices",
            "base": "stETH",
            "quote": "ETH",
            "chain": "ethereum",
        },
    ],
}

# O(1) lookup index: (VENUE_UPPER, SYMBOL_UPPER) → config dict
_SYMBOL_INDEX: dict[tuple[str, str], dict[str, str]] = {
    (entry["venue"].upper(), entry["symbol"].upper()): entry for group in CURATED_SYMBOLS.values() for entry in group
}


def get_symbol_config(venue: str, symbol: str) -> dict[str, str] | None:
    """Return curated config for (venue, symbol), or None if not in the curated list."""
    return _SYMBOL_INDEX.get((venue.upper(), symbol.upper()))
