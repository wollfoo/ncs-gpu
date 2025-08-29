"""
✅ CENTRALIZED ERROR RECOVERY COORDINATOR
Advanced error recovery system với automatic retry mechanisms, exponential backoff,
và coordinated recovery strategies cho mining environment.
"""

import time
import threading
from typing import Dict, Any, Optional, List, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random
from concurrent.futures import ThreadPoolExecutor, Future
from collections import defaultdict, deque

# Import unified logging và error management
try:
    from .module_loggers import get_coordination_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, ErrorContext
except ImportError:
    from module_loggers import get_coordination_logger
    from error_management import get_error_reporter, ErrorCode, ErrorSeverity, ErrorContext

class RecoveryStrategy(Enum):
    """✅ RECOVERY STRATEGIES: Các chiến lược khôi phục cho different error types"""
    IMMEDIATE_RETRY = "immediate_retry"           # Thử lại ngay lập tức
    EXPONENTIAL_BACKOFF = "exponential_backoff"   # Thử lại với exponential backoff
    CIRCUIT_BREAKER = "circuit_breaker"           # Circuit breaker pattern
    ADAPTIVE_RETRY = "adaptive_retry"             # Adaptive retry based on error patterns

class RecoveryStatus(Enum):
    """✅ RECOVERY STATUS: Trạng thái của recovery attempts"""
    PENDING = "pending"                 # Đang chờ xử lý
    IN_PROGRESS = "in_progress"         # Đang thực hiện recovery
    SUCCESS = "success"                 # Khôi phục thành công
    FAILED = "failed"                   # Khôi phục thất bại  
    EXHAUSTED = "exhausted"             # Đã thử hết các attempts

@dataclass
class RetryConfig:
    """✅ RETRY CONFIGURATION: Cấu hình cho retry mechanisms"""
    max_attempts: int = 3                         # Số lần thử tối đa
    initial_delay_ms: float = 100.0               # Thời gian delay ban đầu (ms)
    max_delay_ms: float = 30000.0                 # Thời gian delay tối đa (ms)
    backoff_multiplier: float = 2.0               # Hệ số nhân cho exponential backoff
    jitter_enabled: bool = True                   # Có sử dụng random jitter không
    jitter_range: float = 0.1                     # Phạm vi jitter (±10%)

