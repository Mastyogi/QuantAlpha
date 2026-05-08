#!/usr/bin/env bash
# ============================================================
# QuantAlpha — 24/7 Auto Training Runner (Linux / VPS)
# Usage:
#   chmod +x run_training.sh
#   ./run_training.sh              # foreground with auto-restart
#   ./run_training.sh --daemon     # background (nohup)
#   ./run_training.sh --stop       # kill running instance
#   ./run_training.sh --status     # check if running
#   ./run_training.sh --logs       # tail live logs
# ============================================================

set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"
LOG_DIR="$SCRIPT_DIR/logs"
MODEL_DIR="$SCRIPT_DIR/models"
PID_FILE="$SCRIPT_DIR/.ci_system.pid"
LOG_FILE="$LOG_DIR/training_$(date +%Y%m%d).log"
RESTART_DELAY=15          # seconds between restarts
PYTHON_MIN="3.10"

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; GRAY='\033[0;37m'; NC='\033[0m'

banner() {
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}  QuantAlpha 24/7 Continuous Improvement System${NC}"
    echo -e "${GRAY}  $(date '+%Y-%m-%d %H:%M:%S UTC')${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

step()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*" >&2; }
info()  { echo -e "${GRAY}    $*${NC}"; }

# ── Argument parsing ──────────────────────────────────────────────────────────
MODE="foreground"
for arg in "$@"; do
    case $arg in
        --daemon|-d)  MODE="daemon"   ;;
        --stop)       MODE="stop"     ;;
        --status)     MODE="status"   ;;
        --logs|-l)    MODE="logs"     ;;
        --help|-h)    MODE="help"     ;;
    esac
done

# ── Help ──────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "help" ]]; then
    echo "Usage: $0 [--daemon|--stop|--status|--logs|--help]"
    echo ""
    echo "  (no flag)   Run in foreground with auto-restart"
    echo "  --daemon    Run in background (nohup), write PID to .ci_system.pid"
    echo "  --stop      Kill the background daemon"
    echo "  --status    Show if daemon is running"
    echo "  --logs      Tail live log file"
    exit 0
fi

# ── Stop ──────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "stop" ]]; then
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            rm -f "$PID_FILE"
            echo -e "${GREEN}Stopped PID $PID${NC}"
        else
            warn "PID $PID not running. Removing stale PID file."
            rm -f "$PID_FILE"
        fi
    else
        warn "No PID file found. Is the daemon running?"
    fi
    exit 0
fi

# ── Status ────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "status" ]]; then
    if [[ -f "$PID_FILE" ]]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo -e "${GREEN}✅  Running  (PID $PID)${NC}"
            echo -e "    Log: $LOG_FILE"
            # Show last 5 lines of log
            if [[ -f "$LOG_FILE" ]]; then
                echo ""
                echo "Last 5 log lines:"
                tail -5 "$LOG_FILE" | sed 's/^/    /'
            fi
        else
            echo -e "${RED}❌  Not running (stale PID $PID)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️   No PID file — daemon not started${NC}"
    fi
    exit 0
fi

# ── Logs ──────────────────────────────────────────────────────────────────────
if [[ "$MODE" == "logs" ]]; then
    if [[ -f "$LOG_FILE" ]]; then
        echo -e "${CYAN}Tailing $LOG_FILE  (Ctrl+C to stop)${NC}"
        tail -f "$LOG_FILE"
    else
        warn "Log file not found: $LOG_FILE"
        # Try any log file
        LATEST=$(ls -t "$LOG_DIR"/training_*.log 2>/dev/null | head -1)
        if [[ -n "$LATEST" ]]; then
            echo -e "${CYAN}Tailing $LATEST${NC}"
            tail -f "$LATEST"
        else
            err "No log files found in $LOG_DIR"
        fi
    fi
    exit 0
fi

# ── Pre-flight ────────────────────────────────────────────────────────────────
banner
cd "$SCRIPT_DIR"

