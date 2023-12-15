import os
import logging
import colorlog

def setup_logging(logger_name, log_file_path):
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

    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # Add handlers with appropriate levels
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.DEBUG)  # Set the desired level for the file handler
    file_handler.setFormatter(log_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)  # Set the desired level for the stream handler
    stream_handler.setFormatter(log_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.log_file_path = log_file_path

    return logger