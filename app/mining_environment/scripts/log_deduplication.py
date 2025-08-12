#!/usr/bin/env python3
"""
**Log Deduplication Module** (Mô-đun Loại bỏ Log Trùng lặp – hệ thống khử trùng nhật ký)

Provides intelligent log deduplication to prevent duplicate messages from flooding the logs.
"""

import time
import hashlib
import logging
from typing import Dict, Optional, Tuple
from collections import OrderedDict
from threading import Lock


class LogDeduplicator:
    """
    **Log Deduplicator** (Bộ khử trùng log – công cụ loại bỏ nhật ký trùng lặp)
    
    Features:
    - Message fingerprinting (tạo dấu vân tay thông điệp)
    - Time-based deduplication window (cửa sổ khử trùng theo thời gian)
    - Occurrence counting (đếm số lần xuất hiện)
    - Thread-safe operations (hoạt động an toàn luồng)
    """
    
    def __init__(self, window_seconds: int = 60, max_cache_size: int = 1000):
        """
        Initialize LogDeduplicator.
        
        :param window_seconds: Time window for deduplication (seconds)
        :param max_cache_size: Maximum number of unique messages to cache
        """
        self.window_seconds = window_seconds
        self.max_cache_size = max_cache_size
        self.message_cache: OrderedDict[str, Tuple[float, int]] = OrderedDict()
        self.lock = Lock()
        self.suppressed_count = 0
        self.total_messages = 0
    
    def _generate_fingerprint(self, message: str, level: str = "") -> str:
        """
        Generate a fingerprint for a log message.
        
        :param message: Log message
        :param level: Log level (optional)
        :return: Message fingerprint (hash)
        """
        # Normalize message by removing timestamps and PIDs
        normalized = message
        
        # Remove common timestamp patterns
        import re
        normalized = re.sub(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '', normalized)
        normalized = re.sub(r'\[\d+\.\d+\]', '', normalized)  # Remove [timestamp]
        normalized = re.sub(r'PID[=:]\d+', 'PID=X', normalized)  # Normalize PIDs
        normalized = re.sub(r'GPU[=:]\d+', 'GPU=X', normalized)  # Normalize GPU indices
        normalized = re.sub(r'\d+\.\d+[WMG]B?', 'X', normalized)  # Normalize numbers with units
        
        # Create hash including level
        content = f"{level}:{normalized.strip()}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def should_log(self, message: str, level: str = "") -> Tuple[bool, Optional[str]]:
        """
        Check if a message should be logged or is a duplicate.
        
        :param message: Log message to check
        :param level: Log level
        :return: (should_log, dedup_info) - True if should log, optional dedup info
        """
        fingerprint = self._generate_fingerprint(message, level)
        current_time = time.time()
        
        with self.lock:
            self.total_messages += 1
            
            # Clean old entries outside the window
            self._cleanup_old_entries(current_time)
            
            # Check if message exists in cache
            if fingerprint in self.message_cache:
                last_time, count = self.message_cache[fingerprint]
                
                # Check if within deduplication window
                if current_time - last_time < self.window_seconds:
                    # Update count
                    self.message_cache[fingerprint] = (last_time, count + 1)
                    self.suppressed_count += 1
                    
                    # Log summary every N occurrences
                    if (count + 1) % 10 == 0:
                        dedup_info = f" [Repeated {count + 1}x in last {self.window_seconds}s]"
                        return True, dedup_info
                    
                    return False, None
                else:
                    # Outside window, reset and allow
                    self.message_cache[fingerprint] = (current_time, 1)
                    self.message_cache.move_to_end(fingerprint)
                    return True, None
            else:
                # New message, add to cache
                self.message_cache[fingerprint] = (current_time, 1)
                
                # Enforce cache size limit
                if len(self.message_cache) > self.max_cache_size:
                    self.message_cache.popitem(last=False)
                
                return True, None
    
    def _cleanup_old_entries(self, current_time: float):
        """
        Remove entries outside the deduplication window.
        
        :param current_time: Current timestamp
        """
        cutoff_time = current_time - self.window_seconds
        keys_to_remove = []
        
        for fingerprint, (timestamp, _) in self.message_cache.items():
            if timestamp < cutoff_time:
                keys_to_remove.append(fingerprint)
            else:
                break  # OrderedDict maintains insertion order
        
        for key in keys_to_remove:
            del self.message_cache[key]
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get deduplication statistics.
        
        :return: Dictionary with stats
        """
        with self.lock:
            unique_messages = len(self.message_cache)
            return {
                'total_messages': self.total_messages,
                'suppressed_count': self.suppressed_count,
                'unique_messages': unique_messages,
                'suppression_rate': (self.suppressed_count / max(1, self.total_messages)) * 100
            }
    
    def reset(self):
        """Reset all deduplication state."""
        with self.lock:
            self.message_cache.clear()
            self.suppressed_count = 0
            self.total_messages = 0


class DeduplicatingLogger:
    """
    **Deduplicating Logger Wrapper** (Bộ bọc logger khử trùng – wrapper loại bỏ log trùng lặp)
    
    Wraps a standard logger with deduplication capability.
    """
    
    def __init__(self, logger: logging.Logger, deduplicator: Optional[LogDeduplicator] = None):
        """
        Initialize DeduplicatingLogger.
        
        :param logger: Base logger to wrap
        :param deduplicator: LogDeduplicator instance (creates new if None)
        """
        self.logger = logger
        self.deduplicator = deduplicator or LogDeduplicator()
        self._original_methods = {}
        
        # Store original methods
        for method in ['debug', 'info', 'warning', 'error', 'critical']:
            self._original_methods[method] = getattr(logger, method)
    
    def _log_with_dedup(self, level: str, message: str, *args, **kwargs):
        """
        Log with deduplication (ghi log có khử trùng – loại bỏ trùng lặp).
        
        :param level: Log level (mức log – cấp độ ghi nhật ký)
        :param message: Message to log (thông điệp cần ghi – nội dung log)
        """
        # Format message with args if provided
        if args:
            try:
                message = message % args
            except:
                pass
        
        should_log, dedup_info = self.deduplicator.should_log(message, level)
        
        if should_log:
            # Add dedup info if available
            if dedup_info:
                message = message + dedup_info
            
            # Call original log method
            original_method = self._original_methods[level]
            original_method(message, **kwargs)
    
    def debug(self, message: str, *args, **kwargs):
        """Debug level logging with deduplication."""
        self._log_with_dedup('debug', message, *args, **kwargs)
    
    def info(self, message: str, *args, **kwargs):
        """Info level logging with deduplication."""
        self._log_with_dedup('info', message, *args, **kwargs)
    
    def warning(self, message: str, *args, **kwargs):
        """Warning level logging with deduplication."""
        self._log_with_dedup('warning', message, *args, **kwargs)
    
    def error(self, message: str, *args, **kwargs):
        """Error level logging with deduplication."""
        self._log_with_dedup('error', message, *args, **kwargs)
    
    def critical(self, message: str, *args, **kwargs):
        """Critical level logging with deduplication."""
        self._log_with_dedup('critical', message, *args, **kwargs)
    
    def get_stats(self) -> Dict[str, int]:
        """Get deduplication statistics."""
        return self.deduplicator.get_stats()
    
    def __getattr__(self, name):
        """Forward other attributes to the wrapped logger."""
        return getattr(self.logger, name)


# Global deduplicator instance for shared deduplication
_global_deduplicator = LogDeduplicator(window_seconds=30, max_cache_size=500)


def wrap_logger_with_deduplication(logger: logging.Logger, 
                                  use_global: bool = True,
                                  window_seconds: int = 30) -> DeduplicatingLogger:
    """
    **Wrap logger with deduplication** (Bọc logger với khử trùng – tạo wrapper loại bỏ log trùng lặp)
    
    :param logger: Logger to wrap
    :param use_global: Use global deduplicator (shared across loggers)
    :param window_seconds: Deduplication window if creating new deduplicator
    :return: DeduplicatingLogger instance
    """
    if use_global:
        deduplicator = _global_deduplicator
    else:
        deduplicator = LogDeduplicator(window_seconds=window_seconds)
    
    return DeduplicatingLogger(logger, deduplicator)


def get_deduplication_stats() -> Dict[str, int]:
    """
    **Get global deduplication statistics** (Lấy thống kê khử trùng toàn cục – truy xuất số liệu loại bỏ log trùng lặp)
    
    :return: Dictionary with deduplication stats
    """
    return _global_deduplicator.get_stats()


# Test function
if __name__ == "__main__":
    # Setup test logger
    logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
    test_logger = logging.getLogger("test")
    
    # Wrap with deduplication
    dedup_logger = wrap_logger_with_deduplication(test_logger, use_global=False, window_seconds=5)
    
    # Test the deduplication
    logger.info("🧪 Testing log deduplication...")
    for i in range(5):
        dedup_logger.info("GPU cloaking applied to PID=1234")
        dedup_logger.error("Failed to apply strategy")
        time.sleep(0.5)
    
    # Show stats
    stats = dedup_logger.get_stats()
    logger.info(f"📊 Deduplication Stats: {stats}")
    logger.info(f"📈 Suppression Rate: {stats['suppression_rate']:.1f}%")
