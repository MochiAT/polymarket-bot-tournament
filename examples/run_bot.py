"""Single bot runner example"""

import logging
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.providers.polymarket_provider import PolymarketProvider
from polymarket_bot.execution.paper_trading import PaperTradingEngine
from examples.simple_strategy import SimpleMomentumStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Run a single bot"""
    logger.info("Starting single bot example")
    
    # Get shared market data provider (singleton)
    provider = PolymarketProvider()
    
    # Create paper trading engine
    engine = PaperTradingEngine(strategy_name="SimpleMomentum", initial_balance=10000.0)
    
    # Create strategy
    strategy = SimpleMomentumStrategy(
        name="SimpleMomentum",
        market_data_provider=provider,
        execution_engine=engine,
        threshold=0.55,
    )
    
    # Subscribe strategy to market updates
    provider.subscribe(strategy.on_market_data)
    
    # Start provider
    provider.start()
    
    logger.info("Bot running. Press Ctrl+C to stop.")
    
    try:
        # Run for a while
        while True:
            time.sleep(10)
            
            # Print status
            metrics = engine.get_metrics()
            logger.info(
                f"Status: Trades={metrics['total_trades']}, "
                f"PnL=${metrics['total_pnl']:.2f} ({metrics['pnl_percent']:.2f}%), "
                f"Equity=${metrics['equity']:.2f}"
            )
    
    except KeyboardInterrupt:
        logger.info("Stopping bot...")
        provider.stop()
        
        # Print final metrics
        metrics = engine.get_metrics()
        print("\n" + "="*60)
        print("FINAL RESULTS")
        print("="*60)
        print(f"Strategy: {metrics['strategy_name']}")
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Total PnL: ${metrics['total_pnl']:.2f} ({metrics['pnl_percent']:.2f}%)")
        print(f"Final Equity: ${metrics['equity']:.2f}")
        print(f"Win Rate: {metrics['win_rate']:.1f}%")
        print("="*60)


if __name__ == "__main__":
    main()
