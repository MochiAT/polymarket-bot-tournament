"""CLOB API client for live pricing and orderbooks"""

import logging
import requests
from typing import Optional, Dict, List
from enum import Enum

from polymarket_bot.config import Config
from polymarket_bot.api.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class Side(str, Enum):
    """Order side for price queries"""
    BUY = "BUY"
    SELL = "SELL"


class CLOBClient:
    """Client for Polymarket CLOB API (pricing and orderbooks)"""
    
    def __init__(self, base_url: str = Config.CLOB_API_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self._stale_markets = set()  # Circuit breaker for failed markets
    
    @rate_limiter.with_retry
    def get_price(self, token_id: str, side: Side) -> Optional[float]:
        """
        Get price for a token
        
        Args:
            token_id: CLOB token ID
            side: BUY (lowest ask) or SELL (highest bid)
        
        Returns:
            Price as float or None if error
        """
        url = f"{self.base_url}/price"
        params = {
            "token_id": token_id,
            "side": side.value,
        }
        
        try:
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            price_str = data.get("price", "0")
            return float(price_str) if price_str else None
        except requests.exceptions.RequestException as e:
            logger.warning(f"CLOB API error fetching price for token {token_id}: {e}")
            return None
    
    def get_yes_no_prices(self, yes_token_id: str, no_token_id: str) -> Optional[Dict[str, float]]:
        """
        Get both YES and NO prices for a market
        
        Args:
            yes_token_id: YES outcome token ID
            no_token_id: NO outcome token ID
        
        Returns:
            Dict with yes_price and no_price, or None if error
        """
        try:
            # Buy side for YES
            yes_price = self.get_price(yes_token_id, Side.BUY)
            # Buy side for NO
            no_price = self.get_price(no_token_id, Side.BUY)
            
            if yes_price is None or no_price is None:
                return None
            
            return {
                "yes_price": yes_price,
                "no_price": no_price,
            }
        except Exception as e:
            logger.warning(f"Error fetching YES/NO prices: {e}")
            return None
    
    @rate_limiter.with_retry
    def get_book(self, token_id: str) -> Optional[Dict]:
        """
        Get orderbook for a token
        
        Args:
            token_id: CLOB token ID
        
        Returns:
            Orderbook data or None if error
        """
        url = f"{self.base_url}/book"
        params = {"token_id": token_id}
        
        try:
            response = self.session.get(url, params=params, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"CLOB API error fetching book for token {token_id}: {e}")
            return None
    
    @rate_limiter.with_retry
    def get_prices_history(
        self,
        market_token_id: str,
        interval: str = "1h",
        fidelity: int = 60,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
    ) -> Optional[List[Dict]]:
        """
        Get historical prices for a market
        
        Args:
            market_token_id: CLOB token ID
            interval: Time interval (1h, 1d, 1w, 1m, max)
            fidelity: Resolution in minutes
            start_ts: Optional start timestamp (Unix)
            end_ts: Optional end timestamp (Unix)
        
        Returns:
            List of {t: timestamp, p: price} or None if error
        """
        url = f"{self.base_url}/prices-history"
        params = {
            "market": market_token_id,
            "fidelity": fidelity,
        }
        
        # Use interval OR (startTs + endTs), not both
        if start_ts and end_ts:
            params["startTs"] = start_ts
            params["endTs"] = end_ts
        else:
            params["interval"] = interval
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("history", [])
        except requests.exceptions.RequestException as e:
            logger.warning(f"CLOB API error fetching price history for {market_token_id}: {e}")
            return None
    
    def mark_stale(self, market_id: str):
        """Mark a market as stale (circuit breaker)"""
        self._stale_markets.add(market_id)
        logger.info(f"Market {market_id} marked as stale")
    
    def is_stale(self, market_id: str) -> bool:
        """Check if market is marked stale"""
        return market_id in self._stale_markets
    
    def clear_stale(self, market_id: str):
        """Clear stale marker for a market"""
        self._stale_markets.discard(market_id)
