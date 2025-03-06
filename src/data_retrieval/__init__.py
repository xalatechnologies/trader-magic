from src.config import config

# Use the real client only
from .taapi_client import taapi_client
from .service import data_retrieval_service

__all__ = ["taapi_client", "data_retrieval_service"]