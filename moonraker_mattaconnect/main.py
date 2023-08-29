from flask import Flask, render_template
import requests
from configparser import ConfigParser
import time
import threading
import os
from logger import setup_logging
import json

#---------------------------------------------------
# Set-up
#---------------------------------------------------

LOG_FILE_PATH = os.path.expanduser('~/printer_data/logs/moonraker-mattaconnect.log')
CONFIG_FILE_PATH = os.path.expanduser('~/printer_data/config/moonraker-mattaconnect.cfg')


#---------------------------------------------------
# MattaConnectPlugin
#---------------------------------------------------
class MattaConnectPlugin():

    def __init__(self):
        # Logging
        self.logger = setup_logging(LOG_FILE_PATH)
        # Config 
        self.config = ConfigParser()
        self.config.read(CONFIG_FILE_PATH)
        # Flask
        self.app = Flask(__name__)
        self.MOONRAKER_API_URL = f"http://{self.config.get('moonraker_control', 'printer_ip')}:{self.config.get('moonraker_control', 'printer_port')}"

        self.logger.info("---------- Starting MattaConnectPlugin ----------")
        # Logger tests

        self.logger.info("---- Logging Tests ----")
        self.logger.debug("Debug logging test")
        self.logger.info("Info logging test")
        self.logger.warning("Warning logging test")
        self.logger.error("Error logging test")
        self.logger.info("-----------------------")

        # Default settings
        self.auth_token = ""
        self.snapshot_url = "http://localhost/webcam/snapshot"
        self.default_z_offset = 0.0
        self.nozzle_tip_coords_x = 10.0
        self.nozzle_tip_coords_y = 10.0
        self.webrtc_url = "http://localhost/webcam/webrtc"
        self.live_upload = False
        self.flip_h = False
        self.flip_v = False
        self.rotate = False

        self.start()

    def start(self):
        self.setup_routes()
        flask_thread = threading.Thread(target=self.start_flask)
        flask_thread.setDaemon(True)
        flask_thread.start()

        while True:
            self.logger.info("MattaConnect is running")
            time.sleep(30)
    
    def setup_routes(self):
        @self.app.route('/')
        def index():
            self.logger.debug("Index request.")
            return render_template('index.html')
        
        @self.app.route('/api/home_printer', methods=['POST'])
        def home_printer():
            self.logger.info("Homing Printer.")
            response = requests.post(f"{self.MOONRAKER_API_URL}/printer/gcode/script", json={"script": "G28"})
            if response.status_code == 200:
                self.logger.info(f"Homing Successful; {response.status_code} {response.text}")
            else:
                self.logger.error(f"Homing Unsuccessful; {response.status_code} {response.text}")
            return response.text, response.status_code

        @self.app.route('/api/get_printer_state', methods=['GET'])
        def get_printer_state():
            try:
                self.logger.info("Getting Printer State.")
                response = requests.get(f"{self.MOONRAKER_API_URL}/api/printer")
                printer_info = response.json()
                printer_state = printer_info['state']['text']

                if response.status_code == 200:
                    self.logger.debug(f"Got printer state:\n{printer_state}")
                    self.logger.debug(f"Printer info: {printer_info}")
                else:
                    self.logger.error(f"Error getting printer state. Status Code: {response.status_code}, Response Text: {response.text}")
                return printer_state, response.status_code
            except Exception as e:
                self.logger.error(e)

        @self.app.route('/api/get_temps', methods=['GET'])
        def get_temps():
            try:
                self.logger.info("Getting some printer info.")

                response = requests.get(f"{self.MOONRAKER_API_URL}/api/printer")
                printer_info = response.json()
                temps = printer_info['temperature']

                if response.status_code == 200:
                    self.logger.debug(f"Got printer state:\n{temps}")
                    self.logger.debug(f"Printer info: {printer_info}")
                else:
                    self.logger.error(f"Error getting printer state. Status Code: {response.status_code}, Response Text: {response.text}")
                return temps, response.status_code
            except Exception as e:
                self.logger.error(e)

    def start_flask(self):
        self.logger.info("Starting Flask server...")
        self.app.run(host='0.0.0.0', port=5001)


if __name__ == '__main__':
    plugin = MattaConnectPlugin()