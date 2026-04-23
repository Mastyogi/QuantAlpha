"""
Backtest Runner CLI
====================
Run vectorized backtests + Monte Carlo from the command line.

Usage:
  python scripts/run_backtest.py --symbol BTC/USDT --timeframe 1h --bars 2000
  python scripts/run_backtest.py --symbol BTC/USDT --walk-forward
  python scripts/run_backtest.py --symbol BTC/USDT --monte-carlo --sims 10000
"""
import asyncio, argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def main():
    parser = argparse.ArgumentParser(description="AI Trading Backtest Runner")
    parser.add_argument("--symbol",       default="BTC/USDT")
    parser.add_argument("--timeframe",    default="1h")
    parser.add_argument("--bars",         type=int, default=1000)
    parser.add_argument("--capital",      type=float, default=10000.0)
    parser.add_argument("--risk",         type=float, default=1.0)
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--monte-carlo",  action="store_true")
    parser.add_argument("--sims",         type=int, default=10000)
    parser.add_argument("--output",       default="reports")
    args = parser.parse_args()

    from src.utils.logger import setup_logging, get_logger
    setup_logging(level="INFO")
    logger = get_logger("backtest")

    from src.data.exchange_client import ExchangeClient
    from src.data.data_fetcher import DataFetcher
    from src.backtesting.backtester import VectorizedBacktester
    from src.backtesting.report_generator import BacktestReportGenerator
    from config.settings import settings

    print(f"\n{'═'*55}")
    print(f"  BACKTEST: {args.symbol} {args.timeframe} | {args.bars} bars")
    print(f"  Capital: ${args.capital:,.0f} | Risk: {args.risk}%/trade")
    print(f"{'═'*55}")

    exchange = ExchangeClient()
    await exchange.initialize()
    fetcher  = DataFetcher(exchange)

    try:
        df = await fetcher.get_dataframe(args.symbol, args.timeframe, limit=args.bars)
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        await exchange.close()
        return
    await exchange.close()

    print(f"✅ Fetched {len(df)} candles")

    # Run backtest
    bt     = VectorizedBacktester()
    result = bt.run(df, args.symbol, args.timeframe,
                    initial_capital=args.capital,
                    risk_per_trade_pct=args.risk)

    metrics = {
        "total_trades":     result.total_trades,
        "win_rate":         result.win_rate,
        "profit_factor":    result.profit_factor,
        "sharpe_ratio":     result.sharpe_ratio,
        "total_return_pct": result.total_return_pct,
        "max_drawdown_pct": result.max_drawdown_pct,
        "avg_win_pct":      result.avg_win_pct,
        "avg_loss_pct":     result.avg_loss_pct,
    }
    print("\n" + result.summary())

    mc_result = None
    if args.monte_carlo and result.trades:
        from src.backtesting.monte_carlo import MonteCarloSimulator
        returns = [t.pnl_pct / 100 for t in result.trades if t.pnl_pct != 0]
        if len(returns) >= 10:
            print(f"\n⏳ Running {args.sims:,} Monte Carlo simulations...")
            mc = MonteCarloSimulator(n_simulations=args.sims)
            mc_result = mc.run(returns, initial_equity=args.capital)
            print("\n" + mc_result.summary())
        else:
            print("⚠️  Not enough trades for Monte Carlo (need ≥10)")

    if args.walk_forward:
        from src.backtesting.walk_forward import WalkForwardValidator
        print("\n⏳ Running walk-forward validation (5 folds)...")
        try:
            wfv    = WalkForwardValidator(n_folds=5, min_train_bars=150)
            report = wfv.validate(df, symbol=args.symbol)
            ready, reason = wfv.is_production_ready(report)
            print(f"\nOOS Accuracy:  {report.oos_accuracy:.1%}")
            print(f"OOS Precision: {report.oos_precision:.1%}")
            print(f"Production Ready: {'✅ YES' if ready else '❌ NO — ' + reason}")
        except Exception as e:
            print(f"⚠️  Walk-forward failed: {e}")

    # Generate report
    reporter = BacktestReportGenerator(output_dir=args.output)
    trades_dicts = [
        {"direction": t.direction, "entry_price": t.entry_price,
         "exit_price": t.exit_price, "pnl_pct": t.pnl_pct,
         "exit_reason": t.exit_reason}
        for t in result.trades
    ]
    html_path = reporter.generate_html(args.symbol, args.timeframe, metrics,
                                        trades_dicts, mc_result=mc_result)
    print(f"\n📊 HTML report: {html_path}")

if __name__ == "__main__":
    asyncio.run(main())
