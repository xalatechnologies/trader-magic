from src.config import config

# Use the real client
from .ollama_client import ollama_client
from .service import ai_decision_service

__all__ = ["ollama_client", "ai_decision_service"]