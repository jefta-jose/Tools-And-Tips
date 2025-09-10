import logging
import os
import json
from datetime import datetime, timezone
from typing import Optional


class EnvironmentLogger:
    """
    Custom logger that includes trace ID, timestamp, and environment information
    """
    
    # Environment detection mapping
    ENV_MAPPING = {
        'development': 'development',
        'staging': 'staging',
        'hotfixes': 'hotfixes',
        'production': 'production'
    }
    
    def __init__(self, logger_name: str = __name__, level: str = 'INFO'):
        """
        Initialize the environment logger
        
        Args:
            logger_name: Name of the logger
            level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Clear existing handlers to avoid duplicates
        self.logger.handlers.clear()
        
        # Set up console handler with custom formatter
        console_handler = logging.StreamHandler()
        formatter = self._create_formatter()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Prevent propagation to avoid duplicate logs
        self.logger.propagate = False
        
        self.environment = self._detect_environment()
        self.current_trace_id: Optional[str] = None
    
    def _detect_environment(self) -> str:
        """
        Detect the current environment from various sources
        
        Returns:
            Environment name (development, staging, hotfixes, production)
        """
        # Check environment variables in order of priority
        env_sources = [
            os.getenv('ENVIRONMENT'),
            os.getenv('ENV'),
            os.getenv('STAGE'),
            os.getenv('AWS_LAMBDA_FUNCTION_NAME'),  # For Lambda detection
            'development'  # Default fallback
        ]
        
        for env_var in env_sources:
            if env_var:
                # Extract environment from Lambda function name if present
                if 'lambda' in env_var.lower():
                    if 'prod' in env_var.lower() or 'production' in env_var.lower():
                        return 'production'
                    elif 'staging' in env_var.lower() or 'stage' in env_var.lower():
                        return 'staging'
                    elif 'hotfix' in env_var.lower():
                        return 'hotfixes'
                    else:
                        return 'development'
                
                # Direct environment mapping
                env_lower = env_var.lower().strip()
                return self.ENV_MAPPING.get(env_lower, 'development')
        
        return 'development'
    
    def _create_formatter(self) -> logging.Formatter:
        """
        Create a custom formatter for structured logging with enhanced exception readability
        Returns:
            Custom logging formatter
        """
        import traceback
        class CustomFormatter(logging.Formatter):
            def format(self, record):
                logger_instance = record.__dict__.get('logger_instance')
                trace_id = getattr(logger_instance, 'current_trace_id', None) if logger_instance else None

                log_data = {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'level': record.levelname,
                    'environment': getattr(logger_instance, 'environment', 'unknown') if logger_instance else 'unknown',
                    'trace_id': trace_id,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'module': record.module,
                    'function': record.funcName,
                    'line': record.lineno
                }

                # Enhanced exception info
                if record.exc_info:
                    exc_type, exc_value, exc_tb = record.exc_info
                    # Get root cause safely
                    root_exc = exc_value
                    while root_exc is not None and getattr(root_exc, '__cause__', None):
                        root_exc = root_exc.__cause__
                    # Truncate traceback to last 10 lines for readability
                    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb) if exc_type else []
                    tb_str = ''.join(tb_lines[-10:]).strip() if tb_lines else ''
                    log_data['exception_type'] = exc_type.__name__ if exc_type else None
                    log_data['exception_message'] = str(exc_value) if exc_value else None
                    log_data['root_cause_type'] = type(root_exc).__name__ if root_exc else None
                    log_data['root_cause_message'] = str(root_exc) if root_exc else None
                    log_data['traceback'] = tb_str

                return json.dumps(log_data, ensure_ascii=False)
        return CustomFormatter()
    
    def set_trace_id(self, trace_id: str) -> None:
        """
        Set the current trace ID for all subsequent log messages
        
        Args:
            trace_id: The trace ID to include in logs
        """
        self.current_trace_id = trace_id
    
    def clear_trace_id(self) -> None:
        """Clear the current trace ID"""
        self.current_trace_id = None
    
    def _log_with_context(self, level: str, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """
        Internal method to log with full context
        
        Args:
            level: Log level
            message: Log message
            trace_id: Optional trace ID (overrides current trace ID)
            **kwargs: Additional context to include
        """
        # Use provided trace_id or fall back to current trace_id
        effective_trace_id = trace_id or self.current_trace_id
        
        # Temporarily set trace_id for this log call
        old_trace_id = self.current_trace_id
        self.current_trace_id = effective_trace_id
        
        # Add logger instance to record for formatter access
        extra = {'logger_instance': self, **kwargs}
        
        # Log the message
        getattr(self.logger, level.lower())(message, extra=extra)
        
        # Restore original trace_id
        self.current_trace_id = old_trace_id
    
    def debug(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log debug message"""
        self._log_with_context('DEBUG', message, trace_id, **kwargs)
    
    def info(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log info message"""
        self._log_with_context('INFO', message, trace_id, **kwargs)
    
    def warning(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log warning message"""
        self._log_with_context('WARNING', message, trace_id, **kwargs)
    
    def error(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log error message"""
        self._log_with_context('ERROR', message, trace_id, **kwargs)
    
    def critical(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log critical message"""
        self._log_with_context('CRITICAL', message, trace_id, **kwargs)
    
    def exception(self, message: str, trace_id: Optional[str] = None, **kwargs) -> None:
        """Log exception with traceback"""
        # Use provided trace_id or fall back to current trace_id
        effective_trace_id = trace_id or self.current_trace_id
        
        # Temporarily set trace_id for this log call
        old_trace_id = self.current_trace_id
        self.current_trace_id = effective_trace_id
        
        # Add logger instance to record for formatter access
        extra = {'logger_instance': self, **kwargs}
        
        # Log the exception
        self.logger.exception(message, extra=extra)
        
        # Restore original trace_id
        self.current_trace_id = old_trace_id


# Create a default logger instance
default_logger = EnvironmentLogger('RMRForecast')


def get_logger(name: str = 'RMRForecast', level: str = 'INFO') -> EnvironmentLogger:
    """
    Get a configured environment logger instance
    
    Args:
        name: Logger name
        level: Logging level
        
    Returns:
        Configured EnvironmentLogger instance
    """
    return EnvironmentLogger(name, level)


# Convenience functions using the default logger
def set_trace_id(trace_id: str) -> None:
    """Set trace ID on the default logger"""
    default_logger.set_trace_id(trace_id)


def clear_trace_id() -> None:
    """Clear trace ID on the default logger"""
    default_logger.clear_trace_id()


def debug(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log debug message using default logger"""
    default_logger.debug(message, trace_id, **kwargs)


def info(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log info message using default logger"""
    default_logger.info(message, trace_id, **kwargs)


def warning(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log warning message using default logger"""
    default_logger.warning(message, trace_id, **kwargs)


def error(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log error message using default logger"""
    default_logger.error(message, trace_id, **kwargs)


def critical(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log critical message using default logger"""
    default_logger.critical(message, trace_id, **kwargs)


def exception(message: str, trace_id: Optional[str] = None, **kwargs) -> None:
    """Log exception using default logger"""
    default_logger.exception(message, trace_id, **kwargs)
