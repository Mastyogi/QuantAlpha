#!/bin/bash
# QuantAlpha Trading Bot - One-Click VPS Deployment
# Run this script on your VPS

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables
BOT_DIR="/opt/quantalpha"
VENV_DIR="$BOT_DIR/venv"
SERVICE_NAME="quantalpha"

echo -e "${BLUE}"
echo "============================================================"
echo "  QuantAlpha Trading Bot - VPS Deployment Script"
echo "============================================================"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Please run as root (use: sudo bash deploy_to_vps.sh)${NC}"
    exit 1
fi

# Step 1: Update System
echo -e "${YELLOW}[1/8] Updating system...${NC}"
apt update && apt upgrade -y

# Step 2: Install Dependencies
echo -e "${YELLOW}[2/8] Installing dependencies...${NC}"
apt install -y python3 python3-pip python3-venv git build-essential \
    libssl-dev libffi-dev python3-dev htop curl

# Step 3: Check if bot directory exists
if [ ! -d "$BOT_DIR" ]; then
    echo -e "${RED}Error: Bot directory not found at $BOT_DIR${NC}"
    echo -e "${YELLOW}Please upload your bot files first:${NC}"
    echo "  scp -r /path/to/trading-bot/* root@YOUR_VPS_IP:/opt/quantalpha/"
    exit 1
fi

cd $BOT_DIR

# Step 4: Setup Virtual Environment
echo -e "${YELLOW}[3/8] Setting up virtual environment...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv $VENV_DIR
fi
source $VENV_DIR/bin/activate

# Step 5: Install Python Packages
echo -e "${YELLOW}[4/8] Installing Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Step 6: Check .env file
echo -e "${YELLOW}[5/8] Checking configuration...${NC}"
if [ ! -f "$BOT_DIR/.env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo -e "${YELLOW}Creating template .env file...${NC}"
    cp .env.example .env 2>/dev/null || touch .env
    echo -e "${YELLOW}Please edit .env file and run this script again:${NC}"
    echo "  nano $BOT_DIR/.env"
    exit 1
fi

# Step 7: Create Logs Directory
echo -e "${YELLOW}[6/8] Creating logs directory...${NC}"
mkdir -p $BOT_DIR/logs

# Step 8: Create Systemd Service
echo -e "${YELLOW}[7/8] Creating systemd service...${NC}"
cat > /etc/systemd/system/$SERVICE_NAME.service << EOF
[Unit]
Description=QuantAlpha Trading Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$BOT_DIR
Environment="PATH=$VENV_DIR/bin"
ExecStart=$VENV_DIR/bin/python3 $BOT_DIR/run_trading_bot.py
Restart=always
RestartSec=10
StandardOutput=append:$BOT_DIR/logs/bot.log
StandardError=append:$BOT_DIR/logs/bot_error.log

[Install]
WantedBy=multi-user.target
EOF

# Step 9: Enable and Start Service
echo -e "${YELLOW}[8/8] Starting bot service...${NC}"
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl restart $SERVICE_NAME

# Wait a moment for service to start
sleep 3

# Check status
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}"
    echo "============================================================"
    echo "  ✅ DEPLOYMENT SUCCESSFUL!"
    echo "============================================================"
    echo -e "${NC}"
    echo ""
    echo -e "${GREEN}Bot is now running!${NC}"
    echo ""
    echo "📊 Check status:"
    echo "  systemctl status $SERVICE_NAME"
    echo ""
    echo "📝 View logs:"
    echo "  journalctl -u $SERVICE_NAME -f"
    echo ""
    echo "🎮 Management commands:"
    echo "  systemctl start $SERVICE_NAME    # Start bot"
    echo "  systemctl stop $SERVICE_NAME     # Stop bot"
    echo "  systemctl restart $SERVICE_NAME  # Restart bot"
    echo ""
    echo "📱 Test in Telegram:"
    echo "  Send /status to your bot"
    echo ""
    echo -e "${GREEN}Your bot is LIVE! 🚀${NC}"
    echo ""
else
    echo -e "${RED}"
    echo "============================================================"
    echo "  ❌ DEPLOYMENT FAILED"
    echo "============================================================"
    echo -e "${NC}"
    echo ""
    echo "Check logs for errors:"
    echo "  journalctl -u $SERVICE_NAME -n 50"
    echo ""
    echo "Common issues:"
    echo "  1. Missing .env file"
    echo "  2. Invalid configuration"
    echo "  3. Missing dependencies"
    echo ""
    exit 1
fi
