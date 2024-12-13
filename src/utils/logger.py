"""
Logging utility for the Quake Query tool.
"""
import logging
import os
from datetime import datetime

class Logger:
    def __init__(self):
        self.setup_logger()

    def setup_logger(self):
        """Setup logging configuration"""
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # Create logger
        self.logger = logging.getLogger('QuakeQuery')
        self.logger.setLevel(logging.DEBUG)

        # Create handlers
        timestamp = datetime.now().strftime('%Y%m%d')
        file_handler = logging.FileHandler(f'logs/quake_query_{timestamp}.log', encoding='utf-8')
        console_handler = logging.StreamHandler()

        # Set levels
        file_handler.setLevel(logging.DEBUG)
        console_handler.setLevel(logging.INFO)

        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )

        # Add formatters to handlers
        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)

    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)

    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)

# Global logger instance
logger = Logger() 