"""Shared Polymarket market data provider (singleton)"""

import logging
from typing import List, Callable, Optional, Dict, Set
from threading import Lock
from datetime import datetime

from polymarket_bot.core.market_data import MarketDataProvider, CryptoMarket
from polymarket_bot.api.gamma_client import GammaClient
from polymarket_bot.api.clob_client import CLOBClient
from polymarket_bot.api.token_mapper import TokenMapper
from polymarket_bot.api.market_parser import MarketParser
from polymarket_bot.api.scheduler import Scheduler
from polymarket_bot.api.aggregator import CandleAggregator
from polymarket_bot.config import Config

logger = logging.getLogger(__name__)


class PolymarketProvider(MarketDataProvider):
    """Shared Polymarket data provider (singleton pattern)"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Only initialize once
        if hasattr(self, '_initialized'):
            return
        
        self._initialized = True
        
        # API clients
        self.gamma_client = GammaClient()
        self.clob_client = CLOBClient()
        self.token_mapper = TokenMapper()
        self.market_parser = MarketParser()
        
        # Scheduler
        self.scheduler = Scheduler()
        
        # Candle aggregator
        self.aggregator = CandleAggregator(Config.CANDLE_TIMEFRAMES)
        
        # Markets storage
        self._markets: Dict[str, CryptoMarket] = {}
        self._markets_lock = Lock()
        
        # Subscribers
        self._subscribers: List[Callable[[CryptoMarket], None]] = []
        self._subscribers_lock = Lock()
        
        # Track last seen markets for diff
        self._last_market_ids: Set[str] = set()
        
        # Setup callbacks
        self.scheduler.add_fast_callback(self._on_fast_tick)
        self.scheduler.add_slow_callback(self._on_slow_tick)
    
    def subscribe(self, callback: Callable[[CryptoMarket], None]):
        """Subscribe to market data updates"""
        with self._subscribers_lock:
            self._subscribers.append(callback)
        logger.info(f"New subscriber added, total: {len(self._subscribers)}")
    
    def get_markets(self) -> List[CryptoMarket]:
        """Get all active markets"""
        with self._markets_lock:
            return list(self._markets.values())
    
    def get_market(self, market_id: str) -> Optional[CryptoMarket]:
        """Get a specific market"""
        with self._markets_lock:
            return self._markets.get(market_id)
    
    def _on_slow_tick(self):
        """Slow tick: Refresh market universe with diff"""
        logger.debug("Slow tick: Refreshing market universe")
        
        try:
            # Fetch all active markets from Gamma
            gamma_markets = self.gamma_client.get_all_active_markets()
            
            current_market_ids = set()
            new_markets = []
            
            for gamma_market in gamma_markets:
                market_id = gamma_market.get("id")
                if not market_id:
                    continue
                
                current_market_ids.add(market_id)
                
                # Skip if already have this market
                if market_id in self._last_market_ids:
                    continue
                
                # Validate market
                is_valid, discard_reason = self.gamma_client.validate_market(gamma_market)
                if not is_valid:
                    logger.debug(f"Market {market_id} failed validation: {discard_reason}")
                    continue
                
                # Update token mapper
                if not self.token_mapper.update_from_market(gamma_market):
                    logger.warning(f"Market {market_id} discarded: no_clobTokenIds")
                    continue
                
                # Parse market
                is_crypto, discard_reason, parsed_data = self.market_parser.parse_market(gamma_market)
                if not is_crypto:
                    if discard_reason and discard_reason != "not_crypto_market":
                        logger.warning(f"Market {market_id} discarded: {discard_reason}")
                    continue
                
                # Get token IDs
                token_ids = self.token_mapper.get_token_ids(market_id)
                if not token_ids:
                    continue
                
                # Create CryptoMarket
                crypto_market = CryptoMarket(
                    market_id=market_id,
                    asset=parsed_data["asset"],
                    timeframe=parsed_data["timeframe"],
                    price_to_beat=parsed_data["price_to_beat"],
                    resolution_time=parsed_data["resolution_time"],
                    yes_token_id=token_ids["yes_token_id"],
                    no_token_id=token_ids["no_token_id"],
                    status=parsed_data["status"],
                    title=parsed_data["title"],
                )
                
                new_markets.append(crypto_market)
            
            # Update markets storage
            with self._markets_lock:
                for market in new_markets:
                    self._markets[market.market_id] = market
                
                # Remove markets that are no longer active
                closed_markets = self._last_market_ids - current_market_ids
                for market_id in closed_markets:
                    if market_id in self._markets:
                        del self._markets[market_id]
                        logger.info(f"Removed closed market: {market_id}")
            
            # Update scheduler with market IDs
            active_market_ids = list(self._markets.keys())
            self.scheduler.set_market_ids(active_market_ids)
            
            # Update last seen markets
            self._last_market_ids = current_market_ids
            
            logger.info(
                f"Market universe updated: {len(new_markets)} new, "
                f"{len(closed_markets)} closed, {len(self._markets)} total"
            )
            
        except Exception as e:
            logger.error(f"Error in slow tick: {e}", exc_info=True)
    
    def _on_fast_tick(self, market_ids_batch: List[str]):
        """Fast tick: Update prices for batch of markets"""
        logger.debug(f"Fast tick: Updating {len(market_ids_batch)} markets")
        
        for market_id in market_ids_batch:
            # Skip if marked stale
            if self.clob_client.is_stale(market_id):
                continue
            
            try:
                # Get market
                market = self.get_market(market_id)
                if not market or not market.yes_token_id or not market.no_token_id:
                    continue
                
                # Fetch prices
                prices = self.clob_client.get_yes_no_prices(
                    market.yes_token_id,
                    market.no_token_id
                )
                
                if not prices:
                    # Mark stale on failure
                    self.clob_client.mark_stale(market_id)
                    continue
                
                # Update market
                market.update_prices(prices["yes_price"], prices["no_price"])
                
                # Add tick to aggregator
                if market.yes_price:
                    self.aggregator.add_tick(market_id, datetime.now(), market.yes_price)
                
                # Notify subscribers
                with self._subscribers_lock:
                    for callback in self._subscribers:
                        try:
                            callback(market)
                        except Exception as e:
                            logger.error(f"Error in subscriber callback: {e}", exc_info=True)
                
            except Exception as e:
                logger.error(f"Error updating market {market_id}: {e}", exc_info=True)
                # Mark stale on error
                self.clob_client.mark_stale(market_id)
    
    def start(self):
        """Start the data provider"""
        logger.info("Starting Polymarket provider")
        
        # Initial market refresh
        self._on_slow_tick()
        
        # Start scheduler
        self.scheduler.start()
        
        logger.info("Polymarket provider started")
    
    def stop(self):
        """Stop the data provider"""
        logger.info("Stopping Polymarket provider")
        self.scheduler.stop()
        logger.info("Polymarket provider stopped")
