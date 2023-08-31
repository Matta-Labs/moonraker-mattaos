import flask
from flask import Flask, render_template
import requests
from configparser import ConfigParser
import time
import threading
import os
from logger import setup_logging
import json

from moonraker_mattaconnect.matta import MattaCore # TODO not sure if this format is right?
from moonraker_mattaconnect.printer import MattaPrinter
from moonraker_mattaconnect.utils import init_sentry

#---------------------------------------------------
# Set-up
#---------------------------------------------------

# TODO put them in utils later
LOG_FILE_PATH = os.path.expanduser('~/printer_data/logs/moonraker-mattaconnect.log')
WS_LOG_FILE_PATH = os.path.expanduser('~/printer_data/logs/moonraker-mattaconnect-ws.log')

CONFIG_FILE_PATH = os.path.expanduser('~/printer_data/config/moonraker-mattaconnect.cfg')


#---------------------------------------------------
# MattaConnectPlugin
#---------------------------------------------------
class MattaConnectPlugin():

    def __init__(self):
        # Logging
        self.logger = setup_logging("moonraker-mattaconnect", LOG_FILE_PATH)
        self.logger_ws = setup_logging("moonraker-mattaconnect-ws", WS_LOG_FILE_PATH)
        # Config 
        self.config = ConfigParser()
        self.config.read(CONFIG_FILE_PATH)
        # Flask
        self.app = Flask(__name__)
        # Moonraker API
        # TODO make this a function instead of this long string of text
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
        self.auth_token = "6DXwm1Lm-7nyPC04qDsDbzvjP73Paeb29AETk8o0QyI"
        self.snapshot_url = "http://localhost/webcam/snapshot"
        self.default_z_offset = 0.0
        self.nozzle_tip_coords_x = 10.0
        self.nozzle_tip_coords_y = 10.0
        self.webrtc_url = "http://localhost/webcam/webrtc"
        self.live_upload = False
        self.flip_h = False
        self.flip_v = False
        self.rotate = False

        self._settings = self.get_settings_defaults()

        self.start()

    def get_settings_defaults(self):
        """Returns the plugin's default and configured settings"""
        return {
            "auth_token": self.auth_token,
            "snapshot_url": self.snapshot_url,
            "default_z_offset": self.default_z_offset,
            "nozzle_tip_coords_x": self.nozzle_tip_coords_x,
            "nozzle_tip_coords_y": self.nozzle_tip_coords_y,
            "webrtc_url": self.webrtc_url,
            "live_upload": self.live_upload,
            "flip_h": self.flip_h,
            "flip_v": self.flip_v,
            "rotate": self.rotate,
        }

    def start(self):
        self.setup_routes()
        flask_thread = threading.Thread(target=self.start_flask)
        flask_thread.setDaemon(True)
        flask_thread.start()

        # init_sentry("TEMP_KLIPPER_VERSION_PLACEHOLDER")
        self.matta_os = MattaCore(self.logger, self.logger_ws, self._settings, self.MOONRAKER_API_URL)

        # Temp loop to trap the service.
        # while True:
        #     self.logger.info("MattaConnect is running")
        #     time.sleep(30)

    #---------------------------------------------------
    # MattaOS Server API
    #---------------------------------------------------


    def get_api_commands(self):
        """
        Returns the available API commands as a dictionary.

        Returns:
            dict: A dictionary of available API commands.
        """
        return dict(
            test_auth_token=["auth_token"],
            set_enabled=[],
            ws_reconnect=[],
        )

    def is_api_adminonly(self):
        """
        Checks if API operations require administrative privileges.

        Returns:
            bool: True if administrative privileges are required, False otherwise.
        """
        return True

    def on_api_command(self, command, data):
        """
        Handles API commands received from the client.

        Args:
            command (str): The API command to be executed.
            data (dict): Additional data associated with the command.

        Returns:
            flask.Response: A JSON response containing the result of the command execution.
        """
        if command == "test_auth_token":
            auth_token = data["auth_token"]
            success, status_text = self.matta_os.test_auth_token(token=auth_token)
            return flask.jsonify({"success": success, "text": status_text})

        if command == "ws_reconnect":
            self.matta_os.ws_connect()
            if self.matta_os.ws_connected():
                status_text = "Successfully connected to Matta OS."
                success = True
            else:
                status_text = "Failed to connect to Matta OS."
                success = False

            return flask.jsonify({"success": success, "text": status_text})

    def parse_received_lines(self, comm_instance, line, *args, **kwargs):
        """
        Parse received lines from the printer's communication and update the printer's state accordingly.

        Args:
            comm_instance: Communication instance.
            line (str): The received line from the printer.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            str: The parsed line.
        """
        try:
            self.matta_os._printer.parse_line_for_updates(line)
        except AttributeError:
            self.matta_os._printer = MattaPrinter(self.logger, self.MOONRAKER_API_URL)

        if "UPDATED" in line:
            self.executed_update = True
            self.new_cmd = False
        return line

    def parse_sent_lines(
        self,
        comm_instance,
        phase,
        cmd,
        cmd_type,
        gcode,
        subcode=None,
        tags=None,
        *args,
        **kwargs,
    ):
        """
        Parse sent lines and update relevant attributes based on the sent commands.

        This method is called when a line is sent to the printer. It extracts information
        from the line and updates the corresponding attributes.

        Args:
            comm_instance: Communication instance.
            phase (str): The phase of the command.
            cmd (str): The command sent to the printer.
            cmd_type (str): The type of command.
            gcode (str): The G-code associated with the command.
            subcode (str): Subcode associated with the command (optional).
            tags (dict): Tags associated with the command (optional).
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            str: The parsed command.
        """
        try:
            if tags:
                # tags is set in format: {'source:file', 'filepos:371', 'fileline:7'}
                if "source:file" in tags:
                    # get the current gcode line number
                    # find item starting with fileline
                    line = [
                        set_item for set_item in tags if set_item.startswith("fileline")
                    ][0]
                    # strip file line to get number
                    line = line.replace("fileline:", "")
                    self.matta_os._printer.gcode_line_num_no_comments = line
                    self.matta_os._printer.gcode_cmd = cmd
                elif "plugin:matta_os" in tags or "api:printer.command" in tags:
                    self.matta_os.terminal_cmds.append(cmd)
        except Exception as e:
            self.logger.error(e)
        return cmd



    #---------------------------------------------------
    # Flask (http://raspberrypi.local:5001)
    #---------------------------------------------------
    
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