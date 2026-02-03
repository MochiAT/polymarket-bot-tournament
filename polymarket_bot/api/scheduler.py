"""Multi-rate polling scheduler"""

import logging
import threading
import time
from typing import List, Callable, Optional
from collections import deque

from polymarket_bot.config import Config

logger = logging.getLogger(__name__)


class Scheduler:
    """Multi-rate scheduler for fast/slow ticks with round-robin batching"""
    
    def __init__(
        self,
        fast_tick_interval: int = Config.FAST_TICK_INTERVAL,
        slow_tick_interval: int = Config.SLOW_TICK_INTERVAL,
        max_markets_per_tick: int = Config.MAX_MARKETS_PER_TICK,
        max_runtime_seconds: Optional[float] = None,
    ):
        self.fast_tick_interval = fast_tick_interval
        self.slow_tick_interval = slow_tick_interval
        self.max_markets_per_tick = max_markets_per_tick
        self.max_runtime_seconds = max_runtime_seconds
        
        self._running = False
        self._start_time: Optional[float] = None
        self._fast_thread: Optional[threading.Thread] = None
        self._slow_thread: Optional[threading.Thread] = None
        
        self._fast_callbacks: List[Callable[[List[str]], None]] = []
        self._slow_callbacks: List[Callable[[], None]] = []
        
        self._market_ids: List[str] = []
        self._round_robin_index = 0
        self._lock = threading.Lock()
    
    def set_market_ids(self, market_ids: List[str]):
        """Update the list of market IDs to poll"""
        with self._lock:
            self._market_ids = market_ids
            self._round_robin_index = 0
        logger.info(f"Scheduler updated with {len(market_ids)} markets")
    
    def add_fast_callback(self, callback: Callable[[List[str]], None]):
        """Add callback for fast tick (receives batch of market_ids)"""
        self._fast_callbacks.append(callback)
    
    def add_slow_callback(self, callback: Callable[[], None]):
        """Add callback for slow tick"""
        self._slow_callbacks.append(callback)
    
    def _get_next_batch(self) -> List[str]:
        """Get next batch of market IDs using round-robin"""
        with self._lock:
            if not self._market_ids:
                return []
            
            total_markets = len(self._market_ids)
            
            # If we can fit all markets in one tick
            if total_markets <= self.max_markets_per_tick:
                return self._market_ids.copy()
            
            # Round-robin batching
            start_idx = self._round_robin_index
            end_idx = start_idx + self.max_markets_per_tick
            
            if end_idx >= total_markets:
                # Wrap around
                batch = self._market_ids[start_idx:]
                self._round_robin_index = 0
            else:
                batch = self._market_ids[start_idx:end_idx]
                self._round_robin_index = end_idx
            
            return batch
    
    def _interruptible_sleep(self, duration: float):
        """Sleep in small chunks to allow quick interruption"""
        end_time = time.time() + duration
        while self._running and time.time() < end_time:
            # Sleep in 0.1s chunks for responsiveness
            remaining = end_time - time.time()
            time.sleep(min(0.1, remaining))
    
    def _fast_tick_loop(self):
        """Fast tick loop for price updates"""
        logger.info(f"Fast tick loop started (interval={self.fast_tick_interval}s)")
        
        while self._running:
            try:
                # Check timeout
                if self.max_runtime_seconds and self._start_time:
                    elapsed_total = time.time() - self._start_time
                    if elapsed_total >= self.max_runtime_seconds:
                        logger.warning(f"Fast tick: Max runtime ({self.max_runtime_seconds}s) exceeded, stopping")
                        self._running = False
                        break
                
                start_time = time.time()
                
                # Get next batch of markets
                batch = self._get_next_batch()
                
                if batch:
                    # Call all fast tick callbacks
                    for callback in self._fast_callbacks:
                        try:
                            callback(batch)
                        except Exception as e:
                            logger.error(f"Error in fast tick callback: {e}", exc_info=True)
                
                # Sleep for remaining interval (in small chunks for responsiveness)
                elapsed = time.time() - start_time
                sleep_time = max(0, self.fast_tick_interval - elapsed)
                self._interruptible_sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in fast tick loop: {e}", exc_info=True)
                self._interruptible_sleep(1)
    
    def _slow_tick_loop(self):
        """Slow tick loop for market refresh"""
        logger.info(f"Slow tick loop started (interval={self.slow_tick_interval}s)")
        
        while self._running:
            try:
                # Check timeout
                if self.max_runtime_seconds and self._start_time:
                    elapsed_total = time.time() - self._start_time
                    if elapsed_total >= self.max_runtime_seconds:
                        logger.warning(f"Slow tick: Max runtime ({self.max_runtime_seconds}s) exceeded, stopping")
                        self._running = False
                        break
                
                start_time = time.time()
                
                # Call all slow tick callbacks
                for callback in self._slow_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Error in slow tick callback: {e}", exc_info=True)
                
                # Sleep for remaining interval (in small chunks for responsiveness)
                elapsed = time.time() - start_time
                sleep_time = max(0, self.slow_tick_interval - elapsed)
                self._interruptible_sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in slow tick loop: {e}", exc_info=True)
                self._interruptible_sleep(1)
    
    def start(self):
        """Start the scheduler"""
        if self._running:
            logger.warning("Scheduler already running")
            return
        
        self._running = True
        self._start_time = time.time()
        
        # Start fast tick thread
        self._fast_thread = threading.Thread(target=self._fast_tick_loop, daemon=True)
        self._fast_thread.start()
        
        # Start slow tick thread
        self._slow_thread = threading.Thread(target=self._slow_tick_loop, daemon=True)
        self._slow_thread.start()
        
        if self.max_runtime_seconds:
            logger.info(f"Scheduler started with {self.max_runtime_seconds}s timeout")
        else:
            logger.info("Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        if not self._running:
            return
        
        self._running = False
        
        if self._fast_thread:
            self._fast_thread.join(timeout=5)
        if self._slow_thread:
            self._slow_thread.join(timeout=5)
        
        logger.info("Scheduler stopped")
    
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._running
