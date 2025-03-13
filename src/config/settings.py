import os
from typing import List, Dict
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class TaapiConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: os.getenv("TAAPI_API_KEY", ""))
    rsi_period: int = Field(default_factory=lambda: int(os.getenv("RSI_PERIOD", "14")))
    price_history_interval: str = Field(default_factory=lambda: os.getenv("PRICE_HISTORY_INTERVAL", "5m"))
    price_history_limit: int = Field(default_factory=lambda: int(os.getenv("PRICE_HISTORY_LIMIT", "20")))
    fetch_for_stocks: bool = Field(default_factory=lambda: os.getenv("TAAPI_FETCH_FOR_STOCKS", "true").lower() == "true")

class AlpacaConfig(BaseModel):
    # API credentials
    api_key: str = Field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    api_secret: str = Field(default_factory=lambda: os.getenv("ALPACA_API_SECRET", ""))
    base_url: str = Field(default_factory=lambda: os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets"))

class PolygonConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: os.getenv("POLYGON_API_KEY", ""))

class OpenAIConfig(BaseModel):
    api_key: str = Field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    model: str = Field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))

class OllamaConfig(BaseModel):
    model: str = Field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3"))
    host: str = Field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://ollama:11434"))

class RedisConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("REDIS_HOST", "redis"))
    port: int = Field(default_factory=lambda: int(os.getenv("REDIS_PORT", "6379")))
    db: int = Field(default_factory=lambda: int(os.getenv("REDIS_DB", "0")))

class TradingConfig(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: os.getenv("SYMBOLS", "BTC/USD").split(","))
    trade_percentage: float = Field(default_factory=lambda: float(os.getenv("TRADE_PERCENTAGE", "2.0")))
    trade_fixed_amount: float = Field(default_factory=lambda: float(os.getenv("TRADE_FIXED_AMOUNT", "10.0")))
    use_fixed_amount: bool = Field(default_factory=lambda: os.getenv("TRADE_USE_FIXED", "false").lower() == "true")
    # ALWAYS default to False for safety
    trading_enabled: bool = Field(default=False)
    poll_interval: int = Field(default_factory=lambda: int(os.getenv("POLL_INTERVAL", "120")))

    # Use validator instead of field_validator for pydantic v1
    @validator("trade_percentage")
    def validate_trade_percentage(cls, value):
        if value <= 0 or value > 100:
            raise ValueError("Trade percentage must be between 0 and 100")
        return value
        
    @validator("trade_fixed_amount")
    def validate_trade_fixed_amount(cls, value):
        if value < 1.0:
            raise ValueError("Fixed trade amount must be at least $1.00")
        return value

class FeatureConfig(BaseModel):
    news_strategy: bool = Field(default_factory=lambda: os.getenv("USE_NEWS_STRATEGY", "false").lower() == "true")
    news_buy_threshold: int = Field(default_factory=lambda: int(os.getenv("NEWS_BUY_THRESHOLD", "70")))
    news_sell_threshold: int = Field(default_factory=lambda: int(os.getenv("NEWS_SELL_THRESHOLD", "30")))
    auto_start_strategies: bool = Field(default_factory=lambda: os.getenv("AUTO_START_STRATEGIES", "false").lower() == "true")

class AppConfig(BaseModel):
    taapi: TaapiConfig = TaapiConfig()
    alpaca: AlpacaConfig = AlpacaConfig()
    polygon: PolygonConfig = PolygonConfig()
    openai: OpenAIConfig = OpenAIConfig()
    ollama: OllamaConfig = OllamaConfig()
    redis: RedisConfig = RedisConfig()
    trading: TradingConfig = TradingConfig()
    features: FeatureConfig = FeatureConfig()

config = AppConfig()