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
    
    def __init__(self, base_url: str = Config.GAMMA_API_URL, use_web_scraper: bool = True):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.use_web_scraper = use_web_scraper
        self._scraper = None
    
    @property
    def scraper(self):
        """Lazy load web scraper"""
        if self._scraper is None and self.use_web_scraper:
            from polymarket_bot.api.web_scraper import PolymarketWebScraper
            self._scraper = PolymarketWebScraper()
        return self._scraper
    
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
    
    def get_updown_markets_from_web(self, max_markets: int = 20) -> List[Dict]:
        """
        Fetch Up/Down markets from web scraping (fallback when API doesn't provide them)
        
        Args:
            max_markets: Maximum markets to fetch
        
        Returns:
            List of market dicts compatible with Gamma API format
        """
        if not self.use_web_scraper or self.scraper is None:
            logger.warning("Web scraper disabled, cannot fetch Up/Down markets")
            return []
        
        try:
            logger.info("Fetching Up/Down markets via web scraping")
            scraped_markets = self.scraper.get_active_updown_markets_with_details(max_markets=max_markets)
            
            # Convert scraped format to Gamma API compatible format
            gamma_format_markets = []
            for market in scraped_markets:
                gamma_market = {
                    "id": market.get("market_id"),
                    "question": market.get("question"),
                    "clobTokenIds": market.get("clobTokenIds", []),
                    "active": True,  # Scraped from active page
                    "closed": False,
                    # Add any other fields we have
                    "slug": market.get("slug"),
                }
                gamma_format_markets.append(gamma_market)
            
            logger.info(f"Successfully scraped {len(gamma_format_markets)} Up/Down markets")
            return gamma_format_markets
        
        except Exception as e:
            logger.error(f"Error scraping Up/Down markets: {e}")
            return []
    
    def get_all_active_markets(self, max_markets: int = 1000, include_updown_scraping: bool = True) -> List[Dict]:
        """
        Fetch all active markets with pagination, optionally including web-scraped Up/Down markets
        
        Args:
            max_markets: Maximum total markets to fetch from API
            include_updown_scraping: Whether to add scraped Up/Down markets
        
        Returns:
            List of all active markets
        """
        all_markets = []
        offset = 0
        limit = 100
        
        # Fetch from API
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
        
        # Add Up/Down markets from web scraping
        if include_updown_scraping and self.use_web_scraper:
            updown_markets = self.get_updown_markets_from_web(max_markets=20)
            if updown_markets:
                all_markets.extend(updown_markets)
                logger.info(f"Added {len(updown_markets)} scraped Up/Down markets, total: {len(all_markets)}")
        
        return all_markets

