import json
import logging
import websocket

import os
from logger import setup_logging

WS_LOG_FILE_PATH = os.path.expanduser('~/printer_data/logs/moonraker-mattaconnect-ws.log')
_logger = setup_logging(WS_LOG_FILE_PATH)

class Socket:
    def __init__(self, on_open, on_message, on_close, on_error, url, token):
        self.connect(on_open, on_message, on_close, on_error, url, token)

    def run(self):
        try:
            self.socket.run_forever()
        except Exception as e:
            _logger.error("Socket run: %s", e)
            pass

    def send_msg(self, msg):
        try:
            if isinstance(msg, dict):
                msg = json.dumps(msg)
            if self.connected() and self.socket is not None:
                self.socket.send(msg)
        except Exception as e:
            _logger.error("Socket send_msg: %s", e)
            pass

    def connected(self):
        return self.socket.sock and self.socket.sock.connected

    def connect(self, on_open, on_message, on_close, on_error, url, token):
        url = url + "?token=" + token
        self.socket = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_close=on_close,
            on_error=on_error,
        )

    def disconnect(self):
        _logger.debug("Disconnecting the websocket...")
        self.socket.keep_running = False
        self.socket.close()
        _logger.debug("The websocket has been closed.")