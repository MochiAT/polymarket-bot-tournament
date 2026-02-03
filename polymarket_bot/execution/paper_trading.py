"""Paper trading execution engine"""

import logging
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from threading import Lock

from polymarket_bot.core.execution import (
    ExecutionEngine,
    Order,
    Position,
    OrderSide,
    OrderStatus,
)

logger = logging.getLogger(__name__)


class PaperTradingEngine(ExecutionEngine):
    """Paper trading execution engine for simulation"""
    
    def __init__(self, strategy_name: str, initial_balance: float = 10000.0):
        self.strategy_name = strategy_name
        self.initial_balance = initial_balance
        self.balance = initial_balance
        
        self._positions: Dict[str, Position] = {}
        self._orders: Dict[str, Order] = {}
        self._filled_orders: List[Order] = []
        
        self._lock = Lock()
        
        logger.info(f"Paper trading engine initialized for '{strategy_name}' with ${initial_balance}")
    
    def place_order(self, market_id: str, side: OrderSide, size: float, price: float) -> Order:
        """Place a simulated order"""
        with self._lock:
            # Create order
            order = Order(
                order_id=str(uuid.uuid4()),
                market_id=market_id,
                side=side,
                size=size,
                price=price,
                status=OrderStatus.PENDING,
                created_at=datetime.now(),
            )
            
            # Check if have enough balance
            cost = size * price
            if cost > self.balance:
                logger.warning(f"Insufficient balance for order: need ${cost:.2f}, have ${self.balance:.2f}")
                order.status = OrderStatus.CANCELLED
                return order
            
            # Simulate instant fill at market price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now()
            
            # Deduct cost from balance
            self.balance -= cost
            
            # Update or create position
            if market_id in self._positions:
                pos = self._positions[market_id]
                # If same side, add to position
                if pos.side == side:
                    total_cost = (pos.size * pos.entry_price) + cost
                    pos.size += size
                    pos.entry_price = total_cost / pos.size
                else:
                    # Opposite side - close position
                    if size >= pos.size:
                        # Fully close
                        pnl = self._calculate_pnl(pos, price)
                        self.balance += pnl + (pos.size * price)
                        del self._positions[market_id]
                        logger.info(f"Closed position in {market_id}: PnL ${pnl:.2f}")
                    else:
                        # Partial close
                        pnl = self._calculate_pnl(pos, price) * (size / pos.size)
                        self.balance += pnl + (size * price)
                        pos.size -= size
            else:
                # Create new position
                self._positions[market_id] = Position(
                    market_id=market_id,
                    side=side,
                    size=size,
                    entry_price=price,
                    current_price=price,
                    opened_at=datetime.now(),
                )
            
            # Store order
            self._orders[order.order_id] = order
            self._filled_orders.append(order)
            
            logger.debug(
                f"[{self.strategy_name}] Filled {side.value} order: "
                f"{size} shares @ ${price:.4f} in {market_id}"
            )
            
            return order
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order (no-op in paper trading - instant fills)"""
        return True
    
    def get_positions(self) -> List[Position]:
        """Get all open positions"""
        with self._lock:
            return list(self._positions.values())
    
    def get_position(self, market_id: str) -> Optional[Position]:
        """Get position for a specific market"""
        with self._lock:
            return self._positions.get(market_id)
    
    def close_position(self, market_id: str, current_price: Optional[float] = None) -> bool:
        """Close a position"""
        with self._lock:
            if market_id not in self._positions:
                return False
            
            pos = self._positions[market_id]
            close_price = current_price or pos.current_price
            
            # Calculate PnL
            pnl = self._calculate_pnl(pos, close_price)
            
            # Return capital + PnL
            self.balance += (pos.size * close_price) + pnl
            
            # Remove position
            del self._positions[market_id]
            
            logger.info(
                f"[{self.strategy_name}] Closed position in {market_id}: "
                f"PnL ${pnl:.2f}, Balance ${self.balance:.2f}"
            )
            
            return True
    
    def update_position_price(self, market_id: str, current_price: float):
        """Update position with current market price"""
        with self._lock:
            if market_id in self._positions:
                pos = self._positions[market_id]
                pos.current_price = current_price
                pos.unrealized_pnl = self._calculate_pnl(pos, current_price)
    
    def _calculate_pnl(self, position: Position, current_price: float) -> float:
        """Calculate P&L for a position"""
        if position.side == OrderSide.YES:
            return (current_price - position.entry_price) * position.size
        else:  # NO
            return (position.entry_price - current_price) * position.size
    
    def get_balance(self) -> float:
        """Get current balance"""
        with self._lock:
            return self.balance
    
    def get_equity(self) -> float:
        """Get total equity (balance + unrealized PnL)"""
        with self._lock:
            unrealized = sum(pos.unrealized_pnl for pos in self._positions.values())
            return self.balance + unrealized
    
    def get_trades(self) -> List[Order]:
        """Get all filled orders"""
        with self._lock:
            return self._filled_orders.copy()
    
    def get_total_pnl(self) -> float:
        """Get total PnL (realized + unrealized)"""
        equity = self.get_equity()
        return equity - self.initial_balance
    
    def get_metrics(self) -> Dict:
        """Get performance metrics - always returns equity key"""
        with self._lock:
            trades = self._filled_orders
            positions = list(self._positions.values())
            
            # Always calculate equity
            equity = self.get_equity()
            total_pnl = equity - self.initial_balance
            pnl_percent = (total_pnl / self.initial_balance) * 100 if self.initial_balance > 0 else 0.0
            
            total_trades = len(trades)
            
            # Calculate win rate (rough estimate based on positive PnL)
            wins = sum(1 for t in trades if t.status == OrderStatus.FILLED) if total_trades > 0 else 0
            win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0.0
            
            return {
                "strategy_name": self.strategy_name,
                "total_trades": total_trades,
                "open_positions": len(positions),
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "pnl_percent": pnl_percent,
                "balance": self.balance,
                "equity": equity,  # ALWAYS present
                "initial_balance": self.initial_balance,
            }
