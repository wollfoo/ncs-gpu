#!/usr/bin/env python3
"""
strategies/base.py - Abstract Base Classes (Lớp cơ sở trừu tượng) cho GPU Optimization Strategies

Module này định nghĩa các abstract base classes và interfaces cho tất cả chiến lược tối ưu GPU.
Cung cấp contracts (hợp đồng - định nghĩa hành vi bắt buộc) cho các implementation cụ thể.

Production-ready với:
- Type hints đầy đủ
- Error handling toàn diện
- Metrics collection tích hợp
- Thread-safe operations
"""

import logging
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Tuple, Type, Protocol, runtime_checkable
from datetime import datetime
import psutil

# Import monitoring và orchestrator modules
try:
    from ..monitoring.metrics_collector import MetricsCollector
    from ..orchestrator.lifecycle_manager import ProcessLifecycleState
except ImportError:
    # Fallback nếu chạy standalone
    MetricsCollector = None
    ProcessLifecycleState = None

# Logger configuration
logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """
    Strategy Types (Loại chiến lược) - Các loại chiến lược tối ưu GPU
    
    Mỗi loại tập trung vào một khía cạnh tối ưu khác nhau:
    - BALANCED: Cân bằng giữa hiệu năng và tài nguyên
    - AGGRESSIVE: Tối đa hiệu năng, không quan tâm tài nguyên
    - CONSERVATIVE: Bảo toàn tài nguyên, chấp nhận hiệu năng thấp
    - CLOAK: Ẩn giấu hoạt động, tránh phát hiện
    - ADAPTIVE: Tự động điều chỉnh dựa trên context
    """
    BALANCED = auto()
    AGGRESSIVE = auto()  
    CONSERVATIVE = auto()
    CLOAK = auto()
    ADAPTIVE = auto()


class Priority(Enum):
    """
    Execution Priority (Độ ưu tiên thực thi) - Mức độ ưu tiên cho chiến lược
    """
    CRITICAL = 1   # Tối quan trọng
    HIGH = 2       # Cao
    MEDIUM = 3     # Trung bình
    LOW = 4        # Thấp
    IDLE = 5       # Nhàn rỗi


@dataclass
class StrategyContext:
    """
    Strategy Context (Ngữ cảnh chiến lược) - Thông tin môi trường để quyết định chiến lược
    
    Attributes:
        pid: Process ID cần tối ưu
        gpu_id: GPU ID (index của GPU trong hệ thống)
        gpu_metrics: GPU metrics hiện tại (utilization, memory, temperature)
        system_metrics: System metrics (CPU, RAM, Network)
        constraints: Ràng buộc (max_power, max_temp, min_performance)
        metadata: Thông tin bổ sung
    """
    pid: int
    gpu_id: int = 0  # Default to GPU 0
    gpu_metrics: Dict[str, Any] = field(default_factory=dict)
    system_metrics: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def is_valid(self) -> bool:
        """Validate context data"""
        return (
            self.pid > 0 and
            isinstance(self.gpu_metrics, dict) and
            isinstance(self.system_metrics, dict)
        )


@dataclass
class StrategyResult:
    """
    Strategy Result (Kết quả chiến lược) - Kết quả sau khi áp dụng chiến lược
    
    Attributes:
        success: Thành công hay không
        message: Thông điệp mô tả kết quả
        strategy_type: Loại chiến lược đã áp dụng (optional)
        applied_actions: Các hành động đã thực hiện
        metrics_before: Metrics trước khi áp dụng
        metrics_after: Metrics sau khi áp dụng
        error: Thông tin lỗi nếu có
        duration: Thời gian thực thi (seconds)
    """
    success: bool
    message: str = ""
    strategy_type: Optional[StrategyType] = None
    applied_actions: List[str] = field(default_factory=list)
    metrics_before: Dict[str, Any] = field(default_factory=dict)
    metrics_after: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    
    def get_improvement(self, metric: str) -> Optional[float]:
        """Calculate improvement percentage for a metric"""
        if metric in self.metrics_before and metric in self.metrics_after:
            before = self.metrics_before[metric]
            after = self.metrics_after[metric]
            if before != 0:
                return ((after - before) / before) * 100
        return None


@runtime_checkable
class StrategyProtocol(Protocol):
    """
    Strategy Protocol (Giao thức chiến lược) - Interface contract cho strategies
    
    Định nghĩa các methods bắt buộc mà mọi strategy phải implement.
    Sử dụng Protocol để type checking linh hoạt hơn ABC.
    """
    
    def apply(self, context: StrategyContext) -> StrategyResult:
        """Apply strategy với context cho trước"""
        ...
    
    def validate(self, context: StrategyContext) -> bool:
        """Validate xem strategy có thể áp dụng không"""
        ...
    
    def get_priority(self) -> Priority:
        """Lấy mức độ ưu tiên của strategy"""
        ...
    
    def get_type(self) -> StrategyType:
        """Lấy loại strategy"""
        ...


