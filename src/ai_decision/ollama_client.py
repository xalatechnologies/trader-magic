import json
import httpx
import time
import threading
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.config import config
from src.utils import get_logger
from src.utils.redis_client import redis_client

logger = get_logger("ollama_client")

class OllamaClient:
    def __init__(self):
        self.host = config.ollama.host
        self.model = config.ollama.model
        self.api_url = f"{self.host}/api/generate"
        self.model_ready = False
        
        # Set initial status in Redis
        self._update_model_status("initializing", "Connecting to Ollama server...")
        
        # Start a background thread to check connection and model status
        threading.Thread(target=self._monitor_model_status, daemon=True).start()
    
    def _update_model_status(self, status: str, message: str):
        """Update the Ollama model status in Redis"""
        status_data = {
            "status": status,  # 'initializing', 'downloading', 'ready', 'error'
            "message": message,
            "timestamp": time.time(),
            "model": self.model
        }
        redis_client.set_json("ollama:status", status_data)
        logger.info(f"Ollama status: {status} - {message}")
    
    def _monitor_model_status(self):
        """Background thread to monitor Ollama server and model status"""
        retry_count = 0
        max_retries = 30  # Try for 5 minutes (10 second intervals)
        
        while retry_count < max_retries:
            try:
                # First check if server is available
                response = httpx.get(f"{self.host}/api/tags", timeout=5.0)
                response.raise_for_status()
                
                # Check if our model is available
                available_models = [model["name"] for model in response.json().get("models", [])]
                
                if not available_models:
                    self._update_model_status("downloading", "Waiting for Ollama models to load...")
                elif self.model not in available_models:
                    self._update_model_status("downloading", f"Model {self.model} is downloading...")
                    # Try to initiate pull if not already in progress
                    try:
                        self._pull_model(background=True)
                    except:
                        pass  # Ignore errors, might already be pulling
                else:
                    # Model is ready
                    self._update_model_status("ready", f"Model {self.model} is ready")
                    self.model_ready = True
                    return
                
            except Exception as e:
                self._update_model_status("error", f"Waiting for Ollama server to be available...")
                logger.warning(f"Ollama server not ready: {e}")
            
            # Wait before checking again
            time.sleep(10)
            retry_count += 1
        
        # If we got here, we exceeded retry attempts
        self._update_model_status("error", "Failed to connect to Ollama after multiple attempts")
        logger.error("Failed to establish connection with Ollama after maximum retry attempts")
    
    def _test_connection(self):
        """Test connection to Ollama server and pull model if needed"""
        try:
            # First check connection
            response = httpx.get(f"{self.host}/api/tags")
            response.raise_for_status()
            available_models = [model["name"] for model in response.json().get("models", [])]
            
            if not available_models:
                logger.warning("No models found on Ollama server, pulling required model")
                self._update_model_status("downloading", "No models found, pulling required model...")
                self._pull_model()
            elif self.model not in available_models:
                logger.warning(f"Selected model '{self.model}' not found. Pulling model...")
                self._update_model_status("downloading", f"Model {self.model} not found, downloading...")
                self._pull_model()
            else:
                logger.info(f"Model {self.model} is already available")
                self._update_model_status("ready", f"Model {self.model} is ready")
                self.model_ready = True
                
            logger.info(f"Connected to Ollama server at {self.host}")
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to connect to Ollama server: {e}")
            self._update_model_status("error", f"Failed to connect to Ollama server: {str(e)}")
            raise ConnectionError(f"Failed to connect to Ollama server at {self.host}")
            
    def _pull_model(self, background=False):
        """Pull the required model from Ollama server"""
        try:
            logger.info(f"Pulling model {self.model}...")
            
            # Use the Ollama API to pull the model
            pull_url = f"{self.host}/api/pull"
            payload = {"name": self.model}
            
            # Send the request (this will take time for large models)
            timeout = None if background else 600.0  # No timeout for background pull
            response = httpx.post(pull_url, json=payload, timeout=timeout)
            response.raise_for_status()
            
            logger.info(f"Successfully pulled model {self.model}")
            if not background:
                self._update_model_status("ready", f"Model {self.model} is ready")
                self.model_ready = True
            
        except httpx.HTTPError as e:
            logger.error(f"Failed to pull model {self.model}: {e}")
            self._update_model_status("error", f"Failed to pull model: {str(e)}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, ConnectionError)),
        reraise=True
    )
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generate text using Ollama
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system instructions
            
        Returns:
            Generated text response
        """
        if not self.model_ready:
            status_data = redis_client.get_json("ollama:status") or {}
            status = status_data.get("status", "unknown")
            message = status_data.get("message", "Model not ready")
            logger.warning(f"Attempted to generate text while model not ready. Status: {status}, Message: {message}")
            return f"Model not ready: {message}"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for more deterministic responses
                "num_predict": 500   # Limit response length
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract response text
                if "response" in result:
                    return result["response"]
                else:
                    logger.error(f"Unexpected response format from Ollama: {result}")
                    return ""
                
        except httpx.HTTPError as e:
            logger.error(f"Error calling Ollama API: {e}")
            self._update_model_status("error", f"Error calling Ollama API: {str(e)}")
            raise

ollama_client = OllamaClient()