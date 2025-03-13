"""
Backtesting engine for testing trading strategies using historical data
"""

import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union, Callable

from src.config import config
from src.utils import get_logger
from src.data_retrieval.polygon_client import PolygonClient
from src.strategies.base_strategy import BaseStrategy

logger = get_logger("backtest_engine")

class BacktestEngine:
    """
    Backtesting engine for testing trading strategies on historical data
    """
    
    def __init__(self, 
                 initial_capital: float = 10000.0,
                 commission: float = 0.001,  # 0.1% per trade
                 slippage: float = 0.001,    # 0.1% slippage
                 risk_per_trade: float = 0.02  # 2% risk per trade
                ):
        """
        Initialize the backtesting engine
        
        Args:
            initial_capital: Starting capital for the backtest
            commission: Commission rate as a decimal (e.g., 0.001 = 0.1%)
            slippage: Slippage rate as a decimal
            risk_per_trade: Maximum risk per trade as a decimal (e.g., 0.02 = 2%)
        """
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.risk_per_trade = risk_per_trade
        
        self.positions: Dict[str, Dict[str, Any]] = {}  # Current positions
        self.trades: List[Dict[str, Any]] = []         # Trade history
        self.trade_id = 0                              # Unique trade ID counter
        
        self.equity_curve: List[Dict[str, Any]] = []   # Track equity over time
        self.results: Dict[str, Any] = {}              # Backtest results
        
        # Initialize Polygon client
        self.polygon = PolygonClient()
        
    def run_backtest(self, 
                    strategy: BaseStrategy,
                    symbols: List[str],
                    start_date: Union[str, datetime],
                    end_date: Union[str, datetime],
                    timeframe: str = "1d",
                    verbose: bool = False) -> Dict[str, Any]:
        """
        Run a backtest for a given strategy and time period
        
        Args:
            strategy: Instance of a BaseStrategy subclass
            symbols: List of symbols to backtest
            start_date: Start date for backtest (YYYY-MM-DD)
            end_date: End date for backtest (YYYY-MM-DD)
            timeframe: Data timeframe (1d, 1h, etc.)
            verbose: Whether to print detailed logs
            
        Returns:
            Dictionary with backtest results
        """
        logger.info(f"Starting backtest for {len(symbols)} symbols from {start_date} to {end_date}")
        
        # Convert dates to datetime if they're strings
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d")
        
        # Reset backtest state
        self._reset_backtest()
        
        # Get historical data for all symbols
        all_data = {}
        for symbol in symbols:
            logger.info(f"Fetching historical data for {symbol}")
            symbol_data = self.polygon.get_historical_data_for_backtest(
                symbol, 
                start_date.strftime("%Y-%m-%d"), 
                end_date.strftime("%Y-%m-%d"),
                timeframe
            )
            
            if symbol_data is None or len(symbol_data) == 0:
                logger.warning(f"No historical data found for {symbol}, skipping")
                continue
                
            # Convert to DataFrame and sort by date
            df = pd.DataFrame(symbol_data)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.sort_values('timestamp')
            all_data[symbol] = df
        
        if not all_data:
            logger.error("No historical data found for any symbols")
            return {"error": "No historical data found"}
        
        # Find the common date range across all symbols
        common_dates = self._find_common_dates(all_data)
        if not common_dates:
            logger.error("No common dates found across symbols")
            return {"error": "No common dates found across symbols"}
            
        # Run the backtest day by day
        for date in common_dates:
            date_str = date.strftime("%Y-%m-%d")
            
            # First process open positions (for multi-day positions)
            self._process_open_positions(date, all_data)
            
            # Track equity at start of the day
            self._update_equity_curve(date, "start_of_day")
            
            # Process each symbol for the current date
            for symbol in all_data.keys():
                # Get the day's data
                day_data = all_data[symbol][all_data[symbol]['timestamp'].dt.date == date.date()]
                
                if day_data.empty:
                    continue
                    
                # Prepare data in the format the strategy expects
                formatted_data = self._format_data_for_strategy(symbol, day_data)
                
                # Call strategy to generate signals
                signal = strategy.process_data(formatted_data)
                
                if signal and 'action' in signal:
                    if verbose:
                        logger.info(f"Signal for {symbol} on {date_str}: {signal}")
                        
                    # Execute the trade
                    self._execute_trade(symbol, signal, day_data, date)
            
            # Track equity at end of the day
            self._update_equity_curve(date, "end_of_day")
        
        # Calculate and store results
        self.results = self._calculate_results()
        
        if verbose:
            self._print_results()
            
        return self.results
    
    def plot_results(self, output_dir: str = "./results"):
        """
        Generate and save plots of backtest results
        
        Args:
            output_dir: Directory to save plots
        """
        if not self.equity_curve:
            logger.error("No backtest data to plot")
            return
            
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert equity curve to DataFrame
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['date'] = pd.to_datetime(equity_df['date'])
        equity_df = equity_df.set_index('date')
        
        # Basic equity curve
        plt.figure(figsize=(10, 6))
        plt.plot(equity_df.index, equity_df['equity'], label='Strategy')
        
        # Add buy & hold comparison if available
        if 'buy_hold_equity' in equity_df.columns:
            plt.plot(equity_df.index, equity_df['buy_hold_equity'], label='Buy & Hold', linestyle='--')
            
        plt.title('Equity Curve')
        plt.xlabel('Date')
        plt.ylabel('Portfolio Value ($)')
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(f"{output_dir}/equity_curve.png")
        
        # Drawdown plot
        if 'drawdown' in equity_df.columns:
            plt.figure(figsize=(10, 6))
            plt.plot(equity_df.index, equity_df['drawdown'] * 100)
            plt.title('Drawdown (%)')
            plt.xlabel('Date')
            plt.ylabel('Drawdown (%)')
            plt.grid(True)
            plt.tight_layout()
            plt.savefig(f"{output_dir}/drawdown.png")
        
        # Monthly returns heatmap
        if len(equity_df) > 60:  # Only if we have enough data
            # Calculate monthly returns
            monthly_returns = equity_df['returns'].resample('M').apply(
                lambda x: (1 + x).prod() - 1
            )
            
            # Reshape to a heatmap format
            returns_by_year_month = monthly_returns.groupby([
                monthly_returns.index.year, 
                monthly_returns.index.month
            ]).first().unstack()
            
            # Plot heatmap
            plt.figure(figsize=(12, 8))
            im = plt.imshow(returns_by_year_month.values, cmap='RdYlGn')
            plt.colorbar(im, label='Return (%)')
            
            plt.title('Monthly Returns (%)')
            plt.xticks(range(12), ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])
            plt.yticks(range(len(returns_by_year_month.index)), returns_by_year_month.index)
            
            for i in range(len(returns_by_year_month.index)):
                for j in range(12):
                    if j < returns_by_year_month.values.shape[1] and not np.isnan(returns_by_year_month.values[i, j]):
                        plt.text(j, i, f"{returns_by_year_month.values[i, j]:.1%}", 
                                ha="center", va="center", color="black")
            
            plt.tight_layout()
            plt.savefig(f"{output_dir}/monthly_returns.png")
        
        # Save json results
        with open(f"{output_dir}/backtest_results.json", "w") as f:
            json.dump(self.results, f, indent=4, default=str)
            
        logger.info(f"Backtest plots saved to {output_dir}")
    
    def _reset_backtest(self):
        """Reset backtest state for a new run"""
        self.capital = self.initial_capital
        self.positions = {}
        self.trades = []
        self.trade_id = 0
        self.equity_curve = []
        self.results = {}
    
    def _find_common_dates(self, data_dict: Dict[str, pd.DataFrame]) -> List[datetime]:
        """Find dates that exist across all symbols"""
        date_sets = []
        for symbol, df in data_dict.items():
            dates = set(df['timestamp'].dt.date.unique())
            date_sets.append(dates)
        
        # Find the intersection of all date sets
        if date_sets:
            common_dates = set.intersection(*date_sets)
            # Convert to datetime and sort
            common_dates = sorted([datetime.combine(d, datetime.min.time()) for d in common_dates])
            return common_dates
        return []
    
    def _format_data_for_strategy(self, symbol: str, day_data: pd.DataFrame) -> Dict[str, Any]:
        """Format daily data for strategy processing"""
        # Use the last row (end of day data)
        last_row = day_data.iloc[-1]
        
        # Basic price data
        data = {
            "symbol": symbol,
            "price": float(last_row['close']),
            "timestamp": last_row['timestamp'].timestamp() * 1000,  # Convert to milliseconds
            "polygon_data": {
                "open": float(last_row['open']),
                "high": float(last_row['high']),
                "low": float(last_row['low']),
                "close": float(last_row['close']),
                "volume": int(last_row['volume']),
            }
        }
        
        # Add OHLCV history if available
        if len(day_data) > 1:
            data["polygon_data"]["bars"] = day_data.to_dict('records')
            
        # Calculate some basic indicators
        if len(day_data) >= 14:
            # RSI
            delta = day_data['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(window=14).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            data["rsi"] = {"value": float(rsi.iloc[-1]), "data": rsi.tolist()}
            
            # Moving averages
            data["polygon_data"]["sma_20"] = float(day_data['close'].rolling(20).mean().iloc[-1])
            data["polygon_data"]["sma_50"] = float(day_data['close'].rolling(50).mean().iloc[-1])
            data["polygon_data"]["sma_200"] = float(day_data['close'].rolling(200).mean().iloc[-1])
            
            # Volatility (20-day)
            data["polygon_data"]["volatility"] = float(day_data['close'].pct_change().rolling(20).std().iloc[-1])
        
        return data
    
    def _execute_trade(self, symbol: str, signal: Dict[str, Any], day_data: pd.DataFrame, date: datetime):
        """Execute a trade based on the signal"""
        action = signal['action']
        price = float(day_data.iloc[-1]['close'])
        
        # Apply slippage
        if action == 'buy':
            price = price * (1 + self.slippage)
        elif action == 'sell':
            price = price * (1 - self.slippage)
        
        # Get confidence and risk from signal, or use defaults
        confidence = signal.get('confidence', 1.0)
        risk_factor = signal.get('risk_factor', 1.0) * self.risk_per_trade
        
        if action == 'buy' and symbol not in self.positions:
            # Calculate position size based on risk
            risk_amount = self.capital * risk_factor
            # Use ATR or volatility if available for position sizing
            volatility = signal.get('volatility', day_data['close'].pct_change().std())
            if volatility == 0:
                volatility = 0.01  # Prevent division by zero
            
            # Position size based on risk and volatility
            position_size = risk_amount / (price * volatility * 10)  # 10x leverage on volatility for reasonable sizing
            position_size = min(position_size, self.capital * 0.25)  # Cap at 25% of capital
            
            # Scale by confidence
            position_size *= confidence
            
            # Ensure we have enough capital
            cost = position_size * price
            if cost > self.capital:
                position_size = self.capital / price
                cost = self.capital
            
            # Apply commission
            commission_cost = cost * self.commission
            
            if position_size > 0:
                # Record the trade
                self.trade_id += 1
                trade = {
                    'id': self.trade_id,
                    'symbol': symbol,
                    'action': 'buy',
                    'price': price,
                    'size': position_size,
                    'cost': cost,
                    'commission': commission_cost,
                    'date': date,
                    'signal': signal
                }
                self.trades.append(trade)
                
                # Update capital and add position
                self.capital -= (cost + commission_cost)
                self.positions[symbol] = {
                    'size': position_size,
                    'entry_price': price,
                    'entry_date': date,
                    'current_price': price,
                    'entry_trade_id': self.trade_id
                }
                
                logger.info(f"BUY {position_size:.2f} {symbol} @ ${price:.2f}, Cost: ${cost:.2f}, Comm: ${commission_cost:.2f}")
        
        elif action == 'sell' and symbol in self.positions:
            position = self.positions[symbol]
            position_size = position['size']
            entry_price = position['entry_price']
            
            # Calculate proceeds and profit/loss
            proceeds = position_size * price
            pl = proceeds - (position_size * entry_price)
            
            # Apply commission
            commission_cost = proceeds * self.commission
            net_proceeds = proceeds - commission_cost
            
            # Record the trade
            self.trade_id += 1
            trade = {
                'id': self.trade_id,
                'symbol': symbol,
                'action': 'sell',
                'price': price,
                'size': position_size,
                'proceeds': proceeds,
                'commission': commission_cost,
                'pl': pl,
                'pl_pct': (price / entry_price) - 1,
                'entry_trade_id': position['entry_trade_id'],
                'date': date,
                'signal': signal
            }
            self.trades.append(trade)
            
            # Update capital and remove position
            self.capital += net_proceeds
            del self.positions[symbol]
            
            logger.info(f"SELL {position_size:.2f} {symbol} @ ${price:.2f}, P/L: ${pl:.2f} ({trade['pl_pct']:.2%})")
    
    def _process_open_positions(self, date: datetime, all_data: Dict[str, pd.DataFrame]):
        """Process open positions at the start of each day"""
        for symbol, position in list(self.positions.items()):
            if symbol in all_data:
                day_data = all_data[symbol][all_data[symbol]['timestamp'].dt.date == date.date()]
                if not day_data.empty:
                    # Update current price
                    position['current_price'] = float(day_data.iloc[-1]['close'])
    
    def _update_equity_curve(self, date: datetime, point: str):
        """Update equity curve with current portfolio value"""
        # Calculate current value of all positions
        positions_value = sum(
            pos['size'] * pos['current_price'] 
            for pos in self.positions.values()
        )
        
        # Total equity = cash + positions value
        equity = self.capital + positions_value
        
        # Calculate drawdown
        if not self.equity_curve:
            peak_equity = equity
            drawdown = 0
            daily_return = 0
        else:
            prev_equity = self.equity_curve[-1]['equity']
            daily_return = (equity / prev_equity) - 1
            
            # Track peak equity for drawdown calculation
            peak_equity = max(
                self.equity_curve[-1].get('peak_equity', prev_equity),
                equity
            )
            
            # Drawdown as a percentage of peak equity
            drawdown = 0 if equity >= peak_equity else (peak_equity - equity) / peak_equity
        
        # Record equity point
        self.equity_curve.append({
            'date': date,
            'point': point,
            'equity': equity,
            'cash': self.capital,
            'positions_value': positions_value,
            'peak_equity': peak_equity,
            'drawdown': drawdown,
            'returns': daily_return
        })
    
    def _calculate_results(self) -> Dict[str, Any]:
        """Calculate backtest performance metrics"""
        if not self.trades or not self.equity_curve:
            return {"error": "No trades executed"}
        
        # Basic metrics
        start_equity = self.initial_capital
        end_equity = self.equity_curve[-1]['equity']
        total_return = (end_equity / start_equity) - 1
        
        # Extract trades info
        winning_trades = [t for t in self.trades if t.get('action') == 'sell' and t.get('pl', 0) > 0]
        losing_trades = [t for t in self.trades if t.get('action') == 'sell' and t.get('pl', 0) <= 0]
        
        # Calculate win rate and average trade metrics
        total_closed_trades = len(winning_trades) + len(losing_trades)
        win_rate = len(winning_trades) / total_closed_trades if total_closed_trades > 0 else 0
        
        avg_win = np.mean([t['pl'] for t in winning_trades]) if winning_trades else 0
        avg_loss = np.mean([t['pl'] for t in losing_trades]) if losing_trades else 0
        
        # Profit factor
        gross_profit = sum(t['pl'] for t in winning_trades)
        gross_loss = abs(sum(t['pl'] for t in losing_trades))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Maximum drawdown
        max_drawdown = max([e['drawdown'] for e in self.equity_curve]) if self.equity_curve else 0
        
        # Annualized return and Sharpe ratio
        if len(self.equity_curve) > 1:
            start_date = self.equity_curve[0]['date']
            end_date = self.equity_curve[-1]['date']
            days = (end_date - start_date).days
            
            if days > 0:
                annualized_return = ((1 + total_return) ** (365 / days)) - 1
                
                # Daily returns
                daily_returns = np.array([e['returns'] for e in self.equity_curve if e['point'] == 'end_of_day'])
                
                # Sharpe ratio (annualized, assuming risk-free rate of 0)
                sharpe_ratio = (np.mean(daily_returns) * 252) / (np.std(daily_returns) * np.sqrt(252)) if np.std(daily_returns) > 0 else 0
            else:
                annualized_return = total_return
                sharpe_ratio = 0
        else:
            annualized_return = 0
            sharpe_ratio = 0
        
        # Calculate drawdown statistics
        drawdowns = [e['drawdown'] for e in self.equity_curve]
        avg_drawdown = np.mean(drawdowns) if drawdowns else 0
        
        # Compile results
        results = {
            'start_date': self.equity_curve[0]['date'] if self.equity_curve else None,
            'end_date': self.equity_curve[-1]['date'] if self.equity_curve else None,
            'initial_capital': start_equity,
            'final_capital': end_equity,
            'total_return': total_return,
            'total_return_pct': total_return * 100,
            'annualized_return': annualized_return,
            'annualized_return_pct': annualized_return * 100,
            'max_drawdown': max_drawdown,
            'max_drawdown_pct': max_drawdown * 100,
            'avg_drawdown': avg_drawdown,
            'avg_drawdown_pct': avg_drawdown * 100,
            'sharpe_ratio': sharpe_ratio,
            'total_trades': len(self.trades),
            'total_closed_trades': total_closed_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'win_rate_pct': win_rate * 100,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_holding_period_days': np.mean([
                (t['date'] - self.trades[t['entry_trade_id']-1]['date']).days 
                for t in self.trades if t.get('action') == 'sell'
            ]) if any(t.get('action') == 'sell' for t in self.trades) else 0,
        }
        
        return results
    
    def _print_results(self):
        """Print formatted backtest results to console"""
        if not self.results:
            logger.error("No results to print")
            return
            
        logger.info("\n" + "="*50)
        logger.info("BACKTEST RESULTS")
        logger.info("="*50)
        
        # Format and print key metrics
        logger.info(f"Period: {self.results['start_date']} to {self.results['end_date']}")
        logger.info(f"Initial Capital: ${self.results['initial_capital']:.2f}")
        logger.info(f"Final Capital: ${self.results['final_capital']:.2f}")
        logger.info(f"Total Return: {self.results['total_return_pct']:.2f}%")
        logger.info(f"Annualized Return: {self.results['annualized_return_pct']:.2f}%")
        logger.info(f"Max Drawdown: {self.results['max_drawdown_pct']:.2f}%")
        logger.info(f"Sharpe Ratio: {self.results['sharpe_ratio']:.2f}")
        logger.info(f"Win Rate: {self.results['win_rate_pct']:.2f}%")
        logger.info(f"Profit Factor: {self.results['profit_factor']:.2f}")
        logger.info(f"Total Trades: {self.results['total_trades']}")
        logger.info(f"Winning/Losing: {self.results['winning_trades']}/{self.results['losing_trades']}")
        logger.info(f"Avg Win/Loss: ${self.results['avg_win']:.2f}/${abs(self.results['avg_loss']):.2f}")
        logger.info(f"Avg Holding Period: {self.results['avg_holding_period_days']:.1f} days")
        logger.info("="*50) 