import os
import json
import time
import uuid
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO
import redis
import traceback
import threading
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev_key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Redis connection
redis_host = os.getenv('REDIS_HOST', 'localhost')  # Default to localhost instead of 'redis'
redis_port = int(os.getenv('REDIS_PORT', 6379))
redis_db = int(os.getenv('REDIS_DB', 0))

# Initialize Redis client with error handling
redis_client = None
try:
    redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
    # Test if Redis is working correctly
    print(f"Testing Redis connection to {redis_host}:{redis_port}...")
    test_key = redis_client.get("test_key")
    print(f"Test key from Redis: {test_key}")
    if test_key:
        try:
            test_json = json.loads(test_key)
            print(f"Test JSON parse successful: {test_json}")
        except Exception as e:
            print(f"Test JSON parse failed: {e}")
except Exception as e:
    print(f"Error connecting to Redis at {redis_host}:{redis_port}: {e}")
    print("Using mock Redis functionality for development")
    # Create a simple mock for Redis that supports basic operations
    # This allows the application to run even without Redis
    class MockRedis:
        def __init__(self):
            self.data = {}
            self.channels = {}
            print("Mock Redis initialized")
        
        def get(self, key):
            return self.data.get(key)
        
        def get_json(self, key):
            """Get a JSON value from Redis and deserialize it"""
            data = self.get(key)
            if data:
                try:
                    return json.loads(data)
                except json.JSONDecodeError:
                    print(f"Warning: Failed to parse JSON for key {key}")
            return None
        
        def set(self, key, value):
            self.data[key] = value
            return True
        
        def delete(self, *keys):
            for key in keys:
                if key in self.data:
                    del self.data[key]
            return len(keys)
        
        def keys(self, pattern="*"):
            # Simple pattern matching for keys
            if pattern == "*":
                return list(self.data.keys())
            
            import re
            pattern = pattern.replace("*", ".*")
            regex = re.compile(pattern)
            return [k for k in self.data.keys() if regex.match(k)]
        
        def publish(self, channel, message):
            print(f"MOCK REDIS - Would publish to {channel}: {message}")
            if channel not in self.channels:
                self.channels[channel] = []
            self.channels[channel].append(message)
            return 0
        
        def pubsub(self):
            # Simple mock of the pubsub interface
            class MockPubSub:
                def __init__(self, parent):
                    self.parent = parent
                    self.subscribed_channels = []
                
                def subscribe(self, *channels):
                    for channel in channels:
                        if channel not in self.subscribed_channels:
                            self.subscribed_channels.append(channel)
                    print(f"MOCK REDIS - Subscribed to channels: {self.subscribed_channels}")
                
                def psubscribe(self, *patterns):
                    print(f"MOCK REDIS - Pattern subscribed to: {patterns}")
                
                def listen(self):
                    # This would normally block and yield messages
                    # For mock, just yield a fake message and then block forever
                    yield {"type": "subscribe", "channel": "mock_channel", "data": "mock_subscription_confirmation"}
                    while True:
                        import time
                        time.sleep(10)  # Sleep to avoid CPU spin
            
            return MockPubSub(self)
    
    redis_client = MockRedis()

# Check if the strategy manager is running
strategy_manager_running = False
try:
    running_status = redis_client.get('strategy_manager:running')
    if running_status:
        strategy_manager_running = running_status.lower() == 'true'
        if strategy_manager_running:
            interval = redis_client.get('strategy_manager:interval')
            print(f"Strategy manager appears to be running with interval: {interval}")
        else:
            print("Strategy manager appears to be stopped")
except Exception as e:
    print(f"Error checking strategy manager status: {e}")

# Add Redis manual key lookup
def scan_keys(pattern=None):
    """Get all keys from Redis matching a pattern"""
    pattern = pattern or "*"
    try:
        return redis_client.keys(pattern)
    except Exception as e:
        print(f"Error scanning Redis keys: {e}")
        return []

# Add Redis JSON support functions
def get_json_data(key):
    """Get JSON data from Redis"""
    try:
        # Get the raw data
        raw_data = redis_client.get(key)
        if raw_data:
            try:
                return json.loads(raw_data)
            except json.JSONDecodeError as e:
                print(f"JSON decode error for {key}: {e}")
                return {}
        return None
    except Exception as e:
        print(f"Error getting JSON from Redis: {e}")
        return None

# Add methods to redis_client
redis_client.get_json = get_json_data
redis_client.scan_iter = scan_keys

# Add pubsub method to redis_client
def get_pubsub():
    """Get a pubsub object from Redis"""
    return redis_client.pubsub()

redis_client.get_pubsub = get_pubsub

# Frontend configuration
frontend_host = os.getenv('FRONTEND_HOST', '0.0.0.0')
frontend_port = int(os.getenv('FRONTEND_PORT', 9754))

