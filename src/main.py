import os
import time
import signal
import threading
import sys
import uuid
from datetime import datetime

from src.config import config
from src.utils import get_logger
from src.data_retrieval import data_retrieval_service
from src.ai_decision import ai_decision_service

# Import trade execution service components directly to avoid circular imports
from src.trade_execution.service import TradeExecutionService
trade_execution_service = TradeExecutionService()

logger = get_logger("main")

# Global flag to control the main loop
running = True

def signal_handler(sig, frame):
    """
    Handle termination signals to gracefully shutdown the application
    """
    global running
    logger.info("Received termination signal, shutting down...")
    running = False

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def create_logs_directory():
    """
    Create logs directory if it doesn't exist
    """
    if not os.path.exists("logs"):
        os.makedirs("logs")
        logger.info("Created logs directory")

def setup_services():
    """
    Initialize and start all services
    """
    logger.info("Starting services...")
    
    # IMPORTANT: ALWAYS initialize trading to disabled on startup for safety
    from src.utils import force_trading_disabled
    success = force_trading_disabled()
    logger.info("Trading initialized to DISABLED for safety")
    
    # Double-check the value was set correctly
    from src.utils import redis_client
    trading_enabled = redis_client.client.get("trading_enabled")
    logger.info(f"VERIFY: 'trading_enabled' is currently set to '{trading_enabled}' in Redis")
    
    # Start the data retrieval service
    data_retrieval_service.start()
    logger.info("Data retrieval service started")
    
    # Initialize the strategy manager
    try:
        from src.strategies.strategy_manager import strategy_manager
        logger.info("Strategy manager initialized")
        
        # Log available strategies
        strategies = strategy_manager.get_active_strategies()
        logger.info(f"Available strategies: {len(strategies)}")
        for strategy in strategies:
            logger.info(f"Strategy: {strategy['name']} ({strategy['class']}) - Enabled: {strategy['enabled']}")
            
        # Start the strategy manager polling
        if config.features.auto_start_strategies:
            strategy_manager.start_polling(interval=config.trading.poll_interval)
            logger.info(f"Strategy manager polling started with interval: {config.trading.poll_interval}s")
        else:
            logger.info("Strategy manager auto-start disabled, will start via API")
    except ImportError as e:
        logger.warning(f"Strategy manager not available: {e}")
    except Exception as e:
        logger.error(f"Error initializing strategy manager: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Log key components for debugging
    import json
    logger.info("Active trading symbols: %s", config.trading.symbols)
    logger.info("Trade percentage: %s", config.trading.trade_percentage)
    logger.info("Poll interval: %s", config.trading.poll_interval)
    
    # Log news strategy configuration
    logger.info("News strategy enabled: %s", config.features.news_strategy)
    if config.features.news_strategy:
        logger.info("News strategy buy threshold: %s", config.features.news_buy_threshold)
        logger.info("News strategy sell threshold: %s", config.features.news_sell_threshold)
        logger.info("OpenAI model: %s", config.openai.model)
    
    # Check if signals are already in Redis
    for symbol in config.trading.symbols:
        signal_data = redis_client.get_json(f"signal:{symbol}")
        if signal_data:
            logger.info(f"Found existing signal for {symbol}: {json.dumps(signal_data)}")
        else:
            logger.info(f"No existing signal for {symbol}")
            
        result_data = redis_client.get_json(f"trade_result:{symbol}")
        if result_data:
            logger.info(f"Found existing trade result for {symbol}: {json.dumps(result_data)}")
        else:
            logger.info(f"No existing trade result for {symbol}")

def main_loop():
    """
    Main application loop that coordinates the three components
    """
    global running
    
    logger.info(f"Starting main loop with poll interval: {config.trading.poll_interval} seconds")
    logger.info(f"Trading symbols: {config.trading.symbols}")
    
    # Check if ALPACA_DEBUG_MODE is enabled
    import os
    debug_mode = os.getenv("ALPACA_DEBUG_MODE") == "true"
    logger.info(f"ALPACA_DEBUG_MODE: {debug_mode}")
    
    # Wait initial time for the data retrieval service to get first data
    initial_wait = min(30, config.trading.poll_interval)
    logger.info(f"Waiting {initial_wait} seconds for initial data collection...")
    time.sleep(initial_wait)
    
    # Import for direct redis access
    from src.utils import redis_client
    import json
    
    # Initialize execution count for tracking
    execution_count = 0
    
    # Try to import the strategy manager
    try:
        from src.strategies.strategy_manager import strategy_manager
        has_strategy_manager = True
        logger.info("Strategy manager available for trading decisions")
    except ImportError:
        has_strategy_manager = False
        logger.warning("Strategy manager not available, using legacy decision process")
    
    while running:
        try:
            # Log iteration start
            execution_count += 1
            logger.info(f"Main loop iteration #{execution_count} starting")
            
            # Get all signals at once to avoid decision delays
            all_signals = {}
            
            # First check for signals from the strategy manager
            if has_strategy_manager:
                for symbol in config.trading.symbols:
                    # Check if there's a signal from the strategy manager
                    signal_key = f"signal:{symbol}"
                    signal_data = redis_client.get_json(signal_key)
                    
                    if signal_data:
                        # Convert the signal data to a TradeSignal object
                        from src.utils import TradeSignal, TradeDecision
                        
                        # Check if the signal is recent (within the last 5 minutes)
                        signal_time = datetime.fromisoformat(signal_data.get('timestamp', '')) if 'timestamp' in signal_data else None
                        if signal_time and (datetime.now() - signal_time).total_seconds() < 300:
                            # Create a trade signal from the data
                            signal = TradeSignal(
                                symbol=signal_data.get('symbol'),
                                decision=TradeDecision(signal_data.get('decision')),
                                confidence=signal_data.get('confidence', 0.0),
                                timestamp=signal_time
                            )
                            
                            all_signals[symbol] = signal
                            logger.info(f"Using strategy manager signal for {symbol}: {signal.decision.value}")
            
            # If we don't have signals from the strategy manager, use the legacy approach
            for symbol in config.trading.symbols:
                if symbol not in all_signals:
                    # Get the latest trade signal (already calculated by data_retrieval service)
                    signal = ai_decision_service.get_latest_signal(symbol)
                    if signal:
                        all_signals[symbol] = signal
                        logger.info(f"Retrieved legacy signal for {symbol}: {signal.decision.value}")
                    else:
                        logger.warning(f"No signal found for {symbol}")
                        # Check if RSI data is available
                        rsi_data = data_retrieval_service.get_latest_rsi(symbol)
                        if rsi_data:
                            logger.info(f"RSI data available for {symbol}: {rsi_data.value}, generating signal")
                            # Try to generate a signal
                            signal = ai_decision_service.get_decision(rsi_data)
                            if signal:
                                all_signals[symbol] = signal
                                logger.info(f"Generated new legacy signal for {symbol}: {signal.decision.value}")
            
            # Log how many signals we found
            logger.info(f"Found {len(all_signals)} signals for execution")
            
            # Execute trades for all signals that aren't "hold"
            for symbol, signal in all_signals.items():
                try:
                    if signal.decision.value != "hold":
                        logger.info(f"Executing trade for {symbol} with decision: {signal.decision.value}")
                        
                        # FORCE SUCCESS FOR TESTING 
                        if debug_mode:
                            # Force a successful trade result in debug mode
                            from src.utils import TradeResult
                            import uuid
                            from datetime import datetime
                            
                            mock_price = 45000.0 if "BTC" in symbol else 3000.0
                            mock_quantity = 0.001 if "BTC" in symbol else 0.01
                            
                            # Create a successful trade result
                            result = TradeResult(
                                symbol=symbol,
                                decision=signal.decision,
                                order_id=f"debug-{uuid.uuid4()}",
                                quantity=mock_quantity,
                                price=mock_price,
                                status="executed",
                                error=None,
                                timestamp=datetime.now()
                            )
                            
                            logger.info(f"DEBUG MODE: Created mock trade result for {symbol}")
                        else:
                            # Normal execution
                            result = trade_execution_service.execute_trade(signal)
                        
                        # Handle the result
                        if result:
                            logger.info(f"Trade result for {symbol}: {result.status}")
                            if result.status == "executed":
                                logger.info(f"Order executed for {symbol}: {result.quantity} @ ~${result.price:.2f}")
                                
                                # Debug the result that's being saved in Redis
                                logger.info(f"Trade result object: {result}")
                                
                                # Always save the result to Redis with a long TTL
                                redis_key = f"trade_result:{symbol}"
                                success = redis_client.set_json(redis_key, result.dict(), ttl=86400)  # 24 hour TTL
                                logger.info(f"Saved trade result to Redis key: {redis_key} (success: {success})")
                                
                                # Check if it was saved properly
                                saved_data = redis_client.get_json(redis_key)
                                if saved_data:
                                    logger.info(f"Verified Redis data for {redis_key}: {json.dumps(saved_data)}")
                                else:
                                    logger.error(f"Failed to verify Redis data for {redis_key}!")
                            else:
                                logger.warning(f"Trade not executed. Status: {result.status}, Error: {result.error}")
                        else:
                            logger.error(f"No result returned from trade execution for {symbol}")
                    else:
                        logger.info(f"Decision is to hold for {symbol}, no trade executed")
                except Exception as trade_error:
                    logger.error(f"Error executing trade for {symbol}: {trade_error}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
            
            # Sleep less than the poll interval to check for new signals sooner
            # This ensures we catch new signals shortly after they're generated
            sleep_time = min(60, max(30, config.trading.poll_interval // 2))
            logger.info(f"Main loop iteration #{execution_count} completed. Sleeping for {sleep_time} seconds")
            time.sleep(sleep_time)
            
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            time.sleep(5)  # Brief pause before continuing

def shutdown():
    """
    Perform cleanup and shutdown operations
    """
    logger.info("Shutting down...")
    
    # Stop the data retrieval service
    data_retrieval_service.stop()
    
    # Stop the strategy manager if it's running
    try:
        from src.strategies.strategy_manager import strategy_manager
        strategy_manager.stop_polling()
        logger.info("Strategy manager stopped")
    except ImportError:
        logger.info("Strategy manager not available, skipping shutdown")
    except Exception as e:
        logger.error(f"Error stopping strategy manager: {e}")
    
    logger.info("Shutdown complete")

if __name__ == "__main__":
    # Make sure the logs directory exists
    create_logs_directory()
    
    # Print startup banner
    logger.info("=" * 80)
    logger.info(f"TraderMagic starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Configured to trade: {', '.join(config.trading.symbols)}")
    logger.info(f"Using Ollama model: {config.ollama.model}")
    logger.info(f"Alpaca paper trading: {config.alpaca.paper_trading}")
    logger.info("=" * 80)
    
    try:
        # Set up and start services
        setup_services()
        
        # Run the main loop
        main_loop()
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
    finally:
        # Ensure proper shutdown
        shutdown()