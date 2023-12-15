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

color_echo "Uninstalling moonraker-mattaos..."

# Removing service
sudo systemctl stop moonraker-mattaos
sudo systemctl disable moonraker-mattaos
sudo rm "/etc/systemd/system/moonraker-mattaos.service"
sudo systemctl daemon-reload

# Removing all files and directories
sudo rm ~/printer_data/logs/moonraker-mattaos.log
sudo rm ~/printer_data/config/moonraker-mattaos.cfg
sudo rm -rf ~/moonraker-mattaos
sudo rm -rf ~/moonraker-mattaos-internal # TODO remove after moving to real repo
sudo rm -rf ~/moonraker-mattaos-env

color_echo "Uninstallation complete"
color_echo "Run 'sudo systemctl restart moonraker' to remove cache from GUI"