class ErrorRecoveryCoordinator:
    """
    ✅ CENTRALIZED ERROR RECOVERY: Advanced error recovery coordination system.
    
    Features:
    - Automatic retry với exponential backoff và jitter
    - Multiple recovery strategies based on error types
    - Circuit breaker pattern cho failing operations
    - Thread-safe concurrent recovery operations
    """
    
    def __init__(
        self,
        max_concurrent_recoveries: int = 10,
        default_retry_config: Optional[RetryConfig] = None
    ):
        """Initialize error recovery coordinator"""
        
        # ✅ CONFIGURATION
        self.max_concurrent_recoveries = max_concurrent_recoveries
        self.default_retry_config = default_retry_config or RetryConfig()
        
        # ✅ RECOVERY HANDLERS: Registered recovery functions by error code
        self.recovery_handlers: Dict[ErrorCode, List[Callable]] = defaultdict(list)
        self.recovery_strategies: Dict[ErrorCode, RecoveryStrategy] = {}
        self.custom_retry_configs: Dict[ErrorCode, RetryConfig] = {}
        
        # ✅ CIRCUIT BREAKERS: Circuit breaker state per error type
        self.circuit_breakers: Dict[ErrorCode, Dict[str, Any]] = defaultdict(lambda: {
            'failure_count': 0,
            'last_failure_time': 0,
            'state': 'CLOSED',  # CLOSED, OPEN, HALF_OPEN
            'next_attempt_time': 0
        })
        
        # ✅ METRICS: Recovery performance tracking
        self.recovery_metrics = {
            'total_sessions': 0,
            'successful_recoveries': 0,
            'failed_recoveries': 0,
            'success_rate_by_error_code': defaultdict(float)
        }
        self.metrics_lock = threading.RLock()
        
        # ✅ EXECUTION: Thread pool for concurrent recovery operations
        self.executor = ThreadPoolExecutor(
            max_workers=max_concurrent_recoveries, 
            thread_name_prefix="ErrorRecovery"
        )
        
        # ✅ LOGGING: Unified logging integration
        self.logger = get_coordination_logger()
        self.error_reporter = get_error_reporter()
        
        self.logger.info("✅ [RecoveryCoordinator] Error recovery coordinator initialized (bộ điều phối khôi phục lỗi đã khởi tạo – hệ thống phục hồi sẵn sàng)")
    
    def register_recovery_handler(
        self, 
        error_code: ErrorCode, 
        recovery_handler: Callable[[ErrorContext], Any],
        strategy: RecoveryStrategy = RecoveryStrategy.EXPONENTIAL_BACKOFF,
        retry_config: Optional[RetryConfig] = None
    ) -> None:
        """
        ✅ HANDLER REGISTRATION: Register recovery handler cho specific error code.
        """
        try:
            self.recovery_handlers[error_code].append(recovery_handler)
            self.recovery_strategies[error_code] = strategy
            
            if retry_config:
                self.custom_retry_configs[error_code] = retry_config
            
            self.logger.info(f"✅ [RecoveryCoordinator] Registered handler for {error_code.value} với strategy: {strategy.value}")
            
        except Exception as e:
            self.error_reporter.report_error(
                ErrorCode.INTERNAL_ERROR,
                f"Failed to register recovery handler: {e}",
                ErrorSeverity.MEDIUM,
                module='error_recovery_coordinator',
                function='register_recovery_handler'
            )
    
    def initiate_recovery(
        self, 
        error_context: ErrorContext,
        custom_retry_config: Optional[RetryConfig] = None,
        priority: int = 5
    ) -> Future[Any]:
        """
        ✅ RECOVERY INITIATION: Start recovery process cho một error.
        """
        try:
            # ✅ CIRCUIT BREAKER CHECK
            if self._is_circuit_breaker_open(error_context.error_code):
                self.logger.warning(f"🚫 [RecoveryCoordinator] Circuit breaker OPEN (cầu dao mở – tạm ngưng nỗ lực) for {error_context.error_code.value}")
                future = Future()
                future.set_exception(Exception("Circuit breaker is open"))
                return future
            
            # ✅ HANDLER SELECTION
            handlers = self.recovery_handlers.get(error_context.error_code, [])
            if not handlers:
                self.logger.warning(f"⚠️ [RecoveryCoordinator] No recovery handlers for {error_context.error_code.value}")
                future = Future()
                future.set_exception(Exception(f"No recovery handlers for {error_context.error_code.value}"))
                return future
            
            # ✅ CONFIG SELECTION
            retry_config = custom_retry_config or self.custom_retry_configs.get(
                error_context.error_code, self.default_retry_config
            )
            
            # ✅ ASYNC EXECUTION
            handler = handlers[0]  # Use first handler
            strategy = self.recovery_strategies.get(error_context.error_code, RecoveryStrategy.EXPONENTIAL_BACKOFF)
            
            future = self.executor.submit(self._execute_recovery, error_context, handler, strategy, retry_config)
            
            self.logger.info(f"🚀 [RecoveryCoordinator] Initiated recovery for error: {error_context.error_id}")
            return future
            
        except Exception as e:
            self.error_reporter.report_error(
                ErrorCode.INTERNAL_ERROR,
                f"Failed to initiate recovery: {e}",
                ErrorSeverity.HIGH,
                module='error_recovery_coordinator',
                function='initiate_recovery'
            )
            future = Future()
            future.set_exception(e)
            return future
    
    def _execute_recovery(
        self, 
        error_context: ErrorContext, 
        handler: Callable, 
        strategy: RecoveryStrategy,
        config: RetryConfig
    ) -> Any:
        """Execute recovery với specified strategy"""
        
        try:
            with self.metrics_lock:
                self.recovery_metrics['total_sessions'] += 1
            
            if strategy == RecoveryStrategy.IMMEDIATE_RETRY:
                result = self._execute_immediate_retry(error_context, handler, config)
            elif strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
                result = self._execute_exponential_backoff(error_context, handler, config)
            elif strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                result = self._execute_circuit_breaker_recovery(error_context, handler)
            else:
                result = self._execute_exponential_backoff(error_context, handler, config)
            
            # ✅ SUCCESS
            with self.metrics_lock:
                self.recovery_metrics['successful_recoveries'] += 1
            
            self._update_circuit_breaker_success(error_context.error_code)
            self.logger.info(f"✅ [RecoveryCoordinator] Recovery successful (khôi phục thành công – xử lý lỗi xong) for error: {error_context.error_id}")
            
            return result
            
        except Exception as e:
            # ✅ FAILURE
            with self.metrics_lock:
                self.recovery_metrics['failed_recoveries'] += 1
            
            self._update_circuit_breaker_failure(error_context.error_code)
            self.logger.error(f"❌ [RecoveryCoordinator] Recovery failed (khôi phục thất bại – lỗi tiếp diễn) for error: {error_context.error_id} - {e}")
            raise e
    
    def _execute_exponential_backoff(
        self, 
        error_context: ErrorContext, 
        handler: Callable, 
        config: RetryConfig
    ) -> Any:
        """Execute recovery với exponential backoff"""
        current_delay = config.initial_delay_ms
        
        for attempt in range(1, config.max_attempts + 1):
            try:
                if attempt > 1:
                    delay_with_jitter = self._calculate_delay_with_jitter(current_delay, config)
                    self.logger.debug(f"⏳ [RecoveryCoordinator] Waiting {delay_with_jitter:.1f}ms before attempt {attempt}")
                    time.sleep(delay_with_jitter / 1000.0)
                
                self.logger.info(f"🔄 [RecoveryCoordinator] Executing attempt {attempt}/{config.max_attempts}")
                result = handler(error_context)
                
                self.logger.info(f"✅ [RecoveryCoordinator] Attempt {attempt} successful")
                return result
                
            except Exception as e:
                self.logger.warning(f"❌ [RecoveryCoordinator] Attempt {attempt} failed: {e}")
                
                if attempt >= config.max_attempts:
                    raise Exception(f"Recovery exhausted after {config.max_attempts} attempts. Last error: {e}")
                
                current_delay = min(current_delay * config.backoff_multiplier, config.max_delay_ms)
        
        raise Exception("Recovery attempts exhausted without success")
    
    def _execute_immediate_retry(
        self, 
        error_context: ErrorContext, 
        handler: Callable, 
        config: RetryConfig
    ) -> Any:
        """Execute recovery với immediate retry"""
        for attempt in range(1, config.max_attempts + 1):
            try:
                self.logger.info(f"🔄 [RecoveryCoordinator] Immediate retry attempt {attempt}/{config.max_attempts}")
                result = handler(error_context)
                return result
                
            except Exception as e:
                if attempt >= config.max_attempts:
                    raise Exception(f"Immediate retry exhausted after {config.max_attempts} attempts. Last error: {e}")
        
        raise Exception("Immediate retry attempts exhausted without success")
    
    def _execute_circuit_breaker_recovery(
        self, 
        error_context: ErrorContext, 
        handler: Callable
    ) -> Any:
        """Execute recovery với circuit breaker pattern"""
        error_code = error_context.error_code
        breaker = self.circuit_breakers[error_code]
        
        if breaker['state'] == 'OPEN':
            if time.time() < breaker['next_attempt_time']:
                raise Exception(f"Circuit breaker is OPEN for {error_code.value}")
            else:
                breaker['state'] = 'HALF_OPEN'
                self.logger.info(f"🔄 [CircuitBreaker] Transitioning to HALF_OPEN for {error_code.value}")
        
        try:
            result = handler(error_context)
            
            # ✅ SUCCESS
            breaker['state'] = 'CLOSED'
            breaker['failure_count'] = 0
            
            self.logger.info(f"✅ [CircuitBreaker] SUCCESS - Circuit breaker CLOSED for {error_code.value}")
            return result
            
        except Exception as e:
            # ✅ FAILURE
            breaker['failure_count'] += 1
            breaker['last_failure_time'] = time.time()
            
            if breaker['failure_count'] >= 5:  # Threshold
                breaker['state'] = 'OPEN'
                breaker['next_attempt_time'] = time.time() + 60  # 60 second timeout
                self.logger.warning(f"🚫 [CircuitBreaker] OPEN - Too many failures for {error_code.value}")
            
            raise e
    
    def _calculate_delay_with_jitter(self, base_delay_ms: float, config: RetryConfig) -> float:
        """Add random jitter to delay"""
        if not config.jitter_enabled:
            return base_delay_ms
        
        jitter_amount = base_delay_ms * config.jitter_range
        jitter = random.uniform(-jitter_amount, jitter_amount)
        return max(0, base_delay_ms + jitter)
    
    def _is_circuit_breaker_open(self, error_code: ErrorCode) -> bool:
        """Check if circuit breaker is open"""
        breaker = self.circuit_breakers[error_code]
        
        if breaker['state'] == 'OPEN':
            if time.time() >= breaker['next_attempt_time']:
                return False
            return True
        
        return False
    
    def _update_circuit_breaker_success(self, error_code: ErrorCode) -> None:
        """Update circuit breaker on success"""
        breaker = self.circuit_breakers[error_code]
        breaker['failure_count'] = max(0, breaker['failure_count'] - 1)
        
        if breaker['state'] in ['HALF_OPEN', 'OPEN']:
            breaker['state'] = 'CLOSED'
    
    def _update_circuit_breaker_failure(self, error_code: ErrorCode) -> None:
        """Update circuit breaker on failure"""
        breaker = self.circuit_breakers[error_code]
        breaker['failure_count'] += 1
        breaker['last_failure_time'] = time.time()
    
    def get_recovery_metrics(self) -> Dict[str, Any]:
        """Get comprehensive recovery metrics"""
        try:
            with self.metrics_lock:
                total_recoveries = self.recovery_metrics['successful_recoveries'] + self.recovery_metrics['failed_recoveries']
                success_rate = 0.0
                if total_recoveries > 0:
                    success_rate = (self.recovery_metrics['successful_recoveries'] / total_recoveries) * 100.0
                
                circuit_breaker_status = {}
                for error_code, breaker in self.circuit_breakers.items():
                    circuit_breaker_status[error_code.value] = {
                        'state': breaker['state'],
                        'failure_count': breaker['failure_count'],
                        'last_failure_time': breaker['last_failure_time']
                    }
                
                return {
                    'timestamp': time.time(),
                    'overall_performance': {
                        'total_sessions': self.recovery_metrics['total_sessions'],
                        'successful_recoveries': self.recovery_metrics['successful_recoveries'],
                        'failed_recoveries': self.recovery_metrics['failed_recoveries'],
                        'overall_success_rate_percent': round(success_rate, 2)
                    },
                    'circuit_breakers': circuit_breaker_status,
                    'configuration': {
                        'max_concurrent_recoveries': self.max_concurrent_recoveries,
                        'default_max_attempts': self.default_retry_config.max_attempts,
                        'default_initial_delay_ms': self.default_retry_config.initial_delay_ms
                    }
                }
                
        except Exception as e:
            self.logger.error(f"❌ [RecoveryCoordinator] Failed to get recovery metrics: {e}")
            return {'error': str(e), 'timestamp': time.time()}
    
    def shutdown(self) -> None:
        """Graceful shutdown"""
        try:
            self.logger.info("🛑 [RecoveryCoordinator] Shutting down error recovery coordinator...")
            self.executor.shutdown(wait=True, timeout=30)
            
            final_metrics = self.get_recovery_metrics()
            self.logger.info(
                f"📊 [RecoveryCoordinator] Final metrics: "
                f"{final_metrics['overall_performance']['successful_recoveries']} successful, "
                f"{final_metrics['overall_performance']['failed_recoveries']} failed recoveries"
            )
            
        except Exception as e:
            self.logger.error(f"❌ [RecoveryCoordinator] Shutdown error: {e}")


# ✅ GLOBAL INSTANCE
_global_recovery_coordinator: Optional[ErrorRecoveryCoordinator] = None
_coordinator_lock = threading.RLock()

def get_recovery_coordinator(
    max_concurrent_recoveries: int = 10
) -> ErrorRecoveryCoordinator:
    """Get global recovery coordinator instance"""
    global _global_recovery_coordinator
    
    with _coordinator_lock:
        if _global_recovery_coordinator is None:
            _global_recovery_coordinator = ErrorRecoveryCoordinator(
                max_concurrent_recoveries=max_concurrent_recoveries
            )
        return _global_recovery_coordinator

def get_recovery_metrics() -> Dict[str, Any]:
    """Get recovery metrics from global coordinator"""
    coordinator = get_recovery_coordinator()
    return coordinator.get_recovery_metrics()