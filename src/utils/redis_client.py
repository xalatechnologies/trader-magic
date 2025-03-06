import json
import redis
from typing import Any, Dict, Optional
from datetime import datetime
from src.config import config
from src.utils.logger import get_logger

logger = get_logger("redis_client")

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class RedisClient:
    def __init__(self):
        self.client = redis.Redis(
            host=config.redis.host,
            port=config.redis.port,
            db=config.redis.db,
            decode_responses=True
        )
        try:
            self.client.ping()
            logger.info("Connected to Redis")
            
            # Enable keyspace notifications for all events
            try:
                self.client.config_set('notify-keyspace-events', 'KEA')
                logger.info("Redis keyspace notifications enabled")
            except Exception as e:
                logger.warning(f"Failed to enable Redis keyspace notifications: {e}")
                
        except redis.ConnectionError:
            logger.error("Failed to connect to Redis")
            raise
    
    def scan_iter(self, match=None):
        """Return an iterator of keys matching the given pattern"""
        try:
            for key in self.client.scan_iter(match=match):
                yield key
        except Exception as e:
            logger.error(f"Error scanning Redis keys: {e}")
            return []
            
    def get(self, key: str) -> Optional[str]:
        """
        Get a string value from Redis
        """
        try:
            return self.client.get(key)
        except Exception as e:
            logger.error(f"Error getting key {key} from Redis: {e}")
            return None
            
    def set(self, key: str, value: str, ttl: Optional[int] = None) -> bool:
        """
        Set a string value in Redis
        """
        try:
            result = self.client.set(key, value)
            if ttl:
                self.client.expire(key, ttl)
            return result
        except Exception as e:
            logger.error(f"Error setting key {key} in Redis: {e}")
            return False

    def set_json(self, key: str, data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Store JSON data in Redis
        """
        try:
            # Use the custom encoder to handle datetime objects
            serialized = json.dumps(data, cls=DateTimeEncoder)
            result = self.client.set(key, serialized)
            if ttl:
                self.client.expire(key, ttl)
            return result
        except Exception as e:
            logger.error(f"Error storing data in Redis: {e}")
            return False

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve JSON data from Redis
        """
        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Error retrieving data from Redis: {e}")
            return None

    def delete(self, key: str) -> bool:
        """
        Delete a key from Redis
        """
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Error deleting key from Redis: {e}")
            return False
            
    def get_pubsub(self):
        """
        Get a Redis PubSub object for subscribing to channels
        """
        try:
            return self.client.pubsub()
        except Exception as e:
            logger.error(f"Error creating Redis PubSub object: {e}")
            raise
            
    def publish(self, channel: str, message: str) -> int:
        """
        Publish a message to a Redis channel
        """
        try:
            return self.client.publish(channel, message)
        except Exception as e:
            logger.error(f"Error publishing to Redis channel {channel}: {e}")
            return 0

# Singleton instance
redis_client = RedisClient()