"""Web scraper for Polymarket Up/Down markets at crypto/15M page"""

import requests
import re
import logging
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)


class PolymarketWebScraper:
    """Scraper to fetch Up/Down market IDs from Polymarket website"""
    
    CRYPTO_15M_URL = "https://polymarket.com/crypto/15M"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_updown_market_ids(self) -> List[Dict[str, str]]:
        """
        Scrape the crypto/15M page to get active Up/Down market IDs
        
        Returns:
            List of dicts with 'slug', 'asset', 'timestamp'
        """
        try:
            logger.info(f"Fetching Up/Down markets from {self.CRYPTO_15M_URL}")
            response = self.session.get(self.CRYPTO_15M_URL, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch crypto/15M page: {response.status_code}")
                return []
            
            html = response.text
            
            # Extract event slugs (format: btc-updown-15m-1770204600)
            slug_pattern = r'event/([\w]+-updown-15m-\d+)'
            slugs = set(re.findall(slug_pattern, html))
            
            logger.info(f"Found {len(slugs)} Up/Down event slugs")
            
            markets = []
            for slug in slugs:
                # Parse slug to extract asset and timestamp
                parts = slug.split('-')
                if len(parts) >= 4:
                    asset = parts[0].upper()
                    timestamp = parts[-1]
                    
                    markets.append({
                        'slug': slug,
                        'asset': asset,
                        'timestamp': timestamp,
                        'url': f"https://polymarket.com/event/{slug}"
                    })
            
            # Sort by timestamp (newest first)
            markets.sort(key=lambda x: x['timestamp'], reverse=True)
            
            logger.info(f"Parsed {len(markets)} markets: {[m['asset'] for m in markets[:10]]}")
            
            return markets
        
        except Exception as e:
            logger.error(f"Error scraping Up/Down markets: {e}")
            return []
    
    def fetch_market_details_from_page(self, slug: str) -> Optional[Dict]:
        """
        Fetch a specific market's event page and extract market details
        
        Args:
            slug: Event slug (e.g., 'btc-updown-15m-1770204600')
        
        Returns:
            Dict with market_id, question, clobTokenIds if found
        """
        try:
            url = f"https://polymarket.com/event/{slug}"
            logger.debug(f"Fetching market details from {url}")
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Failed to fetch event page for {slug}: {response.status_code}")
                return None
            
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
            
            if market_id:
                result = {
                    'market_id': market_id,
                    'question': question,
                    'clobTokenIds': clob_token_ids,
                    'slug': slug,
                }
                logger.debug(f"Extracted market {market_id}: {question}")
                return result
            else:
                logger.warning(f"Could not extract market_id from {slug}")
                return None
        
        except Exception as e:
            logger.error(f"Error fetching market details for {slug}: {e}")
            return None
    
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
        for slug_info in market_slugs:
            details = self.fetch_market_details_from_page(slug_info['slug'])
            if details:
                # Merge slug info with details
                details.update({
                    'asset': slug_info['asset'],
                    'timestamp': slug_info['timestamp'],
                })
                markets_with_details.append(details)
        
        logger.info(f"Successfully fetched details for {len(markets_with_details)} markets")
        
        return markets_with_details
