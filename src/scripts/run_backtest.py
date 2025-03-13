#!/usr/bin/env python
"""
Command-line script for running backtests on strategies
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.backtest.backtest_engine import BacktestEngine
from src.strategies.base_strategy import BaseStrategy
from src.strategies.polygon_strategy import PolygonStrategy
from src.strategies.crypto_strategy import CryptoStrategy
from src.strategies.rsi_strategy import RSIStrategy
from src.strategies.news_sentiment_strategy import NewsSentimentStrategy
from src.config import config
from src.utils import get_logger

logger = get_logger("backtest_runner")

def parse_args():
    """Parse command-line arguments"""
    parser = argparse.ArgumentParser(description="Run backtests on trading strategies")
    
    # Required arguments
    parser.add_argument("--strategy", required=True, type=str, 
                        choices=["polygon", "crypto", "rsi", "news_sentiment", "all"],
                        help="Strategy to backtest")
    
    parser.add_argument("--symbols", required=True, type=str,
                        help="Comma-separated list of symbols to test")
    
    # Date range
    parser.add_argument("--start_date", type=str, default=(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
                        help="Start date for backtest (YYYY-MM-DD)")
    
    parser.add_argument("--end_date", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                        help="End date for backtest (YYYY-MM-DD)")
    
    # Timeframe
    parser.add_argument("--timeframe", type=str, default="1d",
                        choices=["1d", "1h", "15m", "5m", "1m"],
                        help="Data timeframe")
    
    # Capital and risk settings
    parser.add_argument("--initial_capital", type=float, default=10000.0,
                        help="Initial capital for backtest")
    
    parser.add_argument("--risk_per_trade", type=float, default=0.02,
                        help="Risk per trade as a decimal (e.g., 0.02 = 2%%)")
    
    parser.add_argument("--commission", type=float, default=0.001,
                        help="Commission rate as a decimal (e.g., 0.001 = 0.1%%)")
    
    # Strategy parameters
    parser.add_argument("--volume_threshold", type=float, default=2.0,
                        help="Volume spike threshold for polygon strategy")
    
    parser.add_argument("--price_change_trigger", type=float, default=0.02,
                        help="Price change percentage to trigger signals (e.g., 0.02 = 2%%)")
    
    parser.add_argument("--rsi_upper", type=float, default=70,
                        help="RSI upper threshold for signals")
    
    parser.add_argument("--rsi_lower", type=float, default=30,
                        help="RSI lower threshold for signals")
    
    # Output options
    parser.add_argument("--output_dir", type=str, default="./backtest_results",
                        help="Directory to save results")
    
    parser.add_argument("--verbose", action="store_true",
                        help="Enable verbose output")
    
    parser.add_argument("--plot", action="store_true",
                        help="Generate plots of results")
    
    return parser.parse_args()

def create_strategy(strategy_name: str, args: argparse.Namespace) -> Optional[BaseStrategy]:
    """Create and configure a strategy instance"""
    if strategy_name == "polygon":
        strategy = PolygonStrategy()
        strategy.configure({
            "volume_spike_threshold": args.volume_threshold,
            "price_change_trigger": args.price_change_trigger,
            "ma_short_period": 20,
            "ma_long_period": 50,
            "enabled": True
        })
        return strategy
    
    elif strategy_name == "crypto":
        strategy = CryptoStrategy()
        strategy.configure({
            "price_change_trigger": args.price_change_trigger,
            "enabled": True
        })
        return strategy
    
    elif strategy_name == "rsi":
        strategy = RSIStrategy()
        strategy.configure({
            "upper_threshold": args.rsi_upper,
            "lower_threshold": args.rsi_lower,
            "enabled": True
        })
        return strategy
    
    elif strategy_name == "news_sentiment":
        strategy = NewsSentimentStrategy()
        strategy.configure({
            "sentiment_threshold": 0.6,  # Threshold for bullish sentiment (0-1)
            "bearish_threshold": 0.4,    # Threshold for bearish sentiment (0-1)
            "enabled": True
        })
        return strategy
    
    return None

def run_backtest(args):
    """Run the backtest with provided arguments"""
    # Parse symbols
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Initialize backtest engine
    engine = BacktestEngine(
        initial_capital=args.initial_capital,
        commission=args.commission,
        risk_per_trade=args.risk_per_trade
    )
    
    # Determine which strategies to test
    strategies_to_test = []
    if args.strategy == "all":
        strategy_names = ["polygon", "crypto", "rsi", "news_sentiment"]
        for name in strategy_names:
            strategy = create_strategy(name, args)
            if strategy:
                strategies_to_test.append((name, strategy))
    else:
        strategy = create_strategy(args.strategy, args)
        if strategy:
            strategies_to_test.append((args.strategy, strategy))
    
    if not strategies_to_test:
        logger.error(f"No valid strategies to test")
        return
    
    # Run backtests for each strategy
    results = {}
    for strategy_name, strategy in strategies_to_test:
        logger.info(f"Running backtest for {strategy_name} strategy...")
        strategy_output_dir = os.path.join(args.output_dir, strategy_name)
        os.makedirs(strategy_output_dir, exist_ok=True)
        
        # Run the backtest
        backtest_results = engine.run_backtest(
            strategy=strategy,
            symbols=symbols,
            start_date=args.start_date,
            end_date=args.end_date,
            timeframe=args.timeframe,
            verbose=args.verbose
        )
        
        # Save results
        results[strategy_name] = backtest_results
        
        # Generate plots if requested
        if args.plot:
            engine.plot_results(output_dir=strategy_output_dir)
        
        # Save strategy config
        with open(os.path.join(strategy_output_dir, "strategy_config.txt"), "w") as f:
            f.write(f"Strategy: {strategy_name}\n")
            f.write(f"Symbols: {args.symbols}\n")
            f.write(f"Period: {args.start_date} to {args.end_date}\n")
            f.write(f"Timeframe: {args.timeframe}\n")
            f.write(f"Initial Capital: ${args.initial_capital:.2f}\n")
            f.write(f"Risk Per Trade: {args.risk_per_trade:.2%}\n")
            f.write(f"Commission: {args.commission:.3%}\n")
            
            # Strategy-specific params
            if strategy_name == "polygon":
                f.write(f"Volume Threshold: {args.volume_threshold:.2f}x\n")
                f.write(f"Price Change Trigger: {args.price_change_trigger:.2%}\n")
            elif strategy_name == "rsi":
                f.write(f"RSI Upper: {args.rsi_upper}\n")
                f.write(f"RSI Lower: {args.rsi_lower}\n")
    
    # Print comparison if multiple strategies
    if len(results) > 1:
        logger.info("\n" + "="*50)
        logger.info("STRATEGY COMPARISON")
        logger.info("="*50)
        
        # Compare key metrics
        comparison = {name: {
            "Total Return": f"{res.get('total_return_pct', 0):.2f}%",
            "Sharpe Ratio": f"{res.get('sharpe_ratio', 0):.2f}",
            "Max Drawdown": f"{res.get('max_drawdown_pct', 0):.2f}%",
            "Win Rate": f"{res.get('win_rate_pct', 0):.2f}%"
        } for name, res in results.items()}
        
        # Print as table
        metrics = ["Total Return", "Sharpe Ratio", "Max Drawdown", "Win Rate"]
        
        # Print header
        header = "Metric".ljust(20)
        for name in results.keys():
            header += name.ljust(15)
        logger.info(header)
        logger.info("-" * 80)
        
        # Print rows
        for metric in metrics:
            row = metric.ljust(20)
            for name in results.keys():
                row += comparison[name][metric].ljust(15)
            logger.info(row)
        
        logger.info("="*50)

if __name__ == "__main__":
    args = parse_args()
    
    # Configure logging
    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    
    run_backtest(args) 