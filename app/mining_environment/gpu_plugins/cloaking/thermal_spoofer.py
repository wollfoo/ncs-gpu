"""Thermal Spoofing Plugin - Wrapper cho libtempspoof.so"""
import os
import logging
from typing import Dict, Any, List
from ..core.interfaces import IGPUCloakService

# Import Thermal logger (đúng mapping cho thermal_spoofer)
try:
    from ...scripts.module_loggers import get_thermal_logger
    logger = get_thermal_logger()
except ImportError:
    # Fallback nếu không có logger
    logger = logging.getLogger(__name__)

class ThermalSpoofer(IGPUCloakService):
    """Plugin quản lý thermal spoofing qua LD_PRELOAD"""
    
    def __init__(self):
        self.enabled = False
        self.fake_temperature = 50
        self.add_noise = False
        self.lib_path = ""
        
    @property
    def name(self) -> str:
        return "thermal_spoofer"
        
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Khởi tạo thermal spoofer"""
        self.fake_temperature = config.get('fake_temperature', 50)
        self.add_noise = config.get('add_noise', False)
        
        # Kiểm tra libtempspoof.so có tồn tại
        self.lib_path = config.get('lib_path', '/opt/hooks/libtempspoof.so')
        if not os.path.exists(self.lib_path):
            logger.warning(f"Thermal spoof library not found: {self.lib_path}")
            gpu_cloak_logger.log_thermal_spoofing(
                action="INITIALIZE",
                status="FAILED",
                lib_path=self.lib_path,
                error_details=f"Thermal spoof library not found: {self.lib_path}"
            )
            return False
            
        logger.info(f"Thermal spoofer initialized with fake_temp={self.fake_temperature}")
        gpu_cloak_logger.log_thermal_spoofing(
            action="INITIALIZE",
            status="SUCCESS",
            fake_temperature=self.fake_temperature,
            add_noise=self.add_noise,
            lib_path=self.lib_path
        )
        return True
        
    def start(self) -> bool:
        """Start thermal spoofing"""
        if not os.path.exists(self.lib_path):
            logger.error(f"Thermal spoof library not found: {self.lib_path}")
            return False
            
        # Thiết lập LD_PRELOAD
        current_preload = os.environ.get('LD_PRELOAD', '')
        if self.lib_path not in current_preload:
            if current_preload:
                os.environ['LD_PRELOAD'] = f"{current_preload}:{self.lib_path}"
            else:
                os.environ['LD_PRELOAD'] = self.lib_path
                
        # Thiết lập environment variables
        os.environ['ENABLE_TEMP_SPOOF'] = '1'
        os.environ['SPOOF_TEMP_VALUE'] = str(self.fake_temperature)
        os.environ['TEMP_SPOOF_ADD_NOISE'] = '1' if self.add_noise else '0'
        
        self.enabled = True
        logger.info("✅ Thermal spoofing started")
        return True
        
    def stop(self) -> None:
        """Stop thermal spoofing"""
        os.environ['ENABLE_TEMP_SPOOF'] = '0'
        self.enabled = False
        logger.info("🛑 Thermal spoofing stopped")
        
    def enable_cloaking(self, strategies: List[str]) -> bool:
        """Kích hoạt thermal cloaking"""
        if 'thermal_spoof' in strategies:
            return self.start()
        return False
        
    def disable_cloaking(self) -> bool:
        """Tắt thermal cloaking"""
        self.stop()
        return True
        
    def update_fake_metrics(self, metrics: Dict[str, int]) -> None:
        """Cập nhật fake temperature"""
        if 'temperature' in metrics:
            self.fake_temperature = metrics['temperature']
            os.environ['SPOOF_TEMP_VALUE'] = str(self.fake_temperature)
            logger.info(f"Updated fake temperature to {self.fake_temperature}°C")
            
    def get_active_strategies(self) -> List[str]:
        """Lấy danh sách strategies đang active"""
        return ['thermal_spoof'] if self.enabled else []
        
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái thermal spoofer"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'fake_temperature': self.fake_temperature,
            'add_noise': self.add_noise,
            'lib_path': self.lib_path,
            'lib_exists': os.path.exists(self.lib_path)
        }