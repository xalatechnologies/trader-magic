from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

class TradingDecision(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    
class MarketStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    AFTER_HOURS = "after_hours"

class RSIData(BaseModel):
    symbol: str
    value: float
    timestamp: datetime = Field(default_factory=datetime.now)

class PriceCandle(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime
    market_status: Optional[MarketStatus] = MarketStatus.OPEN

class PriceHistory(BaseModel):
    symbol: str
    interval: str
    candles: List[PriceCandle]
    timestamp: datetime = Field(default_factory=datetime.now)

class TradeSignal(BaseModel):
    symbol: str
    decision: TradingDecision
    confidence: Optional[float] = None
    rsi_value: float
    timestamp: datetime = Field(default_factory=datetime.now)

class TradeResult(BaseModel):
    symbol: str
    decision: TradingDecision
    order_id: str  # Non-optional to enforce consistent order IDs
    quantity: Optional[float] = None
    price: Optional[float] = None
    status: str = "unknown"  # Default value to prevent validation errors
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        # Add extra validation to ensure order_id is always a string
        validate_assignment = True
        # Allow for extra fields that might be provided
        extra = "ignore"