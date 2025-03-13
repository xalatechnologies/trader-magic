from src.config import config
from src.utils import get_logger

# Import classes
from .taapi_client import TaapiClient
from .polygon_client import PolygonClient
from .news_client import AlpacaNewsClient as NewsClient
from .crypto_news_client import CryptoNewsClient

# Create instances
taapi_client = TaapiClient()
polygon_client = PolygonClient()
news_client = NewsClient()
crypto_news_client = CryptoNewsClient()

# Import the service (which now can import the instances from this file)
from .service import data_retrieval_service

__all__ = ["taapi_client", "data_retrieval_service", "news_client", "crypto_news_client", "polygon_client"]