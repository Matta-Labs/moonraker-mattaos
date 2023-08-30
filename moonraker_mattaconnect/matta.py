from moonraker_mattaconnect.data import DataEngine
from moonraker_mattaconnect.printer import MattaPrinter


class MattaCore:
    def __init__(self, logger, settings, MOONRAKER_API_URL):
        self._logger = logger
        self._settings = settings
        self.MOONRAKER_API_URL = MOONRAKER_API_URL

        self._printer = MattaPrinter(self._logger, self.MOONRAKER_API_URL)

        self.data_engine = DataEngine(self._logger, self._settings, self._printer)