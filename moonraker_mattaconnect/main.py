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
from moonraker_mattaconnect.utils import init_sentry, update_auth_token, get_auth_token

#---------------------------------------------------
# Set-up
#---------------------------------------------------

# TODO put them in utils later
LOG_FILE_PATH = os.path.expanduser('~/printer_data/logs/moonraker-mattaconnect.log')
WS_LOG_FILE_PATH = os.path.expanduser('~/printer_data/logs/moonraker-mattaconnect-ws.log')
CMD_LOG_FILE_PATH = os.path.expanduser('~/printer_data/logs/moonraker-mattaconnect-cmd.log')

CONFIG_FILE_PATH = os.path.expanduser('~/printer_data/config/moonraker-mattaconnect.cfg')


#---------------------------------------------------
# MattaConnectPlugin
#---------------------------------------------------
class MattaConnectPlugin():

    def __init__(self):
        # Logging
        self.logger = setup_logging("moonraker-mattaconnect", LOG_FILE_PATH)
        self.logger_ws = setup_logging("moonraker-mattaconnect-ws", WS_LOG_FILE_PATH)
        self.logger_cmd = setup_logging("moonraker-mattaconnect-cmd", CMD_LOG_FILE_PATH)
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
        self.settings_path = "moonraker_mattaconnect/settings/settings.json"
        # self.auth_token = get_auth_token(self)
        self.auth_token = self.config.get('mattaconnect_settings', 'auth_token')
        self.snapshot_url = self.config.get('mattaconnect_settings', 'camera_snapshot_url')
        self.default_z_offset = 0.0
        self.nozzle_tip_coords_x = 10.0
        self.nozzle_tip_coords_y = 10.0
        self.webrtc_url = self.config.get('mattaconnect_settings', 'webrtc_stream_url')
        self.live_upload = False
        self.flip_h = self.config.getboolean('mattaconnect_settings', 'flip_webcam_horiztonally')
        self.flip_v = self.config.getboolean('mattaconnect_settings', 'flip_webcam_vertically')
        self.rotate = self.config.getboolean('mattaconnect_settings', 'rotate_webcam_90CC')

        self._settings = self.get_settings_defaults()

        # ------------- START PROCESS ---------------

        # init_sentry("TEMP_KLIPPER_VERSION_PLACEHOLDER")
        self.matta_os = MattaCore(self.logger, self.logger_ws, self.logger_cmd, self._settings, self.MOONRAKER_API_URL)
        self.logger.info("Matta class" + str(self.matta_os))
        self.setup_routes()
        self.flask_thread = threading.Thread(target=self.start_flask)
        self.flask_thread.setDaemon(True)
        self.flask_thread.start()
        self.matta_os.test_auth_token(token=self._settings["auth_token"])

        while True:
            time.sleep(30)
            self.logger.info("MattaConnect is running")

    def get_settings_defaults(self):
        """Returns the plugin's default and configured settings"""
        return {
            "auth_token": self.auth_token,
            "snapshot_url": self.snapshot_url,
            "default_z_offset": self.default_z_offset,
            "nozzle_tip_coords_x": self.nozzle_tip_coords_x,
            "nozzle_tip_coords_y": self.nozzle_tip_coords_y,
            "webrtc_url": self.webrtc_url,
            "webrtc_auth_key": "",
            "live_upload": self.live_upload,
            "flip_h": self.flip_h,
            "flip_v": self.flip_v,
            "rotate": self.rotate,
            "path": self.settings_path,
        }

    # def start(self):
    #     self.setup_routes()
    #     flask_thread = threading.Thread(target=self.start_flask)
    #     flask_thread.setDaemon(True)
    #     flask_thread.start()

    #     # init_sentry("TEMP_KLIPPER_VERSION_PLACEHOLDER")
    #     self.matta_os = MattaCore(self.logger, self.logger_ws, self._settings, self.MOONRAKER_API_URL)

    #     # Temp loop to trap the service.
    #     # while True:
    #     #     self.logger.info("MattaConnect is running")
    #     #     time.sleep(30)




    #---------------------------------------------------
    # MattaOS Server API?
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

    # Gone to Flask!
    # def on_api_command(self, command, data):
    #     """
    #     Handles API commands received from the client.

    #     Args:
    #         command (str): The API command to be executed.
    #         data (dict): Additional data associated with the command.

    #     Returns:
    #         flask.Response: A JSON response containing the result of the command execution.
    #     """
    #     if command == "test_auth_token":
    #         auth_token = data["auth_token"]
    #         success, status_text = self.matta_os.test_auth_token(token=auth_token)
    #         return flask.jsonify({"success": success, "text": status_text})

    #     if command == "ws_reconnect":
    #         self.matta_os.ws_connect()
    #         if self.matta_os.ws_connected():
    #             status_text = "Successfully connected to Matta OS."
    #             success = True
    #         else:
    #             status_text = "Failed to connect to Matta OS."
    #             success = False

    #         return flask.jsonify({"success": success, "text": status_text})

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
            self.matta_os._printer = MattaPrinter(self.logger, self.logger_cmd, self.MOONRAKER_API_URL)

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
            response = self.matta_os._printer.home()
            # self.logger.debug(response)
            return str(response), 200

        @self.app.route('/api/get_printer_state', methods=['GET'])
        def get_printer_state():
            self.logger.info("Getting printer state.")
            response = self.matta_os._printer.get_printer_state_object()
            self.logger.debug(response)
            return response["text"], 200

        @self.app.route('/api/get_temps', methods=['GET'])
        def get_temps():
            temps = self.matta_os._printer.get_printer_temp_object()
            return temps, 200

        @self.app.route('/api/test_auth_token', methods=['GET'])
        def test_auth_token():
            # Originally:
            # if command == "test_auth_token":
            #     auth_token = data["auth_token"]
            #     success, status_text = self.matta_os.test_auth_token(token=auth_token)
            #     return flask.jsonify({"success": success, "text": status_text})
            try:
                self.logger.info("Testing auth_token.")
                success, status_text = self.matta_os.test_auth_token(token=self._settings["auth_token"])
                self.logger.debug(success, status_text)

                if success:
                    self.logger.debug(f"Success: {status_text}")
                    self.logger.debug(f"Success_code: {success}")   
                else:
                    self.logger.error(f"Error testing auth_token. Success: {success}, Text: {status_text}")
                return status_text, 200
                # success: bool; status_text: eg "All is tickety boo! Your token is valid."
            except Exception as e:
                self.logger.error(e)
                return status_text, 400
        @self.app.route('/api/save_values', methods=['POST'])
        def save_values():
            data = flask.request.get_json()
            with open(self.settings_path, "w") as file:
                json.dump(data, file)
            update_auth_token(self, self._settings)
            return "OK", 200

        @self.app.route('/api/get_values', methods=['GET'])
        def get_values():
            # with open(self.settings_path, "r") as file:
            #     self.logger.debug("Getting values from settings.json")
            #     data = json.load(file)

            self.logger.debug(self._settings)
            return self._settings, 200


    def start_flask(self):
        self.logger.info("Starting Flask server...")
        self.app.run(host='0.0.0.0', port=5001)
        while True:
            time.sleep(30)
            self.logger.info("Flask server is running")


if __name__ == '__main__':
    plugin = MattaConnectPlugin()