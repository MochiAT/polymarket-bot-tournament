"""Gamma API client for market discovery and metadata"""

import logging
import requests
from typing import List, Dict, Optional
from datetime import datetime

from polymarket_bot.config import Config
from polymarket_bot.api.rate_limiter import rate_limiter

logger = logging.getLogger(__name__)


class GammaClient:
    """Client for Polymarket Gamma API (market data and metadata)"""
    
    def __init__(self, base_url: str = Config.GAMMA_API_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
    
    @rate_limiter.with_retry
    def get_markets(
        self,
        active: bool = True,
        closed: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """
        Fetch markets from Gamma API
        
        Args:
            active: Include active markets
            closed: Include closed markets
            limit: Max markets per request
            offset: Pagination offset
        
        Returns:
            List of market dictionaries
        """
        url = f"{self.base_url}/markets"
        params = {
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "limit": limit,
            "offset": offset,
        }
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Gamma API error fetching markets: {e}")
            raise
    
    def validate_market(self, market: dict) -> tuple[bool, Optional[str]]:
        """
        Validate market against criteria
        
        Returns:
            (is_valid, discard_reason)
        """
        # Check status
        status = market.get("active", False)
        if not status:
            return False, "status_not_active"
        
        # Check end_time in future
        end_time_str = market.get("endDate") or market.get("end_date")
        if end_time_str:
            try:
                # Parse ISO format timestamp
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                if end_time < datetime.now(end_time.tzinfo):
                    return False, "end_time_passed"
            except Exception as e:
                logger.warning(f"Could not parse end_time '{end_time_str}': {e}")
        
        # Check clobTokenIds present
        clob_token_ids = market.get("clobTokenIds", [])
        if not clob_token_ids or len(clob_token_ids) < 2:
            return False, "no_clobTokenIds"
        
        return True, None
    
    def get_all_active_markets(self, max_markets: int = 1000) -> List[Dict]:
        """
        Fetch all active markets with pagination
        
        Args:
            max_markets: Maximum total markets to fetch
        
        Returns:
            List of all active markets
        """
        all_markets = []
        offset = 0
        limit = 100
        
        while len(all_markets) < max_markets:
            try:
                markets = self.get_markets(active=True, closed=False, limit=limit, offset=offset)
                
                if not markets:
                    break
                
                all_markets.extend(markets)
                
                if len(markets) < limit:
                    # No more pages
                    break
                
                offset += limit
            except Exception as e:
                logger.error(f"Error fetching markets at offset {offset}: {e}")
                # Don't crash the system, return what we have
                break
        
        logger.info(f"Fetched {len(all_markets)} markets from Gamma API")
        return all_markets
