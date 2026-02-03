"""Tournament orchestration and results aggregation"""

import logging
import os
import json
import csv
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from polymarket_bot.core.strategy import Strategy
from polymarket_bot.execution.paper_trading import PaperTradingEngine

logger = logging.getLogger(__name__)


class Tournament:
    """Tournament orchestration for multiple strategies"""
    
    def __init__(self, strategies: List[tuple[Strategy, PaperTradingEngine]], results_dir: str = "results"):
        """
        Args:
            strategies: List of (Strategy, PaperTradingEngine) tuples
            results_dir: Directory to save results
        """
        self.strategies = strategies
        self.results_dir = results_dir
        self.start_time = None
        
        # Create results directory
        Path(results_dir).mkdir(parents=True, exist_ok=True)
    
    def start(self):
        """Start tournament tracking"""
        self.start_time = datetime.now()
        logger.info(f"Tournament started with {len(self.strategies)} strategies")
    
    def export_results(self):
        """Export tournament results to CSV and JSON"""
        if not self.start_time:
            logger.warning("Tournament not started, cannot export results")
            return
        
        duration_hours = (datetime.now() - self.start_time).total_seconds() / 3600
        
        logger.info("Exporting tournament results...")
        
        # Collect metrics from all strategies
        leaderboard_data = []
        
        for strategy, engine in self.strategies:
            metrics = engine.get_metrics()
            trades = engine.get_trades()
            positions = engine.get_positions()
            
            # Calculate additional metrics
            total_pnl = metrics["total_pnl"]
            pnl_percent = metrics["pnl_percent"]
            pnl_per_hour = total_pnl / duration_hours if duration_hours > 0 else 0
            
            # Calculate max drawdown (simplified)
            max_drawdown = 0.0  # Would need equity curve for accurate calculation
            
            # Calculate average hold time
            avg_hold_time = 0.0
            if trades:
                hold_times = []
                for trade in trades:
                    if trade.filled_at and trade.created_at:
                        hold_time = (trade.filled_at - trade.created_at).total_seconds() / 3600
                        hold_times.append(hold_time)
                avg_hold_time = sum(hold_times) / len(hold_times) if hold_times else 0
            
            # Exposure time (simplified)
            exposure_time_pct = (len(positions) / metrics["total_trades"]) * 100 if metrics["total_trades"] > 0 else 0
            
            leaderboard_entry = {
                "strategy_name": strategy.get_name(),
                "net_pnl": round(total_pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
                "pnl_per_hour": round(pnl_per_hour, 2),
                "max_drawdown": round(max_drawdown, 2),
                "win_rate": round(metrics["win_rate"], 2),
                "avg_hold_time_hours": round(avg_hold_time, 2),
                "trade_count": metrics["total_trades"],
                "exposure_time_pct": round(exposure_time_pct, 2),
                "final_equity": round(metrics["equity"], 2),
            }
            
            leaderboard_data.append(leaderboard_entry)
            
            # Export per-bot data
            self._export_bot_data(strategy.get_name(), engine, trades, duration_hours)
        
        # Sort leaderboard by PnL
        leaderboard_data.sort(key=lambda x: x["net_pnl"], reverse=True)
        
        # Export leaderboard
        self._export_leaderboard(leaderboard_data)
        
        logger.info(f"Results exported to {self.results_dir}/")
    
    def _export_leaderboard(self, leaderboard_data: List[Dict]):
        """Export leaderboard CSV"""
        leaderboard_path = os.path.join(self.results_dir, "leaderboard.csv")
        
        if not leaderboard_data:
            logger.warning("No leaderboard data to export")
            return
        
        fieldnames = list(leaderboard_data[0].keys())
        
        with open(leaderboard_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(leaderboard_data)
        
        logger.info(f"Leaderboard exported to {leaderboard_path}")
        
        # Print to console
        print("\n" + "="*80)
        print("TOURNAMENT LEADERBOARD")
        print("="*80)
        for i, entry in enumerate(leaderboard_data, 1):
            print(f"{i}. {entry['strategy_name']:<30} PnL: ${entry['net_pnl']:>8.2f} ({entry['pnl_percent']:>6.2f}%) "
                  f"Trades: {entry['trade_count']:>4} Win%: {entry['win_rate']:>5.1f}%")
        print("="*80 + "\n")
    
    def _export_bot_data(self, bot_name: str, engine: PaperTradingEngine, trades: List, duration_hours: float):
        """Export per-bot results"""
        bot_dir = os.path.join(self.results_dir, "bots", bot_name)
        Path(bot_dir).mkdir(parents=True, exist_ok=True)
        
        # Export trades CSV
        trades_path = os.path.join(bot_dir, "trades.csv")
        if trades:
            with open(trades_path, "w", newline="") as f:
                fieldnames = ["order_id", "market_id", "side", "size", "price", "status", "created_at", "filled_at"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for trade in trades:
                    writer.writerow({
                        "order_id": trade.order_id,
                        "market_id": trade.market_id,
                        "side": trade.side.value,
                        "size": trade.size,
                        "price": trade.price,
                        "status": trade.status.value,
                        "created_at": trade.created_at.isoformat() if trade.created_at else "",
                        "filled_at": trade.filled_at.isoformat() if trade.filled_at else "",
                    })
        
        # Export equity curve (simplified)
        equity_path = os.path.join(bot_dir, "equity.csv")
        with open(equity_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "equity"])
            # For now, just export final equity
            writer.writerow([datetime.now().isoformat(), engine.get_equity()])
        
        # Export metrics JSON
        metrics_path = os.path.join(bot_dir, "metrics.json")
        metrics = engine.get_metrics()
        metrics["duration_hours"] = duration_hours
        metrics["pnl_per_hour"] = metrics["total_pnl"] / duration_hours if duration_hours > 0 else 0
        
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.debug(f"Exported data for {bot_name}")
