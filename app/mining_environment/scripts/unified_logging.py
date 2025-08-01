"""
✅ UNIFIED LOGGING SYSTEM
Centralized logging management cho tất cả mining environment modules.
Eliminates duplicate loggers và standardizes log formatting across system.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, Optional, Any
from logging.handlers import RotatingFileHandler
import sys
import time

class UnifiedLoggerManager:
    """
    ✅ CENTRALIZED: Unified logger management system cho consistent logging.
    Single point of control cho tất cả module loggers với standardized formatting.
    """
    
    _instance: Optional['UnifiedLoggerManager'] = None
    _lock = threading.RLock()
    
    # ✅ STANDARDIZED: Common log format cho all modules
    STANDARD_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    # ✅ HIERARCHY: Logger name hierarchy cho organized logging
    LOGGER_HIERARCHY = {
        'mining_environment': {
            'level': logging.INFO,
            'file': 'mining_environment.log',
            'description': 'Main mining environment logger'
        },
        'mining_environment.resource_manager': {
            'level': logging.INFO,
            'file': 'resource_manager.log',
            'description': 'Resource management operations'
        },
        'mining_environment.cloak_strategies': {
            # ⚙️ Nâng mức log lên DEBUG để ghi chi tiết chiến lược cloaking
            'level': logging.DEBUG,
            'file': 'cloak_strategies.log',
            'description': 'Cloaking strategy implementations'
        },
        'mining_environment.cpu_cloaking': {
            # 🔧 CPU cloaking operations (Legacy external stealth only)
            'level': logging.DEBUG,
            'file': 'cpu_cloaking_manager.log',
            'description': 'CPU cloaking legacy operations and external stealth attempts'
        },
        'mining_environment.gpu_cloaking': {
            # 🔧 GPU-specific cloaking operations (Emergency Fix)
            'level': logging.DEBUG,
            'file': 'gpu_cloaking_manager.log',
            'description': 'GPU cloaking and thermal spoofing operations'
        },
        'mining_environment.resource_control': {
            # ⚙️ Nâng mức log lên DEBUG để ghi chi tiết điều khiển tài nguyên
            'level': logging.DEBUG,
            'file': 'resource_control.log',
            'description': 'Low-level resource control operations'
        },
        'mining_environment.coordination': {
            # ✅ NEW: Hook Coordinator và PHASE 3++ coordination logging
            'level': logging.DEBUG,
            'file': 'coordination.log',
            'description': 'Hook coordination và PHASE 3++ sequencing operations'
        },
        # 🗑️ EventBus logger removed - replaced by DirectPIDRegistry
        # DirectPIDRegistry uses existing loggers for communication tracking
    }
    
    def __new__(cls) -> 'UnifiedLoggerManager':
        """Singleton pattern implementation"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize unified logger manager"""
        if getattr(self, '_initialized', False):
            return
            
        self._initialized = True
        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: Dict[str, logging.Handler] = {}
        
        # ✅ CENTRALIZED: Create centralized log directory
        try:
            self.log_dir = Path('/app/mining_environment/logs')
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to local directory if /app is not accessible
            self.log_dir = Path('./logs')
            self.log_dir.mkdir(parents=True, exist_ok=True)
            print(f"⚠️ [UnifiedLogging] Using fallback log directory: {self.log_dir.absolute()}")
        
        # ✅ SETUP: Initialize all loggers in hierarchy
        self._setup_logger_hierarchy()
        
        print(f"✅ [UnifiedLogging] Initialized {len(self._loggers)} loggers in hierarchy")
    
    def _setup_logger_hierarchy(self) -> None:
        """Setup complete logger hierarchy with standardized configuration"""
        try:
            for logger_name, config in self.LOGGER_HIERARCHY.items():
                self._create_logger(
                    name=logger_name,
                    level=config['level'],
                    log_file=config['file'],
                    description=config['description']
                )
            
            # ✅ ROOT LOGGER: Setup root logger for fallback
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.WARNING)  # Only critical messages to root
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Failed to setup logger hierarchy: {e}")
            raise
    
    def _create_logger(self, name: str, level: int, log_file: str, description: str) -> logging.Logger:
        """Create individual logger with standardized configuration"""
        try:
            logger = logging.getLogger(name)
            
            # ✅ PREVENT DUPLICATES: Clear existing handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            
            logger.setLevel(level)
            logger.propagate = False  # Prevent propagation to avoid duplicates
            
            # ✅ FILE HANDLER: Rotating file handler cho log rotation
            log_path = self.log_dir / log_file
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=10*1024*1024,  # 10MB max per file
                backupCount=5,           # Keep 5 backup files
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            
            # ✅ CONSOLE HANDLER: Console output cho important messages
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.WARNING)  # Only warnings+ to console
            
            # ✅ STANDARDIZED FORMATTING
            formatter = logging.Formatter(self.STANDARD_FORMAT, self.DATE_FORMAT)
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)
            
            # ✅ ADD HANDLERS
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            
            # ✅ STORE REFERENCES
            self._loggers[name] = logger
            self._handlers[f"{name}_file"] = file_handler
            self._handlers[f"{name}_console"] = console_handler
            
            # ✅ LOG CREATION
            logger.info(f"📋 [UnifiedLogging] Logger '{name}' initialized: {description}")
            
            return logger
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Failed to create logger '{name}': {e}")
            raise
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        ✅ PRIMARY METHOD: Get logger by name from unified hierarchy.
        
        :param name: Logger name (can be full hierarchy or module name)
        :return: Configured logger instance
        """
        try:
            # ✅ DIRECT MATCH: Check if exact name exists
            if name in self._loggers:
                return self._loggers[name]
            
            # ✅ HIERARCHY MATCH: Try to find in hierarchy
            full_name = f"mining_environment.{name}"
            if full_name in self._loggers:
                return self._loggers[full_name]
            
            # ✅ FALLBACK: Create ad-hoc logger if not in hierarchy
            return self._create_adhoc_logger(name)
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Error getting logger '{name}': {e}")
            # ✅ SAFETY FALLBACK: Return basic logger
            return logging.getLogger(name)
    
    def _create_adhoc_logger(self, name: str) -> logging.Logger:
        """Create ad-hoc logger for modules not in predefined hierarchy"""
        try:
            logger_name = f"mining_environment.{name}" if not name.startswith('mining_environment') else name
            
            return self._create_logger(
                name=logger_name,
                level=logging.INFO,
                log_file=f"{name.replace('.', '_')}.log",
                description=f"Ad-hoc logger for {name}"
            )
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Failed to create ad-hoc logger '{name}': {e}")
            return logging.getLogger(name)
    
    def get_logging_status(self) -> Dict[str, Any]:
        """
        ✅ MONITORING: Get comprehensive logging system status.
        
        :return: Dictionary containing logging system metrics
        """
        try:
            status = {
                'timestamp': time.time(),
                'total_loggers': len(self._loggers),
                'total_handlers': len(self._handlers),
                'log_directory': str(self.log_dir),
                'loggers': {},
                'disk_usage': {}
            }
            
            # ✅ LOGGER DETAILS
            for name, logger in self._loggers.items():
                status['loggers'][name] = {
                    'level': logging.getLevelName(logger.level),
                    'handlers': len(logger.handlers),
                    'propagate': logger.propagate
                }
            
            # ✅ DISK USAGE
            try:
                for log_file in self.log_dir.glob('*.log'):
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    status['disk_usage'][log_file.name] = f"{size_mb:.2f} MB"
            except Exception:
                status['disk_usage'] = "Unable to calculate"
            
            return status
            
        except Exception as e:
            return {'error': f"Failed to get logging status: {e}"}
    
    def cleanup_old_logs(self, days_to_keep: int = 7) -> int:
        """
        ✅ MAINTENANCE: Clean up old log files to manage disk space.
        
        :param days_to_keep: Number of days to keep log files
        :return: Number of files cleaned up
        """
        try:
            import time
            import os
            
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            cleaned_count = 0
            
            for log_file in self.log_dir.glob('*.log*'):
                try:
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        cleaned_count += 1
                except Exception:
                    continue  # Skip files that can't be deleted
            
            if cleaned_count > 0:
                # Log to main logger
                main_logger = self.get_logger('mining_environment')
                main_logger.info(f"🧹 [UnifiedLogging] Cleaned up {cleaned_count} old log files")
            
            return cleaned_count
            
        except Exception as e:
            print(f"❌ [UnifiedLogging] Log cleanup failed: {e}")
            return 0

# ✅ GLOBAL INSTANCE: Create global unified logger manager instance
_unified_manager = UnifiedLoggerManager()

def get_unified_logger(name: str) -> logging.Logger:
    """
    ✅ CONVENIENCE FUNCTION: Get unified logger instance.
    
    :param name: Module name (e.g., 'resource_manager', 'cloak_strategies')
    :return: Configured logger from unified hierarchy
    """
    return _unified_manager.get_logger(name)

def get_logging_status() -> Dict[str, Any]:
    """
    ✅ CONVENIENCE FUNCTION: Get logging system status.
    
    :return: Logging system metrics and status
    """
    return _unified_manager.get_logging_status()

def cleanup_logs(days_to_keep: int = 7) -> int:
    """
    ✅ CONVENIENCE FUNCTION: Clean up old log files.
    
    :param days_to_keep: Days to keep log files (default: 7)
    :return: Number of files cleaned up
    """
    return _unified_manager.cleanup_old_logs(days_to_keep)