import flask
from flask import Flask, render_template, request
import requests
import base64
from configparser import ConfigParser
import time
import threading
import os
from logger import setup_logging
import json

from moonraker_mattaos.matta import MattaCore
from moonraker_mattaos.printer import MattaPrinter
from moonraker_mattaos.utils import init_sentry, update_auth_token

# ---------------------------------------------------
# Set-up
# ---------------------------------------------------

LOG_FILE_PATH = os.path.expanduser("~/printer_data/logs/moonraker-mattaos.log")
WS_LOG_FILE_PATH = os.path.expanduser("~/printer_data/logs/moonraker-mattaos-ws.log")
CMD_LOG_FILE_PATH = os.path.expanduser("~/printer_data/logs/moonraker-mattaos-cmd.log")
CONFIG_FILE_PATH = os.path.expanduser("~/printer_data/config/moonraker-mattaos.cfg")

# ---------------------------------------------------
# MattaOSPlugin
# ---------------------------------------------------
class mattaosPlugin:

    def __init__(self):
        # Logging
        self._logger = setup_logging("moonraker-mattaos", LOG_FILE_PATH)
        self._logger_ws = setup_logging("moonraker-mattaos-ws", WS_LOG_FILE_PATH)
        self._logger_cmd = setup_logging("moonraker-mattaos-cmd", CMD_LOG_FILE_PATH)
        # Config
        self.config = ConfigParser()
        self.config.read(CONFIG_FILE_PATH)
        # Flask
        self.app = Flask(__name__)
        # Moonraker API
        self.MOONRAKER_API_URL = f"http://{self.config.get('moonraker_control', 'printer_ip')}:{self.config.get('moonraker_control', 'printer_port')}"

        self._logger.info("---------- Starting MattaOSPlugin ----------")

        # Logger tests
        self._logger.info("---- Logging Tests ----")
        self._logger.debug("Debug logging test")
        self._logger.info("Info logging test")
        self._logger.warning("Warning logging test")
        self._logger.error("Error logging test")
        self._logger.info("-----------------------")

        # Default settings
        self.auth_token = self.config.get("mattaos_settings", "auth_token")
        self.snapshot_url = self.config.get("mattaos_settings", "camera_snapshot_url")
        self.default_z_offset = 0.0
        self.nozzle_tip_coords_x = self.config.get(
            "mattaos_settings", "nozzle_tip_coords_x"
        )
        self.nozzle_tip_coords_y = self.config.get(
            "mattaos_settings", "nozzle_tip_coords_y"
        )
        self.webrtc_url = self.config.get("mattaos_settings", "webrtc_stream_url")
        self.live_upload = False
        self.flip_h = self.config.getboolean(
            "mattaos_settings", "flip_webcam_horizontally"
        )
        self.flip_v = self.config.getboolean(
            "mattaos_settings", "flip_webcam_vertically"
        )
        self.rotate = self.config.getboolean("mattaos_settings", "rotate_webcam_90CC")
        self.cherry_pick_cmds = self.config.get("mattaos_settings", "cherry_pick_cmds")

        self._settings = self.get_settings_defaults()

        # ------------- START PROCESS ---------------

        self.matta_os = MattaCore(
            self._logger,
            self._logger_ws,
            self._logger_cmd,
            self._settings,
            self.MOONRAKER_API_URL,
        )

        self._logger.info("Matta class" + str(self.matta_os))
        self.setup_routes()
        self.flask_thread = threading.Thread(target=self.start_flask)
        self.flask_thread.setDaemon(True)
        self.flask_thread.start()
        self.matta_os.test_auth_token(token=self._settings["auth_token"])

        while True:
            time.sleep(30)
            self._logger.info("mattaos is running")

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
            "cherry_pick_cmds": self.cherry_pick_cmds,
        }

    # ---------------------------------------------------
    # MattaOS Server API?
    # ---------------------------------------------------

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
    
    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "moonraker-mattaos": {
                "displayName": "MattaOS Plugin",
                "displayVersion": self.matta_os._plugin_version,
                # version check: github repository
                "type": "github_release",
                "user": "Matta-Labs",
                "repo": "octoprint-mattaos",
                "current": self.matta_os._plugin_version,
                # update method: pip
                "pip": "https://github.com/Matta-Labs/moonraker-mattaos/archive/{target_version}.zip",
            }
        }

    def is_api_adminonly(self):
        """
        Checks if API operations require administrative privileges.

        Returns:
            bool: True if administrative privileges are required, False otherwise.
        """
        return True

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
            self.matta_os._printer = MattaPrinter(
                self._logger, self._logger_cmd, self.MOONRAKER_API_URL
            )

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
                    line = [
                        set_item for set_item in tags if set_item.startswith("fileline")
                    ][0]
                    line = line.replace("fileline:", "")
                    self.matta_os._printer.gcode_line_num_no_comments = line
                    self.matta_os._printer.gcode_cmd = cmd
                elif "plugin:matta_os" in tags or "api:printer.command" in tags:
                    self.matta_os.terminal_cmds.append(cmd)
        except Exception as e:
            self._logger.error(e)
        return cmd

    # ---------------------------------------------------
    # Flask (http://raspberrypi.local:5001)
    # ---------------------------------------------------

    def setup_routes(self):
        @self.app.route("/")
        def index():
            self._logger.debug("Index request.")
            return render_template("index.html")

        @self.app.route("/api/home_printer", methods=["POST"])
        def home_printer():
            self._logger.info("Homing Printer.")
            response = self.matta_os._printer.home()
            # self._logger.debug(response)
            return str(response), 200

        @self.app.route("/api/get_printer_state", methods=["GET"])
        def get_printer_state():
            self._logger.info("Getting printer state.")
            response = self.matta_os._printer.get_printer_state_object()
            self._logger.debug(response)
            return response["text"], 200

        @self.app.route("/api/get_temps", methods=["GET"])
        def get_temps():
            temps = self.matta_os._printer.get_printer_temp_object()
            return temps, 200

        @self.app.route("/api/get_snapshot", methods=["GET"])
        def get_snapshot():
            success, status_text, image = self.matta_os.take_snapshot(
                self._settings["snapshot_url"]
            )
            if image is not None:
                # Convert the image to base64
                image_base64 = base64.b64encode(image).decode("utf-8")
            else:
                image_base64 = None
                self._logger.info("No image returned")
            return flask.jsonify(
                {"success": success, "text": status_text, "image": image_base64}
            )

        @self.app.route("/api/test_auth_token", methods=["GET"])
        def test_auth_token():
            try:
                self._logger.info("Testing auth_token.")
                success, status_text = self.matta_os.test_auth_token(
                    token=self._settings["auth_token"]
                )
                self._logger.debug(success, status_text)

                if success:
                    self._logger.debug(f"Success: {status_text}")
                    self._logger.debug(f"Success_code: {success}")
                else:
                    self._logger.error(
                        f"Error testing auth_token. Success: {success}, Text: {status_text}"
                    )
                return status_text, 200
            except Exception as e:
                self._logger.error(e)
                return status_text, 400

        @self.app.route("/api/save_values", methods=["POST"])
        def save_values():
            data = request.get_json()
            nozzleX = data.get("nozzleX")
            nozzleY = data.get("nozzleY")

            # Save the coordinates to the settings
            self._settings["nozzle_tip_coords_x"] = nozzleX
            self._settings["nozzle_tip_coords_y"] = nozzleY

            self.config.set("mattaos_settings", "nozzle_tip_coords_x", str(nozzleX))
            self.config.set("mattaos_settings", "nozzle_tip_coords_y", str(nozzleY))

            with open(CONFIG_FILE_PATH, "w") as configfile:
                self.config.write(configfile)

            return "Coordinates saved", 200

        @self.app.route("/api/get_values", methods=["GET"])
        def get_values():
            self._logger.info(self._settings)
            return self._settings, 200

        @self.app.route("/api/get_settings", methods=["GET"])
        def get_settings():
            return self._settings, 200

    def start_flask(self):
        self._logger.info("Starting Flask server...")
        self.app.run(host="0.0.0.0", port=5001)
        while True:
            time.sleep(30)
            self._logger.info("Flask server is running")


if __name__ == "__main__":
    plugin = mattaosPlugin()
