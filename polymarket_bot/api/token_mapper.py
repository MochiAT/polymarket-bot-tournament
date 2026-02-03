"""Gamma-CLOB token mapping cache"""

import logging
from typing import Dict, Optional, List
from threading import Lock

logger = logging.getLogger(__name__)


class TokenMapper:
    """Maps Gamma market IDs to CLOB token IDs (YES/NO)"""
    
    def __init__(self):
        self._cache: Dict[str, Dict[str, str]] = {}
        self._lock = Lock()
    
    def update_from_market(self, market: dict) -> bool:
        """
        Extract clobTokenIds from Gamma market response and cache
        
        Args:
            market: Gamma market dict with 'id' and 'clobTokenIds'
        
        Returns:
            True if successfully cached, False if invalid
        """
        market_id = market.get("id")
        clob_token_ids = market.get("clobTokenIds", [])
        
        if not market_id:
            logger.warning("Market missing 'id' field, skipping token mapping")
            return False
        
        if not clob_token_ids or len(clob_token_ids) < 2:
            logger.warning(
                f"Market {market_id} missing or invalid clobTokenIds: {clob_token_ids}"
            )
            return False
        
        # Cache the mapping
        with self._lock:
            self._cache[market_id] = {
                "yes_token_id": clob_token_ids[0],
                "no_token_id": clob_token_ids[1],
                "condition_id": market.get("conditionId", ""),
            }
        
        logger.debug(f"Cached token mapping for market {market_id}: YES={clob_token_ids[0]}, NO={clob_token_ids[1]}")
        return True
    
    def get_token_ids(self, market_id: str) -> Optional[Dict[str, str]]:
        """
        Get cached token IDs for a market
        
        Returns:
            Dict with yes_token_id, no_token_id, condition_id or None if not found
        """
        with self._lock:
            return self._cache.get(market_id)
    
    def get_yes_token_id(self, market_id: str) -> Optional[str]:
        """Get YES token ID for a market"""
        mapping = self.get_token_ids(market_id)
        return mapping["yes_token_id"] if mapping else None
    
    def get_no_token_id(self, market_id: str) -> Optional[str]:
        """Get NO token ID for a market"""
        mapping = self.get_token_ids(market_id)
        return mapping["no_token_id"] if mapping else None
    
    def has_mapping(self, market_id: str) -> bool:
        """Check if market has cached token mapping"""
        with self._lock:
            return market_id in self._cache
    
    def clear(self):
        """Clear all cached mappings"""
        with self._lock:
            self._cache.clear()
    
    def get_all_market_ids(self) -> List[str]:
        """Get all cached market IDs"""
        with self._lock:
            return list(self._cache.keys())
