"""
GPU Optimization Logger Module.
Module logger cho tối ưu hóa GPU.

Provides centralized logging with rotation, formatting, and performance tracking.
Cung cấp logging tập trung với rotation, formatting và theo dõi hiệu năng.
"""

import os
import sys
import json
import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Union
from functools import wraps
import traceback
import threading
from contextlib import contextmanager


class ColorFormatter(logging.Formatter):
    """
    Custom formatter with color support for console output.
    Formatter tùy chỉnh với hỗ trợ màu sắc cho console.
    """
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green  
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.
        Format log record với màu sắc.
        """
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
        
        # Format message
        formatted = super().format(record)
        
        # Reset levelname for other handlers
        record.levelname = levelname
        
        return formatted


class StructuredFormatter(logging.Formatter):
    """
    JSON structured logging formatter for production.
    Formatter JSON có cấu trúc cho production.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        Format log record dạng JSON.
        """
        log_obj = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
            'thread': record.thread,
            'thread_name': record.threadName,
            'process': record.process
        }
        
        # Add exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)
            
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 
                          'funcName', 'levelname', 'levelno', 'lineno',
                          'module', 'msecs', 'message', 'pathname', 'process',
                          'processName', 'relativeCreated', 'thread', 'threadName',
                          'exc_info', 'exc_text', 'stack_info']:
                log_obj[key] = value
                
        return json.dumps(log_obj)


class GPULogger:
    """
    Singleton logger for GPU optimization system.
    Logger singleton cho hệ thống tối ưu hóa GPU.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """
        Ensure singleton instance.
        Đảm bảo instance duy nhất.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """
        Initialize logger configuration.
        Khởi tạo cấu hình logger.
        """
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._loggers: Dict[str, logging.Logger] = {}
            self.structured_formatter = None  # Will be set in _setup_root_logger
            self._setup_root_logger()
            
    def _setup_root_logger(self):
        """
        Setup root logger with handlers.
        Thiết lập root logger với handlers.
        """
        # Import config if available
        try:
            from ..config import get_config
            log_level = get_config('system.log_level', 'INFO')
            log_dir = get_config('system.log_dir', os.environ.get('GPU_OPT_LOG_DIR', '/tmp/gpu_optimization/logs'))
            max_bytes = get_config('system.log_max_bytes', 10485760)  # 10MB
            backup_count = get_config('system.log_backup_count', 5)
            enable_console = get_config('system.log_console', True)
            enable_file = get_config('system.log_file', True)
            structured = get_config('system.log_structured', False)
            # Environment overrides
            if os.environ.get('GPU_OPT_STRUCTURED_LOGGING'):
                structured = os.environ['GPU_OPT_STRUCTURED_LOGGING'].lower() == 'true'
        except ImportError:
            # Fallback if config not available
            log_level = os.environ.get('GPU_OPT_LOG_LEVEL', 'INFO')
            log_dir = os.environ.get('GPU_OPT_LOG_DIR', '/tmp/gpu_optimization/logs')
            max_bytes = 10485760  # 10MB
            backup_count = 5
            enable_console = True
            enable_file = True
            
            
        # Create log directory
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Get root logger
        root_logger = logging.getLogger()  # Root logger for all modules
        root_logger.setLevel(getattr(logging, log_level.upper()))
        root_logger.handlers.clear()
        
        # Console handler
        if enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            if structured:
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_formatter = ColorFormatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)
        
        # File handler with rotation
        if enable_file:
            log_file = log_path / 'gpu_optimization.log'
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            if structured:
                self.structured_formatter = StructuredFormatter()
                file_handler.setFormatter(self.structured_formatter)
            else:
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                )
                file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
        # Error file handler
        error_file = log_path / 'gpu_optimization_errors.log'
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_handler.setFormatter(error_formatter)
        root_logger.addHandler(error_handler)
        
        self._root_logger = root_logger
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get or create a logger instance.
        Lấy hoặc tạo instance logger.
        
        Args:
            name: Logger name (tên logger)
            
        Returns:
            Logger instance
        """
        if name not in self._loggers:
            self._loggers[name] = logging.getLogger(name)
        return self._loggers[name]
    
    def set_level(self, level: Union[str, int], logger_name: Optional[str] = None):
        """
        Set logging level.
        Đặt mức độ logging.
        
        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            logger_name: Specific logger name or None for root
        """
        if isinstance(level, str):
            level = getattr(logging, level.upper())
            
        if logger_name:
            logger = self.get_logger(logger_name)
            logger.setLevel(level)
        else:
            self._root_logger.setLevel(level)
    
    def context(self, **kwargs):
        """
        Context manager for adding context to logs.
        Context manager để thêm context vào logs.
        
        Returns context manager from log_context method.
        """
        return self.log_context(**kwargs)
    
    @contextmanager
    def log_context(self, **kwargs):
        """
        Context manager for adding context to logs.
        Context manager để thêm context vào logs.
        
        Example:
            with logger.log_context(request_id='123', user='admin'):
                logger.info('Processing request')
        """
        # Create a custom LoggerAdapter that adds extra context
        class ContextFilter(logging.Filter):
            def __init__(self, context):
                self.context = context
                
            def filter(self, record):
                # Add context to record
                for key, value in self.context.items():
                    setattr(record, key, value)
                return True
        
        # Add filter to all handlers
        context_filter = ContextFilter(kwargs)
        for handler in self._root_logger.handlers:
            handler.addFilter(context_filter)

        # Monkeypatch existing loggers' bound methods to inject extra into call kwargs so tests can inspect
        patched_methods = {}
        def _patch_logger(lg: logging.Logger):
            methods = ['debug', 'info', 'warning', 'error', 'critical', 'exception', 'log']
            original = {}
            for m in methods:
                orig_func = getattr(lg, m)
                @wraps(orig_func)
                def wrapper(*args, __orig=orig_func, **kw):
                    kw.setdefault('extra', {})
                    kw['extra'].update(kwargs)
                    return __orig(*args, **kw)
                setattr(lg, m, wrapper)
                original[m] = orig_func
            return original
        # Apply patches
        for name, lg in self._loggers.items():
            patched_methods[name] = _patch_logger(lg)
        try:
            yield
        finally:
            # Remove filter
            for handler in self._root_logger.handlers:
                handler.removeFilter(context_filter)
            # Restore methods
            for name, originals in patched_methods.items():
                lg = self._loggers.get(name)
                if lg:
                    for m, orig in originals.items():
                        setattr(lg, m, orig)


