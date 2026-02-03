"""Demo: 4 bots con diferentes estrategias y presupuestos"""

import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from polymarket_bot.providers.polymarket_provider import PolymarketProvider
from polymarket_bot.execution.paper_trading import PaperTradingEngine
from examples.simple_strategy import SimpleMomentumStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    # ========================================
    # CONFIGURACIÓN DEL TORNEO
    # ========================================
    TOURNAMENT_DURATION_HOURS = 4  # 🕐 Duración en horas (cambia aquí)
    # ========================================
    
    TOURNAMENT_DURATION_SECONDS = TOURNAMENT_DURATION_HOURS * 3600
    
    # ANALIZADOR DE MERCADOS COMPARTIDO (singleton)
    provider = PolymarketProvider()
    
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
        logger.info(f"✓ {config['name']}\u003e: ${config['budget']:,.0f} initial | threshold={config['threshold']}")
    
    # INICIAR ANALIZADOR DE MERCADOS (alimenta a todos los bots)
    provider.start()
    
    print("\n" + "="*100)
    print(f"🚀 TOURNAMENT RUNNING - {len(bots)} BOTS ACTIVE")
    print("="*100)
    print("📊 Shared Market Analyzer: Fetching Up/Down markets (BTC/ETH/SOL/XRP)")
    print("⚡ Bots update independently based on same market data")
    print(f"⏱️  Duration: {TOURNAMENT_DURATION_HOURS} hours ({TOURNAMENT_DURATION_SECONDS/60:.0f} minutes)")
    print("="*100 + "\n")
    
    # Track tournament time
    start_time = time.time()
    end_time = start_time + TOURNAMENT_DURATION_SECONDS
    
    try:
        while time.time() < end_time:
            time.sleep(30)
            
            # Calculate remaining time
            elapsed = time.time() - start_time
            remaining = end_time - time.time()
            elapsed_mins = int(elapsed / 60)
            remaining_mins = int(remaining / 60)
            progress = (elapsed / TOURNAMENT_DURATION_SECONDS) * 100
            
            # STATUS DE TODOS LOS BOTS
            print("\n" + "="*100)
            print(f"📈 TOURNAMENT STATUS - {time.strftime('%H:%M:%S')} | Elapsed: {elapsed_mins}m | Remaining: {remaining_mins}m | Progress: {progress:.1f}%")
            print("="*100)
            
            for strategy, engine in bots:
                metrics = engine.get_metrics()
                pnl_emoji = "🟢" if metrics['total_pnl'] >= 0 else "🔴"
                
                print(
                    f"{pnl_emoji} {strategy.get_name():<20} | "
                    f"Budget: ${metrics['initial_balance']:>8,.0f} | "
                    f"Equity: ${metrics['equity']:>8,.2f} | "
                    f"PnL: ${metrics['total_pnl']:>7.2f} ({metrics['pnl_percent']:>6.2f}%) | "
                    f"Trades: {metrics['total_trades']:>3}"
                )
            
            print("="*100)
        
        # Tournament completed naturally
        print(f"\n\n⏰ Tournament duration reached! ({TOURNAMENT_DURATION_HOURS} hours completed)")
        
    except KeyboardInterrupt:
        elapsed_mins = int((time.time() - start_time) / 60)
        print(f"\n\n🛑 Tournament stopped manually after {elapsed_mins} minutes")
    
    finally:
        provider.stop()
        
        # RESULTADOS FINALES
        print("\n" + "="*100)
        print("🏆 FINAL RESULTS")
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
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
            print(
                f"{medal} {r['name']:<20} | "
                f"PnL: {r['pnl_percent']:>7.2f}% (${r['pnl']:>8.2f}) | "
                f"Equity: ${r['equity']:>10.2f} | "
                f"Trades: {r['trades']}"
            )
        
        print("="*100)
        print("✅ Tournament complete!\n")


if __name__ == "__main__":
    main()
