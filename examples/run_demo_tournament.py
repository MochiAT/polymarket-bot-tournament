"""Demo: 4 bots con diferentes estrategias y presupuestos"""

import logging
import sys
import time
import json
import csv
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.providers.polymarket_provider import PolymarketProvider
from polymarket_bot.execution.paper_trading import PaperTradingEngine
from examples.simple_strategy import SimpleMomentumStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def export_snapshot(bots, snapshots_dir, elapsed_minutes):
    """Export current tournament state to timestamped files"""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    # Collect results
    results = []
    for strategy, engine in bots:
        metrics = engine.get_metrics()
        results.append({
            'name': strategy.get_name(),
            'budget': metrics['initial_balance'],
            'equity': metrics['equity'],
            'pnl': metrics['total_pnl'],
            'pnl_percent': metrics['pnl_percent'],
            'trades': metrics['total_trades'],
            'win_rate': metrics['win_rate']
        })
    
    # Sort by PnL%
    results.sort(key=lambda x: x['pnl_percent'], reverse=True)
    
    # Export JSON
    json_path = snapshots_dir / f"snapshot_{timestamp}.json"
    with open(json_path, 'w') as f:
        json.dump({
            'timestamp': timestamp,
            'elapsed_minutes': elapsed_minutes,
            'bots': results
        }, f, indent=2)
    
    # Export CSV
    csv_path = snapshots_dir / f"snapshot_{timestamp}.csv"
    if results:
        with open(csv_path, 'w', newline='') as f:
            fieldnames = ['rank', 'name', 'budget', 'equity', 'pnl', 'pnl_percent', 'trades', 'win_rate']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for i, r in enumerate(results, 1):
                r['rank'] = i
                writer.writerow(r)
    
    logger.info(f"Snapshot exported at {elapsed_minutes}m: {json_path.name}")
    return results


