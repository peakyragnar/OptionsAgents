import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import os
from pathlib import Path
import sys

class SafeRotatingFileHandler(RotatingFileHandler):
    """Enhanced rotating handler with better error handling"""
    
    def emit(self, record):
        try:
            super().emit(record)
        except Exception:
            # If logging fails, don't crash the application
            self.handleError(record)

def setup_application_logging(app_name: str = "OptionsAgents"):
    """Set up comprehensive logging for the entire application"""
    
    # Create logs directory
    log_dir = Path.home() / "logs" / app_name
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    )
    
    # 1. Console Handler (for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # 2. Main Application Log (rotated by size)
    app_handler = SafeRotatingFileHandler(
        log_dir / "app.log",
        maxBytes=50 * 1024 * 1024,  # 50MB per file
        backupCount=10,  # Keep 10 backup files
        encoding='utf-8'
    )
    app_handler.setFormatter(formatter)
    app_handler.setLevel(logging.INFO)
    root_logger.addHandler(app_handler)
    
    # 3. Error Log (rotated by size, only errors)
    error_handler = SafeRotatingFileHandler(
        log_dir / "errors.log",
        maxBytes=25 * 1024 * 1024,  # 25MB per file
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setFormatter(formatter)
    error_handler.setLevel(logging.ERROR)
    root_logger.addHandler(error_handler)
    
    # 4. Daily Log (rotated by time)
    daily_handler = TimedRotatingFileHandler(
        log_dir / "daily.log",
        when='midnight',
        interval=1,
        backupCount=7,  # Keep 7 days
        encoding='utf-8'
    )
    daily_handler.setFormatter(formatter)
    daily_handler.setLevel(logging.INFO)
    root_logger.addHandler(daily_handler)
    
    return root_logger

def setup_component_logger(component_name: str, log_level: int = logging.INFO):
    """Set up logging for specific components (trade_feed, snapshot, etc.)"""
    
    logger = logging.getLogger(component_name)
    logger.setLevel(log_level)
    
    # Don't propagate to root logger to avoid duplication
    logger.propagate = False
    
    log_dir = Path.home() / "logs" / "OptionsAgents" / "components"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Component-specific rotating log
    handler = SafeRotatingFileHandler(
        log_dir / f"{component_name}.log",
        maxBytes=10 * 1024 * 1024,  # 10MB per component
        backupCount=3,
        encoding='utf-8'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger

# Rate limiting for error logs
class RateLimitedLogger:
    def __init__(self, logger, max_errors_per_minute=10):
        self.logger = logger
        self.max_errors_per_minute = max_errors_per_minute
        self.error_count = 0
        self.last_reset = 0
        
    def error(self, message, *args, **kwargs):
        import time
        current_time = time.time()
        
        # Reset counter every minute
        if current_time - self.last_reset > 60:
            self.error_count = 0
            self.last_reset = current_time
            
        if self.error_count < self.max_errors_per_minute:
            self.logger.error(message, *args, **kwargs)
            self.error_count += 1
        elif self.error_count == self.max_errors_per_minute:
            self.logger.error("Rate limit reached - suppressing further errors for 1 minute")
            self.error_count += 1