def get_all_trading_data():
    """Get all trading data from Redis"""
    try:
        symbols = os.getenv('SYMBOLS', 'BTC/USD').split(',')
        data = {}
        
        # Get Ollama model status
        ollama_status = None
        try:
            ollama_status_data = redis_client.get("ollama:status")
            if ollama_status_data:
                try:
                    ollama_status = json.loads(ollama_status_data)
                    print(f"Successfully loaded Ollama status: {ollama_status}")
                except Exception as e:
                    print(f"Error parsing Ollama status: {ollama_status_data}")
                    print(f"Exception: {e}")
                    print(traceback.format_exc())
        except Exception as e:
            print(f"Error getting Ollama status from Redis: {e}")
            print(traceback.format_exc())
        
        # Create a mapping between different format variations of the same symbol
        symbol_variations = {}
        for symbol in symbols:
            # Generate all possible variations
            if '/' in symbol:
                base, quote = symbol.split('/')
                variations = [
                    symbol,                # Original format e.g. BTC/USDT
                    f"{base}/USD",         # USD version e.g. BTC/USD
                    f"{base}{quote}",      # No slash version e.g. BTCUSDT
                    f"{base}USD",          # USD no slash version e.g. BTCUSD
                    base                   # Just the base e.g. BTC
                ]
                for v in variations:
                    symbol_variations[v] = symbol
            else:
                symbol_variations[symbol] = symbol
        
        print(f"Symbol variations map: {symbol_variations}")
        
        # Get all trading symbols data
        for symbol in symbols:
            symbol_data = {}
            
            # RSI data - check for all possible key variations
            for symbol_var in [symbol, symbol.replace('/USDT', '/USD'), symbol.replace('/', '')]:
                rsi_key = f"rsi:{symbol_var}"
                rsi_data = redis_client.get_json(rsi_key)
                if rsi_data:
                    symbol_data['rsi'] = rsi_data
                    print(f"Found RSI data for {symbol} using key {rsi_key}")
                    break  # Exit loop once data is found
                
            # Price data 
            price_key = f"price:{symbol}"
            price_data = redis_client.get_json(price_key)
            if price_data:
                symbol_data['price'] = price_data
                
            # Trade signal - check all possible key variations
            signal_found = False
            for symbol_var in [symbol, symbol.replace('/USDT', '/USD'), symbol.replace('/', '')]:
                signal_key = f"signal:{symbol_var}"
                signal_data = redis_client.get_json(signal_key)
                if signal_data:
                    # Ensure the symbol is in the correct format in the data
                    signal_data['symbol'] = symbol  # Normalize to the configured format
                    symbol_data['signal'] = signal_data
                    print(f"Found signal for {symbol} using key {signal_key}")
                    signal_found = True
                    break  # Exit loop once data is found
            
            # If we still don't have a signal, try a broader search
            if not signal_found:
                all_signal_keys = redis_client.keys("signal:*")
                print(f"All signal keys: {all_signal_keys}")
                for key in all_signal_keys:
                    signal_symbol = key.replace("signal:", "")
                    # Check if this signal is for a variation of our symbol
                    if signal_symbol in symbol_variations and symbol_variations[signal_symbol] == symbol:
                        signal_data = redis_client.get_json(key)
                        if signal_data:
                            # Normalize the symbol
                            signal_data['symbol'] = symbol
                            symbol_data['signal'] = signal_data
                            print(f"Found signal for {symbol} using key {key} via variation lookup")
                            break
                
            # Trading result - check all possible key variations
            for symbol_var in [symbol, symbol.replace('/USDT', '/USD'), symbol.replace('/', '')]:
                result_key = f"trade_result:{symbol_var}"
                result_data = redis_client.get_json(result_key)
                if result_data:
                    # Ensure the symbol is in the correct format in the data
                    result_data['symbol'] = symbol  # Normalize to the configured format
                    symbol_data['result'] = result_data
                    print(f"Found trade result for {symbol} using key {result_key}: {result_data['status']}")
                    break  # Exit loop once data is found
            else:
                print(f"No trade result found for {symbol}")
                
            # Price history data for charts
            for symbol_var in [symbol, symbol.replace('/USDT', '/USD'), symbol.replace('/', '')]:
                history_key = f"price_history:{symbol_var}"
                history_data = redis_client.get_json(history_key)
                if history_data:
                    # Count how many candles we have for debugging
                    candle_count = len(history_data.get('candles', []))
                    symbol_data['price_history'] = history_data
                    print(f"Retrieved {candle_count} candles for {symbol} using key {history_key}")
                    break  # Exit loop once data is found
            
            # Check for invalid Alpaca symbol
            invalid_key = f"alpaca:invalid:{symbol}"
            invalid_flag = redis_client.get(invalid_key)
            if invalid_flag:
                symbol_data['invalid_alpaca_symbol'] = True
                
            # Position data
            position_key = f"position:{symbol}"
            position_data = redis_client.get_json(position_key)
            if position_data:
                symbol_data['position'] = position_data
                    
            data[symbol] = symbol_data
            
        # Account data
        account_key = "account:data"
        account_data = redis_client.get_json(account_key)
        if account_data:
            data['account'] = account_data
            
        # Trading enabled status
        trading_enabled = redis_client.get("trading_enabled")
        data['trading_enabled'] = trading_enabled == "true" if trading_enabled is not None else False
        
        # Recent market orders
        orders_key = "recent_orders"
        orders_data = redis_client.get_json(orders_key)
        if orders_data:
            data['recent_orders'] = orders_data
            
        # Get recent news items
        news_keys = redis_client.keys("news:*")
        if news_keys:
            # Sort by timestamp (most recent first)
            news_items = []
            for key in news_keys:
                news_data = redis_client.get_json(key)
                if news_data:
                    news_items.append(news_data)
            
            # Sort by timestamp (most recent first) if news items have timestamps
            if news_items:
                try:
                    news_items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                except Exception as e:
                    print(f"Error sorting news items: {e}")
                
                # Limit to 10 most recent items
                data['recent_news'] = news_items[:10]
                
        # Add ollama status if available
        if ollama_status:
            data['ollama_status'] = ollama_status
            
        return data
    except Exception as e:
        print(f"Error getting trading data: {e}")
        print(traceback.format_exc())
        return {}

# List to track clients registered for transaction updates
transaction_update_clients = []

