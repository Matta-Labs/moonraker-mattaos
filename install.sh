#!/bin/bash

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

# Function to echo colored text
function color_echo {
    local message="$1"
    echo -e "${BLUE}${message}${NC}"
}

color_echo "Initiating installation of moonraker-mattaconnect..."

# Debug:
echo -e "User is: $USER"

# Install required packages
color_echo "Installing required packages..."
sudo apt-get update
# This is only necessary for virtual-klipper-printer # TODO: remove
sudo apt-get install -y python3-virtualenv systemctl nano
color_echo "Required packages installed successfully"

# Set up virtual environment
color_echo "Setting up virtual environment..."
virtualenv ~/moonraker-mattaconnect-env
source ~/moonraker-mattaconnect-env/bin/activate
pip install -e .
color_echo "Virtual environment set up successfully"

# Create and start the service file
SERVICE_FILE="/etc/systemd/system/moonraker-mattaconnect.service"
SERVICE_CONTENT="[Unit]
Description=Moonraker Control Plugin
After=network-online.target moonraker.service

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=/home/${USER}/moonraker-mattaconnect 
ExecStart=/home/${USER}/moonraker-mattaconnect-env/bin/python3 /home/${USER}/moonraker-mattaconnect/moonraker_mattaconnect/main.py 
Restart=always
RestartSec=5"

color_echo "Creating and starting the service file..."
echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null
sudo systemctl enable moonraker-mattaconnect
sudo systemctl daemon-reload
sudo systemctl start moonraker-mattaconnect
color_echo "Service file created and started successfully"

# Create the config.cfg file
CONFIG_FILE="/home/${USER}/printer_data/config/moonraker-mattaconnect.cfg"
CONFIG_CONTENT="[moonraker_control]
enabled = true
printer_ip = localhost
printer_port = 7125"

color_echo "Creating the moonraker-mattaconnect.cfg file..."
echo "$CONFIG_CONTENT" > "$CONFIG_FILE"
color_echo "Config file created successfully"

color_echo "Installation completed!"
