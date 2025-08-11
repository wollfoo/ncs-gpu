"""
Resource Control Package
========================
GPU and process resource management
Quản lý tài nguyên GPU và tiến trình

Modules:
- pid_mapper: Process ID to GPU mapping (Ánh xạ Process ID với GPU)
- gpu_controller: Direct GPU hardware control (Điều khiển phần cứng GPU trực tiếp)
- power_manager: GPU power management (Quản lý điện năng GPU)
- thermal_control: Temperature monitoring and control (Giám sát và kiểm soát nhiệt độ)
"""

from typing import Optional, Dict, Any, List
import logging

# Import các thành phần chính
from .pid_mapper import PIDMapper
from .gpu_controller import GPUController
from .power_manager import PowerManager
from .thermal_control import ThermalController

# Logging configuration
logger = logging.getLogger(__name__)

__version__ = "2.0.0"
__all__ = [
    "ResourceControlSystem",
    "PIDMapper",
    "GPUController", 
    "PowerManager",
    "ThermalController"
]


class ResourceControlSystem:
    """
    Hệ thống quản lý tài nguyên tích hợp
    Integrated resource management system
    
    Tích hợp tất cả các thành phần quản lý tài nguyên GPU:
    - PID mapping (ánh xạ tiến trình)
    - Hardware control (điều khiển phần cứng)
    - Power management (quản lý điện năng)
    - Thermal control (kiểm soát nhiệt độ)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Khởi tạo hệ thống quản lý tài nguyên
        
        Args:
            config: Configuration dictionary (từ điển cấu hình)
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Khởi tạo các thành phần với lazy loading
        self._pid_mapper: Optional[PIDMapper] = None
        self._gpu_controller: Optional[GPUController] = None
        self._power_manager: Optional[PowerManager] = None
        self._thermal_controller: Optional[ThermalController] = None
        
        self.initialized = False
        
    async def initialize(self) -> bool:
        """
        Khởi tạo bất đồng bộ các thành phần
        Async initialization of components
        
        Returns:
            bool: True nếu khởi tạo thành công
        """
        try:
            # Khởi tạo PID mapper
            self._pid_mapper = PIDMapper(
                self.config.get("pid_mapper", {})
            )
            await self._pid_mapper.initialize()
            
            # Khởi tạo GPU controller
            self._gpu_controller = GPUController(
                self.config.get("gpu_controller", {})
            )
            await self._gpu_controller.initialize()
            
            # Khởi tạo Power manager
            self._power_manager = PowerManager(
                self.config.get("power_manager", {}),
                gpu_controller=self._gpu_controller
            )
            await self._power_manager.initialize()
            
            # Khởi tạo Thermal controller
            self._thermal_controller = ThermalController(
                self.config.get("thermal_control", {}),
                gpu_controller=self._gpu_controller,
                power_manager=self._power_manager
            )
            await self._thermal_controller.initialize()
            
            self.initialized = True
            self.logger.info("✅ Resource Control System khởi tạo thành công")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi khởi tạo Resource Control System: {e}")
            return False
    
    async def allocate_resources(
        self,
        pid: int,
        gpu_index: Optional[int] = None,
        requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Phân bổ tài nguyên cho một process
        Allocate resources for a process
        
        Args:
            pid: Process ID cần phân bổ tài nguyên
            gpu_index: GPU index chỉ định (optional)
            requirements: Yêu cầu tài nguyên cụ thể
            
        Returns:
            Dict chứa thông tin phân bổ tài nguyên
        """
        if not self.initialized:
            await self.initialize()
            
        result = {
            "pid": pid,
            "success": False,
            "allocations": {}
        }
        
        try:
            # 1. Map PID to GPU
            mapping = await self._pid_mapper.map_pid_to_gpu(pid, gpu_index)
            result["allocations"]["gpu_mapping"] = mapping
            
            # 2. Apply hardware controls
            if mapping["gpu_index"] is not None:
                control_result = await self._gpu_controller.apply_controls(
                    gpu_index=mapping["gpu_index"],
                    controls=requirements.get("hardware_controls", {}) if requirements else {}
                )
                result["allocations"]["hardware_controls"] = control_result
                
                # 3. Manage power allocation
                power_result = await self._power_manager.allocate_power(
                    gpu_index=mapping["gpu_index"],
                    pid=pid,
                    requirements=requirements.get("power", {}) if requirements else {}
                )
                result["allocations"]["power"] = power_result
                
                # 4. Apply thermal policies
                thermal_result = await self._thermal_controller.apply_thermal_policy(
                    gpu_index=mapping["gpu_index"],
                    policy=requirements.get("thermal_policy", "balanced") if requirements else "balanced"
                )
                result["allocations"]["thermal"] = thermal_result
                
            result["success"] = True
            
        except Exception as e:
            self.logger.error(f"Lỗi phân bổ tài nguyên cho PID {pid}: {e}")
            result["error"] = str(e)
            
        return result
    
    async def release_resources(self, pid: int) -> bool:
        """
        Giải phóng tài nguyên của một process
        Release resources for a process
        
        Args:
            pid: Process ID cần giải phóng tài nguyên
            
        Returns:
            bool: True nếu giải phóng thành công
        """
        try:
            # Unmap PID from GPU
            await self._pid_mapper.unmap_pid(pid)
            
            # Release power allocation
            await self._power_manager.release_power_allocation(pid)
            
            self.logger.info(f"✅ Đã giải phóng tài nguyên cho PID {pid}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi giải phóng tài nguyên cho PID {pid}: {e}")
            return False
    
    async def get_resource_status(self, pid: Optional[int] = None) -> Dict[str, Any]:
        """
        Lấy trạng thái tài nguyên hiện tại
        Get current resource status
        
        Args:
            pid: Process ID cụ thể (optional)
            
        Returns:
            Dict chứa trạng thái tài nguyên
        """
        status = {
            "pid_mappings": await self._pid_mapper.get_all_mappings() if self._pid_mapper else {},
            "gpu_status": await self._gpu_controller.get_status() if self._gpu_controller else {},
            "power_status": await self._power_manager.get_power_status() if self._power_manager else {},
            "thermal_status": await self._thermal_controller.get_thermal_status() if self._thermal_controller else {}
        }
        
        if pid is not None:
            status["pid_specific"] = await self._pid_mapper.get_pid_info(pid) if self._pid_mapper else None
            
        return status
    
    async def shutdown(self):
        """
        Shutdown resource control system gracefully
        Tắt hệ thống quản lý tài nguyên một cách an toàn
        """
        self.logger.info("🔄 Đang shutdown Resource Control System...")
        
        # Shutdown từng thành phần
        if self._thermal_controller:
            await self._thermal_controller.shutdown()
        if self._power_manager:
            await self._power_manager.shutdown()
        if self._gpu_controller:
            await self._gpu_controller.shutdown()
        if self._pid_mapper:
            await self._pid_mapper.shutdown()
            
        self.initialized = False
        self.logger.info("✅ Resource Control System đã shutdown thành công")
