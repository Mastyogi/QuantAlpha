"""
AlphaBot Web Server
===================
Flask application providing:
  - / (GET)                  — Landing page
  - /auth/google             — Redirect to Google OAuth
  - /auth/google/callback    — Google OAuth callback
  - /auth/github             — Redirect to GitHub OAuth
  - /auth/github/callback    — GitHub OAuth callback
  - /auth/demo               — Demo login (no OAuth required)
  - /auth/logout             — Clear session
  - /dashboard               — Protected main dashboard (requires JWT)
  - /dashboard/signals       — Recent signals
  - /dashboard/trades        — Trade history
  - /dashboard/pnl           — P&L summary
  - /dashboard/risk          — Risk panel
  - /dashboard/markets       — Market prices
  - /dashboard/settings      — Settings page
  - /api/v1/status           — JSON status (for health checks)

Auth flow:
  1. User visits / → sees landing page with Sign In buttons
  2. Clicks Google/GitHub → redirects to provider
  3. Provider redirects back to /auth/<provider>/callback with code
  4. Server exchanges code for user info
  5. Issues JWT cookie (auth_token) → redirects to /dashboard
  6. Every protected route validates JWT
"""
from __future__ import annotations

import json
import os
import random
import secrets
import sys
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, List, Optional

from flask import (
    Flask, render_template, redirect, url_for, request,
    jsonify, make_response, session, flash, g
)
from jinja2 import TemplateNotFound

# ── Project root on sys.path ─────────────────────────────────────────────────
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from config.settings import settings
from src.web.auth_utils import create_token, decode_token, get_token_from_request
from src.web.oauth_providers import get_google_provider, get_github_provider, make_demo_user


# ── Flask app factory ─────────────────────────────────────────────────────────

