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

color_echo "Initiating installation of moonraker-mattaos..."

# Debug:
echo -e "User is: $USER"

# Install required packages
color_echo "Installing required packages..."
sudo apt-get update
# This is only necessary for virtual-klipper-printer 
# sudo apt-get install -y python3-virtualenv systemctl nano 
sudo apt-get install -y libopenblas-dev # this is sometimes needed to fix a pandas/numpy import error
color_echo "Required packages installed successfully"

ENV_NAME="moonraker-mattaos-env"

# Set up virtual environment
color_echo "Setting up virtual environment..."
python3 -m virtualenv ~/$ENV_NAME
source ~/$ENV_NAME/bin/activate
color_echo "Virtual environment set up successfully"

# Install the plugin from GitHub
# pip install -e .
color_echo "Installing moonraker-mattaos from GitHub..."
CURL_OUTPUT=$(curl -s https://api.github.com/repos/Matta-Labs/moonraker-mattaos/releases/latest)
color_echo "Curl output is: $CURL_OUTPUT"
GREP_OUTPUT=$(echo $CURL_OUTPUT | grep -oP '"tag_name":\s*"\K[^"]+')
color_echo "Grep output is: $GREP_OUTPUT"
LATEST_RELEASE_TAG=$GREP_OUTPUT

color_echo "Latest release tag is: $LATEST_RELEASE_TAG"
# Install the plugin from GitHub at the latest release
pip install git+https://github.com/Matta-Labs/moonraker-mattaos@$LATEST_RELEASE_TAG#egg=moonraker-mattaos

PYTHON_DIR=$(find /home/${USER}/${ENV_NAME}/lib/ -type d -name "python*" -print -quit)

# Create and start the service file
SERVICE_FILE="/etc/systemd/system/moonraker-mattaos.service"
SERVICE_CONTENT="[Unit]
Description=Moonraker mattaos
After=network-online.target moonraker.service

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=/home/${USER}/moonraker-mattaos
WorkeingDirectory=${PYTHON_DIR}/site-packages/moonraker_mattaos
ExecStart=/home/${USER}/${ENV_NAME}/bin/python3 ${PYTHON_DIR}/site-packages/moonraker_mattaos/main.py
Restart=always
RestartSec=5"

color_echo "Creating and starting the service file..."
echo "$SERVICE_CONTENT" | sudo tee "$SERVICE_FILE" > /dev/null
sudo systemctl enable moonraker-mattaos
sudo systemctl daemon-reload
sudo systemctl start moonraker-mattaos
color_echo "Service file created and started successfully"

# Create the config.cfg file
CONFIG_FILE="/home/${USER}/printer_data/config/moonraker-mattaos.cfg"
CONFIG_CONTENT="[moonraker_control]
enabled = true
printer_ip = localhost
printer_port = 7125
[mattaos_settings]
webrtc_stream_url = http://localhost/webcam/webrtc
camera_snapshot_url = http://localhost/webcam/snapshot
auth_token = <paste your auth token here>
nozzle_tip_coords_x = 10
nozzle_tip_coords_y = 10
flip_webcam_horizontally = false
flip_webcam_vertically = false
rotate_webcam_90CC = false
cherry_pick_cmds = []"



color_echo "Creating the moonraker-mattaos.cfg file..."
echo "$CONFIG_CONTENT" > "$CONFIG_FILE"
color_echo "Config file created successfully"

# Create the crowsnest.conf file
CROWSNEST_FILE="/home/${USER}/printer_data/config/crowsnest.conf"
CROWSNEST_CONTENT="[crowsnest]
log_path: /home/${USER}/printer_data/logs/crowsnest.log
log_level: verbose                      # Valid Options are quiet/verbose/debug
delete_log: false                       # Deletes log on every restart, if set to true
no_proxy: false

[cam 1]
mode: camera-streamer                         # ustreamer - Provides mjpg and snapshots. (All devices)
                                        # camera-streamer - Provides webrtc, mjpg and snapshots. (rpi + Raspi OS based only)
enable_rtsp: false                      # If camera-streamer is used, this enables also usage of an rtsp server
rtsp_port: 8554                         # Set different ports for each device!
port: 8080                              # HTTP/MJPG Stream/Snapshot Port
device: /dev/video0                     # See Log for available ...
resolution: 1920x1080 #640x480 #2592x1944                   # widthxheight format (Originally 640x480)
max_fps: 15 #30                             # If Hardware Supports this it will be forced, otherwise ignored/coerced. (originally 15)
#custom_flags:                          # You can run the Stream Services with custom flags.
#v4l2ctl:                               # Add v4l2-ctl parameters to setup your camera, see Log what your cam is capable of.
# focus_automatic_continuous: false   # Turn off focus_automatic_continuous
# focus_absolute: 500                 # Set focus_absolute to 550
v4l2ctl: 
focus_automatic_continuous: 0
focus_absolute: 500
"

color_echo "Creating the crowsnest.conf file..."
echo "$CROWSNEST_CONTENT" > "$CROWSNEST_FILE"
color_echo "Config file created successfully"

color_echo "Installation completed!"
