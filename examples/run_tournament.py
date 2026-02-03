"""Tournament runner for N strategies in parallel"""

import logging
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.providers.polymarket_provider import PolymarketProvider
from polymarket_bot.execution.paper_trading import PaperTradingEngine
from polymarket_bot.execution.tournament import Tournament
from examples.simple_strategy import SimpleMomentumStrategy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def main():
    """Run tournament with multiple strategies"""
    logger.info("Starting tournament runner")
    
    # Get shared market data provider (singleton)
    provider = PolymarketProvider()
    
    # Create multiple strategies with different parameters
    strategies_configs = [
        {"name": "Momentum_Conservative", "threshold": 0.60},
        {"name": "Momentum_Moderate", "threshold": 0.55},
        {"name": "Momentum_Aggressive", "threshold": 0.50},
    ]
    
    strategies_and_engines = []
    
    for config in strategies_configs:
        # Create paper trading engine for this strategy
        engine = PaperTradingEngine(
            strategy_name=config["name"],
            initial_balance=10000.0,
        )
        
        # Create strategy
        strategy = SimpleMomentumStrategy(
            name=config["name"],
            market_data_provider=provider,
            execution_engine=engine,
            threshold=config["threshold"],
        )
        
        # Subscribe to market updates
        provider.subscribe(strategy.on_market_data)
        
        strategies_and_engines.append((strategy, engine))
        logger.info(f"Registered strategy: {config['name']}")
    
    # Create tournament
    tournament = Tournament(strategies_and_engines, results_dir="results")
    tournament.start()
    
    # Start provider (shared by all strategies)
    provider.start()
    
    logger.info(f"Tournament running with {len(strategies_configs)} strategies. Press Ctrl+C to stop.")
    
    try:
        # Run for a while
        while True:
            time.sleep(30)
            
            # Print status for all strategies
            print("\n" + "="*80)
            print(f"TOURNAMENT STATUS ({len(strategies_and_engines)} strategies)")
            print("="*80)
            
            for strategy, engine in strategies_and_engines:
                metrics = engine.get_metrics()
                print(
                    f"{strategy.get_name():<25} | "
                    f"Trades: {metrics['total_trades']:>3} | "
                    f"PnL: ${metrics['total_pnl']:>8.2f} ({metrics['pnl_percent']:>6.2f}%) | "
                    f"Equity: ${metrics['equity']:>10.2f}"
                )
            
            print("="*80)
    
    except KeyboardInterrupt:
        logger.info("Stopping tournament...")
        provider.stop()
        
        # Export results
        tournament.export_results()
        
        logger.info("Tournament stopped. Results exported to results/")


if __name__ == "__main__":
    main()