def main():
    # ========================================
    # CONFIGURACIÓN DEL TORNEO
    # ========================================
    TOURNAMENT_DURATION_HOURS = 0.083  # Duración en horas (TEST: 30 minutos)
    SNAPSHOT_INTERVAL_MINUTES = 1     # Guardar snapshot cada X minutos
    # ========================================
    
    TOURNAMENT_DURATION_SECONDS = TOURNAMENT_DURATION_HOURS * 3600
    
    # Create results directory
    results_dir = Path("results")
    snapshots_dir = results_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    
    # ANALIZADOR DE MERCADOS COMPARTIDO (singleton) + timeout
    provider = PolymarketProvider(timeout_seconds=TOURNAMENT_DURATION_SECONDS)
    
    # CONFIGURACIÓN DE BOTS
    bots_config = [
        {"name": "Bot_Conservative", "budget": 1000.0, "threshold": 0.65},
        {"name": "Bot_Balanced",     "budget": 5000.0, "threshold": 0.55},
        {"name": "Bot_Aggressive",   "budget": 2000.0, "threshold": 0.50},
        {"name": "Bot_YOLO",         "budget": 500.0,  "threshold": 0.45},
    ]
    
    bots = []
    
    # CREAR CADA BOT
    for config in bots_config:
        # Motor de ejecución con presupuesto inicial
        engine = PaperTradingEngine(
            strategy_name=config["name"],
            initial_balance=config["budget"],
        )
        
        # Estrategia del bot
        strategy = SimpleMomentumStrategy(
            name=config["name"],
            market_data_provider=provider,
            execution_engine=engine,
            threshold=config["threshold"],
        )
        
        # Suscribir al analizador de mercados
        provider.subscribe(strategy.on_market_data)
        
        bots.append((strategy, engine))
        logger.info(f"[OK] {config['name']}: ${config['budget']:,.0f} initial | threshold={config['threshold']}")
    
    # INICIAR ANALIZADOR DE MERCADOS (alimenta a todos los bots)
    provider.start()
    
    print("\n" + "="*100)
    print(f"TOURNAMENT RUNNING - {len(bots)} BOTS ACTIVE")
    print("="*100)
    print("Market Analyzer: Fetching Up/Down markets (BTC/ETH/SOL/XRP)")
    print("Bots update independently based on same market data")
    print(f"Duration: {TOURNAMENT_DURATION_HOURS} hours ({TOURNAMENT_DURATION_SECONDS/60:.0f} minutes)")
    print(f"Snapshots: Every {SNAPSHOT_INTERVAL_MINUTES} minutes -> results/snapshots/")
    print("="*100 + "\n")
    
    # Track tournament time
    start_time = time.time()
    end_time = start_time + TOURNAMENT_DURATION_SECONDS
    last_snapshot_time = start_time
    snapshot_interval_seconds = SNAPSHOT_INTERVAL_MINUTES * 60
    
    try:
        while True:
            # CRITICAL: Check timeout BEFORE sleeping
            current_time = time.time()
            if current_time >= end_time:
                logger.warning(f"Tournament duration reached: {TOURNAMENT_DURATION_HOURS}h")
                break
            
            # Also check if scheduler auto-stopped (safety check)
            if not provider.scheduler.is_running():
                logger.warning("Scheduler auto-stopped due to timeout")
                break
            
            # Sleep for status update interval (or remaining time)
            remaining = end_time - current_time
            sleep_duration = min(30, remaining)
            time.sleep(sleep_duration)
            
            # Calculate metrics
            elapsed = time.time() - start_time
            remaining = max(0, end_time - time.time())
            elapsed_mins = int(elapsed / 60)
            remaining_mins = int(remaining / 60)
            progress = (elapsed / TOURNAMENT_DURATION_SECONDS) * 100
            
            # Check if snapshot needed
            if (time.time() - last_snapshot_time) >= snapshot_interval_seconds:
                export_snapshot(bots, snapshots_dir, elapsed_mins)
                last_snapshot_time = time.time()
            
            # STATUS DE TODOS LOS BOTS
            print("\n" + "="*100)
            print(f"TOURNAMENT STATUS - {time.strftime('%H:%M:%S')} | Elapsed: {elapsed_mins}m | Remaining: {remaining_mins}m | Progress: {progress:.1f}%")
            print("="*100)
            
            for strategy, engine in bots:
                metrics = engine.get_metrics()
                pnl_sign = "+" if metrics['total_pnl'] >= 0 else "-"
                
                print(
                    f"[{pnl_sign}] {strategy.get_name():<20} | "
                    f"Budget: ${metrics['initial_balance']:>8,.0f} | "
                    f"Equity: ${metrics['equity']:>8,.2f} | "
                    f"PnL: ${metrics['total_pnl']:>7.2f} ({metrics['pnl_percent']:>6.2f}%) | "
                    f"Trades: {metrics['total_trades']:>3}"
                )
            
            print("="*100)
        
        # Tournament completed naturally
        print(f"\n\nTournament duration reached! ({TOURNAMENT_DURATION_HOURS} hours completed)")
        
    except KeyboardInterrupt:
        elapsed_mins = int((time.time() - start_time) / 60)
        print(f"\n\nTournament stopped manually after {elapsed_mins} minutes")
    
    finally:
        # Force stop provider (in case scheduler timeout didn't work)
        logger.info("Stopping provider...")
        provider.stop()
        
        # Export final snapshot
        elapsed_mins = int((time.time() - start_time) / 60)
        logger.info("Exporting final snapshot...")
        export_snapshot(bots, snapshots_dir, elapsed_mins)
        
        # RESULTADOS FINALES
        print("\n" + "="*100)
        print("FINAL RESULTS")
        print("="*100)
        
        results = []
        for strategy, engine in bots:
            metrics = engine.get_metrics()
            results.append({
                'name': strategy.get_name(),
                'pnl_percent': metrics['pnl_percent'],
                'pnl': metrics['total_pnl'],
                'equity': metrics['equity'],
                'trades': metrics['total_trades']
            })
        
        # Ordenar por PnL%
        results.sort(key=lambda x: x['pnl_percent'], reverse=True)
        
        for i, r in enumerate(results, 1):
            medal = ["1st", "2nd", "3rd"][i-1] if i <= 3 else f"{i}th"
            print(
                f"{medal:>4} {r['name']:<20} | "
                f"PnL: {r['pnl_percent']:>7.2f}% (${r['pnl']:>8.2f}) | "
                f"Equity: ${r['equity']:>10.2f} | "
                f"Trades: {r['trades']}"
            )
        
        print("="*100)
        print("Tournament complete!\n")


if __name__ == "__main__":
    main()
