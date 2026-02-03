"""Web scraper for Polymarket Up/Down markets at crypto/15M page"""

import requests
import re
import logging
from typing import List, Dict, Optional
import json
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class PolymarketWebScraper:
    """Scraper to fetch Up/Down market IDs from Polymarket website"""
    
    CRYPTO_15M_URL = "https://polymarket.com/crypto/15M"
    
    # Rate limiting settings
    MIN_REQUEST_INTERVAL = 0.5  # Minimum seconds between requests
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # Seconds to wait before retry
    
    # Cache settings
    CACHE_TTL = 60  # Cache results for 60 seconds
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Rate limiting
        self._last_request_time = 0
        
        # Caching
        self._cache = {}
        self._cache_timestamp = None
    
    def _wait_for_rate_limit(self):
        """Ensure minimum time between requests"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()
    
    def _make_request(self, url: str, timeout: int = 10) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic and rate limiting
        
        Args:
            url: URL to fetch
            timeout: Request timeout in seconds
        
        Returns:
            Response object or None on failure
        """
        for attempt in range(self.MAX_RETRIES):
            try:
                self._wait_for_rate_limit()
                
                response = self.session.get(url, timeout=timeout)
                
                if response.status_code == 200:
                    return response
                elif response.status_code == 429:  # Rate limited
                    wait_time = self.RETRY_DELAY * (attempt + 1)
                    logger.warning(f"Rate limited (429), waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                    continue
                elif response.status_code >= 500:  # Server error
                    logger.warning(f"Server error {response.status_code}, retry {attempt + 1}/{self.MAX_RETRIES}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                    continue
                else:
                    logger.error(f"HTTP {response.status_code} for {url}")
                    return None
            
            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout for {url}, retry {attempt + 1}/{self.MAX_RETRIES}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed for {url}: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
        
        logger.error(f"Failed to fetch {url} after {self.MAX_RETRIES} attempts")
        return None
    
    def fetch_updown_market_ids(self) -> List[Dict[str, str]]:
        """
        Scrape the crypto/15M page to get active Up/Down market IDs
        Uses cache to avoid excessive scraping.
        
        Returns:
            List of dicts with 'slug', 'asset', 'timestamp'
        """
        # Check cache
        if self._cache_timestamp and (datetime.now() - self._cache_timestamp) < timedelta(seconds=self.CACHE_TTL):
            if 'market_slugs' in self._cache:
                logger.debug(f"Returning cached market slugs ({len(self._cache['market_slugs'])} markets)")
                return self._cache['market_slugs']
        
        try:
            logger.info(f"Fetching Up/Down markets from {self.CRYPTO_15M_URL}")
            response = self._make_request(self.CRYPTO_15M_URL)
            
            if not response:
                logger.error("Failed to fetch crypto/15M page")
                # Return cached data if available, even if expired
                return self._cache.get('market_slugs', [])
            
            html = response.text
            
            # Extract event slugs (format: btc-updown-15m-1770204600)
            slug_pattern = r'event/([\w]+-updown-15m-\d+)'
            slugs = set(re.findall(slug_pattern, html))
            
            if not slugs:
                logger.warning("No Up/Down event slugs found in HTML")
                return self._cache.get('market_slugs', [])
            
            logger.info(f"Found {len(slugs)} Up/Down event slugs")
            
            markets = []
            for slug in slugs:
                # Parse slug to extract asset and timestamp
                parts = slug.split('-')
                if len(parts) >= 4:
                    try:
                        asset = parts[0].upper()
                        timestamp = parts[-1]
                        
                        # Validate timestamp is numeric
                        int(timestamp)
                        
                        markets.append({
                            'slug': slug,
                            'asset': asset,
                            'timestamp': timestamp,
                            'url': f"https://polymarket.com/event/{slug}"
                        })
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Failed to parse slug {slug}: {e}")
                        continue
            
            # Sort by timestamp (newest first)
            markets.sort(key=lambda x: x['timestamp'], reverse=True)
            
            logger.info(f"Parsed {len(markets)} valid markets: {[m['asset'] for m in markets[:10]]}")
            
            # Update cache
            self._cache['market_slugs'] = markets
            self._cache_timestamp = datetime.now()
            
            return markets
        
        except Exception as e:
            logger.error(f"Unexpected error scraping Up/Down markets: {e}", exc_info=True)
            # Return cached data if available
            return self._cache.get('market_slugs', [])
    
    def fetch_market_details_from_page(self, slug: str) -> Optional[Dict]:
        """
        Fetch a specific market's event page and extract market details
        
        Args:
            slug: Event slug (e.g., 'btc-updown-15m-1770204600')
        
        Returns:
            Dict with market_id, question, clobTokenIds if found
        """
        cache_key = f"market_details_{slug}"
        
        # Check cache
        if cache_key in self._cache:
            cache_age = (datetime.now() - self._cache_timestamp).total_seconds() if self._cache_timestamp else float('inf')
            if cache_age < self.CACHE_TTL:
                logger.debug(f"Returning cached details for {slug}")
                return self._cache[cache_key]
        
        try:
            url = f"https://polymarket.com/event/{slug}"
            logger.debug(f"Fetching market details from {url}")
            
            response = self._make_request(url)
            if not response:
                logger.warning(f"Failed to fetch event page for {slug}")
                return self._cache.get(cache_key)  # Return cached if available
            
            html = response.text
            
            # Try to extract market ID
            market_id_match = re.search(r'"id":"?(\d+)"?', html)
            market_id = market_id_match.group(1) if market_id_match else None
            
            # Try to extract question/title
            question_match = re.search(r'"question":"([^"]+)"', html)
            question = question_match.group(1) if question_match else None
            
            # Try to extract clobTokenIds
            clob_tokens_match = re.search(r'"clobTokenIds":\s*\["([^"]+)",\s*"([^"]+)"\]', html)
            clob_token_ids = None
            if clob_tokens_match:
                clob_token_ids = [clob_tokens_match.group(1), clob_tokens_match.group(2)]
            
            if not market_id:
                logger.warning(f"Could not extract market_id from {slug}")
                return None
            
            result = {
                'market_id': market_id,
                'question': question,
                'clobTokenIds': clob_token_ids,
                'slug': slug,
            }
            
            # Cache the result
            self._cache[cache_key] = result
            
            logger.debug(f"Extracted market {market_id}: {question}")
            return result
        
        except Exception as e:
            logger.error(f"Unexpected error fetching market details for {slug}: {e}", exc_info=True)
            return self._cache.get(cache_key)  # Return cached if available
    
    def get_active_updown_markets_with_details(self, max_markets: int = 20) -> List[Dict]:
        """
        Get active Up/Down markets with full details by scraping individual pages
        
        Args:
            max_markets: Maximum number of markets to fetch details for
        
        Returns:
            List of market dicts with market_id, question, clobTokenIds
        """
        # First, get the list of slugs
        market_slugs = self.fetch_updown_market_ids()
        
        if not market_slugs:
            logger.warning("No Up/Down market slugs found")
            return []
        
        # Limit to avoid too many requests
        market_slugs = market_slugs[:max_markets]
        
        # Fetch details for each market
        markets_with_details = []
        success_count = 0
        fail_count = 0
        
        for slug_info in market_slugs:
            details = self.fetch_market_details_from_page(slug_info['slug'])
            if details:
                # Merge slug info with details
                details.update({
                    'asset': slug_info['asset'],
                    'timestamp': slug_info['timestamp'],
                })
                markets_with_details.append(details)
                success_count += 1
            else:
                fail_count += 1
        
        logger.info(
            f"Fetched details for {success_count} markets "
            f"({fail_count} failed, {len(markets_with_details)} total)"
        )
        
        return markets_with_details
    
    def clear_cache(self):
        """Clear the internal cache"""
        self._cache.clear()
        self._cache_timestamp = None
        logger.debug("Cache cleared")