def get_logger(name: str = 'gpu_optimization') -> logging.Logger:
    """
    Get logger instance - convenience function.
    Lấy instance logger - hàm tiện ích.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    gpu_logger = GPULogger()
    return gpu_logger.get_logger(name)


def log_execution_time(func=None, *, logger: Optional[logging.Logger] = None):
    """
    Decorator to log function execution time.
    Decorator để log thời gian thực thi hàm.
    
    Args:
        func: Function to decorate (auto-filled when used without parens)
        logger: Logger instance to use
        
    Example:
        @log_execution_time  # Without arguments
        def process_data():
            pass
            
        @log_execution_time(logger=custom_logger)  # With arguments
        def another_process():
            pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            _logger = logger if logger else get_logger(f.__module__)
                
            start_time = datetime.now()
            func_name = f.__name__
            
            try:
                _logger.debug(f"⏱️ Starting {func_name}")
                result = f(*args, **kwargs)
                elapsed = (datetime.now() - start_time).total_seconds()
                _logger.info(f"✅ {func_name} completed in {elapsed:.3f}s")
                return result
            except Exception as e:
                elapsed = (datetime.now() - start_time).total_seconds()
                _logger.error(f"❌ {func_name} failed after {elapsed:.3f}s: {str(e)}")
                raise
                
        return wrapper
    
    # Support both @log_execution_time and @log_execution_time()
    if func is None:
        # Called with arguments: @log_execution_time(...)
        return decorator
    else:
        # Called without arguments: @log_execution_time
        return decorator(func)


def log_errors(func=None, *, 
               logger: Optional[logging.Logger] = None,
               reraise: bool = True,
               default_return: Any = None):
    """
    Decorator to log exceptions.
    Decorator để log exceptions.
    
    Args:
        func: Function to decorate (auto-filled when used without parens)
        logger: Logger instance
        reraise: Whether to reraise exception
        default_return: Default return value if exception
        
    Example:
        @log_errors  # Without arguments
        def risky_operation():
            pass
            
        @log_errors(reraise=False, default_return=None)  # With arguments
        def another_operation():
            pass
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            _logger = logger if logger else get_logger(f.__module__)
                
            try:
                return f(*args, **kwargs)
            except Exception as e:
                _logger.exception(
                    f"Exception in {f.__name__}: {str(e)}"
                )
                if reraise:
                    raise
                return default_return
                
        return wrapper
    
    # Support both @log_errors and @log_errors()
    if func is None:
        # Called with arguments: @log_errors(...)
        return decorator
    else:
        # Called without arguments: @log_errors
        return decorator(func)


# Convenience functions for direct logging
def debug(msg: str, **kwargs):
    """Log debug message (log thông điệp debug)"""
    get_logger().debug(msg, **kwargs)

def info(msg: str, **kwargs):
    """Log info message (log thông điệp info)"""
    get_logger().info(msg, **kwargs)

def warning(msg: str, **kwargs):
    """Log warning message (log cảnh báo)"""
    get_logger().warning(msg, **kwargs)

def error(msg: str, **kwargs):
    """Log error message (log lỗi)"""
    get_logger().error(msg, **kwargs)

def critical(msg: str, **kwargs):
    """Log critical message (log nghiêm trọng)"""
    get_logger().critical(msg, **kwargs)

def exception(msg: str, **kwargs):
    """Log exception with traceback (log exception với traceback)"""
    get_logger().exception(msg, **kwargs)
