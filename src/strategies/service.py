"""
Strategy Manager Service
This module runs the Strategy Manager as a standalone service.
"""

import os
import time
import signal
import sys
from datetime import datetime

from src.utils import get_logger, redis_client
from src.strategies.strategy_manager import StrategyManager

logger = get_logger("strategy_manager_service")

def run_standalone():
    """Run the strategy manager as a standalone service"""
    logger.info("Starting Strategy Manager Service")
    
    # Create the strategy manager
    manager = StrategyManager()
    
    # Register signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        manager.stop_polling()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Determine the polling interval from config or environment
    from src.config import config
    poll_interval = int(os.getenv("POLL_INTERVAL", config.trading.poll_interval))
    
    # Register with Redis that we're starting up
    redis_client.client.set("strategy_manager:status", "starting")
    redis_client.client.set("strategy_manager:startup_time", datetime.now().isoformat())
    
    # Start polling for data
    try:
        # Register with Redis that we're running
        redis_client.client.set("strategy_manager:status", "running")
        
        # Auto-start based on config
        auto_start = config.features.auto_start_strategies
        if auto_start:
            logger.info(f"Auto-starting strategy manager with poll interval of {poll_interval} seconds")
            manager.start_polling(interval=poll_interval)
        else:
            logger.info("Strategy manager initialized but not auto-started (waiting for frontend command)")
            # Even if not auto-started, we should register our presence
            redis_client.client.set("strategy_manager:running", "false")
        
        # Keep the main thread alive
        while True:
            # Store the latest heartbeat
            redis_client.client.set("strategy_manager:heartbeat", datetime.now().isoformat())
            time.sleep(5)
            
    except Exception as e:
        logger.error(f"Error in strategy manager service: {e}")
        # Register with Redis that we've crashed
        redis_client.client.set("strategy_manager:status", f"error: {str(e)}")
        manager.stop_polling()
        sys.exit(1)

if __name__ == "__main__":
    run_standalone() 