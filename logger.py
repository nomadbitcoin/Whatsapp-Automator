import logging
import os
from datetime import datetime
from typing import Optional
from config import (
    LOG_LEVEL,
    LOG_DIR,
    LOG_TO_FILE,
    LOG_TO_CONSOLE,
    LOG_FORMAT
)


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, 'logger'):
            self.setup_logger()

    def setup_logger(self, override_level: Optional[str] = None):
        """Configure logging with file and console handlers"""
        # Use override_level if provided, otherwise use config
        log_level = override_level.upper() if override_level else LOG_LEVEL
        numeric_level = getattr(logging, log_level)

        # Create logger
        self.logger = logging.getLogger('WhatsAppBot')
        self.logger.setLevel(numeric_level)

        # Prevent adding handlers multiple times
        if self.logger.handlers:
            self.logger.handlers.clear()

        # Add file handler if enabled
        if LOG_TO_FILE:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            log_file = os.path.join(LOG_DIR, f'whatsapp_bot_{timestamp}.log')

            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(numeric_level)
            file_formatter = logging.Formatter(LOG_FORMAT['file'])
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        # Add console handler if enabled
        if LOG_TO_CONSOLE:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(numeric_level)
            console_formatter = logging.Formatter(LOG_FORMAT['console'])
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        self.logger.debug(f"Logger initialized with level {log_level}")

    def get_logger(self):
        return self.logger

    def set_level(self, level: str):
        """Dynamically change log level"""
        numeric_level = getattr(logging, level.upper())
        self.logger.setLevel(numeric_level)
        for handler in self.logger.handlers:
            handler.setLevel(numeric_level)
        self.logger.debug(f"Log level changed to {level}")


# Global logger instance
logger = Logger().get_logger()
