import requests

class PrinterAPI:
    def __init__(self, logger, api_url):
        self._logger = logger
        self.api_url = api_url

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

    def has_job(self):
        """Checks if the printer currently has a print job."""
        if (
            self._printer.is_printing()
            or self._printer.is_paused()
            or self._printer.is_pausing()
        ):
            self.printing = True
            self.finished = False
            return True
        self.extruding = False
        self.printing = False
        return False

    def get_printer_state(self):
        try:
            self._logger.info("Getting Printer State.")
            response = requests.get(f"{self.api_url}/api/printer")
            printer_info = response.json()
            printer_state = printer_info['state']['text']
            return printer_state
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Failed to get printer state: {e}")
            return None

