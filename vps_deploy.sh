#!/bin/bash
#  Trading Bot - VPS Deployment Script
# Run this on your VPS as root

set -e

echo "============================================================"
echo "QuantAlpha Trading Bot - VPS Deployment"
echo "============================================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Variables
BOT_DIR="/opt/quantalpha"
VENV_DIR="$BOT_DIR/venv"
SERVICE_NAME="quantalpha"

# Step 1: System Update
echo -e "${YELLOW}Step 1: Updating system...${NC}"
apt update && apt upgrade -y

# Step 2: Install Dependencies
echo -e "${YELLOW}Step 2: Installing dependencies...${NC}"
apt install -y python3 python3-pip python3-venv git build-essential \
    libssl-dev libffi-dev python3-dev htop

# Step 3: Create Directory
echo -e "${YELLOW}Step 3: Creating bot directory...${NC}"
mkdir -p $BOT_DIR
cd $BOT_DIR

# Step 4: Setup Virtual Environment
echo -e "${YELLOW}Step 4: Setting up virtual environment...${NC}"
python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# Step 5: Install Python Packages
echo -e "${YELLOW}Step 5: Installing Python packages...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# Step 6: Create Logs Directory
echo -e "${YELLOW}Step 6: Creating logs directory...${NC}"
mkdir -p $BOT_DIR/logs

# Step 7: Create Systemd Service
echo -e "${YELLOW}Step 7: Creating systemd service...${NC}"
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

# Step 8: Enable and Start Service
echo -e "${YELLOW}Step 8: Enabling service...${NC}"
systemctl daemon-reload
systemctl enable $SERVICE_NAME

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo "Next steps:"
echo "1. Upload your bot files to: $BOT_DIR"
echo "2. Create .env file: nano $BOT_DIR/.env"
echo "3. Start bot: systemctl start $SERVICE_NAME"
echo "4. Check status: systemctl status $SERVICE_NAME"
echo "5. View logs: journalctl -u $SERVICE_NAME -f"
echo ""
echo "Management commands:"
echo "  Start:   systemctl start $SERVICE_NAME"
echo "  Stop:    systemctl stop $SERVICE_NAME"
echo "  Restart: systemctl restart $SERVICE_NAME"
echo "  Status:  systemctl status $SERVICE_NAME"
echo "  Logs:    journalctl -u $SERVICE_NAME -f"
echo ""
