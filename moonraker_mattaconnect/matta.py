from .data import DataEngine

class MattaCore:
    def __init__(self, logger, settings):
        self._logger = logger
        self._settings = settings

        self.data_engine = DataEngine(self._logger, self._settings)