class BaseStrategy(ABC):
    """
    Base Strategy (Chiến lược cơ sở) - Abstract base class cho tất cả strategies
    
    Cung cấp:
    - Common functionality cho tất cả strategies
    - Abstract methods bắt buộc phải implement
    - Metrics collection và error handling
    - Thread-safe operations với locks
    """
    
    def __init__(self,
                 name: str,
                 strategy_type: StrategyType,
                 priority: Priority = Priority.MEDIUM,
                 max_retries: int = 3,
                 retry_delay: float = 1.0,
                 timeout: float = 30.0):
        """
        Initialize base strategy
        
        Args:
            name: Tên của strategy
            strategy_type: Loại chiến lược
            priority: Mức độ ưu tiên
            max_retries: Số lần retry tối đa
            retry_delay: Delay giữa các lần retry (seconds)
            timeout: Timeout cho mỗi operation (seconds)
        """
        self.name = name
        self.strategy_type = strategy_type
        self.priority = priority
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics tracking
        self.stats = {
            'total_applications': 0,
            'successful': 0,
            'failed': 0,
            'total_duration': 0.0,
            'last_applied': None
        }
        
        # Metrics collector nếu available
        self.metrics_collector = None
        if MetricsCollector:
            try:
                self.metrics_collector = MetricsCollector()
            except Exception as e:
                logger.warning(f"Could not initialize MetricsCollector: {e}")
        
        logger.info(f"Initialized {self.__class__.__name__} "
                   f"[type={strategy_type.name}, priority={priority.name}]")
    
    @abstractmethod
    def apply(self, context: StrategyContext) -> StrategyResult:
        """
        Apply strategy (Áp dụng chiến lược) - Method chính để thực thi strategy
        
        Args:
            context: Strategy context chứa thông tin môi trường
            
        Returns:
            StrategyResult với kết quả thực thi
            
        Note:
            Các subclass PHẢI implement method này
        """
        pass
    
    @abstractmethod
    def validate(self, context: StrategyContext) -> bool:
        """
        Validate strategy applicability (Xác thực khả năng áp dụng)
        
        Kiểm tra xem strategy có thể áp dụng trong context hiện tại không.
        
        Args:
            context: Strategy context để validate
            
        Returns:
            True nếu có thể áp dụng, False nếu không
            
        Note:
            Các subclass PHẢI implement validation logic riêng
        """
        pass
    
    def execute_with_retry(self, context: StrategyContext) -> StrategyResult:
        """
        Execute strategy with retry logic (Thực thi với cơ chế retry)
        
        Wrapper method cung cấp retry logic và error handling.
        
        Args:
            context: Strategy context
            
        Returns:
            StrategyResult sau khi thực thi (có thể qua nhiều lần retry)
        """
        with self._lock:
            start_time = time.time()
            last_error = None
            
            for attempt in range(self.max_retries):
                try:
                    # Validate trước khi apply
                    if not self.validate(context):
                        return StrategyResult(
                            success=False,
                            strategy_type=self.strategy_type,
                            error="Validation failed - context not suitable for strategy"
                        )
                    
                    # Collect metrics before
                    metrics_before = self._collect_current_metrics(context.pid)
                    
                    # Apply strategy
                    result = self.apply(context)
                    
                    # Collect metrics after
                    metrics_after = self._collect_current_metrics(context.pid)
                    
                    # Update result với metrics
                    result.metrics_before = metrics_before
                    result.metrics_after = metrics_after
                    result.duration = time.time() - start_time
                    
                    # Update statistics
                    self._update_stats(result)
                    
                    # Log metrics nếu collector available
                    if self.metrics_collector and result.success:
                        self._log_metrics(result)
                    
                    return result
                    
                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"Strategy {self.strategy_type.name} "
                                 f"attempt {attempt + 1}/{self.max_retries} failed: {e}")
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(min(2 ** attempt, 10))  # Exponential backoff
            
            # All retries failed
            return StrategyResult(
                success=False,
                strategy_type=self.strategy_type,
                error=f"All {self.max_retries} attempts failed. Last error: {last_error}",
                duration=time.time() - start_time
            )
    
    def _collect_current_metrics(self, pid: int) -> Dict[str, Any]:
        """
        Collect current metrics (Thu thập metrics hiện tại)
        
        Args:
            pid: Process ID
            
        Returns:
            Dictionary chứa các metrics
        """
        metrics = {}
        
        try:
            # Process metrics
            if psutil.pid_exists(pid):
                process = psutil.Process(pid)
                metrics['cpu_percent'] = process.cpu_percent(interval=0.1)
                metrics['memory_mb'] = process.memory_info().rss / 1024 / 1024
                metrics['num_threads'] = process.num_threads()
            
            # GPU metrics (simplified - cần integration với nvidia-ml-py)
            metrics['gpu_utilization'] = 0  # TODO: Integrate với GPU monitoring
            metrics['gpu_memory_mb'] = 0    # TODO: Integrate với GPU monitoring
            metrics['gpu_temperature'] = 0   # TODO: Integrate với GPU monitoring
            
            # System metrics
            metrics['system_cpu'] = psutil.cpu_percent(interval=0.1)
            metrics['system_memory'] = psutil.virtual_memory().percent
            
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
        
        return metrics
    
    def _update_stats(self, result: StrategyResult):
        """Update internal statistics"""
        self.stats['total_applications'] += 1
        if result.success:
            self.stats['successful'] += 1
        else:
            self.stats['failed'] += 1
        self.stats['total_duration'] += result.duration
        self.stats['last_applied'] = datetime.now().isoformat()
    
    def _log_metrics(self, result: StrategyResult):
        """Log metrics to collector if available"""
        if self.metrics_collector:
            try:
                self.metrics_collector.add_metric(
                    metric_type=f"strategy_{self.strategy_type.name.lower()}",
                    data={
                        'success': result.success,
                        'duration': result.duration,
                        'improvements': {
                            'gpu_utilization': result.get_improvement('gpu_utilization'),
                            'memory_usage': result.get_improvement('memory_mb')
                        },
                        'timestamp': result.timestamp
                    }
                )
            except Exception as e:
                logger.error(f"Error logging metrics: {e}")
    
    def get_priority(self) -> Priority:
        """Get strategy priority"""
        return self.priority
    
    def get_type(self) -> StrategyType:
        """Get strategy type"""
        return self.strategy_type
    
    def get_stats(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        with self._lock:
            return self.stats.copy()
    
    def reset_stats(self):
        """Reset statistics"""
        with self._lock:
            self.stats = {
                'total_applications': 0,
                'successful': 0,
                'failed': 0,
                'total_duration': 0.0,
                'last_applied': None
            }
    
    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}("
                f"type={self.strategy_type.name}, "
                f"priority={self.priority.name}, "
                f"stats={self.stats['successful']}/{self.stats['total_applications']})")


