from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import jwt
from datetime import datetime, timedelta
from config.settings import settings
from src.utils.logger import get_logger
import os

logger = get_logger(__name__)

# Rate limiter - prevent starlette from reading .env (encoding issues on Windows)
# Environment variables are already loaded by python-dotenv in start.py
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("REDIS_URL", "memory://"),
    config_filename=None  # Don't read .env - already loaded by python-dotenv
)

# Security
security = HTTPBearer()


def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return payload."""
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_jwt_token(user_id: str, email: str) -> str:
    """Create JWT token for user."""
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours)
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def create_api_server(engine=None, health_check_system=None) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Trading Bot API",
        description="REST API for monitoring and controlling the trading bot",
        version="1.0.0",
    )

    # Add rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health_check():
        """Simple health check endpoint."""
        return {"status": "ok", "service": "trading-bot"}
    
    @app.get("/health/detailed")
    async def detailed_health_check():
        """Detailed health check with component status."""
        if health_check_system:
            await health_check_system.check_all_components()
            return health_check_system.get_health_report()
        return {
            "overall_status": "unknown",
            "message": "Health check system not configured"
        }

    @app.get("/api/status")
    async def get_status():
        if engine:
            return await engine.get_status()
        return {"status": "no_engine"}

    @app.get("/api/signals")
    async def get_signals():
        from src.database.repositories import SignalRepository
        repo = SignalRepository()
        signals = await repo.get_recent_signals(limit=20)
        return [
            {
                "id": s.id,
                "symbol": s.symbol,
                "direction": s.direction.value if s.direction else None,
                "strategy": s.strategy_name,
                "confidence": s.ai_confidence,
                "entry": s.entry_price,
                "created_at": str(s.created_at),
            }
            for s in signals
        ]

    @app.get("/api/trades")
    async def get_trades():
        from src.database.repositories import TradeRepository
        repo = TradeRepository()
        trades = await repo.get_recent_trades(limit=20)
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "direction": t.direction.value if t.direction else None,
                "status": t.status.value if t.status else None,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "is_paper": t.is_paper_trade,
                "opened_at": str(t.opened_at),
            }
            for t in trades
        ]

    @app.get("/api/pnl")
    async def get_pnl():
        from src.database.repositories import TradeRepository
        repo = TradeRepository()
        stats = await repo.get_daily_stats()
        return stats
    
    # ── GAP 7: New API Endpoints ──────────────────────────────────────────────
    
    @app.get("/api/patterns")
    @limiter.limit("100/minute")
    async def get_patterns(request: Request, user: dict = Depends(verify_jwt_token)):
        """Get all trading patterns from pattern library."""
        from src.database.pattern_library import PatternLibrary
        pattern_lib = PatternLibrary()
        patterns = await pattern_lib.get_top_patterns(limit=50)
        return {
            "patterns": [
                {
                    "id": p.id,
                    "name": p.name,
                    "win_rate": p.win_rate,
                    "profit_factor": p.profit_factor,
                    "sharpe_ratio": p.sharpe_ratio,
                    "trade_count": p.trade_count,
                    "regime": p.regime,
                    "is_active": p.is_active,
                }
                for p in patterns
            ]
        }
    
    @app.post("/api/patterns/{pattern_id}/toggle")
    @limiter.limit("100/minute")
    async def toggle_pattern(
        request: Request,
        pattern_id: str,
        user: dict = Depends(verify_jwt_token)
    ):
        """Toggle pattern active status."""
        from src.database.pattern_library import PatternLibrary
        pattern_lib = PatternLibrary()
        success = await pattern_lib.toggle_pattern(pattern_id)
        return {"success": success, "pattern_id": pattern_id}
    
    @app.get("/api/models")
    @limiter.limit("100/minute")
    async def get_models(request: Request, user: dict = Depends(verify_jwt_token)):
        """Get all deployed models."""
        from src.ml.self_improvement_engine import DeploymentManager
        deployment_mgr = DeploymentManager()
        models = await deployment_mgr.get_all_deployments()
        return {
            "models": [
                {
                    "symbol": m.symbol,
                    "version": m.version,
                    "precision": m.precision,
                    "deployed_at": m.deployed_at.isoformat(),
                    "is_active": m.is_active,
                }
                for m in models
            ]
        }
    
    @app.post("/api/models/{symbol}/activate")
    @limiter.limit("100/minute")
    async def activate_model(
        request: Request,
        symbol: str,
        version: str,
        user: dict = Depends(verify_jwt_token)
    ):
        """Activate a specific model version."""
        from src.ml.self_improvement_engine import DeploymentManager
        deployment_mgr = DeploymentManager()
        success = await deployment_mgr.activate_version(symbol, version)
        return {"success": success, "symbol": symbol, "version": version}
    
    @app.get("/api/config")
    @limiter.limit("100/minute")
    async def get_config(request: Request, user: dict = Depends(verify_jwt_token)):
        """Get current bot configuration."""
        return {
            "trading_mode": settings.trading_mode,
            "confluence_threshold": settings.confluence_threshold,
            "ai_confidence_threshold": settings.ai_confidence_threshold,
            "risk_per_trade_pct": settings.risk_per_trade_pct,
            "max_position_size_pct": settings.max_position_size_pct,
            "max_daily_loss_pct": settings.max_daily_loss_pct,
            "max_drawdown_pct": settings.max_drawdown_pct,
            "max_open_positions": settings.max_open_positions,
            "trading_pairs": settings.trading_pairs,
            "enable_forex": settings.enable_forex,
            "enable_commodities": settings.enable_commodities,
        }
    
    @app.post("/api/config")
    @limiter.limit("100/minute")
    async def update_config(
        request: Request,
        config_updates: dict,
        user: dict = Depends(verify_jwt_token)
    ):
        """Update bot configuration (requires approval)."""
        from src.telegram.approval_system import ApprovalSystem, ProposalType
        approval_system = ApprovalSystem()
        
        proposal_id = await approval_system.create_proposal(
            proposal_type=ProposalType.PARAMETER_CHANGE,
            title="Configuration Update",
            description=f"Update configuration: {config_updates}",
            metadata={"config_updates": config_updates}
        )
        
        return {"proposal_id": proposal_id, "status": "pending_approval"}
    
    @app.get("/api/performance/daily")
    @limiter.limit("100/minute")
    async def get_daily_performance(request: Request, user: dict = Depends(verify_jwt_token)):
        """Get daily performance statistics."""
        from src.database.repositories import TradeRepository
        repo = TradeRepository()
        stats = await repo.get_daily_stats()
        return stats
    
    @app.get("/api/performance/summary")
    @limiter.limit("100/minute")
    async def get_performance_summary(request: Request, user: dict = Depends(verify_jwt_token)):
        """Get overall performance summary."""
        if engine:
            status = await engine.get_status()
            return {
                "equity": status["equity"],
                "daily_pnl": status["daily_pnl"],
                "win_rate_today": status["win_rate_today"],
                "trades_today": status["trades_today"],
                "open_positions": status["open_positions"],
            }
        return {"error": "Engine not available"}
    
    @app.get("/api/risk/events")
    @limiter.limit("100/minute")
    async def get_risk_events(request: Request, user: dict = Depends(verify_jwt_token)):
        """Get recent risk events (circuit breakers, drawdowns)."""
        from src.database.repositories import AuditLogRepository
        repo = AuditLogRepository()
        events = await repo.get_recent_risk_events(limit=50)
        return {
            "events": [
                {
                    "event_type": e.event_type,
                    "details": e.details,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in events
            ]
        }
    
    @app.post("/api/backtest")
    @limiter.limit("10/minute")
    async def run_backtest(
        request: Request,
        backtest_params: dict,
        user: dict = Depends(verify_jwt_token)
    ):
        """Run backtest with given parameters."""
        from src.backtesting.backtester import Backtester
        
        symbol = backtest_params.get("symbol", "EURUSD")
        start_date = backtest_params.get("start_date")
        end_date = backtest_params.get("end_date")
        
        backtester = Backtester(initial_capital=10000.0)
        results = await backtester.run(symbol, start_date, end_date)
        
        return {
            "symbol": symbol,
            "results": results,
            "status": "completed"
        }
    
    @app.get("/api/tuning/status")
    @limiter.limit("100/minute")
    async def get_tuning_status(request: Request, user: dict = Depends(verify_jwt_token)):
        """Get auto-tuning system status."""
        if engine and hasattr(engine, 'auto_tuning_system'):
            status = engine.auto_tuning_system.get_status()
            return status
        return {"error": "Auto-tuning system not available"}
    
    @app.post("/api/tuning/trigger")
    @limiter.limit("10/minute")
    async def trigger_tuning(request: Request, user: dict = Depends(verify_jwt_token)):
        """Manually trigger parameter optimization."""
        if engine and hasattr(engine, 'auto_tuning_system'):
            result = await engine.auto_tuning_system.optimize()
            return {
                "status": "completed",
                "best_sharpe": result.best_sharpe,
                "oos_sharpe": result.out_of_sample_sharpe,
                "trials": result.trials_completed,
            }
        return {"error": "Auto-tuning system not available"}

    return app
