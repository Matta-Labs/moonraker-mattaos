import json
import psutil
from datetime import datetime
import sentry_sdk
import os
from sys import platform

MATTA_OS_ENDPOINT = "https://os.matta.ai/"
# MATTA_OS_ENDPOINT = "http://192.168.68.108"

MATTA_TMP_DATA_DIR = os.path.join(os.path.expanduser("~"), ".matta", "moonraker-mattaconnect")

SAMPLING_TIMEOUT = 1.25  # sample every 1.25 seconds


def get_cloud_http_url():
    """
    Gets the cloud HTTP URL.

    Returns:
        str: The cloud URL.
    """
    # make sure the URL ends with a slash
    url = MATTA_OS_ENDPOINT
    if not url.endswith("/"):
        url += "/"
    return url


def get_cloud_websocket_url():
    """
    Gets the cloud websocket URL.

    Returns:
        str: The cloud URL.
    """
    # make sure the URL ends with a slash
    url = MATTA_OS_ENDPOINT.replace("http", "ws")
    if not url.endswith("/"):
        url += "/"
    return url


def get_api_url():
    """
    Gets the cloud API URL.

    Returns:
        str: The cloud URL.
    """
    return get_cloud_http_url() + "api/v1/"


def generate_auth_headers(token):
    """
    Generates the authentication headers for API requests.

    Returns:
        dict: The authentication headers.
    """
    return {"Authorization": token}


def convert_bytes_to_formatted_string(bytes):
    """
    Converts bytes to a formatted string representation (KB, MB, or GB).
    """
    if bytes > 1024**3:
        bytes = str(round(bytes / 1024**3, 2)) + "GB"
    elif bytes > 1024**2:
        bytes = str(round(bytes / 1024**2, 2)) + "MB"
    elif bytes > 1024:
        bytes = str(round(bytes / 1024, 2)) + "KB"
    return bytes


def get_current_memory_usage(os):
    """
    Gets the current memory usage of the computer/SBC depending on the OS.

    Args:
        os (str): The operating system identifier. Valid values are "linux", "windows", or "mac".

    Returns:
        tuple: A tuple containing three values: used memory (formatted string),
               total memory (formatted string), and memory usage percentage.
    """
    if os == "linux":
        used = psutil.virtual_memory().used
        used = convert_bytes_to_formatted_string(used)
        total = psutil.virtual_memory().total
        total = convert_bytes_to_formatted_string(total)
        percent = psutil.virtual_memory().percent
        return used, total, percent
    elif os == "windows":
        used = psutil.virtual_memory().used
        used = convert_bytes_to_formatted_string(used)
        total = psutil.virtual_memory().total
        total = convert_bytes_to_formatted_string(total)
        percent = psutil.virtual_memory().percent
        return used, total, percent
    elif os == "mac":
        used = psutil.virtual_memory().used
        used = convert_bytes_to_formatted_string(used)
        total = psutil.virtual_memory().total
        total = convert_bytes_to_formatted_string(total)
        percent = psutil.virtual_memory().percent
        return used, total, percent
    else:
        return 0, 0, 0


def get_gcode_upload_dir():
    """
    Returns the path for the directory where G-code files are uploaded.

    Returns:
        str: The path for the G-code upload directory.
    """
    # Force it to be klipper raspberry pi's directory for gcodes
    return os.path.expanduser("~/printer_data/gcodes")

def make_timestamp():
    """Generates a timestamp string in the format 'YYYY-MM-DDTHH:MM:SS.sssZ'"""
    dt = datetime.utcnow().isoformat(sep="T", timespec="milliseconds") + "Z"
    return dt

def init_sentry(version):
    sentry_sdk.init(
        dsn="https://8a15383bc2f14c1ca06e4fe5c1788265@o289703.ingest.sentry.io/4504774026592256",
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        # We recommend adjusting this value in production.
        traces_sample_rate=0.01,
        release=f"MattaOSLite@{version}",
    )

def commandlines_from_json(json):
    """
    Converts a json object to a list of commandlines
    """
    commandlines = []
    for cmd in json["gcode_store"]:
        commandlines.append(cmd["message"])
    return commandlines

def remove_cmds(history, new_cmds, logger):
    """
    Remove the commands in history that are the same as the cmds in new_cmds
    """
    def check_to_the_end(history, history_index, new_cmds):
        new_cmd_index = 0
        while history_index < len(history) and new_cmd_index < len(new_cmds):
            if new_cmds[new_cmd_index] not in history[history_index]:
                return False
            history_index += 1
            new_cmd_index += 1
        return True
    if new_cmds == []:
        return []
    for index, cmd in enumerate(history):
        # logger.debug(f"cmd: {cmd}, {new_cmds[0] in cmd}")
        if new_cmds[0] in cmd:
            if check_to_the_end(history, index, new_cmds):
                logger.debug(f"Removing {len(new_cmds)} commands from history")
                if len(history) - index > len(new_cmds):
                    return []
                return new_cmds[(len(history)- index):]
            # logger.debug(f"cmd: {cmd} is not the same as new_cmds: {new_cmds[0]}")
    return new_cmds

def cherry_pick_cmds(cls, terminal_commands):
    """
    Cherry pick the commands that have values in the json list
    """
    with open(cls._settings["path"], "r") as file:
        data = json.load(file)
        cherry_list = data["terminalCmds"]
    cherry_picked_cmds = []
    cls._logger.debug(f"cherry_list: {cherry_list}, terminal_commands: {terminal_commands}")
    for cmd in terminal_commands:
        if any(cherry in cmd for cherry in cherry_list):
            cherry_picked_cmds.append(cmd)
    cls._logger.debug(f"cherry_picked_cmds: {cherry_picked_cmds}")
    return cherry_picked_cmds

def get_auth_token(cls):
    """
    Gets the auth token from the config file
    """
    with open(cls.settings_path, "r") as file:
        data = json.load(file)
        return data["authToken"]

def update_auth_token(cls):
    """
    Updates the auth token from the config file
    """
    auth_token = get_auth_token(cls)
    cls._settings["auth_token"] = auth_token
    cls.matta_os._settings["auth_token"] = auth_token
    cls.matta_os.data_engine._settings["auth_token"] = auth_token
    return auth_token

# def remove_log_part(lines):
#     """
#     Removes the log part of the lines

#     Example of the Log line:
#     2023-09-19 10:22:32,443 DEBUG    Printer is: Operational
#     =>
#     Printer is: Operational
#     """
#     cleaned_lines = []
#     for line in lines:
#         if "DEBUG" in line:
#             cleaned_lines.append(line.split("DEBUG")[1].strip())
#         if "INFO" in line:
#             cleaned_lines.append(line.split("INFO")[1].strip())
#         if "WARNING" in line:
#             cleaned_lines.append(line.split("WARNING")[1].strip())
#         if "ERROR" in line:
#             cleaned_lines.append(line.split("ERROR")[1].strip())
    
#     return cleaned_lines
