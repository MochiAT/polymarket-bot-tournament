"""Candle aggregation system"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Candle:
    """OHLCV candle"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class CandleAggregator:
    """Aggregate tick data into OHLCV candles"""
    
    def __init__(self, timeframes_minutes: List[int]):
        """
        Args:
            timeframes_minutes: List of timeframe durations in minutes (e.g., [15, 60, 240, 1440])
        """
        self.timeframes = timeframes_minutes
        
        # Storage: {market_id: {timeframe: [candles]}}
        self._candles: Dict[str, Dict[int, List[Candle]]] = defaultdict(
            lambda: {tf: [] for tf in self.timeframes}
        )
        
        # Current partial candles
        self._partial: Dict[str, Dict[int, Optional[Candle]]] = defaultdict(
            lambda: {tf: None for tf in self.timeframes}
        )
    
    def add_tick(self, market_id: str, timestamp: datetime, price: float):
        """Add a price tick and update candles"""
        for timeframe in self.timeframes:
            self._update_candle(market_id, timeframe, timestamp, price)
    
    def _update_candle(self, market_id: str, timeframe: int, timestamp: datetime, price: float):
        """Update or create candle for a specific timeframe"""
        # Get candle start time (rounded down to timeframe)
        minutes_since_epoch = int(timestamp.timestamp() / 60)
        candle_start_minute = (minutes_since_epoch // timeframe) * timeframe
        candle_start = datetime.fromtimestamp(candle_start_minute * 60, tz=timestamp.tzinfo)
        
        partial = self._partial[market_id][timeframe]
        
        # If no partial candle or new candle period
        if partial is None or partial.timestamp != candle_start:
            # Save previous partial candle
            if partial is not None:
                self._candles[market_id][timeframe].append(partial)
                # Keep only last 1000 candles per timeframe
                if len(self._candles[market_id][timeframe]) > 1000:
                    self._candles[market_id][timeframe] = self._candles[market_id][timeframe][-1000:]
            
            # Create new partial candle
            self._partial[market_id][timeframe] = Candle(
                timestamp=candle_start,
                open=price,
                high=price,
                low=price,
                close=price,
            )
        else:
            # Update existing partial candle
            partial.high = max(partial.high, price)
            partial.low = min(partial.low, price)
            partial.close = price
    
    def get_candles(self, market_id: str, timeframe: int, limit: int = 100) -> List[Candle]:
        """Get most recent candles for a market and timeframe"""
        if market_id not in self._candles:
            return []
        
        if timeframe not in self._candles[market_id]:
            return []
        
        candles = self._candles[market_id][timeframe]
        return candles[-limit:] if candles else []
    
    def get_latest_candle(self, market_id: str, timeframe: int) -> Optional[Candle]:
        """Get latest completed candle (not partial)"""
        candles = self.get_candles(market_id, timeframe, limit=1)
        return candles[0] if candles else None
