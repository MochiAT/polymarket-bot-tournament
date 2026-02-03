"""Strategy base class"""

from abc import ABC, abstractmethod
from typing import List

from polymarket_bot.core.market_data import CryptoMarket, MarketDataProvider
from polymarket_bot.core.execution import ExecutionEngine


class Strategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(
        self,
        name: str,
        market_data_provider: MarketDataProvider,
        execution_engine: ExecutionEngine,
    ):
        self.name = name
        self.market_data = market_data_provider
        self.execution = execution_engine
    
    @abstractmethod
    def on_market_data(self, market: CryptoMarket):
        """Called when market data is updated"""
        pass
    
    def on_markets_update(self, markets: List[CryptoMarket]):
        """Called when multiple markets are updated (optional override)"""
        for market in markets:
            self.on_market_data(market)
    
    def get_name(self) -> str:
        """Get strategy name"""
        return self.name
