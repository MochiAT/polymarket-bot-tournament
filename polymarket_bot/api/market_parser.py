"""Crypto binary market parser with robust extraction"""

import re
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime

from polymarket_bot.config import Config

logger = logging.getLogger(__name__)


class MarketParser:
    """Parser for crypto binary markets"""
    
    # Regex patterns for parsing
    ASSET_PATTERN = re.compile(
        r'\b(bitcoin|btc|ethereum|eth|solana|sol|xrp)\b',
        re.IGNORECASE
    )
    PRICE_PATTERN = re.compile(
        r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:USD)?',
        re.IGNORECASE
    )
    TIMEFRAME_PATTERN = re.compile(
        r'\b(\d+)\s*(minute|hour|day)s?\b',
        re.IGNORECASE
    )
    
    def __init__(self):
        self.asset_synonyms = Config.ASSET_SYNONYMS
    
    def extract_asset(self, title: str) -> Optional[str]:
        """Extract normalized asset from title"""
        match = self.ASSET_PATTERN.search(title)
        if match:
            asset_raw = match.group(1).lower()
            return self.asset_synonyms.get(asset_raw)
        return None
    
    def extract_price_to_beat(self, market: dict) -> Optional[float]:
        """
        Extract price_to_beat with fallback hierarchy:
        1. Direct field
        2. Regex from title
        3. Regex from description/rules
        
        Returns:
            Price as float or None
        """
        # 1. Try direct field
        price = market.get("price_to_beat") or market.get("priceToBeats")
        if price is not None:
            try:
                return float(price)
            except (ValueError, TypeError):
                pass
        
        # 2. Try title
        title = market.get("question", "") or market.get("title", "")
        match = self.PRICE_PATTERN.search(title)
        if match:
            try:
                price_str = match.group(1).replace(",", "")
                return float(price_str)
            except (ValueError, IndexError):
                pass
        
        # 3. Try description/rules
        description = market.get("description", "") or market.get("rules", "")
        match = self.PRICE_PATTERN.search(description)
        if match:
            try:
                price_str = match.group(1).replace(",", "")
                return float(price_str)
            except (ValueError, IndexError):
                pass
        
        return None
    
    def extract_timeframe(self, market: dict, title: str) -> Optional[str]:
        """
        Extract timeframe with hierarchy:
        1. Explicit duration fields
        2. Regex from title
        3. Calculate from timestamps
        
        Returns:
            Normalized timeframe (15m, 1h, 4h, 1d) or None
        """
        # 1. Try explicit duration field
        duration_minutes = market.get("duration_minutes")
        if duration_minutes:
            return self._normalize_timeframe_minutes(duration_minutes)
        
        # 2. Try regex from title
        match = self.TIMEFRAME_PATTERN.search(title)
        if match:
            value = int(match.group(1))
            unit = match.group(2).lower()
            
            if "minute" in unit:
                return self._normalize_timeframe_minutes(value)
            elif "hour" in unit:
                return self._normalize_timeframe_minutes(value * 60)
            elif "day" in unit:
                return self._normalize_timeframe_minutes(value * 1440)
        
        # 3. Try to calculate from timestamps
        end_time_str = market.get("endDate") or market.get("end_date")
        start_time_str = market.get("creationDate") or market.get("creation_date")
        
        if end_time_str and start_time_str:
            try:
                end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                duration_seconds = (end_time - start_time).total_seconds()
                duration_minutes = int(duration_seconds / 60)
                return self._normalize_timeframe_minutes(duration_minutes)
            except Exception:
                pass
        
        return None
    
    def _normalize_timeframe_minutes(self, minutes: int) -> Optional[str]:
        """Normalize minutes to standard timeframe"""
        if 10 <= minutes <= 20:
            return "15m"
        elif 45 <= minutes <= 75:
            return "1h"
        elif 210 <= minutes <= 270:
            return "4h"
        elif 1200 <= minutes <= 1680:
            return "1d"
        return None
    
    def parse_market(self, market: dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Parse and validate a crypto binary market
        
        Returns:
            (is_valid, discard_reason, parsed_data)
        """
        title = market.get("question", "") or market.get("title", "")
        
        # Extract asset
        asset = self.extract_asset(title)
        if not asset:
            logger.debug(f"Market '{title}' does not match crypto asset pattern")
            return False, "not_crypto_market", None
        
        # Check if asset is supported
        if asset not in Config.SUPPORTED_ASSETS:
            return False, "unsupported_asset", None
        
        # Extract price_to_beat
        price_to_beat = self.extract_price_to_beat(market)
        if price_to_beat is None:
            logger.warning(f"Market '{title}' missing price_to_beat")
            return False, "no_price_to_beat", None
        
        # Extract timeframe
        timeframe = self.extract_timeframe(market, title)
        if not timeframe or timeframe not in Config.SUPPORTED_TIMEFRAMES:
            logger.debug(f"Market '{title}' has unsupported timeframe: {timeframe}")
            return False, "unsupported_timeframe", None
        
        # Extract resolution time
        resolution_time_str = market.get("endDate") or market.get("end_date")
        resolution_time = None
        if resolution_time_str:
            try:
                resolution_time = datetime.fromisoformat(
                    resolution_time_str.replace("Z", "+00:00")
                )
            except Exception as e:
                logger.warning(f"Could not parse resolution_time: {e}")
        
        parsed_data = {
            "asset": asset,
            "timeframe": timeframe,
            "price_to_beat": price_to_beat,
            "resolution_time": resolution_time,
            "market_id": market.get("id"),
            "title": title,
            "status": market.get("active", False),
        }
        
        return True, None, parsed_data
