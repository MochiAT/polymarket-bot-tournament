"""Simple momentum-based strategy example"""

import logging

from polymarket_bot.core.strategy import Strategy
from polymarket_bot.core.market_data import CryptoMarket
from polymarket_bot.core.execution import OrderSide

logger = logging.getLogger(__name__)


class SimpleMomentumStrategy(Strategy):
    """Simple momentum strategy: Buy YES if probability rising"""
    
    def __init__(self, name, market_data_provider, execution_engine, threshold=0.55):
        super().__init__(name, market_data_provider, execution_engine)
        self.threshold = threshold
        self._last_probabilities = {}
    
    def on_market_data(self, market: CryptoMarket):
        """Called when market data is updated"""
        if not market.implied_probability:
            return
        
        market_id = market.market_id
        current_prob = market.implied_probability
        
        # Check if we have previous probability
        if market_id not in self._last_probabilities:
            self._last_probabilities[market_id] = current_prob
            return
        
        last_prob = self._last_probabilities[market_id]
        
        # Check for momentum
        prob_change = current_prob - last_prob
        
        # Buy YES if probability increasing and above threshold
        if prob_change > 0.02 and current_prob > self.threshold:
            # Check if we already have a position
            position = self.execution.get_position(market_id)
            if not position or position.side != OrderSide.YES:
                # Place order
                logger.info(
                    f"[{self.name}] Momentum signal: {market.asset} {market.timeframe} "
                    f"prob: {current_prob:.2%} (Δ{prob_change:+.2%})"
                )
                self.execution.place_order(
                    market_id=market_id,
                    side=OrderSide.YES,
                    size=10.0,  # 10 shares
                    price=current_prob,
                )
        
        # Buy NO if probability decreasing and below (1 - threshold)
        elif prob_change < -0.02 and current_prob < (1 - self.threshold):
            position = self.execution.get_position(market_id)
            if not position or position.side != OrderSide.NO:
                logger.info(
                    f"[{self.name}] Reverse momentum signal: {market.asset} {market.timeframe} "
                    f"prob: {current_prob:.2%} (Δ{prob_change:+.2%})"
                )
                self.execution.place_order(
                    market_id=market_id,
                    side=OrderSide.NO,
                    size=10.0,
                    price=1 - current_prob,
                )
        
        # Update last probability
        self._last_probabilities[market_id] = current_prob
