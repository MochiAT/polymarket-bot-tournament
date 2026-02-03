"""Execution abstractions"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List
from abc import ABC,abstractmethod
from enum import Enum


class OrderSide(str, Enum):
    """Order side"""
    YES = "YES"
    NO = "NO"


class OrderStatus(str, Enum):
    """Order status"""
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


@dataclass
class Order:
    """Standardized order representation"""
    order_id: str
    market_id: str
    side: OrderSide
    size: float  # Number of shares
    price: float  # Price per share
    status: OrderStatus = OrderStatus.PENDING
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None


@dataclass
class Position:
    """Position tracking"""
    market_id: str
    side: OrderSide
    size: float  # Number of shares
    entry_price: float  # Average entry price
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    opened_at: Optional[datetime] = None


class ExecutionEngine(ABC):
    """Abstract base class for execution"""
    
    @abstractmethod
    def place_order(self, market_id: str, side: OrderSide, size: float, price: float) -> Order:
        """Place an order"""
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Position]:
        """Get all open positions"""
        pass
    
    @abstractmethod
    def get_position(self, market_id: str) -> Optional[Position]:
        """Get position for a specific market"""
        pass
    
    @abstractmethod
    def close_position(self, market_id: str) -> bool:
        """Close a position"""
        pass
    
    @abstractmethod
    def get_balance(self) -> float:
        """Get current balance"""
        pass
