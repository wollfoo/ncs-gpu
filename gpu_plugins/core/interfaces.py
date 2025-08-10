"""GPU Plugin Interfaces - Định nghĩa các interface chuẩn cho GPU plugins"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class IGPUPlugin(ABC):
    """Base interface cho tất cả GPU plugins"""
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Khởi tạo plugin với cấu hình
        
        Args:
            config: Dictionary chứa cấu hình plugin
            
        Returns:
            bool: True nếu khởi tạo thành công
        """
        pass
    
    @abstractmethod
    def start(self) -> bool:
        """Bắt đầu hoạt động plugin
        
        Returns:
            bool: True nếu khởi động thành công
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Dừng plugin và cleanup resources"""
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái hiện tại của plugin
        
        Returns:
            Dict: Dictionary chứa thông tin trạng thái
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tên của plugin"""
        pass

class IGPUCloakService(IGPUPlugin):
    """Interface cho GPU cloaking services"""
    
    @abstractmethod
    def enable_cloaking(self, strategies: List[str]) -> bool:
        """Kích hoạt các chiến lược cloaking
        
        Args:
            strategies: Danh sách tên các chiến lược cloaking
            
        Returns:
            bool: True nếu kích hoạt thành công
        """
        pass
    
    @abstractmethod
    def disable_cloaking(self) -> bool:
        """Tắt tất cả chiến lược cloaking
        
        Returns:
            bool: True nếu tắt thành công
        """
        pass
    
    @abstractmethod
    def update_fake_metrics(self, metrics: Dict[str, int]) -> None:
        """Cập nhật fake metrics
        
        Args:
            metrics: Dictionary chứa các metric và giá trị fake
        """
        pass
    
    @abstractmethod
    def get_active_strategies(self) -> List[str]:
        """Lấy danh sách các chiến lược đang active
        
        Returns:
            List[str]: Danh sách tên chiến lược active
        """
        pass

# GPU telemetry filtering removed for memory optimization

class IGPUHookManager(IGPUPlugin):
    """Interface cho GPU hook management"""
    
    @abstractmethod
    def install_hooks(self, hook_types: List[str]) -> bool:
        """Cài đặt các hooks
        
        Args:
            hook_types: Danh sách loại hooks cần cài đặt
            
        Returns:
            bool: True nếu cài đặt thành công
        """
        pass
    
    @abstractmethod
    def uninstall_hooks(self) -> bool:
        """Gỡ bỏ tất cả hooks
        
        Returns:
            bool: True nếu gỡ bỏ thành công
        """
        pass
    
    @abstractmethod
    def get_installed_hooks(self) -> List[str]:
        """Lấy danh sách hooks đã cài đặt
        
        Returns:
            List[str]: Danh sách tên hooks
        """
        pass