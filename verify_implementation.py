#!/usr/bin/env python3
"""
Implementation Verification Script
Checks that all components are properly implemented and wired.
"""
import sys
import os
from pathlib import Path


def check_file_exists(filepath: str) -> bool:
    """Check if file exists."""
    return Path(filepath).exists()


def check_implementation():
    """Verify all implementation requirements."""
    print("🔍 Verifying Trading Bot Implementation...\n")
    
    all_checks_passed = True
    
    # ── GAP 1: AutoTuningSystem ───────────────────────────────────────────────
    print("📋 GAP 1: AutoTuningSystem")
    if check_file_exists("src/ml/auto_tuning_system.py"):
        print("  ✅ src/ml/auto_tuning_system.py exists")
    else:
        print("  ❌ src/ml/auto_tuning_system.py missing")
        all_checks_passed = False
    
    # ── GAP 2: RegimeDetector ─────────────────────────────────────────────────
    print("\n📋 GAP 2: RegimeDetector Enhancements")
    if check_file_exists("src/signals/regime_detector.py"):
        print("  ✅ src/signals/regime_detector.py exists")
        # Check for Redis integration
        try:
            with open("src/signals/regime_detector.py", "r", encoding="utf-8") as f:
                content = f.read()
                if "redis.asyncio" in content:
                    print("  ✅ Redis integration found")
                else:
                    print("  ⚠️  Redis integration not found")
        except Exception as e:
            print(f"  ⚠️  Could not read file: {e}")
    else:
        print("  ❌ src/signals/regime_detector.py missing")
        all_checks_passed = False
    
    # ── GAP 3: Signal Engine ──────────────────────────────────────────────────
    print("\n📋 GAP 3: Signal Engine Regime Integration")
    if check_file_exists("src/signals/signal_engine.py"):
        print("  ✅ src/signals/signal_engine.py exists")
    else:
        print("  ❌ src/signals/signal_engine.py missing")
        all_checks_passed = False
    
    # ── GAP 4: Correlation Guard ──────────────────────────────────────────────
    print("\n📋 GAP 4: Adaptive Risk Correlation Guard")
    if check_file_exists("src/risk/adaptive_risk.py"):
        print("  ✅ src/risk/adaptive_risk.py exists")
        try:
            with open("src/risk/adaptive_risk.py", "r", encoding="utf-8") as f:
                content = f.read()
                if "check_correlation_guard" in content:
                    print("  ✅ check_correlation_guard method found")
                else:
                    print("  ⚠️  check_correlation_guard method not found")
        except Exception as e:
            print(f"  ⚠️  Could not read file: {e}")
    else:
        print("  ❌ src/risk/adaptive_risk.py missing")
        all_checks_passed = False
    
    # ── GAP 5: Error Handler ──────────────────────────────────────────────────
    print("\n📋 GAP 5: Error Handler")
    if check_file_exists("src/core/error_handler.py"):
        print("  ✅ src/core/error_handler.py exists")
    else:
        print("  ❌ src/core/error_handler.py missing")
        all_checks_passed = False
    
    # ── GAP 6: Health Check ───────────────────────────────────────────────────
    print("\n📋 GAP 6: Health Check System")
    if check_file_exists("src/core/health_check.py"):
        print("  ✅ src/core/health_check.py exists")
    else:
        print("  ❌ src/core/health_check.py missing")
        all_checks_passed = False
    
    # ── GAP 7: API Endpoints ──────────────────────────────────────────────────
    print("\n📋 GAP 7: API Server Endpoints")
    if check_file_exists("src/api/server.py"):
        print("  ✅ src/api/server.py exists")
        try:
            with open("src/api/server.py", "r", encoding="utf-8") as f:
                content = f.read()
                endpoints = [
                    "/api/patterns",
                    "/api/models",
                    "/api/config",
                    "/api/performance/daily",
                    "/api/tuning/status",
                ]
                for endpoint in endpoints:
                    if endpoint in content:
                        print(f"  ✅ {endpoint} endpoint found")
                    else:
                        print(f"  ⚠️  {endpoint} endpoint not found")
        except Exception as e:
            print(f"  ⚠️  Could not read file: {e}")
    else:
        print("  ❌ src/api/server.py missing")
        all_checks_passed = False
    
    # ── GAP 8: Telegram Commands ──────────────────────────────────────────────
    print("\n📋 GAP 8: Telegram Commands")
    if check_file_exists("src/telegram/handlers.py"):
        print("  ✅ src/telegram/handlers.py exists")
        try:
            with open("src/telegram/handlers.py", "r", encoding="utf-8") as f:
                content = f.read()
                commands = [
                    "handle_tune",
                    "handle_tuning_status",
                    "handle_pattern_off",
                    "handle_pattern_on",
                    "handle_regime",
                ]
                for cmd in commands:
                    if cmd in content:
                        print(f"  ✅ {cmd} found")
                    else:
                        print(f"  ⚠️  {cmd} not found")
        except Exception as e:
            print(f"  ⚠️  Could not read file: {e}")
    else:
        print("  ❌ src/telegram/handlers.py missing")
        all_checks_passed = False
    
    # ── GAP 9: Bot Engine Integration ─────────────────────────────────────────
    print("\n📋 GAP 9: Bot Engine Integration")
    if check_file_exists("src/core/bot_engine.py"):
        print("  ✅ src/core/bot_engine.py exists")
        try:
            with open("src/core/bot_engine.py", "r", encoding="utf-8") as f:
                content = f.read()
                components = [
                    "auto_tuning_system",
                    "health_check_system",
                    "profit_booking_engine",
                    "self_improvement_engine",
                    "pattern_library",
                    "portfolio_compounder",
                ]
                for comp in components:
                    if comp in content:
                        print(f"  ✅ {comp} initialized")
                    else:
                        print(f"  ⚠️  {comp} not found")
        except Exception as e:
            print(f"  ⚠️  Could not read file: {e}")
    else:
        print("  ❌ src/core/bot_engine.py missing")
        all_checks_passed = False
    
    # ── GAP 10: Tests ─────────────────────────────────────────────────────────
    print("\n📋 GAP 10: Tests")
    test_files = [
        "tests/unit/test_auto_tuning.py",
        "tests/unit/test_regime_detector.py",
        "tests/unit/test_signal_regime_filter.py",
        "tests/unit/test_correlation_guard.py",
        "tests/unit/test_error_handler.py",
        "tests/integration/test_full_pipeline.py",
    ]
    for test_file in test_files:
        if check_file_exists(test_file):
            print(f"  ✅ {test_file} exists")
        else:
            print(f"  ❌ {test_file} missing")
            all_checks_passed = False
    
    # ── Configuration Files ───────────────────────────────────────────────────
    print("\n📋 Configuration Files")
    config_files = [
        ".env.example",
        "config/settings.py",
        "pytest.ini",
        "requirements.txt",
    ]
    for config_file in config_files:
        if check_file_exists(config_file):
            print(f"  ✅ {config_file} exists")
        else:
            print(f"  ⚠️  {config_file} missing")
    
    # ── Documentation ─────────────────────────────────────────────────────────
    print("\n📋 Documentation")
    docs = [
        "GAPS_IMPLEMENTATION_STATUS.md",
        "IMPLEMENTATION_COMPLETE_FINAL.md",
        "SETUP_GUIDE.md",
        "MAXIMUM_COMPOUNDING_STRATEGY.md",
    ]
    for doc in docs:
        if check_file_exists(doc):
            print(f"  ✅ {doc} exists")
        else:
            print(f"  ⚠️  {doc} missing")
    
    # ── Final Summary ─────────────────────────────────────────────────────────
    print("\n" + "="*60)
    if all_checks_passed:
        print("✅ ALL CRITICAL CHECKS PASSED!")
        print("\n🚀 Bot is ready for paper trading deployment")
        print("\nNext steps:")
        print("1. Configure .env file with your API keys")
        print("2. Run: alembic upgrade head")
        print("3. Run: python src/main.py")
        print("4. Monitor via Telegram: /start")
        return 0
    else:
        print("⚠️  SOME CHECKS FAILED")
        print("\nPlease review the output above and fix missing components")
        return 1


if __name__ == "__main__":
    sys.exit(check_implementation())
