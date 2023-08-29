import os
import logging
import colorlog

def setup_logging(log_file_path):
    # Create the logs directory if it doesn't exist
    logs_dir = os.path.dirname(log_file_path)
    os.makedirs(logs_dir, exist_ok=True)

    # Configure logging with colorlog
    log_formatter = colorlog.ColoredFormatter(
        "%(asctime)s %(log_color)s%(levelname)-8s%(reset)s %(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'blue',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Add handlers
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setFormatter(log_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(log_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
