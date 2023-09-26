import base64
import requests
import re
import os
from .utils import commandlines_from_json, make_timestamp, remove_cmds

# TODO remove
# import httpx
import time

class MattaPrinter:
    """Virtual Printer class for storing current parameters"""
    def __init__(self, logger, logger_cmd, MOONRAKER_API_URL):
        self._logger = logger
        self._logger_cmd = logger_cmd
        self._printer = self # TODO change in the future
        self.MOONRAKER_API_URL = MOONRAKER_API_URL

        self.printing = False  # True when print job is running
        self.finished = True  # True for loop when print job has just finished

        self.flow_rate = 100  # in percent
        self.feed_rate = 100  # in percent
        self.z_offset = 0.0  # in mm
        self.hotend_temp_offset = 0.0  # in degrees C
        self.bed_temp_offset = 0.0  # in degrees C

        self.gcode_line_num_no_comments = 0
        self.gcode_cmd = ""

        self.new_print_job = False
        self.current_job = None

    #---------------------------------------------------
    # Moonraker API Calls
    #---------------------------------------------------

    def get(self, endpoint):
        try:
            response = requests.get(self.MOONRAKER_API_URL + endpoint)
            # time.sleep(0.5) # TODO REMOVE
            response.raise_for_status()  # Raise an error for bad responses
            return response.json()
        except requests.exceptions.RequestException as e:
            self._logger.error(f"GET request error: {e}")
            return None

    def post(self, endpoint, *args, **kwargs):
        try:
            response = requests.post(self.MOONRAKER_API_URL + endpoint, *args, **kwargs)
            # time.sleep(0.5)  # TODO REMOVE
            response.raise_for_status()  # Raise an error for bad responses
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"POST request error: {e}")
            return None

    def delete(self, endpoint):
        try:
            response = requests.delete(self.MOONRAKER_API_URL + endpoint)
            # time.sleep(0.5)  # TODO REMOVE
            response.raise_for_status()  # Raise an error for bad responses
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"DELETE request error: {e}")
            return None

    # async def get(self, endpoint):
    #     async with httpx.AsyncClient() as client:
    #         try:
    #             response = client.get(self.MOONRAKER_API_URL + endpoint)
    #             response.raise_for_status()  # Raise an error for bad responses
    #             return response.json()
    #         except httpx.HTTPError as e:
    #             self._logger.error(f"GET request error: {e}")
    #             return None

    # async def post(self, endpoint, *args, **kwargs):
    #     async with httpx.AsyncClient() as client:
    #         try:
    #             response = client.post(self.MOONRAKER_API_URL + endpoint, *args, **kwargs)
    #             response.raise_for_status()  # Raise an error for bad responses
    #             return response.json()
    #         except httpx.HTTPError as e:
    #             print(f"POST request error: {e}")
    #             return None

    # contains ["text"] and ["flags"] (a bool for each flag)
    def get_printer_state_object(self):
        content = self.get("/api/printer")
        return content["state"]
    
    # contains ["bed"] and ["tool0"], each with ["actual"], ["offset"], ["target"]
    def get_printer_temp_object(self):
        content = self.get("/api/printer")
        return content["temperature"]
    
    # contains ["filename"], ["total_duration"], ["print_duration"], ["filament_used"]
    def get_print_stats_object(self):
        content = self.get("/printer/objects/query?print_stats")
        return content["result"]["status"]["print_stats"]
    
    # Only using it once so just here to make code more readable. 
    def get_gcode_base_name(self):
        content = self.get("/printer/objects/query?print_stats")
        return content["result"]["status"]["print_stats"]["filename"]
    
    def get_object_list(self):
        content = self.get("/printer/objects/list")
        self._logger.info(f"Object list: {content}")
        return content["result"]["objects"]
    
    def get_all_print_objects(self):
        all_objects_to_query = ['webhooks', 'configfile', 'mcu', 'gcode_move', 'print_stats', 'virtual_sdcard', 'pause_resume', 'display_status', 'gcode_macro CANCEL_PRINT', 'gcode_macro PAUSE', 'gcode_macro RESUME', 'gcode_macro SET_PAUSE_NEXT_LAYER', 'gcode_macro SET_PAUSE_AT_LAYER', 'gcode_macro SET_PRINT_STATS_INFO', 'gcode_macro _TOOLHEAD_PARK_PAUSE_CANCEL', 'gcode_macro _CLIENT_EXTRUDE', 'gcode_macro _CLIENT_RETRACT', 'heaters', 'heater_bed', 'heater_fan hotend_fan', 'fan', 'probe', 'bed_mesh', 'filament_switch_sensor e0_sensor', 'bed_screws', 'stepper_enable', 'motion_report', 'query_endstops', 'idle_timeout', 'system_stats', 'manual_probe', 'toolhead', 'extruder']
        query_string = ""
        for obj in all_objects_to_query:
            query_string += f"{obj}&"
        content = self.get("/printer/objects/query?" + query_string[:-1])
        self._logger.info(f"Objects: {content}")
        return content["result"]
    
    def get_printer_objects(self):
        objects_query = ["gcode_move"]
        query_string = ""
        for obj in objects_query:
            query_string += f"{obj}&"
        content = self.get("/printer/objects/query?" + query_string[:-1])
        result = content["result"]
        result = {
                "flow_rate": result["status"]["gcode_move"]["extrude_factor"],
                "feed_rate": result["status"]["gcode_move"]["speed_factor"],
                "z_offset": result["status"]["gcode_move"]["homing_origin"][2],
        }
        return result
    
    def get_job_data(self):
        # works only for octoprint
        # content = self.get("/api/job")
        # # self._logger.info(f"Job data: {content}")
        # return content
        objects_query = ["print_stats", "virtual_sdcard"]
        query_string = ""
        for obj in objects_query:
            query_string += f"{obj}&"
        content = self.get("/printer/objects/query?" + query_string[:-1])
        result = content["result"]
        return result

    def send_gcode(self, gcode_cmd):
        endpoint = "/printer/gcode/script"
        response = self.post(endpoint, json={"script": gcode_cmd})
        return response

    def clear_print_stats(self):
        gcode = "SDCARD_RESET_FILE"
        response = self.send_gcode(gcode)
        return response

    def get_estimate_print_time(self, filename):
        endpoint = "/server/files/metadata?filename=" + filename
        response = self.get(endpoint)
        return response["result"]["estimated_time"]

    def get_files(self):
        content = self.get("/server/files/list?root=gcodes")
        return content["result"]

    def get_and_refactor_files(self):
        # Octoprint layout
        # "name":"many_prints.gcode",
        # "display":"many_prints.gcode",
        # "path":"many_prints.gcode",
        # "type":"machinecode",
        # "typePath":[
        #     "machinecode",
        #     "gcode"
        # ],
        # "size":14474412,
        # "date":1692807205
        klipper_files = self.get_files()
        files = {}
        files["files"] = {}
        files["files"]["local"] = {}
        for file in klipper_files:
            files["files"]["local"][file["path"]] = {}
            files["files"]["local"][file["path"]]["name"] = file["path"]
            files["files"]["local"][file["path"]]["display"] = file["path"]
            files["files"]["local"][file["path"]]["path"] = file["path"]
            files["files"]["local"][file["path"]]["type"] = 'machinecode'
            files["files"]["local"][file["path"]]["size"] = file["size"]
            files["files"]["local"][file["path"]]["date"] = file["modified"]
        return files
    
    def home_printer(self):
        endpoint = "/printer/gcode/script"
        response = self.post(endpoint, json={"script": "G28"})
        # response = requests.post(f"{self.MOONRAKER_API_URL}/printer/gcode/script", json={"script": "G28"})
        # if response.status_code == 200:
        #     self.logger.info(f"Homing Successful; {response.status_code} {response.text}")
        # else:
        #     self.logger.error(f"Homing Unsuccessful; {response.status_code} {response.text}")
        return response
    
    def select_file(self, filename, sd, printAfterSelect):
        # adds job to queue
        # start queue printing
        # endpoint = "/server/job_queue/job"
        # json = {"filenames": [filename], "reset": False}
        # if printAfterSelect:
        #     response = self.post(endpoint, json=json)
        # else:
        #     response = None
        # self._logger.info(f"Select file response: {response}")
        # response_start = self.queue_start()
        # self._logger.info(f"Start queue response: {response_start}")
        # return response
        # self.queue_reset()

        endpoint = "/printer/print/start"
        json = {"filename": filename}
        if printAfterSelect:
            response = self.post(endpoint, json=json)
        return response
    
    def queue_start(self):
        endpoint = "/server/job_queue/start"
        response = self.post(endpoint)
        return response
    
    def queue_pause(self):
        endpoint = "/server/job_queue/pause"
        response = self.post(endpoint)
        return response
    
    def queue_status(self):
        endpoint = "/server/job_queue/status"
        response = self.get(endpoint)
        return response
    
    def queue_reset(self):
        endpoint = "/server/job_queue/job?all=true"
        response = self.delete(endpoint)
        return response

    def pause_print(self):
        endpoint = "/printer/print/pause"
        response = self.post(endpoint, json={})
        return response
    
    def cancel_print(self):
        endpoint = "/printer/print/cancel"
        response = self.post(endpoint, json={})
        return response
    
    def resume_print(self):
        endpoint = "/printer/print/resume"
        response = self.post(endpoint, json={})
        return response
    
    def get_cmds(self):
        endpoint = "/server/gcode_store?count=50"
        response = self.get(endpoint)
        new_cmds = commandlines_from_json(response["result"])
        return new_cmds
    
    def get_printer_cmds(self):
        """
        Gets the printer commands from the printer object.

        Returns:
            None
        """
        # retreive printer commands from logger_cmd
        logs_path = self._logger_cmd.log_file_path
        lines = None
        with open(logs_path, "r") as f:
            # read last 50 lines
            history = f.readlines()[-50:]
        # get printer commands
        new_cmds = self.get_cmds()
        cleaned_cmds = remove_cmds(history, new_cmds, self._logger)
        for cmd in cleaned_cmds:
            self._logger_cmd.info(cmd)
        return cleaned_cmds
    #---------------------------------------------------
    # Octoprint-MattaConnect code
    #---------------------------------------------------

    def has_job(self):
        """Checks if the printer currently has a print job."""
        printer_state = self.get_printer_state_object()
        state_flags = printer_state["flags"]
        if (
            state_flags["printing"]
            or state_flags["paused"]
            or state_flags["pausing"]
        ):
            self.printing = True
            self.finished = False
            return True
        # self.extruding = False
        self.printing = False
        return False

    def make_job_name(self):
        """Generates a job name string in the format 'filename_timestamp'"""
        job_file_path = self.get_gcode_base_name()
        filename, _ = os.path.splitext(job_file_path)
        dt = make_timestamp()
        return f"{filename}_{dt}"
    
    # def get_current_job(self):
    #     """Retrieves information on the current print job"""
    #     return self._printer.get_gcode_base_name()

    def is_operational(self):
        """Checks if the printer is operational"""
        state = self.get_printer_state_object()
        state_flags = state["flags"]
        return state_flags["ready"] or state_flags["operational"] # or state_flags["error"]

    def just_finished(self):
        """Checks if the state has turned from printing to finished"""
        if self.printing == False and self.finished == False:
            return True
        return False


    # ------------------ Non-processed functions from here ------------------

    def reset(self):
        """Resets all parameters to default values"""
        self.flow_rate = 100
        self.feed_rate = 100
        self.z_offset = 0.0
        self.hotend_temp_offset = 0.0
        self.bed_temp_offset = 0.0

    def set_flow_rate(self, new_flow_rate):
        """
        Sets the flow rate of the printer.

        Args:
            new_flow_rate (int): The new flow rate in percent.

        """
        if new_flow_rate > 0:
            self.flow_rate = new_flow_rate

    def set_feed_rate(self, new_feed_rate):
        """
        Sets the feed rate of the printer.

        Args:
            new_feed_rate (int): The new feed rate in percent.

        """
        if new_feed_rate > 0:
            self.feed_rate = new_feed_rate

    def set_z_offset(self, new_z_offset):
        """
        Sets the Z offset of the printer.

        Args:
            new_z_offset (float): The new Z offset value.

        """
        self.z_offset = new_z_offset

    def connected(self):
        """
        Checks if the printer is connected.

        Returns:
            bool: True if the printer is connected, False otherwise.
        """
        # TODO check 
        # get_current_connection = self._printer.get_current_connection()
        # (connection_string, port, baudrate, printer_profile) = get_current_connection
        # if port is None or baudrate is None:
        #     return False
        return True

    def get_data(self):
        """
        Retrieves data about the printer's current state, temperatures, and other information.

        Returns:
            dict: A dictionary containing the printer's state, temperature data, and printer data.
        """
        printer_data = {}
        printer_data = self.get_and_refactor_files()
        # get job data
        job_data = self.get_job_data()
        # Guide:
        # job[file][name] = job[filename]
        # job[estimatedPrintTime] = job[total_duration]
        # job[filament] = job[filament_used]
        
        # progress[completion] = progress
        # progress[printTime] = job[print_duration]
        # progress[printTimeLeft] = job[total_duration] - job[print_duration]
        self._logger.info("Started job data parsing")
        printer_data["state"] = self.get_printer_state_object()
        filename = job_data["status"]["print_stats"]["filename"]
        is_active = job_data["status"]["virtual_sdcard"]["is_active"]
        if filename == "" or filename == None or is_active == False: 
            estimated_print_time = 0
        elif job_data["status"]["print_stats"]["print_duration"] < 20 or job_data["status"]["virtual_sdcard"]["progress"] < 0.05:
            estimated_print_time = self.get_estimate_print_time(job_data["status"]["print_stats"]["filename"])
        else:
            self._logger.info(f"Print duration: {job_data['status']['print_stats']['print_duration']}, Progress: {job_data['status']['virtual_sdcard']['progress']}")
            estimated_print_time = job_data["status"]["print_stats"]["print_duration"] / job_data["status"]["virtual_sdcard"]["progress"]
        printer_data["job"] = {
            "file": {
                "name": job_data["status"]["print_stats"]["filename"],
                "size" : job_data["status"]["virtual_sdcard"]["file_size"],
            },
            "estimatedPrintTime": estimated_print_time,
            "filament": job_data["status"]["print_stats"]["filament_used"]
        }
        printer_data["progress"] = {
            "completion": job_data["status"]["virtual_sdcard"]["progress"]*100,
            "printTime": job_data["status"]["print_stats"]["print_duration"],
            "printTimeLeft": printer_data["job"]["estimatedPrintTime"] - job_data["status"]["print_stats"]["print_duration"],
        }
        printer_data["offsets"] = {}
        printer_data["resends"] = {
            "count":0,
            "transmitted":0,
            "ratio":0
        }
        data = {
            "state": printer_data["state"]['text'],
            "temperature_data": self.get_printer_temp_object(),
            "printer_data": printer_data,
        }
        return data

    def parse_line_for_updates(self, line):
        """
        Parses a line for updates to printer parameters and applies them.

        Args:
            line (str): The line of text to parse.

        """
        try:
            if "Flow" in line:
                flow_regex = re.compile(r"Flow: (\d+)\%")
                match = flow_regex.search(line)
                new_flow_rate = int(match.group(1))
                self.set_flow_rate(new_flow_rate)
            elif "Feed" in line:
                feed_regex = re.compile(r"Feed: (\d+)\%")
                match = feed_regex.search(line)
                new_feed_rate = int(match.group(1))
                self.set_feed_rate(new_feed_rate)
            elif "Probe Z Offset" in line:
                z_offset_regex = re.compile(r"Probe Z Offset: (-?(\d+)((\.\d+)?))")
                match = z_offset_regex.search(line)
                new_z_offset = float(match.group(1))
                self.set_z_offset(new_z_offset)
        except re.error as e:
            self._logger.error(f"Regex Error in virtual printer: {e}")
        except Exception as e:
            self._logger.error(f"General Error in virtual printer: {e}")

    def handle_cmds(self, json_msg):
        """
        Handles different commands received as JSON messages.

        Args:
            json_msg (dict): The JSON message containing the command.

        """
        if "motion" in json_msg:
            if json_msg["motion"]["cmd"] == "home":
                try:
                    self._printer.home(axes=json_msg["motion"]["axes"])
                except KeyError:
                    self._printer.home()
            elif json_msg["motion"]["cmd"] == "move":
                self._printer.jog(
                    axes=json_msg["motion"]["axes"],
                    relative=True,
                )
            elif json_msg["motion"]["cmd"] == "extrude":
                self._printer.extrude(amount=float(json_msg["motion"]["value"]))
            elif json_msg["motion"]["cmd"] == "retract":
                self._printer.extrude(amount=float(json_msg["motion"]["value"]))
        elif "temperature" in json_msg:
            if json_msg["temperature"]["cmd"] == "temperature":
                self._printer.set_temperature(
                    heater=json_msg["temperature"]["heater"],
                    value=float(json_msg["temperature"]["value"]),
                )
        elif "execute" in json_msg:
            if json_msg["execute"]["cmd"] == "pause":
                self._printer.pause_print()
            elif json_msg["execute"]["cmd"] == "resume":
                self._printer.resume_print()
            elif json_msg["execute"]["cmd"] == "cancel":
                self._printer.cancel_print()
            elif json_msg["execute"]["cmd"] == "toggle":
                self._printer.toggle_pause_print()
            elif json_msg["execute"]["cmd"] == "reset":
                self._printer.clear_print_stats()
        elif "files" in json_msg:
            if json_msg["files"]["cmd"] == "print":
                on_sd = True if json_msg["files"]["loc"] == "sd" else False
                self._printer.select_file(
                    json_msg["files"]["file"], sd=on_sd, printAfterSelect=True
                )
            elif json_msg["files"]["cmd"] == "select":
                on_sd = True if json_msg["files"]["loc"] == "sd" else False
                self._printer.select_file(
                    json_msg["files"]["file"], sd=on_sd, printAfterSelect=False
                )
            elif json_msg["files"]["cmd"] == "upload":
                file_content = base64.b64decode(json_msg["files"]["content"])
                content_string = file_content.decode("utf-8")
                filename  = json_msg["files"]["file"]
                files = {"file": (filename, content_string)}
                response = self.post("/server/files/upload", files=files)
                self._logger.info(f"Upload response: {response}")

            elif json_msg["files"]["cmd"] == "delete":
                destination = FileDestinations.SDCARD if json_msg["files"]["loc"] == "sd" else FileDestinations.LOCAL
                if json_msg["files"]["type"] == "folder":
                    self._file_manager.remove_folder(path=json_msg["files"]["file"], destination=destination)
                else: 
                    self._file_manager.remove_file(path=json_msg["files"]["file"], destination=destination)
            elif json_msg["files"]["cmd"] == "new_folder":
                destination = FileDestinations.SDCARD if json_msg["files"]["loc"] == "sd" else FileDestinations.LOCAL
                self._file_manager.add_folder(
                    path=json_msg["files"]["folder"],
                    destination=destination,
                    ignore_existing=True,
                    display=None,
                )
        elif "gcode" in json_msg:
            if json_msg["gcode"]["cmd"] == "send":
                self._printer.commands(commands=json_msg["gcode"]["lines"])