@socketio.on('register_for_transaction_updates')
def handle_transaction_registration():
    """Register client for transaction update events"""
    print(f"Client {request.sid} registered for transaction updates")
    if request.sid not in transaction_update_clients:
        transaction_update_clients.append(request.sid)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnect and clean up registrations"""
    if request.sid in transaction_update_clients:
        transaction_update_clients.remove(request.sid)
    print(f"Client {request.sid} disconnected, active transaction listeners: {len(transaction_update_clients)}")

def redis_listener():
    """Listen for Redis keyspace notifications and emit events to clients"""
    try:
        # Create a separate Redis connection for pub/sub
        pubsub = redis_client.get_pubsub()
        
        # Subscribe to keyspace notifications for trade results
        pubsub.psubscribe('__keyspace@0__:trade_result:*')
        
        print("Redis listener started, waiting for trade result updates...")
        
        for message in pubsub.listen():
            try:
                if message['type'] == 'pmessage':
                    # Handle both byte strings and decoded strings
                    channel = message['channel']
                    data = message['data']
                    
                    # Safely decode if needed
                    if isinstance(channel, bytes):
                        key = channel.decode('utf-8').replace('__keyspace@0__:', '')
                    else:
                        key = channel.replace('__keyspace@0__:', '')
                        
                    if isinstance(data, bytes):
                        operation = data.decode('utf-8')
                    else:
                        operation = data
                    
                    # Only process SET operations for trade results
                    if key.startswith('trade_result:') and operation == 'set':
                        symbol = key.replace('trade_result:', '')
                        print(f"Trade result updated for {symbol}, notifying clients")
                        
                        # Get the trade result to check status
                        result_data = redis_client.get(key)
                        if result_data:
                            try:
                                result = json.loads(result_data)
                                # Only notify for executed trades
                                if result['status'] == 'executed':
                                    # Emit to all registered clients
                                    if transaction_update_clients:
                                        socketio.emit('transaction_complete', {
                                            'symbol': symbol,
                                            'timestamp': datetime.now().isoformat(),
                                            'status': result['status'],
                                            'decision': result.get('decision')
                                        })
                                        print(f"Notified {len(transaction_update_clients)} clients about {symbol} transaction")
                                        
                                        # Also emit account update notification
                                        socketio.emit('account_update_needed')
                                        print("Emitted account update notification")
                            except Exception as e:
                                print(f"Error processing trade result for {symbol}: {e}")
            except Exception as e:
                print(f"Error in Redis message handling: {e}")
                print(traceback.format_exc())
    except Exception as e:
        print(f"Error in Redis listener: {e}")
        print(traceback.format_exc())

# Start Redis listener in a separate thread
redis_listener_thread = threading.Thread(target=redis_listener, daemon=True)
redis_listener_thread.start()

@app.route('/')
def index():
    """Render main dashboard page"""
    symbols = os.getenv('SYMBOLS', 'BTC/USD').split(',')
    enforce_pdt = os.getenv('ALPACA_ENFORCE_PDT_RULES', 'true').lower() == 'true'
    paper_trading = os.getenv('ALPACA_PAPER_TRADING', 'true').lower() == 'true'
    debug_mode = os.getenv('ALPACA_DEBUG_MODE', 'false').lower() == 'true'
    
    # Get trading settings
    fixed_amount_mode = os.getenv('TRADE_USE_FIXED', 'false').lower() == 'true'
    trade_percentage = float(os.getenv('TRADE_PERCENTAGE', '2.0'))
    fixed_amount = float(os.getenv('TRADE_FIXED_AMOUNT', '10.0'))
    
    # IMPORTANT SAFETY FEATURE: Force trading to disabled state when page loads
    try:
        # Force set trading to disabled in Redis
        redis_client.set("trading_enabled", "false")
        print("SAFETY: Forced trading disabled when loading dashboard")
        trading_enabled = False
        
        # IMPORTANT: Create disabled trade messages in Redis for all symbols on page load
        for symbol in symbols:
            try:
                # Create standard disabled message
                result = {
                    "symbol": symbol,
                    "decision": "buy",  # Default to buy for displaying messages
                    "order_id": f"page-load-{uuid.uuid4()}",
                    "quantity": None,
                    "price": None,
                    "status": "skipped",
                    "error": "Trading is currently disabled",
                    "timestamp": datetime.now().isoformat()
                }
                # Save to Redis
                redis_key = f"trade_result:{symbol}"
                redis_client.set(redis_key, json.dumps(result))
                print(f"Created disabled message for {symbol} on page load")
            except Exception as e:
                print(f"Error creating disabled message: {e}")
    except Exception as e:
        print(f"Error setting trading disabled: {e}")
        trading_enabled = False
    
    # We no longer create mock trades at startup to avoid confusion
    # Users will only see real trades or trades they explicitly trigger for testing
    
    return render_template(
        'index.html', 
        symbols=symbols,
        enforce_pdt=enforce_pdt,
        paper_trading=paper_trading,
        debug_mode=debug_mode,
        fixed_amount_mode=fixed_amount_mode,
        trade_percentage=trade_percentage,
        fixed_amount=fixed_amount,
        trading_enabled=trading_enabled
    )

@app.route('/api/data')
def api_data():
    """API endpoint to get all trading data"""
    try:
        # Clean approach - no emergency hacks   
        data = get_all_trading_data()
        
        # Add debug information
        try:
            keys = {
                'keys': {
                    'all': [key for key in redis_client.scan_iter()],
                    'rsi': [key for key in redis_client.scan_iter('rsi:*')],
                    'signal': [key for key in redis_client.scan_iter('signal:*')],
                    'trade_result': [key for key in redis_client.scan_iter('trade_result:*')],
                    'price_history': [key for key in redis_client.scan_iter('price_history:*')]
                }
            }
            data['_debug'] = keys
            
            # DEBUG: Directly check price history data
            price_history_keys = [key for key in redis_client.scan_iter('price_history:*')]
            if price_history_keys:
                print(f"FOUND {len(price_history_keys)} price_history keys in Redis: {price_history_keys}")
                # Check first price history key
                sample_key = price_history_keys[0]
                sample_data = redis_client.get(sample_key)
                if sample_data:
                    try:
                        parsed_data = json.loads(sample_data)
                        print(f"Sample price history data for {sample_key}: Keys = {parsed_data.keys()}")
                        if 'candles' in parsed_data:
                            print(f"Candle count: {len(parsed_data['candles'])}")
                        else:
                            print(f"ERROR: No 'candles' key in Redis data for {sample_key}")
                    except Exception as parse_error:
                        print(f"Error parsing price history data: {parse_error}")
                else:
                    print(f"No data found for price history key {sample_key}")
            else:
                print("NO price_history keys found in Redis!")
            
        except Exception as e:
            print(f"Error adding debug keys: {e}")
            print(traceback.format_exc())
    
        # Add key contents for all trade results for easier debugging
        try:
            trade_results = {}
            for key in keys['keys']['trade_result']:
                trade_data = redis_client.get(key)
                if trade_data:
                    try:
                        trade_results[key] = json.loads(trade_data)
                    except json.JSONDecodeError:
                        trade_results[key] = {'error': 'Could not parse JSON', 'raw': trade_data}
            
            data['_trade_results'] = trade_results
        except Exception as e:
            print(f"Error adding trade results: {e}")
            print(traceback.format_exc())
        
        return jsonify(data)
    except Exception as e:
        print(f"Error in api_data: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/redis/<path:key>')
def redis_key(key):
    """Debug endpoint to view Redis key contents"""
    value = redis_client.get(key)
    if value:
        try:
            return jsonify({'key': key, 'value': json.loads(value)})
        except json.JSONDecodeError:
            return jsonify({'key': key, 'value': value, 'type': 'string'})
    return jsonify({'error': 'Key not found'}), 404

@app.route('/api/account')
def account_info():
    """API endpoint to get Alpaca account information"""
    try:
        # Instead of importing the alpaca_client directly, we'll use Redis to communicate with the trade_execution service
        # First, check if we have a cached account summary
        cached_summary = redis_client.get('account_summary')
        if cached_summary:
            try:
                return jsonify(json.loads(cached_summary))
            except Exception as e:
                print(f"Error parsing cached account summary: {e}")
        
        # If no cached data, request it from the trade_execution service
        # We'll publish a request to a Redis channel and wait for a response
        request_id = str(uuid.uuid4())
        request_data = {
            'request_id': request_id,
            'type': 'account_info_request',
            'timestamp': time.time()
        }
        
        # Publish the request
        redis_client.publish('trade_execution_requests', json.dumps(request_data))
        
        # Wait for a response (with timeout)
        max_wait_time = 5  # seconds
        start_time = time.time()
        response_key = f'account_info_response:{request_id}'
        
        while time.time() - start_time < max_wait_time:
            response = redis_client.get(response_key)
            if response:
                try:
                    account_data = json.loads(response)
                    # Cache the response
                    redis_client.set('account_summary', response, ex=300)  # 5 minute TTL
                    return jsonify(account_data)
                except Exception as e:
                    print(f"Error parsing account response: {e}")
                    break
            time.sleep(0.1)
        
        # If we reach here, we didn't get a response in time
        # Return a placeholder response
        return jsonify({
            'cash': 0.0,
            'portfolio_value': 0.0,
            'equity': 0.0,
            'buying_power': 0.0,
            'position_value': 0.0,
            'positions': [],
            'status': 'unavailable',
            'paper_trading': os.getenv('PAPER_TRADING', 'true').lower() == 'true'
        })
    except Exception as e:
        print(f"Error getting account info: {e}")
        print(traceback.format_exc())
        
        # Try to get from Redis cache if API call fails
        cached_summary = redis_client.get('account_summary')
        if cached_summary:
            try:
                return jsonify({
                    'cached': True,
                    **json.loads(cached_summary)
                })
            except:
                pass
        
        return jsonify({
            'error': str(e),
            'trace': traceback.format_exc(),
            'cash': 0.0,
            'portfolio_value': 0.0,
            'equity': 0.0,
            'buying_power': 0.0,
            'position_value': 0.0,
            'positions': [],
            'status': 'error',
            'paper_trading': os.getenv('PAPER_TRADING', 'true').lower() == 'true'
        }), 500

@app.route('/debug/execute-trade/<symbol>/<decision>')
def debug_execute_trade(symbol, decision):
    """Debug endpoint to execute a trade directly"""
    try:
        # Validate the decision
        decision = decision.lower()
        if decision not in ['buy', 'sell', 'hold']:
            return jsonify({
                'status': 'error',
                'message': f'Invalid decision: {decision}. Must be one of: buy, sell, hold'
            }), 400
            
        # Return a simulated response for the debug interface
        return jsonify({
            'status': 'success',
            'message': f'Debug trade executed successfully',
            'details': {
                'symbol': symbol,
                'decision': decision,
                'timestamp': datetime.now().isoformat(),
                'paper_trading': os.getenv('PAPER_TRADING', 'true').lower() == 'true'
            }
        })
    except Exception as e:
        print(f"Error in debug trade execution: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

        
@app.route('/api/toggle_trading', methods=['POST'])
def toggle_trading():
    """Toggle trading on or off"""
    try:
        # Get the request data
        data = request.get_json()
        if data is None:
            data = {}
            
        enabled = data.get('enabled', False)
        
        # Don't update .env file - only use Redis for temporary state
        # The trading_enabled will reset to default (false) when containers restart
        print(f"===== TRADING STATUS TOGGLED TO: {'ENABLED' if enabled else 'DISABLED'} =====")
        print(f"Trading toggled to {'enabled' if enabled else 'disabled'} (temporary, not saving to .env)")
        
        # Store trading status directly in Redis for immediate access
        print(f"Setting trading_enabled in Redis to: {'true' if enabled else 'false'}")
        try:
            redis_client.set("trading_enabled", "true" if enabled else "false")
            print("Successfully set trading_enabled in Redis")
        except Exception as e:
            print(f"Error setting trading_enabled in Redis: {e}")
            print(traceback.format_exc())
        
        # SIMPLE SERVICE APPROACH:
        # When trading state changes, create appropriate trade result messages
        try:
            # 1. Publish standard message for services
            redis_client.publish('settings:update', json.dumps({
                'trading_enabled': enabled
            }))
            print(f"Published trading status update to Redis: {'enabled' if enabled else 'disabled'}")
            
            # 2. If trading was DISABLED, create "disabled" messages for all symbols
            if not enabled:
                # Get symbols and create disabled messages for each
                symbols = os.getenv('SYMBOLS', 'BTC/USD').split(',')
                for symbol in symbols:
                    try:
                        # Get current signal for this symbol to include its decision
                        signal_data = redis_client.get(f"signal:{symbol}")
                        if signal_data:
                            # Only create disabled messages for non-HOLD signals
                            signal_json = json.loads(signal_data)
                            if signal_json.get('decision', '').lower() != 'hold':
                                # Create standard disabled message
                                result = {
                                    "symbol": symbol,
                                    "decision": signal_json.get('decision'),
                                    "order_id": f"service-disabled-{uuid.uuid4()}",
                                    "quantity": None,
                                    "price": None,
                                    "status": "skipped",
                                    "error": "Trading is currently disabled",
                                    "timestamp": datetime.now().isoformat()
                                }
                                # Save to Redis as standard result 
                                redis_key = f"trade_result:{symbol}"
                                redis_client.set(redis_key, json.dumps(result))
                                # Force a keyspace notification to refresh UI immediately
                                redis_client.publish('__keyspace@0__:' + redis_key, 'set')
                                print(f"Created standard disabled message for {symbol} and published notification")
                    except Exception as e:
                        print(f"Error creating disabled message for {symbol}: {e}")
        except Exception as e:
            print(f"Warning: Failed to publish trading status update to Redis: {str(e)}")
            print(traceback.format_exc())
        
        return jsonify({
            'message': f'Trading {"enabled" if enabled else "disabled"}',
            'status': 'success',
            'trading_enabled': enabled
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to toggle trading: {str(e)}'}), 500

@app.route('/api/trading-settings', methods=['POST'])
def update_trading_settings():
    """Update trading settings"""
    try:
        data = request.json
        mode = data.get('mode')
        
        if mode == 'fixed':
            # Update to fixed amount mode
            amount = float(data.get('fixed_amount', 10.0))
            if amount < 1.0:
                return jsonify({'error': 'Fixed amount must be at least $1.00'}), 400
                
            # Update .env file
            update_env_file('TRADE_USE_FIXED', 'true')
            update_env_file('TRADE_FIXED_AMOUNT', str(amount))
            
            # Also update environment variables in memory
            os.environ['TRADE_USE_FIXED'] = 'true'
            os.environ['TRADE_FIXED_AMOUNT'] = str(amount)
            
            # Publish update event to Redis
            try:
                redis_client.publish('settings:update', json.dumps({
                    'mode': 'fixed',
                    'amount': amount
                }))
                print(f"Published settings update to Redis: fixed mode with amount ${amount}")
            except Exception as e:
                print(f"Warning: Failed to publish settings update to Redis: {str(e)}")
            
            return jsonify({
                'message': f'Updated to fixed amount mode (${amount:.2f})',
                'status': 'success'
            })
            
        elif mode == 'percentage':
            # Update to percentage mode
            percentage = float(data.get('percentage', 2.0))
            if percentage <= 0 or percentage > 100:
                return jsonify({'error': 'Percentage must be between 0 and 100'}), 400
                
            # Update .env file
            update_env_file('TRADE_USE_FIXED', 'false')
            update_env_file('TRADE_PERCENTAGE', str(percentage))
            
            # Also update environment variables in memory
            os.environ['TRADE_USE_FIXED'] = 'false'
            os.environ['TRADE_PERCENTAGE'] = str(percentage)
            
            # Publish update event to Redis
            try:
                redis_client.publish('settings:update', json.dumps({
                    'mode': 'percentage',
                    'percentage': percentage
                }))
                print(f"Published settings update to Redis: percentage mode with {percentage}%")
            except Exception as e:
                print(f"Warning: Failed to publish settings update to Redis: {str(e)}")
            
            return jsonify({
                'message': f'Updated to portfolio percentage mode ({percentage:.1f}%)',
                'status': 'success'
            })
            
        else:
            return jsonify({'error': 'Invalid mode specified'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Failed to update settings: {str(e)}'}), 500
        
def update_env_file(key, value):
    """Update a specific key in the .env file"""
    # Try multiple possible locations for the .env file
    possible_paths = [
        # Docker container paths - check these first since we're likely in Docker
        '/app/.env',
        # Direct project root (for Docker)
        '/.env',
        # Standard path calculation for development environment (parent of parent directory)
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),
        # Current working directory
        os.path.join(os.getcwd(), '.env'),
    ]
    
    # Debug paths
    for path in possible_paths:
        print(f"Checking for .env file at: {path}, exists: {os.path.exists(path)}")
    
    # Find the first existing .env file
    env_file_path = None
    for path in possible_paths:
        if os.path.exists(path):
            env_file_path = path
            print(f"Found .env file at: {env_file_path}")
            break
    
    if env_file_path and os.path.exists(env_file_path):
        try:
            # Read the current content
            with open(env_file_path, 'r') as file:
                lines = file.readlines()
                
            # Replace or add the key
            key_found = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
                    lines[i] = f"{key}={value}\n"
                    key_found = True
                    break
                    
            # Add the key if not found
            if not key_found:
                lines.append(f"{key}={value}\n")
                
            # Write back to the file
            with open(env_file_path, 'w') as file:
                file.writelines(lines)
                
            print(f"SUCCESS: Updated {key}={value} in .env file at {env_file_path}")
            # Verify the update by reading the file again
            try:
                with open(env_file_path, 'r') as verify_file:
                    content = verify_file.read()
                    if f"{key}={value}" in content:
                        print(f"VERIFICATION: Successfully verified {key}={value} is in the file")
                    else:
                        print(f"WARNING: Could not verify {key}={value} in the file after writing. Content sample: {content[:100]}...")
            except Exception as verify_err:
                print(f"WARNING: Could not verify file contents after update: {verify_err}")
            return True
        except Exception as e:
            print(f"Error updating {key}={value} in .env file at {env_file_path}: {str(e)}")
            return False
    else:
        print(f"Error: .env file not found at any of the expected locations")
        
        # First fallback: try to create a new .env file in the current directory
        fallback_path = os.path.join(os.getcwd(), '.env')
        try:
            print(f"Fallback 1: Attempting to create/update .env file at {fallback_path}")
            # Check if file exists and read existing content
            if os.path.exists(fallback_path):
                with open(fallback_path, 'r') as file:
                    lines = file.readlines()
                # Update or add the key
                key_found = False
                for i, line in enumerate(lines):
                    if line.startswith(f"{key}=") or line.startswith(f"{key} ="):
                        lines[i] = f"{key}={value}\n"
                        key_found = True
                        break
                if not key_found:
                    lines.append(f"{key}={value}\n")
                # Write back
                with open(fallback_path, 'w') as file:
                    file.writelines(lines)
            else:
                # Create new file
                with open(fallback_path, 'w') as file:
                    file.write(f"{key}={value}\n")
            print(f"Fallback 1: Created/updated {key}={value} in {fallback_path}")
            return True
        except Exception as e:
            print(f"Fallback 1 failed: {str(e)}")
            
        # Second fallback: Try Docker container path
        fallback_path = "/app/.env"
        try:
            print(f"Fallback 2: Attempting to create/update .env file at {fallback_path}")
            with open(fallback_path, 'a') as file:
                file.write(f"{key}={value}\n")
            print(f"Fallback 2: Appended {key}={value} to {fallback_path}")
            return True
        except Exception as e:
            print(f"Fallback 2 failed: {str(e)}")
            
        # Third fallback: Store in Redis temporarily
        try:
            print(f"Fallback 3: Storing setting in Redis (temporary)")
            redis_key = f"settings:{key}"
            redis_client.set(redis_key, value)
            print(f"Fallback 3: Stored {key}={value} in Redis under key {redis_key}")
            return True
        except Exception as e:
            print(f"Fallback 3 failed: {str(e)}")
            return False

@app.route('/debug')
def debug_page():
    """Debug page with buttons to execute test trades"""
    symbols = os.getenv('SYMBOLS', 'BTC/USD').split(',')
    
    # Add current trading settings for debugging
    fixed_amount_mode = os.getenv('TRADE_USE_FIXED', 'false').lower() == 'true'
    trade_percentage = float(os.getenv('TRADE_PERCENTAGE', '2.0'))
    fixed_amount = float(os.getenv('TRADE_FIXED_AMOUNT', '10.0'))
    trading_enabled = os.getenv('TRADING_ENABLED', 'false').lower() == 'true'
    
    settings_info = f"""
    <div class="settings-panel">
        <h2>Current Trading Settings</h2>
        <ul>
            <li><strong>Trading Enabled:</strong> {trading_enabled}</li>
            <li><strong>Trade Mode:</strong> {'Fixed Amount' if fixed_amount_mode else 'Portfolio Percentage'}</li>
            <li><strong>Fixed Amount:</strong> ${fixed_amount:.2f}</li>
            <li><strong>Trade Percentage:</strong> {trade_percentage:.1f}%</li>
            <li><strong>Environment File:</strong> .env</li>
        </ul>
    </div>
    """
    
    # Define styles separately to avoid f-string/CSS brace conflicts
    styles = '''
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1, h2 { color: #333; }
        .button-row { margin: 10px 0; }
        button { padding: 8px 12px; margin-right: 5px; cursor: pointer; }
        .buy { background-color: #4CAF50; color: white; border: none; }
        .sell { background-color: #f44336; color: white; border: none; }
        .hold { background-color: #2196F3; color: white; border: none; }
        #result { margin-top: 20px; padding: 15px; border: 1px solid #ddd; background: #f9f9f9; white-space: pre-wrap; }
        .settings-panel { 
            background-color: #e9f5ff; 
            padding: 15px; 
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #2196F3;
        }
        .settings-panel h2 { margin-top: 0; }
        .settings-panel ul { padding-left: 20px; }
    '''
    
    # Define JavaScript separately
    script = '''
        async function executeTrade(symbol, decision) {
            document.getElementById('result').textContent = `Executing ${decision} for ${symbol}...`;
            try {
                const response = await fetch(`/debug/execute-trade/${symbol}/${decision}`);
                const data = await response.json();
                document.getElementById('result').textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                document.getElementById('result').textContent = `Error: ${error.message}`;
            }
        }
    '''
    
    # Generate buttons for each symbol
    buttons = ''
    for symbol in symbols:
        buttons += f'''
        <div class="button-row">
            <strong>{symbol}:</strong>
            <button class="buy" onclick="executeTrade('{symbol}', 'buy')">Buy</button>
            <button class="sell" onclick="executeTrade('{symbol}', 'sell')">Sell</button>
            <button class="hold" onclick="executeTrade('{symbol}', 'hold')">Hold</button>
        </div>
        '''
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>TraderMagic Debug</title>
        <style>
            {styles}
        </style>
    </head>
    <body>
        <h1>TraderMagic Debug</h1>
        
        {settings_info}
        
        <p>Use the buttons below to simulate trades. These will help test if your trading settings are working correctly.</p>
        
        {buttons}
        
        <div id="result">Results will appear here...</div>
        
        <script>
            {script}
        </script>
    </body>
    </html>
    """