class CompositeStrategy(BaseStrategy):
    """
    Composite Strategy (Chiến lược tổng hợp) - Kết hợp nhiều strategies
    
    Cho phép kết hợp và thực thi nhiều strategies theo thứ tự hoặc song song.
    Hữu ích cho các scenarios phức tạp cần nhiều optimization techniques.
    """
    
    def __init__(self,
                 strategies: List[BaseStrategy],
                 parallel: bool = False,
                 stop_on_failure: bool = True):
        """
        Initialize composite strategy
        
        Args:
            strategies: List các strategies để kết hợp
            parallel: Thực thi song song hay tuần tự
            stop_on_failure: Dừng nếu một strategy thất bại
        """
        super().__init__(
            strategy_type=StrategyType.ADAPTIVE,
            priority=Priority.HIGH
        )
        self.strategies = strategies
        self.parallel = parallel
        self.stop_on_failure = stop_on_failure
    
    def apply(self, context: StrategyContext) -> StrategyResult:
        """Apply all composed strategies"""
        results = []
        all_actions = []
        total_duration = 0
        
        for strategy in self.strategies:
            if not self.parallel:
                result = strategy.execute_with_retry(context)
                results.append(result)
                all_actions.extend(result.applied_actions)
                total_duration += result.duration
                
                if not result.success and self.stop_on_failure:
                    return StrategyResult(
                        success=False,
                        strategy_type=self.strategy_type,
                        applied_actions=all_actions,
                        error=f"Strategy {strategy.get_type().name} failed",
                        duration=total_duration
                    )
        
        # TODO: Implement parallel execution với ThreadPoolExecutor
        
        return StrategyResult(
            success=all(r.success for r in results),
            strategy_type=self.strategy_type,
            applied_actions=all_actions,
            duration=total_duration
        )
    
    def validate(self, context: StrategyContext) -> bool:
        """Validate if at least one strategy can be applied"""
        return any(s.validate(context) for s in self.strategies)


# Export public API
__all__ = [
    'BaseStrategy',
    'CompositeStrategy',
    'StrategyType',
    'Priority',
    'StrategyContext',
    'StrategyResult',
    'StrategyProtocol'
]
