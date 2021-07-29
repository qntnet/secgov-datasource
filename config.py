import datetime
import io
import logging
import os

PROXY = os.getenv('PROXY')

logging.basicConfig(level=logging.INFO)

DELAY = 0.2
ERROR_DELAY = 0.2
ERROR_403_DELAY = 660

DEBUG = os.getenv("DEBUG", 'false').lower() == 'true'

WORK_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "work")
RAW_DIR = os.path.join(WORK_DIR, "raw")
PARSED_DIR = os.path.join(WORK_DIR, "parsed")

LOCK_FILE = os.path.join(WORK_DIR, 'lock')

FILE_NAME_DELIMITER = '.'

io.DEFAULT_BUFFER_SIZE = 512 * 1024






