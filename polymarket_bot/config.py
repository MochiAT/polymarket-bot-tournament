"""Configuration management for Polymarket bot"""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings"""
    
    # API Endpoints
    GAMMA_API_URL: str = os.getenv("GAMMA_API_URL", "https://gamma-api.polymarket.com")
    CLOB_API_URL: str = os.getenv("CLOB_API_URL", "https://clob.polymarket.com")
    
    # Polling Configuration
    FAST_TICK_INTERVAL: int = int(os.getenv("FAST_TICK_INTERVAL", "5"))
    SLOW_TICK_INTERVAL: int = int(os.getenv("SLOW_TICK_INTERVAL", "60"))
    MAX_MARKETS_PER_TICK: int = int(os.getenv("MAX_MARKETS_PER_TICK", "50"))
    
    # Candle Aggregation Timeframes (in minutes)
    CANDLE_TIMEFRAMES: List[int] = [
        int(x) for x in os.getenv("CANDLE_TIMEFRAMES", "15,60,240,1440").split(",")
    ]
    
    # Supported Assets
    SUPPORTED_ASSETS: List[str] = ["BTC", "ETH", "SOL", "XRP"]
    
    # Asset Synonyms
    ASSET_SYNONYMS = {
        "bitcoin": "BTC",
        "btc": "BTC",
        "ethereum": "ETH",
        "eth": "ETH",
        "solana": "SOL",
        "sol": "SOL",
        "xrp": "XRP",
    }
    
    # Supported Timeframes
    SUPPORTED_TIMEFRAMES: List[str] = ["15m", "1h", "4h", "1d"]
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Rate Limiting
    MAX_RETRIES: int = 3
    INITIAL_BACKOFF: float = 1.0
    MAX_BACKOFF: float = 60.0
