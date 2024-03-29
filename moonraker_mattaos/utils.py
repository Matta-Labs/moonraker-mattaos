import json
import psutil
from datetime import datetime
from moonraker_mattaos.gcode_parser import GcodeParser
import sentry_sdk
import os
import requests
import threading
from sys import platform

MATTA_OS_ENDPOINT = "https://os.matta.ai/"
# MATTA_OS_ENDPOINT = "http://localhost"

MATTA_TMP_DATA_DIR = os.path.join(
    os.path.expanduser("~"), ".matta", "moonraker-mattaos"
)

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
    return os.path.expanduser("~/printer_data/gcodes")


def make_timestamp():
    """Generates a timestamp string in the format 'YYYY-MM-DDTHH:MM:SS.sssZ'"""
    dt = datetime.utcnow().isoformat(sep="T", timespec="milliseconds") + "Z"
    return dt


def before_send(event, hint):
    if "logentry" in event and "message" in event["logentry"]:
        list_of_common_errors = [
            "Handshake status 404 Not Found"
            "Handshake status 500 Internal Server Error",
            "Handshake status 502 Bad Gateway",
            "Handshake status 504 Gateway Timeout",
            "Connection refused - goodbye",
            "Temporary failure in name resolution",
        ]
        for error in list_of_common_errors:
            if error in event["logentry"]["message"]:
                return None
        return event


def init_sentry(version):
    sentry_sdk.init(
        dsn="https://687d2f7c85af84f983b3d9980468c24c@o289703.ingest.sentry.io/4506337826570240",
        # Set traces_sample_rate to 0.1 to capture 10%
        # of transactions for performance monitoring.
        traces_sample_rate=0.1,
        before_send=before_send,
        # Set profiles_sample_rate to 0.1 to profile 10%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=0.1,
        release=f"moonraker-mattaos@{version}",
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
        if new_cmds[0] in cmd:
            if check_to_the_end(history, index, new_cmds):
                logger.debug(f"Removing {len(new_cmds)} commands from history")
                if len(history) - index > len(new_cmds):
                    return []
                return new_cmds[(len(history) - index) :]
    return new_cmds


def cherry_pick_cmds(self, terminal_commands):
    """
    Cherry pick the commands that have values in the json list
    """

    cherry_list = self._settings["cherry_pick_cmds"]
    cherry_picked_cmds = []
    self._logger.debug(
        f"cherry_list: {cherry_list}, terminal_commands: {terminal_commands}"
    )
    for cmd in terminal_commands:
        if any(cherry in cmd for cherry in cherry_list):
            cherry_picked_cmds.append(cmd)
    self._logger.debug(f"cherry_picked_cmds: {cherry_picked_cmds}")
    return cherry_picked_cmds


def update_auth_token(self, _settings):
    """
    Updates the auth token from the config file
    """
    auth_token = _settings["auth_token"]
    self._settings["auth_token"] = auth_token
    self.matta_os._settings["auth_token"] = auth_token
    self.matta_os.data_engine._settings["auth_token"] = auth_token
    return auth_token


def get_and_refactor_file(file):
    # Split the path into individual components
    path = file["path"]
    components = path.split("/")

    # Initialize an empty JSON structure
    json_structure = {}

    # Initialize a reference to the current level of the JSON structure
    current_level = json_structure
    current_path = ""
    # Iterate through the components of the path
    for index, component in enumerate(components):
        # Create an empty dictionary for the current component
        current_level[component] = {}
        current_path += "/" + component
        if index != len(components) - 1:
            # refactor file
            current_level[component] = {}
            current_level[component]["name"] = component
            current_level[component]["display"] = component
            current_level[component]["path"] = current_path
            current_level[component]["type"] = "folder"
            current_level[component]["size"] = file["size"]
            current_level[component]["date"] = file["modified"]
            current_level[component]["children"] = {}
            current_level = current_level[component]["children"]
        else:
            # refactor folder
            current_level[component] = {}
            current_level[component]["name"] = component
            current_level[component]["display"] = component
            current_level[component]["path"] = current_path
            current_level[component]["type"] = "machinecode"
            current_level[component]["size"] = file["size"]
            current_level[component]["date"] = file["modified"]
    return json_structure


def merge_json(obj1, obj2):
    if obj1 == {} or obj1 == None:
        return obj2
    if obj2 == {} or obj2 == None:
        return obj1
    for key, value in obj2.items():
        if key in obj1 and isinstance(obj1[key], dict) and isinstance(value, dict):
            # If both values are dictionaries, recursively merge them
            merge_json(obj1[key], value)
        elif key in obj1 and isinstance(obj1[key], set) and isinstance(value, set):
            # If both values are sets, merge them
            obj1[key] |= value
        else:
            # Otherwise, set or update the value in obj1
            obj1[key] = value
    return obj1


def is_temperature_command(gcode):
    if "M104" in gcode or "M109" in gcode:
        return True
    return False


def clean_gcode_list(gcode_list):
    clean_list = []
    for index, gcode in enumerate(gcode_list):
        if gcode["type"] == "response":
            continue
        if is_temperature_command(gcode["message"]):
            continue
        clean_list.append(gcode)
    return clean_list

def get_file_from_backend(bucket_file, auth_token):
    """Gets a file from the backend"""
    full_url = get_api_url() + "print-jobs/printer/gcode/uploadfile"
    headers = generate_auth_headers(auth_token)
    data = {"bucket_file": bucket_file}
    try:
        resp = requests.post(
            url=full_url,
            data=data,
            headers=headers,
            timeout=5,
        )
        # print data from resp
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        raise e  # Windows


def get_file_from_url(file_url):
    """
    Downloads file from URL and returns the file content as a string.

    Args:
        file_url (str): The URL to download the file from.
    """
    try:
        resp = requests.get(file_url, timeout=5)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        raise e


def post_file_to_backend_for_download(file_name, file_content, auth_token):
    """Posts a file to the backend"""
    full_url = get_api_url() + "printers/upload-from-edge/download-request"
    headers = generate_auth_headers(auth_token)
    # get the content type given file name extension (gcode, stl, etc.)
    content_type = "text/plain"
    if (
        file_name.lower().endswith(".stl")
        or file_name.lower().endswith(".obj")
        or file_name.lower().endswith(".3mf")
    ):
        content_type = "application/octet-stream"
    files = {
        "file": (file_name, file_content, content_type),
    }
    try:
        resp = requests.post(
            url=full_url,
            files=files,
            headers=headers,
            timeout=5,
        )
        # print data from resp
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        raise e


def inject_auth_key(webrtc_data, json_msg, logger):
    """
    Injects the auth key into the webrtc data.
    """
    if "auth_key" in json_msg:
        webrtc_data["webrtc_data"]["auth_key"] = json_msg["auth_key"]
        logger.info(
            "MattaOS- injected auth key into webrtc data: %s",
            json_msg["auth_key"],
        )
    return webrtc_data

def read_gcode_file(filename) -> GcodeParser:
    with open(filename, 'r') as f:
        gcode = f.read()
    gcode = GcodeParser(gcode, include_comments=False)
    return gcode