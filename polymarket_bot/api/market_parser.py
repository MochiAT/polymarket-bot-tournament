"""Crypto binary market parser with robust extraction"""

import re
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime

from polymarket_bot.config import Config

logger = logging.getLogger(__name__)


class MarketParser:
    """Parser for crypto binary markets with robust title normalization"""
    
    def __init__(self):
        self.asset_synonyms = Config.ASSET_SYNONYMS
        self._discard_counts = {}
        self._discard_log_count = 0
        self._max_discard_logs = 30
    
    def normalize_title(self, title: str) -> str:
        """
        Normalize title for robust parsing:
        - Lowercase
        - Replace Unicode dashes (–, —) with normal dash (-)
        - Collapse multiple spaces
        - Trim whitespace
        """
        if not title:
            return ""
        
        # Convert to lowercase
        normalized = title.lower()
        
        # Replace Unicode dashes with normal dash
        normalized = normalized.replace('\u2013', '-')  # en dash
        normalized = normalized.replace('\u2014', '-')  # em dash
        
        # Collapse multiple spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Trim
        normalized = normalized.strip()
        
        return normalized
    
    def extract_asset(self, title_norm: str) -> Optional[str]:
        """Extract normalized asset from normalized title"""
        for synonym, asset in self.asset_synonyms.items():
            if synonym in title_norm:
                return asset
        return None
    
    def is_up_or_down_market(self, title_norm: str) -> bool:
        """
        Check if market is a directional binary market
        Accepts variations: 'up or down', 'up/down', 'updown', 'up-down'
        """
        patterns = [
            'up or down',
            'up/down',
            'updown',
            'up-down',
            'higher or lower',
            'above or below',
        ]
        return any(pattern in title_norm for pattern in patterns)
    
    def parse_timeframe(self, title_norm: str, market: dict) -> Optional[str]:
        """
        Parse timeframe with flexible patterns
        
        Returns one of: 15m, 1h, 4h, 1d
        
        Priority:
        1. Explicit metadata fields
        2. Regex on normalized title
        3. Time window calculation (e.g., "7:30am-7:45am" = 15m)
        4. None if not found
        """
        # 1. Try explicit fields
        duration_minutes = market.get("duration_minutes")
        if duration_minutes:
            tf = self._normalize_timeframe_minutes(int(duration_minutes))
            if tf:
                return tf
        
        # 2. Parse from normalized title with flexible patterns
        
        # 15m patterns
        if re.search(r'\b15\s*m\b', title_norm):
            return "15m"
        if re.search(r'\b15\s*min(?:s|ute|utes)?\b', title_norm):
            return "15m"
        if re.search(r'\b15-min(?:ute)?s?\b', title_norm):
            return "15m"
        
        # 1h patterns
        if re.search(r'\b1\s*h\b', title_norm):
            return "1h"
        if re.search(r'\b1\s*hour(?:s)?\b', title_norm):
            return "1h"
        if re.search(r'\b60\s*min(?:s|ute|utes)?\b', title_norm):
            return "1h"
        
        # 4h patterns
        if re.search(r'\b4\s*h\b', title_norm):
            return "4h"
        if re.search(r'\b4\s*hour(?:s)?\b', title_norm):
            return "4h"
        if re.search(r'\b240\s*min(?:s|ute|utes)?\b', title_norm):
            return "4h"
        
        # 1d patterns
        if re.search(r'\b1\s*d\b', title_norm):
            return "1d"
        if re.search(r'\b1\s*day\b', title_norm):
            return "1d"
        if re.search(r'\b24\s*hour(?:s)?\b', title_norm):
            return "1d"
        if re.search(r'\b1440\s*min(?:s|ute|utes)?\b', title_norm):
            return "1d"
        
        # 3. Try to extract time window and calculate duration
        # Pattern: "7:30AM-7:45AM" or "7:30am-7:45am"
        time_window_pattern = r'(\d{1,2}):(\d{2})\s*(am|pm)\s*-\s*(\d{1,2}):(\d{2})\s*(am|pm)'
        match = re.search(time_window_pattern, title_norm)
        if match:
            start_hour, start_min, start_period, end_hour, end_min, end_period = match.groups()
            
            # Convert to 24-hour format
            start_hour = int(start_hour)
            end_hour = int(end_hour)
            
            if start_period == 'pm' and start_hour != 12:
                start_hour += 12
            elif start_period == 'am' and start_hour == 12:
                start_hour = 0
            
            if end_period == 'pm' and end_hour != 12:
                end_hour += 12
            elif end_period == 'am' and end_hour == 12:
                end_hour = 0
            
            # Calculate duration in minutes
            start_total_min = start_hour * 60 + int(start_min)
            end_total_min = end_hour * 60 + int(end_min)
            
            duration_min = end_total_min - start_total_min
            if duration_min < 0:
                duration_min += 24 * 60  # Crossed midnight
            
            # Normalize to standard timeframe
            tf = self._normalize_timeframe_minutes(duration_min)
            if tf:
                logger.debug(f"Extracted {duration_min} minutes from time window, normalized to {tf}")
                return tf
        
        return None
    
    def _normalize_timeframe_minutes(self, minutes: int) -> Optional[str]:
        """Map duration in minutes to standard timeframe"""
        if 10 <= minutes <= 20:
            return "15m"
        elif 45 <= minutes <= 75:
            return "1h"
        elif 210 <= minutes <= 270:
            return "4h"
        elif 1200 <= minutes <= 1680:
            return "1d"
        return None
    
    def extract_price_to_beat(self, market: dict, title: str) -> Optional[float]:
        """
        Extract price_to_beat with fallback hierarchy:
        1. Direct field
        2. Regex from title
        3. Regex from description/rules
        """
        # 1. Try direct field
        price = market.get("price_to_beat") or market.get("priceToBeats")
        if price is not None:
            try:
                return float(price)
            except (ValueError, TypeError):
                pass
        
        # 2. Try title
        price_pattern = re.compile(r'\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)')
        match = price_pattern.search(title)
        if match:
            try:
                price_str = match.group(1).replace(",", "")
                return float(price_str)
            except (ValueError, IndexError):
                pass
        
        # 3. Try description/rules
        description = market.get("description", "") or market.get("rules", "")
        match = price_pattern.search(description)
        if match:
            try:
                price_str = match.group(1).replace(",", "")
                return float(price_str)
            except (ValueError, IndexError):
                pass
        
        return None
    
    def log_discard(self, market_id: str, reason: str, asset: Optional[str], 
                    timeframe: Optional[str], title: str, title_norm: str):
        """
        Log market discard with context (max 30 logs per refresh)
        """
        # Track counts
        self._discard_counts[reason] = self._discard_counts.get(reason, 0) + 1
        
        # Only log first 30 discards with full details
        if self._discard_log_count < self._max_discard_logs:
            logger.warning(
                f"Market {market_id} discarded: {reason}\n"
                f"  asset={asset or 'None'} timeframe={timeframe or 'None'}\n"
                f"  title=\"{title[:160]}\"\n"
                f"  title_norm=\"{title_norm[:160]}\""
            )
            self._discard_log_count += 1
        elif self._discard_log_count == self._max_discard_logs:
            logger.info(f"Reached max discard logs ({self._max_discard_logs}), suppressing further detailed logs")
            self._discard_log_count += 1
    
    def reset_discard_stats(self):
        """Reset discard counters (call at start of each refresh)"""
        if self._discard_counts:
            logger.info(f"Discard summary: {dict(self._discard_counts)}")
        self._discard_counts = {}
        self._discard_log_count = 0
    
    def parse_market(self, market: dict) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Parse and validate a crypto binary market
        
        Returns:
            (is_valid, discard_reason, parsed_data)
        """
        market_id = market.get("id", "unknown")
        title = market.get("question", "") or market.get("title", "")
        title_norm = self.normalize_title(title)
        
        # Check for "Up or Down"
        if not self.is_up_or_down_market(title_norm):
            self.log_discard(market_id, "not_up_or_down", None, None, title, title_norm)
            return False, "not_up_or_down", None
        
        # Extract asset
        asset = self.extract_asset(title_norm)
        if not asset:
            self.log_discard(market_id, "no_asset", None, None, title, title_norm)
            return False, "no_asset", None
        
        # Check if asset is supported
        if asset not in Config.SUPPORTED_ASSETS:
            self.log_discard(market_id, "unsupported_asset", asset, None, title, title_norm)
            return False, "unsupported_asset", None
        
        # Parse timeframe
        timeframe = self.parse_timeframe(title_norm, market)
        if not timeframe or timeframe not in Config.SUPPORTED_TIMEFRAMES:
            self.log_discard(market_id, "unsupported_timeframe", asset, timeframe, title, title_norm)
            return False, "unsupported_timeframe", None
        
        # Extract price_to_beat (OPTIONAL for intraday Up/Down markets)
        price_to_beat = self.extract_price_to_beat(market, title)
        
        # For intraday Up/Down markets (15m), price_to_beat is optional
        # The reference price is likely the market price at start time
        is_intraday = timeframe == "15m"
        
        if price_to_beat is None and not is_intraday:
            self.log_discard(market_id, "no_price_to_beat", asset, timeframe, title, title_norm)
            return False, "no_price_to_beat", None
        
        # Extract resolution time
        resolution_time_str = market.get("endDate") or market.get("end_date")
        resolution_time = None
        if resolution_time_str:
            try:
                resolution_time = datetime.fromisoformat(
                    resolution_time_str.replace("Z", "+00:00")
                )
            except Exception as e:
                logger.debug(f"Could not parse resolution_time: {e}")
        
        parsed_data = {
            "asset": asset,
            "timeframe": timeframe,
            "price_to_beat": price_to_beat,  # Can be None for intraday markets
            "resolution_time": resolution_time,
            "market_id": market_id,
            "title": title,
            "status": market.get("active", False),
        }
        
        return True, None, parsed_data
