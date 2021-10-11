# vim: sw=4:ts=4:et:cc=120

import logging
import logging.config
import os.path
import sys

from typing import Optional


def initialize_logging(logging_config_path: Optional[str] = None):
    try:
        if logging_config_path is None:
            logging_config_path = os.path.join("etc", "console_logging.ini")

        # TODO handle case when logging configuration is missing

        logging.config.fileConfig(logging_config_path, disable_existing_loggers=False)
    except Exception as e:
        sys.stderr.write(f"unable to load logging configuration: {e}")
        raise e

    logging.getLogger("aiosqlite").setLevel(logging.ERROR)

    # if CONFIG['global'].getboolean('log_sql'):
    # logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
    # logging.getLogger('sqlalchemy.dialects').setLevel(logging.DEBUG)
    # logging.getLogger('sqlalchemy.pool').setLevel(logging.DEBUG)
    # logging.getLogger('sqlalchemy.orm').setLevel(logging.DEBUG)


def get_logger():
    return logging.getLogger("ace")
