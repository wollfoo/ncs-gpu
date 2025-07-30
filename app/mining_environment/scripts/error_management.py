"""
✅ CENTRALIZED ERROR MANAGEMENT SYSTEM
Standardized error handling, propagation và recovery mechanisms cho mining environment.
"""

import logging
import threading
import time
import traceback
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from concurrent.futures import ThreadPoolExecutor
import json

# Import unified logging
try:
    from .unified_logging import get_unified_logger
except ImportError:
    # Fallback for standalone execution
    from unified_logging import get_unified_logger

class ErrorSeverity(Enum):
    """✅ STANDARDIZED: Error severity levels cho consistent categorization"""
    CRITICAL = "CRITICAL"    # System-breaking errors, immediate attention required
    HIGH = "HIGH"            # Major functionality affected, urgent fix needed
    MEDIUM = "MEDIUM"        # Moderate impact, fix in next iteration
    LOW = "LOW"              # Minor issues, cosmetic problems
    INFO = "INFO"            # Informational messages, not actual errors

class ErrorCode(Enum):
    """✅ STANDARDIZED: Standardized error codes cho system-wide error identification"""
    
    # Strategy-related errors (1000-1999)
    STRATEGY_APPLICATION_FAILED = 1001
    STRATEGY_NOT_FOUND = 1002
    STRATEGY_VALIDATION_FAILED = 1003
    STRATEGY_TIMEOUT = 1004
    
    # Resource management errors (2000-2999)
    RESOURCE_MANAGER_INIT_FAILED = 2001
    RESOURCE_ALLOCATION_FAILED = 2002
    RESOURCE_CLEANUP_FAILED = 2003
    RESOURCE_VALIDATION_FAILED = 2004
    
    # Process-related errors (3000-3999)
    PROCESS_NOT_FOUND = 3001
    PROCESS_ACCESS_DENIED = 3002
    PROCESS_MONITORING_FAILED = 3003
    PROCESS_TERMINATION_FAILED = 3004
    
    # System-level errors (4000-4999)
    SYSTEM_RESOURCE_EXHAUSTED = 4001
    SYSTEM_CONFIGURATION_INVALID = 4002
    SYSTEM_DEPENDENCY_MISSING = 4003
    SYSTEM_PERMISSION_DENIED = 4004
    
    # Communication errors (5000-5999)
    EVENTBUS_COMMUNICATION_FAILED = 5001
    EVENTBUS_SUBSCRIPTION_FAILED = 5002
    EVENTBUS_PUBLISH_FAILED = 5003
    
    # Unknown/Generic errors (9000-9999)
    UNKNOWN_ERROR = 9001
    INTERNAL_ERROR = 9002