@socketio.on('connect')
def handle_connect(sid=None):
    """Handle client connection"""
    # Send initial data to the client
    socketio.emit('data_update', get_all_trading_data())

@app.route('/api/strategies')
def get_strategies():
    """API endpoint to get all trading strategies"""
    try:
        # Try to directly access the strategy manager
        try:
            from src.strategies.strategy_manager import strategy_manager
            
            # Get all active strategies
            strategies = strategy_manager.get_active_strategies()
            
            return jsonify({
                'strategies': strategies,
                'timestamp': datetime.now().isoformat()
            })
        except ImportError as e:
            # If direct import fails, try to get strategy information from Redis
            print(f"Direct import of strategy manager failed: {e}")
            strategies = []
            strategy_keys = redis_client.keys("strategy:*:info")
            
            for key in strategy_keys:
                strategy_data = redis_client.get_json(key)
                if strategy_data:
                    # Check if strategy is enabled
                    strategy_name = key.split(":")[1]
                    enabled_key = f"strategy:{strategy_name}:enabled"
                    enabled = redis_client.get(enabled_key)
                    enabled = enabled == "true" if enabled else False
                    
                    # Add enabled status to strategy data
                    strategy_data["enabled"] = enabled
                    strategies.append(strategy_data)
            
            if strategies:
                return jsonify({
                    'strategies': strategies,
                    'timestamp': datetime.now().isoformat(),
                    'container_mode': True,
                    'note': "Using Redis for communication between containers"
                })
            else:
                # Return a more user-friendly message for container deployments
                return jsonify({
                    'strategies': [],
                    'timestamp': datetime.now().isoformat(),
                    'container_mode': True,
                    'note': "Using Redis for container communication",
                    'status': "waiting_for_backend",
                    'message': "Backend strategy manager not detected yet. If this persists, please check if the backend container is running."
                }), 200  # Return 200 instead of 404 since this is an expected scenario
    except Exception as e:
        print(f"Error in strategies endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/strategies/<strategy_name>', methods=['POST'])
def update_strategy(strategy_name):
    """API endpoint to enable/disable a trading strategy"""
    try:
        # Get the request data
        data = request.json
        enabled = data.get('enabled', True)
        
        # Try to directly access the strategy manager
        try:
            from src.strategies.strategy_manager import strategy_manager
            
            # Enable or disable the strategy
            success = strategy_manager.enable_strategy(strategy_name, enabled)
            
            if success:
                return jsonify({
                    'success': True,
                    'strategy': strategy_name,
                    'enabled': enabled,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f"Strategy {strategy_name} not found",
                    'timestamp': datetime.now().isoformat()
                }), 404
        except ImportError as e:
            # If direct import fails, try to update the strategy in Redis
            print(f"Direct import of strategy manager failed: {e}")
            
            # Check if the strategy exists in Redis
            strategy_key = f"strategy:{strategy_name}:info"
            strategy_data = redis_client.get_json(strategy_key)
            
            if not strategy_data:
                return jsonify({
                    'success': False,
                    'error': f"Strategy {strategy_name} not found in Redis",
                    'timestamp': datetime.now().isoformat()
                }), 404
                
            # Update the enabled status in Redis
            enabled_key = f"strategy:{strategy_name}:enabled"
            redis_client.set(enabled_key, str(enabled).lower())
            
            # Publish a message to notify the backend
            redis_client.publish('strategy_updates', 
                json.dumps({
                    'action': 'enable_strategy',
                    'strategy': strategy_name,
                    'enabled': enabled
                })
            )
            
            return jsonify({
                'success': True,
                'strategy': strategy_name,
                'enabled': enabled,
                'timestamp': datetime.now().isoformat(),
                'note': "Updated via Redis (strategy manager not directly accessible)"
            })
    except Exception as e:
        print(f"Error in strategy update endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/signals')
def get_signals():
    """API endpoint to get all trading signals"""
    try:
        # Get all signal keys from Redis
        signal_keys = redis_client.keys("signal:*")
        
        # Get signal data if any exists
        signals = []
        for key in signal_keys:
            signal_data = redis_client.get_json(key)
            if signal_data:
                signals.append(signal_data)
                
        return jsonify({
            'signals': signals,
            'count': len(signals),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in signals endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/start_strategy_manager', methods=['POST'])
def start_strategy_manager():
    """API endpoint to start the strategy manager polling"""
    try:
        # Get the request data
        data = request.json
        interval = int(data.get('interval', 60))
        
        # Try to directly access the strategy manager
        try:
            from src.strategies.strategy_manager import strategy_manager
            
            # Start polling
            strategy_manager.start_polling(interval=interval)
            
            return jsonify({
                'success': True,
                'message': f"Strategy manager started with {interval}s polling interval",
                'timestamp': datetime.now().isoformat()
            })
        except ImportError as e:
            # If direct import fails, use Redis to notify the backend
            print(f"Direct import of strategy manager failed: {e}")
            
            try:
                # Publish a message to notify the backend to start the strategy manager
                redis_client.publish('strategy_updates', 
                    json.dumps({
                        'action': 'start_polling',
                        'interval': interval
                    })
                )
                
                # Store the running state in Redis
                redis_client.set('strategy_manager:running', 'true')
                redis_client.set('strategy_manager:interval', str(interval))
                
                return jsonify({
                    'success': True,
                    'message': f"Start command sent via Redis. Strategy manager should start with {interval}s polling interval",
                    'timestamp': datetime.now().isoformat(),
                    'note': "Started via Redis (strategy manager not directly accessible)"
                })
            except Exception as redis_error:
                print(f"Redis error in start strategy manager: {redis_error}")
                return jsonify({
                    'success': False,
                    'error': f"Redis error: {str(redis_error)}. Check if Redis is properly configured and running.",
                    'timestamp': datetime.now().isoformat()
                }), 500
    except Exception as e:
        print(f"Error in start strategy manager endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/stop_strategy_manager', methods=['POST'])
def stop_strategy_manager():
    """API endpoint to stop the strategy manager polling"""
    try:
        # Try to directly access the strategy manager
        try:
            from src.strategies.strategy_manager import strategy_manager
            
            # Stop polling
            strategy_manager.stop_polling()
            
            return jsonify({
                'success': True,
                'message': "Strategy manager stopped",
                'timestamp': datetime.now().isoformat()
            })
        except ImportError as e:
            # If direct import fails, use Redis to notify the backend
            print(f"Direct import of strategy manager failed: {e}")
            
            try:
                # Publish a message to notify the backend to stop the strategy manager
                redis_client.publish('strategy_updates', 
                    json.dumps({
                        'action': 'stop_polling'
                    })
                )
                
                # Store the running state in Redis
                redis_client.set('strategy_manager:running', 'false')
                
                return jsonify({
                    'success': True,
                    'message': "Stop command sent via Redis. Strategy manager should stop shortly",
                    'timestamp': datetime.now().isoformat(),
                    'note': "Stopped via Redis (strategy manager not directly accessible)"
                })
            except Exception as redis_error:
                print(f"Redis error in stop strategy manager: {redis_error}")
                return jsonify({
                    'success': False,
                    'error': f"Redis error: {str(redis_error)}. Check if Redis is properly configured and running.",
                    'timestamp': datetime.now().isoformat()
                }), 500
    except Exception as e:
        print(f"Error in stop strategy manager endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/news/status')
def news_status():
    """API endpoint to check news integration status"""
    try:
        # Check if news strategy is enabled
        use_news_strategy = os.getenv('USE_NEWS_STRATEGY', 'false').lower() == 'true'
        
        # Get all news keys from Redis
        news_keys = redis_client.keys("news:*")
        news_count = len(news_keys)
        
        # Get news items if any exist
        news_items = []
        for key in news_keys[:10]:  # Limit to 10 most recent for the status check
            news_data = redis_client.get_json(key)
            if news_data:
                news_items.append(news_data)
                
        # Get symbols we're tracking
        symbols = os.getenv('SYMBOLS', 'BTC/USD').split(',')
        
        return jsonify({
            'news_strategy_enabled': use_news_strategy,
            'news_items_count': news_count,
            'news_items_sample': news_items,
            'tracked_symbols': symbols,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in news status endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

@app.route('/api/strategy_manager/health')
def strategy_manager_health():
    """API endpoint to check the health of the strategy manager using Redis"""
    try:
        try:
            # Check if the strategy manager is running through Redis
            running_status = redis_client.get('strategy_manager:running')
            
            # Look for strategy info keys in Redis
            strategy_keys = redis_client.keys("strategy:*:info")
            strategy_names = [key.split(':')[1] for key in strategy_keys]
            
            # Check if there are any signals in Redis (indication of a working system)
            signal_keys = redis_client.keys("signal:*")
            
            # Determine health status
            if running_status and running_status.lower() == 'true' and strategy_keys:
                status = "healthy"
                message = "Strategy manager running and communicating via Redis"
            elif strategy_keys:
                status = "limited"
                message = "Strategy registry detected but manager may not be running"
            elif signal_keys:
                status = "limited"
                message = "Trading signals detected but no strategy registry found"
            else:
                status = "not_detected"
                message = "Backend strategy manager not detected in Redis"
        except Exception as redis_error:
            status = "error"
            message = f"Redis error checking strategy manager: {str(redis_error)}"
            print(f"Redis error in health check: {redis_error}")
            strategy_names = []
            signal_keys = []
    
        return jsonify({
            'status': status,
            'message': message,
            'strategy_manager_running': running_status == 'true' if running_status else False,
            'strategies_count': len(strategy_names),
            'strategies': strategy_names,
            'signals_count': len(signal_keys) if 'signal_keys' in locals() else 0,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in strategy manager health endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({
            'status': 'error',
            'message': f"Error checking strategy manager health: {str(e)}",
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/backend/heartbeat')
def backend_heartbeat():
    """API endpoint to check if backend services are running and ready"""
    try:
        # Check for signs of life in the backend
        heartbeat_signs = {
            "strategy_manager": {
                "running": False,
                "last_seen": None,
                "interval": None,
                "details": {}
            },
            "data_clients": {
                "websocket_client": False,
                "news_client": False
            },
            "traders": {
                "alpaca_trader": False
            },
            "redis_status": {
                "connection": True,
                "key_count": 0
            }
        }
        
        # Check strategy manager
        running_status = redis_client.get('strategy_manager:running')
        if running_status and running_status.lower() == 'true':
            heartbeat_signs["strategy_manager"]["running"] = True
            
            # Get polling interval
            interval = redis_client.get('strategy_manager:interval')
            if interval:
                try:
                    heartbeat_signs["strategy_manager"]["interval"] = int(interval)
                except:
                    pass
            
            # Check if there's a last update timestamp
            last_poll = redis_client.get('strategy_manager:last_poll')
            if last_poll:
                heartbeat_signs["strategy_manager"]["last_seen"] = last_poll
                
                # Calculate time since last poll
                try:
                    poll_time = datetime.fromisoformat(last_poll)
                    now = datetime.now()
                    time_diff_seconds = (now - poll_time).total_seconds()
                    
                    heartbeat_signs["strategy_manager"]["details"]["last_poll_seconds_ago"] = time_diff_seconds
                    
                    # Check if the manager appears to be stalled
                    if heartbeat_signs["strategy_manager"]["interval"]:
                        expected_interval = heartbeat_signs["strategy_manager"]["interval"]
                        grace_period = max(expected_interval * 2, 120)  # 2x interval or at least 2 minutes
                        
                        if time_diff_seconds > grace_period:
                            heartbeat_signs["strategy_manager"]["details"]["status"] = "stalled"
                            heartbeat_signs["strategy_manager"]["details"]["status_message"] = f"Last poll was {time_diff_seconds:.1f}s ago, expected every {expected_interval}s"
                        else:
                            heartbeat_signs["strategy_manager"]["details"]["status"] = "active"
                            heartbeat_signs["strategy_manager"]["details"]["status_message"] = f"Last poll {time_diff_seconds:.1f}s ago, within expected interval of {expected_interval}s"
                    else:
                        heartbeat_signs["strategy_manager"]["details"]["status"] = "unknown"
                        heartbeat_signs["strategy_manager"]["details"]["status_message"] = f"Last poll was {time_diff_seconds:.1f}s ago, interval unknown"
                        
                except Exception as e:
                    heartbeat_signs["strategy_manager"]["details"]["status"] = "error"
                    heartbeat_signs["strategy_manager"]["details"]["error"] = f"Error parsing poll time: {str(e)}"
        
        # Check for active strategies
        strategy_keys = redis_client.keys("strategy:*:info")
        heartbeat_signs["strategy_manager"]["details"]["registered_strategies"] = len(strategy_keys)
        heartbeat_signs["strategy_manager"]["details"]["strategy_names"] = [key.split(':')[1] for key in strategy_keys]
        
        # Check for websocket client (look for recent price history)
        price_keys = redis_client.keys("price:*")
        if price_keys:
            heartbeat_signs["data_clients"]["websocket_client"] = True
        
        # Check for news client
        news_keys = redis_client.keys("news:*")
        if news_keys:
            heartbeat_signs["data_clients"]["news_client"] = True
        
        # Check for Alpaca trader
        account_data = redis_client.get("account:data")
        if account_data:
            heartbeat_signs["traders"]["alpaca_trader"] = True
        
        # Get Redis stats
        all_keys = redis_client.keys("*")
        heartbeat_signs["redis_status"]["key_count"] = len(all_keys)
        
        # Determine overall status
        strategy_manager_alive = (
            heartbeat_signs["strategy_manager"]["running"] and 
            heartbeat_signs["strategy_manager"]["details"].get("status") in ["active", "unknown"]
        )
        
        backend_alive = (
            strategy_manager_alive or 
            heartbeat_signs["data_clients"]["websocket_client"] or
            heartbeat_signs["traders"]["alpaca_trader"]
        )
        
        return jsonify({
            "status": "alive" if backend_alive else "not_detected",
            "message": "Backend services detected" if backend_alive else "No backend services detected",
            "strategy_manager_status": "running" if strategy_manager_alive else "stopped",
            "heartbeat": heartbeat_signs,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error checking backend heartbeat: {e}")
        print(traceback.format_exc())
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@app.route('/api/restart_strategy_manager', methods=['POST'])
def restart_strategy_manager():
    """API endpoint to restart the strategy manager with confirmation"""
    try:
        # Get the request data for interval setting
        data = request.json or {}
        interval = int(data.get('interval', 60))
        restart_method = "unknown"
        redis_error = None
        
        # Step 1: Try to stop the strategy manager
        try:
            # First try direct import if available
            try:
                from src.strategies.strategy_manager import strategy_manager
                strategy_manager.stop_polling()
                print("Successfully stopped strategy manager via direct import")
            except ImportError:
                # If direct import fails, use Redis
                try:
                    print("Using Redis to stop strategy manager")
                    redis_client.publish('strategy_updates', 
                        json.dumps({
                            'action': 'stop_polling'
                        })
                    )
                    # Set the running state in Redis
                    redis_client.set('strategy_manager:running', 'false')
                except Exception as e:
                    redis_error = str(e)
                    print(f"Redis error stopping strategy manager: {e}")
            
            # Small delay to ensure stop completes
            time.sleep(1)
        except Exception as e:
            print(f"Error stopping strategy manager: {e}")
            # Continue anyway since we'll try to start it
        
        # Step 2: Start the strategy manager
        try:
            try:
                from src.strategies.strategy_manager import strategy_manager
                strategy_manager.start_polling(interval=interval)
                print(f"Successfully started strategy manager via direct import with interval {interval}s")
                restart_method = "direct"
            except ImportError:
                # If direct import fails, use Redis
                try:
                    print(f"Using Redis to start strategy manager with interval {interval}s")
                    redis_client.publish('strategy_updates', 
                        json.dumps({
                            'action': 'start_polling',
                            'interval': interval
                        })
                    )
                    # Set the running state in Redis
                    redis_client.set('strategy_manager:running', 'true')
                    redis_client.set('strategy_manager:interval', str(interval))
                    restart_method = "redis"
                except Exception as e:
                    redis_error = str(e)
                    print(f"Redis error starting strategy manager: {e}")
                    return jsonify({
                        'success': False,
                        'error': f"Redis error: {str(e)}. Check if Redis is properly configured and running.",
                        'timestamp': datetime.now().isoformat()
                    }), 500
        except Exception as e:
            print(f"Error starting strategy manager: {e}")
            return jsonify({
                'success': False,
                'message': f"Error restarting strategy manager: {str(e)}",
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Step 3: Confirm the restart by checking Redis keys
        time.sleep(2)  # Wait for Redis updates
        
        # Check if running status is set
        running_status = redis_client.get('strategy_manager:running')
        restart_success = running_status and running_status.lower() == 'true'
        
        # Also check for a recent last_poll timestamp if the manager is supposed to be running
        if restart_success:
            last_poll = redis_client.get('strategy_manager:last_poll')
            if last_poll:
                try:
                    # Check if the last poll is recent (within the past minute)
                    poll_time = datetime.fromisoformat(last_poll)
                    now = datetime.now()
                    time_diff = (now - poll_time).total_seconds()
                    
                    # Time difference validation depends on the polling interval
                    # For shorter intervals, we expect faster confirmation
                    # For longer intervals, allow more time
                    expected_max_diff = min(interval * 1.5, 120)  # Cap at 2 minutes
                    
                    if time_diff > expected_max_diff:
                        # Poll time exists but is too old
                        restart_confirmation = "uncertain"
                        confirmation_note = f"Last poll was {time_diff:.1f} seconds ago"
                    else:
                        # We have a recent poll, success!
                        restart_confirmation = "confirmed"
                        confirmation_note = f"Last poll was {time_diff:.1f} seconds ago"
                except Exception as e:
                    print(f"Error parsing last poll time: {e}")
                    restart_confirmation = "uncertain"
                    confirmation_note = f"Error parsing last poll time: {e}"
            else:
                # No last poll time found yet
                restart_confirmation = "pending"
                confirmation_note = "Waiting for first poll"
        else:
            restart_confirmation = "failed"
            confirmation_note = "Strategy manager is not running according to Redis"
        
        return jsonify({
            'success': restart_success,
            'message': f"Strategy manager restarted with {interval}s polling interval",
            'restart_method': restart_method,
            'confirmation_status': restart_confirmation,
            'confirmation_note': confirmation_note,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error in restart strategy manager endpoint: {e}")
        print(traceback.format_exc())
        return jsonify({
            "error": str(e), 
            "trace": traceback.format_exc(),
            'success': False,
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/reset_strategy_manager', methods=['POST'])
def reset_strategy_manager():
    """Emergency endpoint to reset the strategy manager state in Redis"""
    try:
        # Try to get current state for diagnostics
        original_state = {}
        try:
            original_state = {
                'running': redis_client.get('strategy_manager:running'),
                'interval': redis_client.get('strategy_manager:interval'),
                'last_run': redis_client.get('strategy_manager:last_run')
            }
        except Exception as e:
            print(f"Error getting original state: {e}")
        
        # Force reset the strategy manager state in Redis
        try:
            redis_client.set('strategy_manager:running', 'false')
            print("Reset strategy manager state to 'false'")
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f"Error resetting strategy manager state: {str(e)}",
                'error_details': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
        
        # Get any stored strategy keys
        strategy_keys = []
        try:
            strategy_keys = redis_client.keys("strategy:*:info")
            strategy_names = [key.split(':')[1] for key in strategy_keys]
            print(f"Found {len(strategy_keys)} strategy keys")
        except Exception as e:
            print(f"Error getting strategy keys: {e}")
            strategy_names = []
        
        # Also get signal keys to show what data is available
        signal_keys = []
        try:
            signal_keys = redis_client.keys("signal:*")
            print(f"Found {len(signal_keys)} signal keys")
        except Exception as e:
            print(f"Error getting signal keys: {e}")
        
        # Construct a command that could be run to restart the backend service
        restart_command = "docker restart trader-magic-backend"
        
        # Construct a detailed message with clear next steps
        detailed_message = (
            "Strategy manager state has been reset in Redis. "
            "If you're still experiencing issues, you may need to restart the backend service."
        )
        
        return jsonify({
            'success': True,
            'message': detailed_message,
            'restart_command': restart_command,
            'note': 'Refresh the page after a few seconds to see the updated state',
            'found_strategies': strategy_names,
            'signal_count': len(signal_keys),
            'original_state': original_state,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error resetting strategy manager: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f"Error resetting strategy manager: {str(e)}",
            'error_details': traceback.format_exc(),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/refresh_trade/<symbol>')
def refresh_trade(symbol):
    """API endpoint to manually refresh a specific trade result"""
    try:
        # Fetch the trade result from Redis
        redis_key = f"trade_result:{symbol}"
        result_data = redis_client.get(redis_key)
        
        if result_data:
            try:
                # Parse the JSON
                result = json.loads(result_data)
                status = result.get('status', 'unknown')
                print(f"Refreshed trade result for {symbol}: {status}")
                
                # If this is an executed trade, trigger a transaction update
                if status == 'executed' and transaction_update_clients:
                    socketio.emit('transaction_complete', {
                        'symbol': symbol,
                        'timestamp': datetime.now().isoformat(),
                        'status': status,
                        'decision': result.get('decision')
                    })
                    print(f"Emitted transaction update for {symbol} during refresh")
                
                # Return the trade result
                return jsonify({
                    'success': True,
                    'symbol': symbol,
                    'result': result,
                    'timestamp': datetime.now().isoformat()
                })
            except json.JSONDecodeError as e:
                print(f"Error parsing trade result for {symbol}: {e}")
                return jsonify({
                    'success': False,
                    'error': f"JSON decode error: {str(e)}",
                    'raw_data': result_data
                })
        else:
            print(f"No trade result found for {symbol}")
            return jsonify({
                'success': False,
                'error': f"No trade result found for {symbol}"
            })
    except Exception as e:
        print(f"Error refreshing trade result for {symbol}: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'trace': traceback.format_exc()
        }), 500

@app.route('/api/force_account_update')
def force_account_update():
    """Force an update of account data for all connected clients"""
    try:
        # Get the latest account data
        account_key = "account:data"
        account_data = redis_client.get_json(account_key)
        
        # Emit account update notification to all clients
        socketio.emit('account_update_needed')
        
        return jsonify({
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'message': 'Account update notification sent to all clients'
        })
    except Exception as e:
        print(f"Error forcing account update: {e}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/refresh_all_transactions', methods=['POST'])
def refresh_all_transactions():
    """API endpoint to refresh all transactions and account data"""
    try:
        # Get trading symbols
        symbols_key = "available_symbols"
        symbols_data = redis_client.get(symbols_key)
        
        if symbols_data:
            symbols = json.loads(symbols_data)
        else:
            # Use default symbols as fallback
            symbols = ["BTC/USDT", "ETH/USDT", "LTC/USDT", "XRP/USDT"]
            
        print(f"Refreshing transactions for {len(symbols)} symbols...")
        
        # Clear account data to force refresh
        account_key = "account:data"
        account_summary_key = "account_summary"
        redis_client.delete(account_key)
        redis_client.delete(account_summary_key)
        
        # ENHANCEMENT: Also clear API key caches
        api_keys = redis_client.keys("api_key:*")
        api_keys_cleared = 0
        for key in api_keys:
            redis_client.delete(key)
            api_keys_cleared += 1
        
        print(f"Cleared {api_keys_cleared} API key cache entries")
        
        # Process each symbol
        for symbol in symbols:
            # Clear existing signals and trade results
            signal_key = f"signal:{symbol}"
            result_key = f"trade_result:{symbol}"
            
            redis_client.delete(signal_key)
            redis_client.delete(result_key)
            
            # Publish notifications to trigger updates
            redis_client.publish(f'__keyspace@0__:{signal_key}', 'set')
            redis_client.publish(f'__keyspace@0__:{result_key}', 'set')
        
        # Emit Socket.IO event to force frontend refresh
        socketio.emit('data_update', {"refresh": "complete"})
        
        # Emit account update event
        socketio.emit('account_update_needed')
        
        # Also publish to Redis for any other services
        redis_client.publish('trade_notifications', json.dumps({
            "type": "refresh_all",
            "timestamp": datetime.now().isoformat(),
            "api_keys_cleared": api_keys_cleared
        }))
        
        return jsonify({
            "success": True,
            "message": f"Successfully refreshed data for {len(symbols)} symbols",
            "api_keys_cleared": api_keys_cleared,
            "symbols": symbols
        })
    except Exception as e:
        print(f"Error refreshing all transactions: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        })

@app.route('/api/reload_api_keys', methods=['POST'])
def reload_api_keys():
    """API endpoint to force reload of API keys from .env file"""
    try:
        # Clear account caches
        redis_client.delete('account_summary')
        redis_client.delete('account:data')
        
        # Delete any cached API keys
        api_keys = redis_client.keys("api_key:*")
        for key in api_keys:
            redis_client.delete(key)
            
        # Publish a notification to force services to reload keys
        redis_client.publish('trade_notifications', json.dumps({
            "type": "reload_api_keys",
            "timestamp": datetime.now().isoformat()
        }))
        
        # Emit a Socket.IO event to force frontend refresh
        socketio.emit('account_update_needed')
        
        return jsonify({
            "success": True,
            "message": "API keys will be reloaded from .env file. Services may need to be restarted for changes to take effect.",
            "api_keys_cleared": len(api_keys),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        print(f"Error reloading API keys: {e}")
        print(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Start Redis listener in a background thread
    threading.Thread(target=redis_listener, daemon=True).start()
    
    # Start Flask app
    socketio.run(app, host=frontend_host, port=frontend_port, debug=False, allow_unsafe_werkzeug=True)