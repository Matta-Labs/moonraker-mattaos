import time
import json
import threading
import requests
import subprocess
import os
import sys

# For Python 3.8 and later, use importlib.metadata
if sys.version_info >= (3, 8):
    from importlib import metadata
else:
    # For Python versions before 3.8, use the backport
    # You'll need to ensure importlib_metadata is installed for versions < 3.8
    # Can be installed via pip: pip install importlib_metadata
    import importlib_metadata as metadata

from moonraker_mattaos.utils import (
    cherry_pick_cmds,
    inject_auth_key,
    make_timestamp,
    get_cloud_http_url,
    get_cloud_websocket_url,
    get_current_memory_usage,
    generate_auth_headers,
)

from moonraker_mattaos.data import DataEngine
from moonraker_mattaos.printer import MattaPrinter
from moonraker_mattaos.ws import Socket


class MattaCore:
    def __init__(self, logger, logger_ws, logger_cmd, settings, MOONRAKER_API_URL):
        self._logger = logger
        self._logger_ws = logger_ws
        self._logger_cmd = logger_cmd
        self._settings = settings
        self.MOONRAKER_API_URL = MOONRAKER_API_URL

        self.nozzle_camera_count = 0
        self.ws = None
        self.ws_loop_time = 5
        self.terminal_cmds = []
        self.os = "Linux"  # TODO remove force OS type

        self._plugin_version = self.check_package_version("moonraker-mattaos")

        # ---------------------------------------------------------

        self._logger.debug("Starting mattaos Plugin...")

        # Start printer
        self._printer = MattaPrinter(
            self._logger, self._logger_cmd, self.MOONRAKER_API_URL, settings
        )

        # Start websocket
        self.user_online = False
        self.start_websocket_thread()

        # Start data loop
        self.data_engine = DataEngine(
            self._logger, self._logger_cmd, self._settings, self._printer
        )

        # Check for updates at startup
        self.over_the_air_update()

    def get_package_install_location(self, package_name):
        try:
            # Use importlib.metadata to get the distribution for the package
            distribution = metadata.distribution(package_name)
            
            # The 'Path' object for the distribution location can be converted to a string if needed
            return str(distribution.locate_file(''))
        except metadata.PackageNotFoundError:
            return None
        
    def get_package_version(self, package_name):
        try:
            return metadata.version(package_name)
        except metadata.PackageNotFoundError:
            return None
        
    # Example usage to get the version of a package
    def check_package_update_available(self, package_name):
        self._logger.info("Checking for new version")
        response = requests.get(f'https://api.github.com/repos/Matta-Labs/{package_name}/releases/latest')
        data = response.json()
        self._logger.info(data)
        release_tag =  data.get("tag_name", None)
        if release_tag is not None:
            release_tag = release_tag.replace("v", "")
        current_package_version = self.get_package_version(package_name)
        if current_package_version is not None:
            current_package_version = current_package_version.replace("v", "")
        new_version_available = False
        if release_tag != current_package_version:
            new_version_available = True
        self._logger.info(f"Current version: {current_package_version}")
        self._logger.info(f"Latest version: {release_tag}")
        return new_version_available

    def check_package_version(self, package_name):
        current_package_version = self.get_package_version(package_name)
        self._logger.info(f"Current version: {current_package_version}")
        return current_package_version

    def over_the_air_update(self):
        plugin_install_location = self.get_package_install_location("moonraker-mattaos")
        # /home/pi/oprint/lib/python3.7/site-packages/moonraker_mattaos
        # get the pip install location
        # find lib in the path and remove everything after it
        plugin_install_location = plugin_install_location.split("/lib/")[0]
        pip_path = os.path.join(plugin_install_location, "bin", "pip")

        self._logger.info(plugin_install_location)
        self._logger.info(pip_path)

        # check if there is a new version available
        new_version_available = self.check_package_update_available("moonraker-mattaos")
        
        if new_version_available:
            # run subprocess to update the plugin
            try:
                def log_subprocess_output(pipe):
                    for line in iter(pipe.readline, b''): # b'\n'-separated lines
                        self._logger.info('got line from subprocess: %r', line)

                process = subprocess.Popen(["bash", "./update.sh"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

                with process.stdout:
                    log_subprocess_output(process.stdout)
                exitcode = process.wait() # 0 means success
                self._logger.info(f"Plugin updated successfully {exitcode}") 
            except subprocess.CalledProcessError as e:
                self._logger.error("Error updating plugin: %s", e)
                self._logger.info("Error:", e)
                self._logger.info("Output:", e.stdout)
                self._logger.info("Errors:", e.stderr)

    def start_websocket_thread(self):
        """Starts the main WS thread."""
        self._logger_ws.debug("Setting up main WS thread...")
        ws_data_thread = threading.Thread(target=self.websocket_thread_loop)
        ws_data_thread.daemon = True
        ws_data_thread.start()
        self._logger_ws.debug("Main WS thread running.")

    def update_ws_send_interval(self):
        """
        Updates the WebSocket send interval based on the current print job status.
        """
        if self.user_online and self._printer.has_job():
            # When the user is online and printer is printing
            self.ws_loop_time = 1.25  # 1250ms websocket send interval
        elif self.user_online:
            # When the user is online
            self.ws_loop_time = 1.25  # 1250ms websocket send interval
        else:
            # When the user is offline
            self.ws_loop_time = 30  # 30s websocket send interval

    def ws_connected(self):
        """
        Checks if the WebSocket connection is currently connected.

        Returns:
            bool: True if the WebSocket connection is connected, False otherwise.

        """
        if hasattr(self, "ws") and self.ws is not None:
            if self.ws.connected():
                return True
        return False

    def ws_connect(self, wait=True):
        """
        Connects to the WebSocket server.

        Args:
            wait (bool): Indicates whether to wait for a few seconds after connecting.
        """
        self._logger_ws.info("Connecting websocket")
        try:
            full_url = get_cloud_websocket_url() + "api/v1/ws/printer"
            if self.ws_connected():
                self.ws.disconnect()
                self.ws = None
                if self.ws_thread:
                    self.ws_thread.join()
                    self.ws_thread = None
            self.ws = Socket(
                logger_ws=self._logger_ws,
                on_message=lambda _, msg: self.ws_on_message(msg),
                url=full_url,
                token=self._settings["auth_token"],
            )
            self.ws_thread = threading.Thread(target=self.ws.run)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            if wait:
                time.sleep(2)  # wait for 2 seconds
        except Exception as e:
            self._logger_ws.error("ws_on_close: %s", e)

    def ws_on_message(self, incoming_msg):
        """
        Callback function called when a message is received over the WebSocket connection.

        Args:
            ws: The WebSocket instance.
            msg (str): The received message.

        """
        try:
            # Get current thread's ID and print it
            json_msg = json.loads(incoming_msg)
            self._logger_ws.info("ws_on_message: %s", json_msg)
            msg = self.ws_data()  # default message
            if (
                json_msg.get("token", None) == self._settings["auth_token"]
                and json_msg.get("interface", None) == "client"
            ):
                self._logger_ws.info("Token and interface match")
                if json_msg.get("state", None) == "online":
                    self.user_online = True
                    msg = self.ws_data()
                elif json_msg.get("state", None) == "offline":
                    self.user_online = False
                    msg = self.ws_data()
                elif json_msg.get("webrtc", None) == "request":
                    # check if auth_key has already been received
                    self._logger_ws.info("WebRTC request received")
                    webrtc_auth_key = json_msg.get("auth_key", None)
                    self._logger_ws.info(f"New key {webrtc_auth_key}")
                    last_webrtc_auth_key = self._settings.get("webrtc_auth_key", None)
                    self._logger_ws.info(f"Last key {last_webrtc_auth_key}")
                    if (
                        webrtc_auth_key is not None
                        and webrtc_auth_key != last_webrtc_auth_key
                    ):
                        # save auth_key
                        self._logger_ws.info("Saving new key")
                        self._settings["webrtc_auth_key"] = webrtc_auth_key
                        webrtc_data = self.request_webrtc_stream()
                        if webrtc_data is not None:
                            webrtc_data = inject_auth_key(
                                webrtc_data, json_msg, self._logger
                            )
                            webcam_transforms = {
                                "flip_h": self._settings.get("flip_h"),
                                "flip_v": self._settings.get("flip_v"),
                                "rotate": self._settings.get("rotate"),
                            }
                            webrtc_data["transforms"] = webcam_transforms
                            msg = self.ws_data(extra_data=webrtc_data)
                        else:
                            msg = self.ws_data()
                elif json_msg.get("webrtc", None) == "remote_candidate":
                    webrtc_data = self.remote_webrtc_stream(candidate=json_msg["data"])
                    if webrtc_data is not None:
                        webrtc_data = inject_auth_key(
                            webrtc_data, json_msg, self._logger
                        )
                        webcam_transforms = {
                            "flip_h": self._settings.get("flip_h"),
                            "flip_v": self._settings.get("flip_v"),
                            "rotate": self._settings.get("rotate"),
                        }
                        webrtc_data["transforms"] = webcam_transforms
                        msg = self.ws_data(extra_data=webrtc_data)
                    else:
                        msg = self.ws_data()
                elif json_msg.get("webrtc", None) == "offer":
                    webrtc_data = self.connect_webrtc_stream(offer=json_msg["data"])
                    if webrtc_data is not None:
                        webrtc_data = inject_auth_key(
                            webrtc_data, json_msg, self._logger
                        )
                        webcam_transforms = {
                            "flip_h": self._settings.get("flip_h"),
                            "flip_v": self._settings.get("flip_v"),
                            "rotate": self._settings.get("rotate"),
                        }
                        webrtc_data["transforms"] = webcam_transforms
                        msg = self.ws_data(extra_data=webrtc_data)
                    else:
                        msg = self.ws_data()
                elif json_msg.get("status", None) != None:
                    terminal_commands = self._printer.get_printer_cmds()
                    cleaned_cmds = cherry_pick_cmds(self, terminal_commands)
                    extra_data = {"terminal_commands": {"command_list": cleaned_cmds}}
                    msg = self.ws_data(extra_data=extra_data)
                elif json_msg.get("update", None) == "update":
                    self.over_the_air_update()
                else:
                    self._printer.handle_cmds(json_msg)
                    msg = self.ws_data()
            self.ws_send(msg)
            self.update_ws_send_interval()
        except Exception as e:
            self._logger.info("ws_on_message: %s", e)

    def ws_send(self, msg):
        """
        Sends a message over the WebSocket connection.

        Args:
            msg (str): The message to send.

        """
        try:
            if self.ws_connected():
                self.ws.send_msg(msg)
        except Exception as e:
            self._logger_ws.error("ws_send: %s", e)

    def ws_data(self, extra_data=None):
        """
        Generates the data payload to be sent over the WebSocket connection.

        Args:
            extra_data (dict): Additional data to include in the payload.

        Returns:
            dict: The data payload.

        """
        try:
            data = {
                "type": "printer_packet",
                "token": self._settings["auth_token"],
                "timestamp": make_timestamp(),
                "files": self._printer.get_and_refactor_files()["files"],
                "terminal_cmds": self.terminal_cmds,
                "system": {
                    "software": "moonraker",
                    "version": self._printer.get_klipper_version(),
                    "os": self.os,
                    "memory": get_current_memory_usage(self.os),
                    "plugin_version": self._plugin_version,

                },
                "nozzle_tip_coords": {
                    "nozzle_tip_coords_x": int(self._settings["nozzle_tip_coords_x"]),
                    "nozzle_tip_coords_y": int(self._settings["nozzle_tip_coords_y"]),
                },
                "webcam_transforms": {
                    "flip_h": self._settings["flip_h"],
                    "flip_v": self._settings["flip_v"],
                    "rotate": self._settings["rotate"],
                },
            }
            if self._printer.connected():
                printer_data = self._printer.get_data()
                data.update(printer_data)
            if extra_data:
                data.update(extra_data)
            return data
        except Exception as e:
            self._logger_ws.error("ws_data: %s", e)
            return {}

    def test_auth_token(self, token):
        """
        Tests the validity of an authorization token.

        Args:
            token (str): The authorization token to test.

        Returns:
            tuple: A tuple containing a boolean indicating success and a status message.
        """
        full_url = get_cloud_http_url() + "api/v1/printers/ping"
        success = False
        status_text = "Oh no! An unknown error occurred."
        if token == "":
            status_text = "Please enter a token."
            return success, status_text
        try:
            headers = generate_auth_headers(token)
            resp = requests.get(
                url=full_url,
                headers=headers,
            )
            if resp.status_code == 200:
                if self.ws_connected():
                    self.ws.disconnect()
                status_text = "All is tickety boo! Your token is valid."
                success = True
            elif resp.status_code == 401:
                status_text = "Whoopsie. That token is invalid."
            else:
                status_text = "Oh no! An unknown error occurred."
        except requests.exceptions.RequestException as e:
            self._logger_ws.warning(
                "Testing authorization token: %s, URL: %s, Headers %s",
                e,
                full_url,
                generate_auth_headers(token),
            )
            status_text = "Error. Please check Klipper's internet connection"
        return success, status_text

    def take_snapshot(self, url):
        """
        Takes a snapshot of the current print job.

        Args:
            url (str): The URL to send the snapshot to.

        Returns:
            Image: The snapshot image.
        """
        success = False
        image = None
        status_text = "Oh no! An unknown error occurred."
        if url == "":
            status_text = "Please add snapshot URL to the moonraker-mattaos.conf file."
            return success, status_text, image
        try:
            resp = requests.get(url, stream=True)
        except requests.exceptions.RequestException as e:
            self._logger.debug("Error when sending request: %s", e)
            status_text = "Error when sending request: " + str(e)
            return success, status_text, image
        if resp.status_code == 200:
            success = True
            image = resp.content
            status_text = "Image captured successfully."
        else:
            status_text = "Error: received status code " + str(resp.status_code)
        return success, status_text, image

    def websocket_thread_loop(self):
        """
        Sends data over the WebSocket connection.

        This method continuously sends data while the WebSocket connection is active.
        It uses an exponential backoff strategy for reconnection attempts.

        """
        old_time = time.perf_counter()
        time_buffer = 0.0
        while True:
            try:
                self.ws_connect()
                while self.ws_connected():
                    current_time = time.perf_counter()
                    if (current_time - old_time) > self.ws_loop_time - time_buffer:
                        time_buffer = max(
                            0, current_time - old_time - self.ws_loop_time
                        )
                        old_time = current_time
                        # get terminal commands
                        self.terminal_cmds = self._printer.get_printer_cmds(clean=False)
                        msg = self.ws_data()
                        self.ws.send_msg(msg)
                    time.sleep(0.1)  # slow things down to 100ms
                    self.update_ws_send_interval()
            except Exception as e:
                self._logger_ws.error("websocket_thread_loop: %s", e)
                if self.ws_connected():
                    self.ws.disconnect()
                    self.ws = None
            finally:
                try:
                    if self.ws_connected():
                        self.ws.disconnect()
                        self.ws = None
                except Exception as e:
                    self._logger_ws.error("ws_send_data: %s", e)
            time.sleep(0.1)  # slow things down to 100ms

    def request_webrtc_stream(self):
        """
        Initiates a WebRTC stream by sending a request to the /webcam/webrtc endpoint.

        Note: This method only works with the new camera-streamer stack.

        Returns:
            dict: A dictionary containing WebRTC data if the request is successful, None otherwise.
        """
        self._logger_ws.info("Requesting WebRTC stream")
        ice_servers = [{"urls": ["stun:stun.l.google.com:19302"]}]
        params = {
            "type": "request",
            "res": None,
            "iceServers": ice_servers,
        }
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(
                self._settings["webrtc_url"], json=params, headers=headers, timeout=5
            )
            if resp.status_code == 200:
                return {"webrtc_data": resp.json()}
        except requests.exceptions.RequestException as e:
            self._logger_ws.error(e)
        except Exception as e:
            self._logger_ws.error(e)
        return {
            "webrtc_error": "WebRTC request failed. Couldn't connect to the camera streamer."
        }

    def remote_webrtc_stream(self, candidate):
        """
        Sends WebRTC candidate data to the /webcam/webrtc endpoint to establish a remote stream.

        Note: This method only works with the new camera-streamer stack.

        Args:
            candidate (dict): The WebRTC candidate data.

        Returns:
            dict: A dictionary containing WebRTC data if the request is successful, None otherwise.
        """
        self._logger_ws.info("Sending remote webrtc candidate")
        params = {
            "type": candidate.get("type", None),
            "id": candidate.get("id", None),
            "candidates": candidate.get("candidates", None),
        }
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(
                self._settings["webrtc_url"], json=params, headers=headers, timeout=5
            )
            if resp.status_code == 200:
                return {"webrtc_data": resp.json()}
        except requests.exceptions.RequestException as e:
            self._logger_ws.error(e)
        except Exception as e:
            self._logger_ws.error(e)
        return {
            "webrtc_error": "WebRTC remote handshake failed. Couldn't connect to the camera streamer."
        }

    def connect_webrtc_stream(self, offer):
        """
        Sends WebRTC offer data to the /webcam/webrtc endpoint to establish a WebRTC stream.

        Note: This method only works with the new camera-streamer stack.

        Args:
            offer (dict): The WebRTC offer data.

        Returns:
            dict: A dictionary containing WebRTC data if the request is successful, None otherwise.
        """
        params = {
            "type": offer["type"],
            "id": offer["id"],
            "sdp": offer["sdp"],
        }
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(
                self._settings["webrtc_url"], json=params, headers=headers, timeout=5
            )
            if resp.status_code == 200:
                return {"webrtc_data": resp.json()}
        except requests.exceptions.RequestException as e:
            self._logger_ws.error(e)
        except Exception as e:
            self._logger_ws.error(e)
        return {
            "webrtc_error": "WebRTC connection completion failed. Couldn't connect to the camera streamer."
        }
