import logging
import os
import sys

LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "epub_reader.log"))
_configured = False


def configure_logging():
	global _configured
	if _configured:
		return
	logging.basicConfig(
		level=logging.DEBUG,
		format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
		handlers=[
			logging.FileHandler(LOG_FILE),
			logging.StreamHandler(sys.stdout),
		],
	)
	logging.getLogger(__name__).info(f"Logging initialized. Log file: {LOG_FILE}")
	_configured = True


def get_logger(name):
	configure_logging()
	return logging.getLogger(name)
