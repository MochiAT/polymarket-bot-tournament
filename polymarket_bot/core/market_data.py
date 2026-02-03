"""Market data abstractions"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Callable, List
from abc import ABC, abstractmethod


@dataclass
class CryptoMarket:
    """Standardized crypto binary market"""
    market_id: str
    asset: str  # BTC, ETH, SOL, XRP
    timeframe: str  # 15m, 1h, 4h, 1d
    price_to_beat: float
    resolution_time: Optional[datetime]
    yes_price: Optional[float] = None
    no_price: Optional[float] = None
    implied_probability: Optional[float] = None
    yes_token_id: Optional[str] = None
    no_token_id: Optional[str] = None
    status: str = "active"
    title: str = ""
    
    def update_prices(self, yes_price: float, no_price: float):
        """Update prices and calculate implied probability"""
        self.yes_price = yes_price
        self.no_price = no_price
        # Implied probability is the YES price (in prediction markets, price = probability)
        self.implied_probability = yes_price


class MarketDataProvider(ABC):
    """Abstract base class for market data providers"""
    
    @abstractmethod
    def subscribe(self, callback: Callable[[CryptoMarket], None]):
        """Subscribe to market data updates"""
        pass
    
    @abstractmethod
    def get_markets(self) -> List[CryptoMarket]:
        """Get all active markets"""
        pass
    
    @abstractmethod
    def get_market(self, market_id: str) -> Optional[CryptoMarket]:
        """Get a specific market"""
        pass
    
    @abstractmethod
    def start(self):
        """Start the data provider"""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop the data provider"""
        pass
