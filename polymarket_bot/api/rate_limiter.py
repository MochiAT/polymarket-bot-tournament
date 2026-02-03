"""Rate limiting and retry logic with exponential backoff"""

import time
import logging
from typing import Callable, Any, Optional
from functools import wraps

from polymarket_bot.config import Config

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter with exponential backoff for API requests"""
    
    def __init__(
        self,
        max_retries: int = Config.MAX_RETRIES,
        initial_backoff: float = Config.INITIAL_BACKOFF,
        max_backoff: float = Config.MAX_BACKOFF,
    ):
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
    
    def with_retry(self, func: Callable) -> Callable:
        """Decorator to add retry logic with exponential backoff"""
        
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            backoff = self.initial_backoff
            
            while retries <= self.max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_msg = str(e)
                    
                    # Check if it's a rate limit or server error
                    is_rate_limit = "429" in error_msg or "Too Many Requests" in error_msg
                    is_server_error = "500" in error_msg or "502" in error_msg or "503" in error_msg
                    is_timeout = "timeout" in error_msg.lower() or "Timeout" in error_msg
                    
                    if not (is_rate_limit or is_server_error or is_timeout):
                        # Not a retryable error
                        raise
                    
                    retries += 1
                    if retries > self.max_retries:
                        logger.error(f"Max retries ({self.max_retries}) exceeded for {func.__name__}: {error_msg}")
                        raise
                    
                    # Calculate backoff with exponential increase
                    sleep_time = min(backoff * (2 ** (retries - 1)), self.max_backoff)
                    
                    logger.warning(
                        f"Retryable error in {func.__name__} (attempt {retries}/{self.max_retries}): "
                        f"{error_msg}. Retrying in {sleep_time:.1f}s..."
                    )
                    
                    time.sleep(sleep_time)
            
            # Should not reach here
            raise Exception(f"Unexpected error in retry logic for {func.__name__}")
        
        return wrapper


# Global rate limiter instance
rate_limiter = RateLimiter()
