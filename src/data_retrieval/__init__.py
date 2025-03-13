from src.config import config

# Use the real client only
from .taapi_client import taapi_client
from .service import data_retrieval_service
from .news_client import news_client
from .crypto_news_client import crypto_news_client

__all__ = ["taapi_client", "data_retrieval_service", "news_client", "crypto_news_client"]