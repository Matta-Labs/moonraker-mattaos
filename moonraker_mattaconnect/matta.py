import time
import json
import threading
import backoff
import requests
import concurrent.futures

# from octoprint.util.platform import get_os
# from octoprint.util.version import get_octoprint_version_string

from moonraker_mattaconnect.utils import (
    cherry_pick_cmds,
    make_timestamp,
    get_cloud_http_url,
    get_cloud_websocket_url,
    get_current_memory_usage,
    generate_auth_headers,
)

from moonraker_mattaconnect.data import DataEngine
from moonraker_mattaconnect.printer import MattaPrinter
from moonraker_mattaconnect.ws import Socket

class MattaCore:
    def __init__(self, logger, logger_ws, logger_cmd, settings, MOONRAKER_API_URL):
        self._logger = logger
        self._logger_ws = logger_ws
        self._logger_cmd = logger_cmd
        self._settings = settings
        self.MOONRAKER_API_URL = MOONRAKER_API_URL

        # self._file_manager = plugin._file_manager
        self.nozzle_camera_count = 0
        self.ws = None
        self.ws_loop_time = 5
        self.webrtc_request_time = 0
        self.terminal_cmds = []
        # get OS type (linux, windows, mac)
        self.os = "linux" # TODO remove force OS type
        # get OctoPrint version
        self.klipper_version = "TEMP_KLIIPPER_VERSION_STRING" # TODO change this


        # ---------------------------------------------------------

        self._logger.debug("Starting MattaConnect Plugin...")

        # Start printer
        self._printer = MattaPrinter(self._logger, self._logger_cmd, self.MOONRAKER_API_URL)

        # Start websocket
        self.user_online = False
        self.start_websocket_thread()

        # Start data loop
        self.data_engine = DataEngine(self._logger, self._logger_cmd, self._settings, self._printer)


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
        # self._logger.debug(f"Update in time, {time.perf_counter()} {self.webrtc_request_time}")
        if time.perf_counter() - self.webrtc_request_time < 15:
            # When the WebRTC stream is being requested slow down the websocket send interval
            self.ws_loop_time = 15
        elif self.user_online and self._printer.has_job():
            # When the user is online and printer is printing
            self.ws_loop_time = 1.25 # 1250ms websocket send interval
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
        self._logger_ws.debug("Connecting websocket")
        try:
            full_url = get_cloud_websocket_url() + "api/v1/ws/printer"
            self.ws = Socket(
                logger_ws = self._logger_ws,
                on_open=lambda ws: self.ws_on_open(ws),
                on_message=lambda ws, msg: self.ws_on_message(ws, msg),
                on_close=lambda ws, close_status_code, close_msg: self.ws_on_close(
                    ws, close_status_code, close_msg
                ),
                on_error=lambda ws, error: self.ws_on_error(ws, error),
                url=full_url,
                token=self._settings["auth_token"],
            )
            ws_thread = threading.Thread(target=self.ws.run)
            ws_thread.daemon = True
            ws_thread.start()
            if wait:
                time.sleep(2) # wait for 2 seconds
        except Exception as e:
            self._logger_ws.error("ws_on_close: %s", e)
            pass

    def ws_on_open(self, ws):
        """
        Callback function called when the WebSocket connection is opened.

        Args:
            ws: The WebSocket instance.

        """
        self._logger_ws.debug("Opening MattaConnect websocket...")

    def ws_on_close(self, ws, close_status_code, close_msg):
        """
        Callback function called when the WebSocket connection is closed.

        Args:
            ws: The WebSocket instance.
            close_status_code (int): The close status code.
            close_msg (str): The close message.

        """
        self._logger_ws.debug(
            f"Closing websocket... code: {close_status_code} msg: {close_msg}"
        )
        try:
            self.ws.disconnect()
            self.ws = None
        except Exception as e:
            self._logger_ws.error("ws_on_close: %s", e)
            pass

    def ws_on_error(self, ws, error):
        """
        Callback function called when a WebSocket error occurs.

        Args:
            ws: The WebSocket instance.
            error: The error that occurred.

        """
        self._logger_ws.error("ws_on_error: %s", error)

    def ws_on_message(self, ws, msg):
        """
        Callback function called when a message is received over the WebSocket connection.

        Args:
            ws: The WebSocket instance.
            msg (str): The received message.

        """
        json_msg = json.loads(msg)
        self._logger_ws.info("ws_on_message: %s", json_msg)
        if (
            json_msg["token"] == self._settings["auth_token"]
            and json_msg["interface"] == "client"
        ):
            if json_msg.get("state", None) == "online":
                self.user_online = True
                msg = self.ws_data()
            elif json_msg.get("state", None) == "offline":
                self.user_online = False
                msg = self.ws_data()
            elif json_msg.get("webrtc", None) == "request":
                webrtc_data = self.request_webrtc_stream()
                msg = self.ws_data(extra_data=webrtc_data)
            elif json_msg.get("webrtc", None) == "remote_candidate":
                webrtc_data = self.remote_webrtc_stream(candidate=json_msg["data"])
                msg = self.ws_data(extra_data=webrtc_data)
            elif json_msg.get("webrtc", None) == "offer":
                webrtc_data = self.connect_webrtc_stream(offer=json_msg["data"])
                msg = self.ws_data(extra_data=webrtc_data)
            elif json_msg.get("status", None) != None:
                terminal_commands = self._printer.get_printer_cmds()
                cleaned_cmds = cherry_pick_cmds(self, terminal_commands)
                extra_data = {"terminal_commands" : {"command_list": cleaned_cmds}}
                msg = self.ws_data(extra_data=extra_data)
            else:
                self._printer.handle_cmds(json_msg)
                msg = self.ws_data()
        self.ws_send(msg)
        self.update_ws_send_interval()
    
    def ws_send(self, msg):
        """
        Sends a message over the WebSocket connection.

        Args:
            msg (str): The message to send.

        """
        try:
            if self.ws_connected():
                self._logger_ws.info("Sending...")
                self.ws.send_msg(msg)
                self._logger_ws.info("Sent")
            else:
                self.ws_connect()
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
        data = {
            "token": self._settings["auth_token"],
            "timestamp": make_timestamp(),
            "files": self._printer.get_and_refactor_files()["files"], # None, # self._file_manager.list_files(recursive=True), # TODO no file manager
            "terminal_cmds": self.terminal_cmds,
            "system": {
                "version": self.klipper_version,
                "os": self.os,
                "memory": get_current_memory_usage(self.os),
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
        # self._logger.info("Auth token: %s", self._settings["auth_token"])
        if self._printer.connected():
            printer_data = self._printer.get_data()
            data.update(printer_data)
        if extra_data:
            data.update(extra_data)
        return data

    @backoff.on_exception(backoff.expo, requests.exceptions.RequestException)
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
        # self._settings.set(["auth_token"], token, force=True)
        # self._settings.save()
        # self._settings["auth_token"] = token # TODO test this
        try:
            headers = generate_auth_headers(token)
            resp = requests.get(
                url=full_url,
                headers=headers,
            )
            if resp.status_code == 200:
                # self._settings.set(["auth_token"], token, force=True)
                # self._settings.save()
                # self._settings["auth_token"] = token # TODO test this
                if self.ws_connected():
                    self.ws.disconnect()
                self.ws_connect()
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
            status_text = "Error. Please check OctoPrint's internet connection"
        return success, status_text

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
                self._logger_ws.debug("Starting websocket_thread_loop")
                while self.ws_connected():
                    current_time = time.perf_counter()
                    if (current_time - old_time) > self.ws_loop_time:
                        self._logger_ws.debug(f"Sending data: {current_time - old_time}, Loop-time: {self.ws_loop_time}")
                        # time_buffer = max(
                        #     0, current_time - old_time - self.ws_loop_time
                        # )
                        old_time = current_time
                        msg = self.ws_data()
                        # time.sleep(1)  # slow things down to 100ms
                        self._logger_ws.debug("Sending ws_data")
                        self.ws.send_msg(msg)
                        self._logger_ws.debug("Sent ws_data")
                        self.update_ws_send_interval()
                    time.sleep(0.1)  # slow things down to 100ms
                    
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

    def request_webrtc_stream(self):
        """
        Initiates a WebRTC stream by sending a request to the /webcam/webrtc endpoint.

        Note: This method only works with the new camera-streamer stack.

        Returns:
            dict: A dictionary containing WebRTC data if the request is successful, None otherwise.
        """
        self._logger_ws.info("Requesting WebRTC stream")
        # update the last time we requested a webrtc stream
        self.webrtc_request_time = time.perf_counter()
        self.update_ws_send_interval()
        ice_servers = [{"urls": ["stun:stun.l.google.com:19302"]}]
        params = {
            "type": "request",
            "res": None,
            "iceServers": ice_servers,
        }
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(
                self._settings["webrtc_url"], json=params, headers=headers
            )
            if resp.status_code == 200:
                return {"webrtc_data": resp.json()}
        except requests.exceptions.RequestException as e:
            self._logger_ws.error(e)
        except Exception as e:
            self._logger_ws.error(e)
        return None

    def remote_webrtc_stream(self, candidate):
        """
        Sends WebRTC candidate data to the /webcam/webrtc endpoint to establish a remote stream.

        Note: This method only works with the new camera-streamer stack.

        Args:
            candidate (dict): The WebRTC candidate data.

        Returns:
            dict: A dictionary containing WebRTC data if the request is successful, None otherwise.
        """
        params = {
            "type": candidate["type"],
            "id": candidate["id"],
            "candidates": candidate["candidates"],
        }
        headers = {"Content-Type": "application/json"}
        try:
            resp = requests.post(
                self._settings["webrtc_url"], json=params, headers=headers
            )
            if resp.status_code == 200:
                return {"webrtc_data": resp.json()}
        except requests.exceptions.RequestException as e:
            self._logger_ws.error(e)
        except Exception as e:
            self._logger_ws.error(e)
        return None

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
                self._settings["webrtc_url"], json=params, headers=headers
            )
            if resp.status_code == 200:
                return {"webrtc_data": resp.json()}
        except requests.exceptions.RequestException as e:
            self._logger_ws.error(e)
        except Exception as e:
            self._logger_ws.error(e)
        return None