"""
Base classes and interfaces for GPU optimization.

Các lớp cơ sở và giao diện cho tối ưu hóa GPU.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OptimizationStatus(Enum):
    """Optimization status enum.
    
    Enum trạng thái tối ưu hóa.
    """
    IDLE = "idle"           # Nhàn rỗi
    RUNNING = "running"     # Đang chạy
    SUCCESS = "success"     # Thành công
    FAILED = "failed"       # Thất bại
    CANCELLED = "cancelled" # Đã hủy


@dataclass
class OptimizationResult:
    """Result of optimization operation.
    
    Kết quả của thao tác tối ưu hóa.
    """
    status: OptimizationStatus
    metrics: Dict[str, Any] = None
    error: Optional[str] = None
    duration: float = 0.0
    
    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class BaseOptimizer(ABC):
    """Base class for all optimizers.
    
    Lớp cơ sở cho tất cả trình tối ưu hóa.
    """
    
    def __init__(self, name: str = "BaseOptimizer"):
        """Initialize optimizer.
        
        Khởi tạo trình tối ưu hóa.
        
        Args:
            name: Optimizer name
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._status = OptimizationStatus.IDLE
        self._last_result: Optional[OptimizationResult] = None
        
    @abstractmethod
    def optimize(self, target: Any, **kwargs) -> OptimizationResult:
        """Perform optimization.
        
        Thực hiện tối ưu hóa.
        
        Args:
            target: Target to optimize
            **kwargs: Additional arguments
            
        Returns:
            Optimization result
        """
        pass
        
    @abstractmethod
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration.
        
        Xác thực cấu hình.
        
        Args:
            config: Configuration to validate
            
        Returns:
            True if valid, False otherwise
        """
        pass
        
    def get_status(self) -> OptimizationStatus:
        """Get current status.
        
        Lấy trạng thái hiện tại.
        
        Returns:
            Current status
        """
        return self._status
        
    def get_last_result(self) -> Optional[OptimizationResult]:
        """Get last optimization result.
        
        Lấy kết quả tối ưu hóa cuối cùng.
        
        Returns:
            Last result or None
        """
        return self._last_result
        
    def reset(self):
        """Reset optimizer state.
        
        Đặt lại trạng thái trình tối ưu hóa.
        """
        self._status = OptimizationStatus.IDLE
        self._last_result = None
        self.logger.info(f"{self.name} reset")


class BaseStrategy(ABC):
    """Base class for optimization strategies.
    
    Lớp cơ sở cho các chiến lược tối ưu hóa.
    """
    
    def __init__(self, strategy_id: str, name: str):
        """Initialize strategy.
        
        Khởi tạo chiến lược.
        
        Args:
            strategy_id: Unique strategy ID
            name: Strategy name
        """
        self.strategy_id = strategy_id
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
    @abstractmethod
    def execute(self, target_pid: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute strategy.
        
        Thực thi chiến lược.
        
        Args:
            target_pid: Target process ID
            context: Execution context
            
        Returns:
            Execution result with metrics and logs
        """
        pass
        
    @abstractmethod
    def validate(self) -> bool:
        """Validate strategy readiness.
        
        Xác thực sẵn sàng của chiến lược.
        
        Returns:
            True if ready, False otherwise
        """
        pass
        
    def __str__(self):
        return f"{self.name}({self.strategy_id})"


class BaseMonitor(ABC):
    """Base class for monitors.
    
    Lớp cơ sở cho các trình giám sát.
    """
    
    def __init__(self, name: str = "BaseMonitor"):
        """Initialize monitor.
        
        Khởi tạo trình giám sát.
        
        Args:
            name: Monitor name
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        self._is_running = False
        
    @abstractmethod
    def start(self):
        """Start monitoring.
        
        Bắt đầu giám sát.
        """
        pass
        
    @abstractmethod
    def stop(self):
        """Stop monitoring.
        
        Dừng giám sát.
        """
        pass
        
    @abstractmethod
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics.
        
        Thu thập metrics hiện tại.
        
        Returns:
            Current metrics
        """
        pass
        
    def is_running(self) -> bool:
        """Check if monitor is running.
        
        Kiểm tra xem trình giám sát có đang chạy không.
        
        Returns:
            True if running, False otherwise
        """
        return self._is_running


class BaseResourceManager(ABC):
    """Base class for resource managers.
    
    Lớp cơ sở cho các trình quản lý tài nguyên.
    """
    
    def __init__(self, name: str = "BaseResourceManager"):
        """Initialize resource manager.
        
        Khởi tạo trình quản lý tài nguyên.
        
        Args:
            name: Manager name
        """
        self.name = name
        self.logger = logging.getLogger(f"{__name__}.{name}")
        
    @abstractmethod
    def allocate(self, resource_type: str, amount: int) -> bool:
        """Allocate resources.
        
        Phân bổ tài nguyên.
        
        Args:
            resource_type: Type of resource
            amount: Amount to allocate
            
        Returns:
            True if successful, False otherwise
        """
        pass
        
    @abstractmethod
    def release(self, resource_type: str, amount: int) -> bool:
        """Release resources.
        
        Giải phóng tài nguyên.
        
        Args:
            resource_type: Type of resource
            amount: Amount to release
            
        Returns:
            True if successful, False otherwise
        """
        pass
        
    @abstractmethod
    def get_available(self, resource_type: str) -> int:
        """Get available resource amount.
        
        Lấy số lượng tài nguyên khả dụng.
        
        Args:
            resource_type: Type of resource
            
        Returns:
            Available amount
        """
        pass


# Export all base classes
__all__ = [
    'OptimizationStatus',
    'OptimizationResult',
    'BaseOptimizer',
    'BaseStrategy',
    'BaseMonitor',
    'BaseResourceManager'
]
