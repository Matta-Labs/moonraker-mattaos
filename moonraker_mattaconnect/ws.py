import json
import logging
import websocket

import os

class Socket:
    def __init__(self, logger_ws, on_message, url, token):
        self._logger_ws = logger_ws
        self.connect(on_message, url, token)

    def run(self):
        try:
            self.socket.run_forever()
        except Exception as e:
            self._logger_ws.error("Socket run: %s", e)

    def send_msg(self, msg):
        try:
            if isinstance(msg, dict):
                msg = json.dumps(msg)
            if self.connected() and self.socket is not None:
                self.socket.send(msg)
        except Exception as e:
            self._logger_ws.error("Socket send_msg: %s", e)
            pass

    def connected(self):
        return self.socket and self.socket.sock and self.socket.sock.connected

    def connect(self, on_message, url, token):
        url = url + "?token=" + token
        self.socket = websocket.WebSocketApp(
            url,
            on_message=on_message,
        )

    def disconnect(self):
        self._logger_ws.debug("Disconnecting the websocket...")
        try:
            self.socket.keep_running = False
            self.socket.close()
            self.socket = None
        except Exception as e:
            self._logger_ws.error("Socket disconnect: %s", e)
        self._logger_ws.debug("The websocket has been closed.")