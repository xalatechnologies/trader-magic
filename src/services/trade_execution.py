from src.utils.balance_checker import BalanceChecker

class TradeExecutionService:
    def __init__(self):
        # Initialize balance checker
        self.balance_checker = BalanceChecker(self.redis_client)
        
    def process_signal(self, symbol, signal_data):
        """Process a trading signal for the given symbol."""
        try:
            # Before executing the trade, check for sufficient balance
            has_sufficient, available_balance = self.balance_checker.has_sufficient_balance(
                amount_needed=self._estimate_trade_amount(symbol, decision), 
                currency="USD"
            )
            
            if not has_sufficient:
                self.logger.warning(f"Insufficient balance for {symbol} trade. Available: ${available_balance:.2f}")
                
                # Get a safe trade amount instead
                safe_qty = self.balance_checker.get_safe_trade_amount(
                    symbol=symbol,
                    price=self._get_current_price(symbol),
                    use_percentage=self.use_fixed_amount,
                    percentage=self.trade_percentage,
                    fixed_amount=self.fixed_amount
                )
                
                if safe_qty <= 0:
                    # Not enough for even a minimal trade, skip it
                    error_message = f"Insufficient balance for {symbol}. Required: ${self._estimate_trade_amount(symbol, decision):.2f}, Available: ${available_balance:.2f}"
                    self._record_trade_result(symbol, "skipped", error=error_message)
                    return
                else:
                    # Use the safe quantity instead
                    self.logger.info(f"Using reduced quantity for {symbol}: {safe_qty} units")
                    qty = safe_qty
            
            # ... rest of the method ...
        except Exception as e:
            self.logger.error(f"Error processing signal: {e}")
            self._record_trade_result(symbol, "failed", error=str(e))

    # ... rest of the existing methods ... 