@dataclass
class ErrorContext:
    """✅ STANDARDIZED: Rich error context object cho detailed error information"""
    
    error_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    message: str = ""
    module: str = ""
    function: str = ""
    line_number: Optional[int] = None
    process_id: Optional[int] = None
    strategy_name: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_actions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error context to dictionary for serialization"""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp,
            'error_code': self.error_code.value,
            'severity': self.severity.value,
            'message': self.message,
            'module': self.module,
            'function': self.function,
            'line_number': self.line_number,
            'process_id': self.process_id,
            'strategy_name': self.strategy_name,
            'context_data': self.context_data,
            'stack_trace': self.stack_trace,
            'recovery_attempted': self.recovery_attempted,
            'recovery_successful': self.recovery_successful,
            'recovery_actions': self.recovery_actions
        }

class CentralizedErrorReporter:
    """
    ✅ CENTRALIZED: Central error reporting system với EventBus integration.
    Handles error collection, propagation, recovery coordination.
    """
    
    def __init__(self, event_bus: Optional[Any] = None):
        """Initialize centralized error reporter"""
        self.logger = get_unified_logger('error_management')
        self.event_bus = event_bus
        
        # ✅ ERROR STORAGE: In-memory error storage với recent error tracking
        self.error_history: List[ErrorContext] = []
        self.error_lock = threading.RLock()
        self.max_history_size = 1000
        
        # ✅ RECOVERY HANDLERS: Registered recovery mechanisms
        self.recovery_handlers: Dict[ErrorCode, List[Callable]] = {}
        
        # ✅ ERROR METRICS: Track error statistics
        self.error_metrics = {
            'total_errors': 0,
            'errors_by_severity': {sev.value: 0 for sev in ErrorSeverity},
            'errors_by_code': {code.value: 0 for code in ErrorCode},
            'recovery_success_rate': 0.0,
            'recent_errors': []  # Last 10 errors for quick access
        }
        
        # ✅ THREAD POOL: For async error handling
        self.error_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ErrorHandler")
        
        self.logger.info("✅ [ErrorReporter] Centralized error reporter initialized")
    
    def report_error(
        self, 
        error_code: ErrorCode,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        module: str = "",
        function: str = "",
        process_id: Optional[int] = None,
        strategy_name: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ) -> ErrorContext:
        """
        ✅ PRIMARY METHOD: Report error với comprehensive context.
        
        :param error_code: Standardized error code
        :param message: Human-readable error message
        :param severity: Error severity level
        :param module: Module where error occurred
        :param function: Function where error occurred
        :param process_id: Related process ID (if applicable)
        :param strategy_name: Related strategy name (if applicable)
        :param context_data: Additional context information
        :param exception: Python exception object (if available)
        :return: ErrorContext object với unique error ID
        """
        try:
            # ✅ CREATE ERROR CONTEXT
            error_context = ErrorContext(
                error_code=error_code,
                severity=severity,
                message=message,
                module=module,
                function=function,
                process_id=process_id,
                strategy_name=strategy_name,
                context_data=context_data or {},
                stack_trace=traceback.format_exc() if exception else None
            )
            
            # ✅ ENHANCED CONTEXT: Add stack frame information
            import inspect
            frame = inspect.currentframe()
            if frame and frame.f_back:
                caller_frame = frame.f_back
                error_context.line_number = caller_frame.f_lineno
                if not error_context.function:
                    error_context.function = caller_frame.f_code.co_name
                if not error_context.module:
                    error_context.module = caller_frame.f_code.co_filename.split('/')[-1]
            
            # ✅ STORE ERROR
            with self.error_lock:
                self.error_history.append(error_context)
                
                # ✅ CLEANUP: Maintain history size limit
                if len(self.error_history) > self.max_history_size:
                    self.error_history.pop(0)
                
                # ✅ UPDATE METRICS
                self._update_metrics(error_context)
            
            # ✅ LOG ERROR
            log_level = {
                ErrorSeverity.CRITICAL: logging.CRITICAL,
                ErrorSeverity.HIGH: logging.ERROR,
                ErrorSeverity.MEDIUM: logging.WARNING,
                ErrorSeverity.LOW: logging.INFO,
                ErrorSeverity.INFO: logging.INFO
            }.get(severity, logging.WARNING)
            
            self.logger.log(
                log_level,
                f"🚨 [{severity.value}] {error_code.value}: {message} (ID: {error_context.error_id})"
            )
            
            # 🗑️ EventBus removed - error reporting handled by logging system only
            
            # ✅ RECOVERY ATTEMPT: Try automated recovery
            self.error_executor.submit(self._attempt_recovery, error_context)
            
            return error_context
            
        except Exception as e:
            # ✅ FALLBACK: If error reporting fails, use basic logging
            self.logger.critical(f"💥 [ErrorReporter] Failed to report error: {e}")
            return ErrorContext(message=f"Error reporting failed: {e}")
    
    def _update_metrics(self, error_context: ErrorContext) -> None:
        """Update internal error metrics"""
        self.error_metrics['total_errors'] += 1
        self.error_metrics['errors_by_severity'][error_context.severity.value] += 1
        self.error_metrics['errors_by_code'][error_context.error_code.value] += 1
        
        # ✅ RECENT ERRORS: Keep track of recent errors for quick analysis
        self.error_metrics['recent_errors'].append({
            'error_id': error_context.error_id,
            'timestamp': error_context.timestamp,
            'severity': error_context.severity.value,
            'code': error_context.error_code.value,
            'message': error_context.message[:100]  # Truncated for space
        })
        
        # Keep only last 10 recent errors
        if len(self.error_metrics['recent_errors']) > 10:
            self.error_metrics['recent_errors'].pop(0)
    
    def _publish_error_event(self, error_context: ErrorContext) -> None:
        """Publish error event to EventBus"""
        try:
            if self.event_bus and hasattr(self.event_bus, 'publish'):
                event_data = {
                    'event_type': 'system_error',
                    'error_context': error_context.to_dict(),
                    'requires_attention': error_context.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]
                }
                
                self.event_bus.publish('system:error_reported', event_data)
                
        except Exception as e:
            self.logger.warning(f"⚠️ [ErrorReporter] Failed to publish error event: {e}")
    
    def _attempt_recovery(self, error_context: ErrorContext) -> None:
        """Attempt automated error recovery với enhanced coordination"""
        try:
            error_context.recovery_attempted = True
            
            # ✅ COORDINATED RECOVERY: Try ErrorRecoveryCoordinator first for high/critical errors
            if error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                try:
                    self.logger.info(f"🎆 [Recovery] Initiating coordinated recovery for {error_context.error_code.value}")
                    
                    # Import recovery coordinator locally to avoid circular imports
                    try:
                        from .error_recovery_coordinator import get_recovery_coordinator
                    except ImportError:
                        from error_recovery_coordinator import get_recovery_coordinator
                    
                    coordinator = get_recovery_coordinator()
                    recovery_future = coordinator.initiate_recovery(error_context)
                    
                    # ✅ ASYNC HANDLING: Don't wait for result, let it run asynchronously
                    error_context.recovery_actions.append("Coordinated recovery initiated")
                    self.logger.info(f"✅ [Recovery] Coordinated recovery started for error {error_context.error_id}")
                    
                    # Still run legacy recovery as backup
                    
                except Exception as coord_error:
                    self.logger.warning(f"⚠️ [Recovery] Coordinated recovery failed, falling back: {coord_error}")
                    error_context.recovery_actions.append(f"Coordinated recovery failed: {coord_error}")
            
            # ✅ LEGACY RECOVERY: Original recovery logic as fallback
            recovery_handlers = self.recovery_handlers.get(error_context.error_code, [])
            
            if not recovery_handlers:
                self.logger.debug(f"🔧 [Recovery] No legacy recovery handlers for {error_context.error_code.value}")
                return
            
            for handler in recovery_handlers:
                try:
                    recovery_result = handler(error_context)
                    if recovery_result:
                        error_context.recovery_successful = True
                        error_context.recovery_actions.append(f"Legacy handler {handler.__name__} succeeded")
                        self.logger.info(f"✅ [Recovery] Legacy recovery successful for error {error_context.error_id}")
                        break
                    else:
                        error_context.recovery_actions.append(f"Legacy handler {handler.__name__} failed")
                        
                except Exception as recovery_error:
                    error_context.recovery_actions.append(f"Legacy handler {handler.__name__} exception: {recovery_error}")
                    self.logger.warning(f"⚠️ [Recovery] Legacy recovery handler failed: {recovery_error}")
            
            # ✅ UPDATE RECOVERY METRICS
            self._update_recovery_metrics()
            
        except Exception as e:
            self.logger.error(f"❌ [Recovery] Recovery attempt failed: {e}")
    
    def _update_recovery_metrics(self) -> None:
        """Update recovery success rate metrics"""
        try:
            with self.error_lock:
                total_recovery_attempts = sum(1 for e in self.error_history if e.recovery_attempted)
                successful_recoveries = sum(1 for e in self.error_history if e.recovery_successful)
                
                if total_recovery_attempts > 0:
                    self.error_metrics['recovery_success_rate'] = (successful_recoveries / total_recovery_attempts) * 100
                    
        except Exception as e:
            self.logger.debug(f"Error updating recovery metrics: {e}")
    
    def register_recovery_handler(self, error_code: ErrorCode, handler: Callable) -> None:
        """
        ✅ RECOVERY SYSTEM: Register recovery handler cho specific error code.
        
        :param error_code: ErrorCode to handle
        :param handler: Callable recovery function (must accept ErrorContext, return bool)
        """
        try:
            if error_code not in self.recovery_handlers:
                self.recovery_handlers[error_code] = []
            
            self.recovery_handlers[error_code].append(handler)
            self.logger.info(f"✅ [Recovery] Registered handler for {error_code.value}")
            
        except Exception as e:
            self.logger.error(f"❌ [Recovery] Failed to register handler: {e}")
    
    def get_error_metrics(self) -> Dict[str, Any]:
        """
        ✅ MONITORING: Get comprehensive error metrics cho system monitoring.
        
        :return: Dictionary containing error statistics and recent errors
        """
        try:
            with self.error_lock:
                return {
                    'timestamp': time.time(),
                    'total_errors': self.error_metrics['total_errors'],
                    'errors_by_severity': dict(self.error_metrics['errors_by_severity']),
                    'errors_by_code': dict(self.error_metrics['errors_by_code']),
                    'recovery_success_rate': self.error_metrics['recovery_success_rate'],
                    'recent_errors': list(self.error_metrics['recent_errors']),
                    'error_history_size': len(self.error_history),
                    'recovery_handlers_count': sum(len(handlers) for handlers in self.recovery_handlers.values())
                }
                
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Failed to get error metrics: {e}")
            return {'error': str(e)}
    
    def get_errors_by_severity(self, severity: ErrorSeverity, limit: int = 50) -> List[ErrorContext]:
        """Get recent errors filtered by severity"""
        try:
            with self.error_lock:
                filtered_errors = [e for e in self.error_history if e.severity == severity]
                return filtered_errors[-limit:] if filtered_errors else []
                
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Failed to filter errors by severity: {e}")
            return []
    
    def cleanup_old_errors(self, days_to_keep: int = 7) -> int:
        """Clean up old errors from history"""
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            with self.error_lock:
                initial_count = len(self.error_history)
                self.error_history = [e for e in self.error_history if e.timestamp > cutoff_time]
                cleaned_count = initial_count - len(self.error_history)
                
                if cleaned_count > 0:
                    self.logger.info(f"🧹 [ErrorReporter] Cleaned up {cleaned_count} old errors")
                
                return cleaned_count
                
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Error cleanup failed: {e}")
            return 0
    
    def shutdown(self) -> None:
        """Graceful shutdown of error reporter"""
        try:
            self.logger.info("🛑 [ErrorReporter] Shutting down error reporter...")
            
            # ✅ SHUTDOWN EXECUTOR
            self.error_executor.shutdown(wait=True, timeout=10)
            
            # ✅ FINAL METRICS
            final_metrics = self.get_error_metrics()
            self.logger.info(f"📊 [ErrorReporter] Final metrics: {final_metrics['total_errors']} total errors")
            
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Shutdown error: {e}")

# ✅ GLOBAL INSTANCE: Create global error reporter instance
_global_error_reporter: Optional[CentralizedErrorReporter] = None
_reporter_lock = threading.RLock()

def get_error_reporter(event_bus: Optional[Any] = None) -> CentralizedErrorReporter:
    """
    ✅ CONVENIENCE FUNCTION: Get global error reporter instance.
    
    :param event_bus: EventBus instance for error propagation
    :return: CentralizedErrorReporter instance
    """
    global _global_error_reporter
    
    with _reporter_lock:
        if _global_error_reporter is None:
            _global_error_reporter = CentralizedErrorReporter(event_bus)
        return _global_error_reporter

def report_error(
    error_code: ErrorCode,
    message: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    **kwargs
) -> ErrorContext:
    """
    ✅ CONVENIENCE FUNCTION: Quick error reporting using global reporter.
    
    :param error_code: Standardized error code
    :param message: Error message
    :param severity: Error severity
    :param kwargs: Additional context parameters
    :return: ErrorContext object
    """
    reporter = get_error_reporter()
    return reporter.report_error(error_code, message, severity, **kwargs)

def register_recovery_handler(error_code: ErrorCode, handler: Callable) -> None:
    """
    ✅ CONVENIENCE FUNCTION: Register recovery handler using global reporter.
    
    :param error_code: ErrorCode to handle
    :param handler: Recovery handler function
    """
    reporter = get_error_reporter()
    reporter.register_recovery_handler(error_code, handler)

def get_error_metrics() -> Dict[str, Any]:
    """
    ✅ CONVENIENCE FUNCTION: Get error metrics using global reporter.
    
    :return: Error metrics dictionary
    """
    reporter = get_error_reporter()
    return reporter.get_error_metrics()

# ✅ ADVANCED RECOVERY: Delayed import to avoid circular imports

def initiate_coordinated_recovery(
    error_context: ErrorContext,
    retry_config = None,  # Optional[RetryConfig] - avoid forward ref
    priority: int = 5
) -> Any:
    """
    ✅ COORDINATED RECOVERY: Initiate advanced recovery using ErrorRecoveryCoordinator.
    
    :param error_context: Error context from error reporter
    :param retry_config: Custom retry configuration
    :param priority: Recovery priority (1-10)
    :return: Future object for async recovery result
    """
    try:
        from .error_recovery_coordinator import get_recovery_coordinator
    except ImportError:
        from error_recovery_coordinator import get_recovery_coordinator
    
    coordinator = get_recovery_coordinator()
    return coordinator.initiate_recovery(error_context, retry_config, priority)

def register_coordinated_recovery_handler(
    error_code: ErrorCode,
    recovery_handler: Callable,
    strategy = None,  # RecoveryStrategy - avoid forward ref
    retry_config = None  # Optional[RetryConfig] - avoid forward ref
) -> None:
    """
    ✅ COORDINATED HANDLER: Register recovery handler with ErrorRecoveryCoordinator.
    
    :param error_code: Error code to handle
    :param recovery_handler: Recovery handler function
    :param strategy: Recovery strategy to use
    :param retry_config: Custom retry configuration
    """
    try:
        from .error_recovery_coordinator import get_recovery_coordinator, RecoveryStrategy
    except ImportError:
        from error_recovery_coordinator import get_recovery_coordinator, RecoveryStrategy
    
    if strategy is None:
        strategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
    
    coordinator = get_recovery_coordinator()
    coordinator.register_recovery_handler(error_code, recovery_handler, strategy, retry_config)

def get_recovery_performance_metrics() -> Dict[str, Any]:
    """
    ✅ RECOVERY METRICS: Get comprehensive recovery performance metrics.
    
    :return: Recovery performance metrics dictionary
    """
    try:
        from .error_recovery_coordinator import get_recovery_coordinator
    except ImportError:
        from error_recovery_coordinator import get_recovery_coordinator
    
    coordinator = get_recovery_coordinator()
    return coordinator.get_recovery_metrics()