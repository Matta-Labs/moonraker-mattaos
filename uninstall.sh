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

color_echo "Uninstalling moonraker-mattaconnect..."

# Removing service
sudo systemctl stop moonraker-mattaconnect
sudo systemctl disable moonraker-mattaconnect
sudo rm "/etc/systemd/system/moonraker-mattaconnect.service"
sudo systemctl daemon-reload

# Removing all files and directories
sudo rm ~/printer_data/logs/moonraker-mattaconnect.log
sudo rm ~/printer_data/config/moonraker-mattaconnect.cfg
sudo rm -rf ~/moonraker-mattaconnect
sudo rm -rf ~/moonraker-mattaconnect-internal # TODO remove after moving to real repo
sudo rm -rf ~/moonraker-mattaconnect-env

color_echo "Uninstallation complete"
color_echo "Run 'sudo systemctl restart moonraker' to remove cache from GUI"