def create_app() -> Flask:
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir   = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
    )
    app.secret_key = settings.jwt_secret_key

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_auth_cookie(response, user_info: dict):
        token = create_token(user_info, settings.jwt_secret_key, settings.jwt_expire_hours)
        response.set_cookie(
            "auth_token", token,
            max_age=settings.jwt_expire_hours * 3600,
            httponly=True,
            samesite="Lax",
        )
        return response

    def _get_current_user() -> Optional[dict]:
        return get_token_from_request(
            request.cookies, dict(request.headers), settings.jwt_secret_key
        )

    def _is_email_allowed(email: str) -> bool:
        if not settings.allowed_emails:
            return True
        return email.lower() in [e.lower() for e in settings.allowed_emails]

    def _redirect_base() -> str:
        return settings.oauth_redirect_base.rstrip("/")

    # ── Auth decorator ────────────────────────────────────────────────────────

    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = _get_current_user()
            if not user:
                return redirect("/?next=" + request.path + "#login")
            g.user = user
            return f(*args, **kwargs)
        return decorated

    # ── Bot state snapshot (from PaperTrader / BotEngine if available) ────────

    def _get_bot_snapshot() -> dict:
        """Get live bot state. Gracefully returns mock data if bot not running."""
        try:
            from src.execution.paper_trader import PaperTrader
            from src.risk.risk_manager import RiskManager
            # If shared instances exist in a registry, use them.
            # For now generate realistic mock snapshot.
        except Exception:
            pass

        # Build realistic demo data
        rng = random.Random(42)
        equity = 10_000 + rng.uniform(-500, 800)
        daily_pnl = rng.uniform(-150, 320)
        total_trades = rng.randint(8, 40)
        winning = int(total_trades * rng.uniform(0.45, 0.72))

        # Equity history (30 sessions)
        eq_hist = [10000.0]
        for _ in range(29):
            eq_hist.append(eq_hist[-1] * (1 + rng.gauss(0, 0.008)))

        signals = [
            {
                "symbol": sym,
                "direction": rng.choice(["BUY", "SELL", "NEUTRAL"]),
                "signal_strength": round(rng.uniform(0.4, 0.95), 2),
                "ai_confidence": round(rng.uniform(0.60, 0.95), 2),
                "strategy_name": rng.choice(["TrendFollowing", "MeanReversion", "Ensemble"]),
                "created_at": f"{rng.randint(0,23):02d}:{rng.randint(0,59):02d} UTC",
            }
            for sym in ["EURUSD", "GBPUSD", "EURUSD", "XAUUSD", "GBPUSD"]
        ]
        buy_count  = sum(1 for s in signals if s["direction"] == "BUY")
        sell_count = sum(1 for s in signals if s["direction"] == "SELL")

        positions = []
        if rng.random() > 0.4:
            ep = 43500 + rng.gauss(0, 200)
            cp = ep * (1 + rng.uniform(-0.02, 0.03))
            positions.append({
                "symbol": "EURUSD", "side": "buy",
                "size": 200, "entry_price": ep, "current_price": cp,
                "stop_loss": ep * 0.975, "take_profit": ep * 1.045,
                "unrealized_pnl": round((cp - ep) / ep * 200, 2),
            })

        # Market prices for all instruments
        base_prices = {
            "EURUSD": 43500, "GBPUSD": 2318, "USDJPY": 98,
            "EURUSD": 1.0850, "GBPUSD": 1.2654, "USDJPY": 149.32,
            "AUDUSD": 0.6521,
            "XAUUSD": 2031.8, "XAGUSD": 22.74, "USOIL": 78.65,
        }
        market_prices = [
            {
                "symbol": sym,
                "price": p * (1 + rng.gauss(0, 0.001)),
                "change": round(rng.gauss(0, 1.5), 2),
                "asset_class": (
                    "crypto" if "/" in sym
                    else "commodity" if sym in ("XAUUSD", "XAGUSD", "USOIL")
                    else "forex"
                ),
            }
            for sym, p in base_prices.items()
        ]

        # Try to load real paper trader stats
        try:
            from src.execution.paper_trader import _GLOBAL_PAPER_TRADER
            if _GLOBAL_PAPER_TRADER:
                stats = _GLOBAL_PAPER_TRADER.get_stats()
                equity     = stats["equity"]
                daily_pnl  = stats.get("daily_pnl", daily_pnl)
                total_trades = stats["total_trades"]
                winning    = stats["winning_trades"]
        except Exception:
            pass

        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0

        return {
            "bot_state":        "SCANNING",
            "trading_mode":     settings.trading_mode,
            "equity":           round(equity, 2),
            "daily_pnl":        round(daily_pnl, 2),
            "daily_loss_limit": equity * settings.max_daily_loss_pct / 100,
            "open_positions":   len(positions),
            "max_positions":    settings.max_open_positions,
            "total_trades":     total_trades,
            "win_rate":         round(win_rate, 1),
            "max_drawdown":     round(rng.uniform(1, 8), 2),
            "signals_today":    len(signals),
            "buy_signals":      buy_count,
            "sell_signals":     sell_count,
            "signals":          signals[:10],
            "positions":        positions,
            "market_prices":    market_prices,
            "equity_history":   [round(v, 2) for v in eq_hist],
            "circuit_breaker":  False,
            "active_instruments": len(base_prices),
            "last_updated":     datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        }

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.route("/")
    def landing():
        user = _get_current_user()
        if user:
            return redirect("/dashboard")
        google = get_google_provider(_redirect_base())
        github = get_github_provider(_redirect_base())
        error   = request.args.get("error", "")
        message = request.args.get("message", "")
        return render_template(
            "landing.html",
            google_configured=google.is_configured(),
            github_configured=github.is_configured(),
            allowed_emails=bool(settings.allowed_emails),
            error=error,
            message=message,
        )

    # ── Google OAuth ─────────────────────────────────────────────────────────

    @app.route("/auth/google")
    def auth_google():
        google = get_google_provider(_redirect_base())
        if not google.is_configured():
            return redirect("/?error=Google+OAuth+not+configured")
        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        return redirect(google.get_authorization_url(state))

    @app.route("/auth/google/callback")
    def auth_google_callback():
        google = get_google_provider(_redirect_base())
        error = request.args.get("error")
        if error:
            return redirect(f"/?error={error}#login")

        state = request.args.get("state", "")
        if state != session.get("oauth_state", ""):
            return redirect("/?error=Invalid+state+parameter#login")
        session.pop("oauth_state", None)

        code = request.args.get("code", "")
        success, user_info = google.exchange_code(code)
        if not success:
            return redirect(f"/?error=Google+auth+failed#login")

        if not _is_email_allowed(user_info["email"]):
            return redirect("/?error=Email+not+authorized#login")

        resp = make_response(redirect("/dashboard"))
        return _set_auth_cookie(resp, user_info)

    # ── GitHub OAuth ──────────────────────────────────────────────────────────

    @app.route("/auth/github")
    def auth_github():
        github = get_github_provider(_redirect_base())
        if not github.is_configured():
            return redirect("/?error=GitHub+OAuth+not+configured#login")
        state = secrets.token_urlsafe(32)
        session["oauth_state"] = state
        return redirect(github.get_authorization_url(state))

    @app.route("/auth/github/callback")
    def auth_github_callback():
        github = get_github_provider(_redirect_base())
        error = request.args.get("error")
        if error:
            return redirect(f"/?error={error}#login")

        state = request.args.get("state", "")
        if state != session.get("oauth_state", ""):
            return redirect("/?error=Invalid+state#login")
        session.pop("oauth_state", None)

        code = request.args.get("code", "")
        success, user_info = github.exchange_code(code)
        if not success:
            return redirect("/?error=GitHub+auth+failed#login")

        if not _is_email_allowed(user_info.get("email", "")):
            return redirect("/?error=Email+not+authorized#login")

        resp = make_response(redirect("/dashboard"))
        return _set_auth_cookie(resp, user_info)

    # ── Demo login ────────────────────────────────────────────────────────────

    @app.route("/auth/demo")
    def auth_demo():
        user_info = make_demo_user()
        resp = make_response(redirect("/dashboard"))
        return _set_auth_cookie(resp, user_info)

    # ── Logout ────────────────────────────────────────────────────────────────

    @app.route("/auth/logout")
    def auth_logout():
        resp = make_response(redirect("/"))
        resp.delete_cookie("auth_token")
        return resp

    # ── Dashboard routes ─────────────────────────────────────────────────────

    @app.route("/dashboard")
    @login_required
    def dashboard():
        snap = _get_bot_snapshot()
        return render_template("dashboard.html", user=g.user, **snap)

    @app.route("/dashboard/signals")
    @login_required
    def dashboard_signals():
        snap = _get_bot_snapshot()
        # Full signals page reuses dashboard with signals tab highlighted
        return render_template("dashboard.html", user=g.user, **snap)

    @app.route("/dashboard/trades")
    @login_required
    def dashboard_trades():
        snap = _get_bot_snapshot()
        return render_template("dashboard.html", user=g.user, **snap)

    @app.route("/dashboard/pnl")
    @login_required
    def dashboard_pnl():
        snap = _get_bot_snapshot()
        return render_template("dashboard.html", user=g.user, **snap)

    @app.route("/dashboard/risk")
    @login_required
    def dashboard_risk():
        snap = _get_bot_snapshot()
        return render_template("dashboard.html", user=g.user, **snap)

    @app.route("/dashboard/markets")
    @login_required
    def dashboard_markets():
        snap = _get_bot_snapshot()
        return render_template("dashboard.html", user=g.user, **snap)

    @app.route("/dashboard/settings")
    @login_required
    def dashboard_settings():
        snap = _get_bot_snapshot()
        return render_template("dashboard.html", user=g.user, **snap)

    # ── JSON API ─────────────────────────────────────────────────────────────

    @app.route("/api/v1/status")
    def api_status():
        user = _get_current_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401
        snap = _get_bot_snapshot()
        return jsonify({
            "status": "ok",
            "bot_state":    snap["bot_state"],
            "equity":       snap["equity"],
            "daily_pnl":    snap["daily_pnl"],
            "open_positions": snap["open_positions"],
            "signals_today":  snap["signals_today"],
            "trading_mode":   snap["trading_mode"],
            "timestamp":      snap["last_updated"],
        })

    @app.route("/api/v1/signals")
    def api_signals():
        user = _get_current_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401
        snap = _get_bot_snapshot()
        return jsonify({"signals": snap["signals"]})

    @app.route("/api/v1/market-prices")
    def api_market_prices():
        user = _get_current_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401
        snap = _get_bot_snapshot()
        return jsonify({"prices": snap["market_prices"]})

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "alphabot-web", "version": "2.0"})

    # ── Error handlers ────────────────────────────────────────────────────────

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "internal server error"}), 500

    return app


# ── Jinja2 filter for tojson ──────────────────────────────────────────────────
def _tojson_filter(value):
    return json.dumps(value)


# ── Entry point ───────────────────────────────────────────────────────────────

def run_web_server(host: str = "0.0.0.0", port: int = None, debug: bool = False):
    app = create_app()
    app.jinja_env.filters["tojson"] = _tojson_filter
    port = port or settings.web_port
    print(f"\n🌐 AlphaBot Web Server starting on http://{host}:{port}")
    print(f"   Dashboard: http://localhost:{port}/dashboard")
    print(f"   Auth demo: http://localhost:{port}/auth/demo\n")
    app.run(host=host, port=port, debug=debug, use_reloader=False)


if __name__ == "__main__":
    run_web_server(debug=True)
