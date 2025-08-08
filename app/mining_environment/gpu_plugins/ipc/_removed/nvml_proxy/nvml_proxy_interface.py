# -*- coding: utf-8 -*-
"""NVML Proxy Plugin Interface

Interface cho NVML Proxy Plugin - quản lý lifecycle và configuration
của nvml_proxy_daemon.py như một GPU plugin.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class INVMLProxyPlugin(ABC):
    """Interface cho NVML Proxy Plugin"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Tên plugin"""
        pass
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize plugin với configuration
        
        Args:
            config: Configuration dictionary
            
        Returns:
            bool: True nếu thành công
        """
        pass
    
    @abstractmethod
    def start(self) -> bool:
        """Start plugin và proxy daemon
        
        Returns:
            bool: True nếu thành công
        """
        pass
    
    @abstractmethod
    def stop(self) -> bool:
        """Stop plugin và proxy daemon
        
        Returns:
            bool: True nếu thành công
        """
        pass
    
    @abstractmethod
    def start_proxy_daemon(self) -> bool:
        """Khởi động proxy daemon process
        
        Returns:
            bool: True nếu daemon started successfully
        """
        pass
    
    @abstractmethod
    def stop_proxy_daemon(self) -> bool:
        """Dừng proxy daemon process
        
        Returns:
            bool: True nếu daemon stopped successfully
        """
        pass
    
    @abstractmethod
    def is_proxy_running(self) -> bool:
        """Kiểm tra proxy daemon status
        
        Returns:
            bool: True nếu daemon đang chạy
        """
        pass
    
    @abstractmethod
    def update_proxy_config(self, config: Dict[str, Any]) -> bool:
        """Cập nhật proxy configuration
        
        Args:
            config: New configuration dictionary
            
        Returns:
            bool: True nếu cập nhật thành công
        """
        pass
    
    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái plugin
        
        Returns:
            Dict: Status information
        """
        pass
    
    @abstractmethod
    def enable_cloaking(self, strategies: Optional[List[str]] = None) -> bool:
        """Enable cloaking functionality
        
        Args:
            strategies: List of strategies (optional)
            
        Returns:
            bool: True nếu thành công
        """
        pass
    
    @abstractmethod
    def disable_cloaking(self) -> bool:
        """Disable cloaking functionality
        
        Returns:
            bool: True nếu thành công
        """
        pass
    
    @abstractmethod
    def update_fake_metrics(self, metrics: Dict[str, int]) -> bool:
        """Update fake metrics configuration
        
        Args:
            metrics: Dictionary của metrics values
            
        Returns:
            bool: True nếu cập nhật thành công
        """
        pass