# Python check
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    err "Python not found. Install Python $PYTHON_MIN+"
    exit 1
fi
PYTHON=$(command -v python3 || command -v python)
PY_VER=$($PYTHON --version 2>&1)
step "Python: $PY_VER  ($PYTHON)"

# Create dirs
mkdir -p "$LOG_DIR" "$MODEL_DIR"
step "Directories: logs/  models/"

# Virtual environment
if [[ ! -d "$VENV_DIR" ]]; then
    step "Creating virtual environment at .venv ..."
    $PYTHON -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
PYTHON="$VENV_DIR/bin/python"
step "Virtualenv activated: $VENV_DIR"

# Install / upgrade dependencies
step "Installing dependencies (pip install -r requirements.txt)..."
pip install -r requirements.txt -q --no-warn-script-location \
    2>&1 | tee "$LOG_DIR/pip_install.log" | grep -E "^(ERROR|WARNING|Successfully)" || true
info "Full pip log: $LOG_DIR/pip_install.log"

# PYTHONPATH
export PYTHONPATH="$SCRIPT_DIR"
step "PYTHONPATH=$PYTHONPATH"

# ── Core run function ─────────────────────────────────────────────────────────
run_ci() {
    local iter=0
    while true; do
        iter=$((iter + 1))
        TS=$(date '+%H:%M:%S')
        echo ""
        echo -e "${CYAN}[$TS] ▶  Run #$iter — continuous_improvement_system.py${NC}"

        # Run and capture exit code
        set +e
        "$PYTHON" continuous_improvement_system.py 2>&1 | tee -a "$LOG_FILE"
        EXIT_CODE=${PIPESTATUS[0]}
        set -e

        TS=$(date '+%H:%M:%S')
        if [[ $EXIT_CODE -eq 0 ]]; then
            echo -e "${GREEN}[$TS] Exited cleanly.${NC}"
        else
            echo -e "${RED}[$TS] Crashed (exit $EXIT_CODE). Check $LOG_FILE${NC}"
        fi

        echo -e "${GRAY}    Restarting in ${RESTART_DELAY}s... (Ctrl+C to stop)${NC}"
        sleep "$RESTART_DELAY"
    done
}

# ── Daemon mode ───────────────────────────────────────────────────────────────
if [[ "$MODE" == "daemon" ]]; then
    # Kill existing daemon if running
    if [[ -f "$PID_FILE" ]]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            warn "Killing existing daemon (PID $OLD_PID)..."
            kill "$OLD_PID"
            sleep 2
        fi
    fi

    step "Starting daemon (nohup)..."
    nohup bash -c "
        source '$VENV_DIR/bin/activate'
        export PYTHONPATH='$SCRIPT_DIR'
        cd '$SCRIPT_DIR'
        $(declare -f run_ci)
        run_ci
    " >> "$LOG_FILE" 2>&1 &

    DAEMON_PID=$!
    echo "$DAEMON_PID" > "$PID_FILE"

    sleep 2
    if kill -0 "$DAEMON_PID" 2>/dev/null; then
        echo ""
        echo -e "${GREEN}✅  Daemon started!${NC}"
        info "PID      : $DAEMON_PID"
        info "PID file : $PID_FILE"
        info "Log file : $LOG_FILE"
        echo ""
        echo -e "${CYAN}Commands:${NC}"
        echo "  ./run_training.sh --status   # check status"
        echo "  ./run_training.sh --logs     # tail live logs"
        echo "  ./run_training.sh --stop     # stop daemon"
    else
        err "Daemon failed to start. Check $LOG_FILE"
        exit 1
    fi
    exit 0
fi

# ── Foreground mode ───────────────────────────────────────────────────────────
echo -e "${GRAY}  Log file : $LOG_FILE${NC}"
echo -e "${GRAY}  Stop     : Ctrl+C${NC}"
echo ""

# Trap Ctrl+C
trap 'echo ""; echo -e "${YELLOW}Stopped by user.${NC}"; exit 0' INT TERM

run_ci
