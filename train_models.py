#!/usr/bin/env python3
"""Train models for all trading pairs."""
import asyncio
import os
from src.data.exchange_client import ExchangeClient
from src.data.data_fetcher import DataFetcher
from src.signals.signal_engine import FineTunedSignalEngine
from config.settings import settings

async def train_all_models():
    print("=" * 70)
    print("Training Models for All Trading Pairs")
    print("=" * 70)
    
    # Initialize
    exchange = ExchangeClient()
    await exchange.initialize()
    fetcher = DataFetcher(exchange)
    engine = FineTunedSignalEngine(model_dir="models")
    
    symbols = settings.trading_pairs
    print(f"\nSymbols to train: {symbols}\n")
    
    for symbol in symbols:
        print(f"\n{'─' * 70}")
        print(f"Training: {symbol}")
        print(f"{'─' * 70}")
        
        try:
            # Fetch maximum historical data (500 candles)
            print(f"  📊 Fetching data...")
            df = await fetcher.get_dataframe(symbol, "1h", limit=500)
            
            if df is None or len(df) < 200:
                print(f"  ❌ Insufficient data: {len(df) if df is not None else 0} candles")
                print(f"     Need at least 200 candles for training")
                continue
            
            print(f"  ✅ Fetched {len(df)} candles")
            print(f"     Date range: {df.index[0]} to {df.index[-1]}")
            print(f"     Latest price: ${df['close'].iloc[-1]:.2f}")
            
            # Train model
            print(f"  🤖 Training ensemble model...")
            metrics = engine.train_model(
                symbol=symbol,
                df=df,
                asset_class="crypto" if "/" in symbol else "forex",
                force_retrain=True
            )
            
            if "error" in metrics:
                print(f"  ❌ Training failed: {metrics['error']}")
                continue
            
            print(f"  ✅ Training complete!")
            print(f"     Precision: {metrics.get('precision', 0):.1%}")
            print(f"     Recall: {metrics.get('recall', 0):.1%}")
            print(f"     F1 Score: {metrics.get('f1', 0):.3f}")
            print(f"     AUC: {metrics.get('auc', 0):.3f}")
            print(f"     Samples: {metrics.get('n_samples', 0)}")
            
            # Test signal generation
            print(f"  🎯 Testing signal generation...")
            signal = await engine.analyze(symbol=symbol, df_1h=df)
            
            print(f"     Direction: {signal.direction}")
            print(f"     Approved: {signal.approved}")
            print(f"     Confidence: {signal.ai_confidence:.2%}")
            print(f"     Confluence: {signal.confluence_score:.0f}/100")
            
            if signal.approved:
                print(f"     ✅ Signal would fire!")
            else:
                print(f"     ℹ️  Rejected: {signal.rejection_reason}")
        
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    await exchange.close()
    
    print(f"\n{'=' * 70}")
    print("Training Complete!")
    print(f"{'=' * 70}")
    
    # List trained models
    model_dir = "models"
    if os.path.exists(model_dir):
        models = [f for f in os.listdir(model_dir) if f.endswith('.joblib')]
        print(f"\n✅ Trained models ({len(models)}):")
        for model in models:
            print(f"   • {model}")
    else:
        print(f"\n⚠️  No models directory found")

if __name__ == "__main__":
    asyncio.run(train_all_models())
