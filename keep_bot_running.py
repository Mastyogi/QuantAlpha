"""
Keep Bot Running 24/7 with Auto-Restart
========================================
Monitors bot and restarts if it crashes
"""
import subprocess
import time
import sys
from datetime import datetime

def log(message):
    """Log with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def run_bot():
    """Run bot and restart if it crashes."""
    restart_count = 0
    max_restarts = 10
    restart_delay = 60  # seconds
    
    while restart_count < max_restarts:
        try:
            log("🚀 Starting KellyAI Trading Bot...")
            
            # Start bot process
            process = subprocess.Popen(
                [sys.executable, "run_trading_bot.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            log(f"✅ Bot started (PID: {process.pid})")
            
            # Wait for process to complete
            return_code = process.wait()
            
            if return_code == 0:
                log("✅ Bot stopped normally")
                break
            else:
                log(f"⚠️  Bot crashed with code {return_code}")
                restart_count += 1
                
                if restart_count < max_restarts:
                    log(f"🔄 Restarting in {restart_delay} seconds... (Attempt {restart_count}/{max_restarts})")
                    time.sleep(restart_delay)
                else:
                    log(f"❌ Max restarts ({max_restarts}) reached. Stopping.")
                    break
                    
        except KeyboardInterrupt:
            log("🛑 Shutdown requested by user")
            if process:
                process.terminate()
            break
        except Exception as e:
            log(f"❌ Error: {e}")
            restart_count += 1
            if restart_count < max_restarts:
                time.sleep(restart_delay)
            else:
                break
    
    log("👋 Bot monitor stopped")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("🤖 KellyAI Bot Monitor - 24/7 Auto-Restart")
    print("="*60)
    print("\nThis will keep your bot running 24/7")
    print("Press Ctrl+C to stop\n")
    
    run_bot()
