"""
PID Mapper Module
=================
Process ID to GPU mapping and tracking
Ánh xạ và theo dõi Process ID với GPU

Chức năng chính:
- Map PID to GPU devices (Ánh xạ PID với thiết bị GPU)
- Track process health (Theo dõi sức khỏe tiến trình)
- Detect zombie processes (Phát hiện tiến trình zombie)
- Load balancing across GPUs (Cân bằng tải giữa các GPU)
"""

import asyncio
import logging
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any

import psutil

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    logging.warning("⚠️ pynvml không khả dụng - sử dụng fallback mode")


class ProcessStatus(Enum):
    """Trạng thái của process"""
    RUNNING = "running"
    SLEEPING = "sleeping"
    ZOMBIE = "zombie"
    STOPPED = "stopped"
    DEAD = "dead"
    UNKNOWN = "unknown"


@dataclass
class ProcessInfo:
    """
    Thông tin chi tiết về một process
    Detailed information about a process
    """
    pid: int
    name: str = "unknown"
    status: ProcessStatus = ProcessStatus.UNKNOWN
    gpu_index: Optional[int] = None
    gpu_memory_mb: float = 0.0
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    create_time: float = 0.0
    last_seen: float = field(default_factory=time.time)
    health_score: int = 100  # 0-100
    
    def update_last_seen(self):
        """Cập nhật thời gian last seen"""
        self.last_seen = time.time()
    
    def is_stale(self, timeout: float = 60.0) -> bool:
        """Kiểm tra process có stale không"""
        return (time.time() - self.last_seen) > timeout
    
    def calculate_health_score(self) -> int:
        """
        Tính toán health score dựa trên các metrics
        Calculate health score based on metrics
        """
        score = 100
        
        # Trừ điểm cho zombie status
        if self.status == ProcessStatus.ZOMBIE:
            score -= 50
        elif self.status == ProcessStatus.STOPPED:
            score -= 30
        elif self.status == ProcessStatus.DEAD:
            score = 0
            
        # Trừ điểm cho CPU usage quá cao
        if self.cpu_percent > 90:
            score -= 20
        elif self.cpu_percent > 70:
            score -= 10
            
        # Trừ điểm cho memory usage quá cao
        if self.memory_percent > 90:
            score -= 15
        elif self.memory_percent > 70:
            score -= 5
            
        # Trừ điểm nếu process quá cũ mà không active
        age = time.time() - self.create_time
        if age > 3600 and self.cpu_percent < 1:  # 1 giờ không active
            score -= 10
            
        self.health_score = max(0, min(100, score))
        return self.health_score


class PIDMapper:
    """
    PID to GPU Mapper
    Ánh xạ Process ID với GPU và theo dõi sức khỏe
    
    Features:
    - Automatic GPU assignment (Tự động gán GPU)
    - Load balancing (Cân bằng tải)
    - Health monitoring (Giám sát sức khỏe)
    - Zombie detection (Phát hiện zombie)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Khởi tạo PID Mapper
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Process tracking
        self.pid_to_gpu: Dict[int, int] = {}  # PID -> GPU index
        self.gpu_to_pids: Dict[int, Set[int]] = defaultdict(set)  # GPU -> Set of PIDs
        self.process_info: Dict[int, ProcessInfo] = {}  # PID -> ProcessInfo
        
        # GPU information
        self.num_gpus = 0
        self.gpu_load: Dict[int, float] = {}  # GPU index -> load percentage
        
        # Configuration
        self.max_pids_per_gpu = self.config.get("max_pids_per_gpu", 10)
        self.health_check_interval = self.config.get("health_check_interval", 30)  # seconds
        self.zombie_cleanup_interval = self.config.get("zombie_cleanup_interval", 60)  # seconds
        self.load_balance_threshold = self.config.get("load_balance_threshold", 0.3)  # 30% difference
        
        # Background tasks
        self._health_check_task = None
        self._zombie_cleanup_task = None
        self._running = False
        
    async def initialize(self) -> bool:
        """
        Khởi tạo PID Mapper và detect GPUs
        Initialize PID Mapper and detect GPUs
        
        Returns:
            bool: True nếu khởi tạo thành công
        """
        try:
            # Detect số lượng GPU
            if NVML_AVAILABLE:
                try:
                    pynvml.nvmlInit()
                    self.num_gpus = pynvml.nvmlDeviceGetCount()
                    self.logger.info(f"✅ Detected {self.num_gpus} GPUs qua NVML")
                except Exception as e:
                    self.logger.warning(f"⚠️ NVML init failed: {e}, using fallback")
                    self.num_gpus = self._detect_gpus_fallback()
            else:
                self.num_gpus = self._detect_gpus_fallback()
            
            if self.num_gpus == 0:
                self.logger.warning("⚠️ Không phát hiện GPU nào, sử dụng virtual GPU")
                self.num_gpus = 1  # Virtual GPU
            
            # Initialize GPU load tracking
            for i in range(self.num_gpus):
                self.gpu_load[i] = 0.0
                self.gpu_to_pids[i] = set()
            
            # Start background tasks
            self._running = True
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            self._zombie_cleanup_task = asyncio.create_task(self._zombie_cleanup_loop())
            
            self.logger.info(f"✅ PID Mapper initialized với {self.num_gpus} GPUs")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi khởi tạo PID Mapper: {e}")
            return False
    
    def _detect_gpus_fallback(self) -> int:
        """Fallback method để detect GPUs qua nvidia-smi"""
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=index", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                gpu_count = len(result.stdout.strip().split('\n'))
                self.logger.info(f"✅ Detected {gpu_count} GPUs qua nvidia-smi")
                return gpu_count
        except Exception:
            pass
        return 0
    
    async def map_pid_to_gpu(
        self, 
        pid: int, 
        preferred_gpu: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Map một PID với GPU
        Map a PID to GPU
        
        Args:
            pid: Process ID cần map
            preferred_gpu: GPU index ưu tiên (optional)
            
        Returns:
            Dict chứa mapping information
        """
        result = {
            "pid": pid,
            "gpu_index": None,
            "success": False,
            "reason": ""
        }
        
        try:
            # Kiểm tra process tồn tại
            if not psutil.pid_exists(pid):
                result["reason"] = f"PID {pid} không tồn tại"
                return result
            
            # Nếu PID đã được map
            if pid in self.pid_to_gpu:
                gpu_index = self.pid_to_gpu[pid]
                result["gpu_index"] = gpu_index
                result["success"] = True
                result["reason"] = "PID đã được map từ trước"
                
                # Update process info
                await self._update_process_info(pid)
                return result
            
            # Collect process information
            proc_info = await self._get_process_info(pid)
            if proc_info is None:
                result["reason"] = f"Không thể lấy thông tin process {pid}"
                return result
            
            # Select GPU dựa trên load balancing
            if preferred_gpu is not None and 0 <= preferred_gpu < self.num_gpus:
                gpu_index = preferred_gpu
            else:
                gpu_index = await self._select_best_gpu()
            
            # Map PID to GPU
            self.pid_to_gpu[pid] = gpu_index
            self.gpu_to_pids[gpu_index].add(pid)
            self.process_info[pid] = proc_info
            proc_info.gpu_index = gpu_index
            
            # Update GPU load
            await self._update_gpu_load(gpu_index)
            
            result["gpu_index"] = gpu_index
            result["success"] = True
            result["reason"] = f"Mapped PID {pid} to GPU {gpu_index}"
            
            self.logger.info(f"✅ Mapped PID {pid} ({proc_info.name}) to GPU {gpu_index}")
            
        except Exception as e:
            result["reason"] = f"Error: {str(e)}"
            self.logger.error(f"❌ Lỗi mapping PID {pid}: {e}")
        
        return result
    
    async def unmap_pid(self, pid: int) -> bool:
        """
        Unmap một PID khỏi GPU
        Unmap a PID from GPU
        
        Args:
            pid: Process ID cần unmap
            
        Returns:
            bool: True nếu unmap thành công
        """
        try:
            if pid not in self.pid_to_gpu:
                return True  # Already unmapped
            
            gpu_index = self.pid_to_gpu[pid]
            
            # Remove mappings
            del self.pid_to_gpu[pid]
            self.gpu_to_pids[gpu_index].discard(pid)
            
            if pid in self.process_info:
                del self.process_info[pid]
            
            # Update GPU load
            await self._update_gpu_load(gpu_index)
            
            self.logger.info(f"✅ Unmapped PID {pid} from GPU {gpu_index}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi unmap PID {pid}: {e}")
            return False
    
    async def _get_process_info(self, pid: int) -> Optional[ProcessInfo]:
        """Lấy thông tin chi tiết về process"""
        try:
            proc = psutil.Process(pid)
            
            # Get process status
            status_str = proc.status()
            status_map = {
                "running": ProcessStatus.RUNNING,
                "sleeping": ProcessStatus.SLEEPING,
                "zombie": ProcessStatus.ZOMBIE,
                "stopped": ProcessStatus.STOPPED,
                "dead": ProcessStatus.DEAD
            }
            status = status_map.get(status_str, ProcessStatus.UNKNOWN)
            
            # Get process metrics
            with proc.oneshot():
                info = ProcessInfo(
                    pid=pid,
                    name=proc.name(),
                    status=status,
                    cpu_percent=proc.cpu_percent(interval=0.1),
                    memory_percent=proc.memory_percent(),
                    create_time=proc.create_time()
                )
            
            # Calculate health score
            info.calculate_health_score()
            
            return info
            
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None
        except Exception as e:
            self.logger.error(f"Error getting process info for PID {pid}: {e}")
            return None
    
    async def _update_process_info(self, pid: int):
        """Cập nhật thông tin process"""
        if pid not in self.process_info:
            return
        
        new_info = await self._get_process_info(pid)
        if new_info:
            old_info = self.process_info[pid]
            new_info.gpu_index = old_info.gpu_index
            new_info.gpu_memory_mb = old_info.gpu_memory_mb  # Preserve GPU memory
            self.process_info[pid] = new_info
    
    async def _select_best_gpu(self) -> int:
        """
        Chọn GPU tốt nhất dựa trên load balancing
        Select best GPU based on load balancing
        """
        if self.num_gpus == 1:
            return 0
        
        # Update all GPU loads
        for gpu_index in range(self.num_gpus):
            await self._update_gpu_load(gpu_index)
        
        # Find GPU with lowest load
        min_load = float('inf')
        best_gpu = 0
        
        for gpu_index, load in self.gpu_load.items():
            # Consider number of processes too
            num_pids = len(self.gpu_to_pids[gpu_index])
            combined_score = load + (num_pids * 10)  # Weight by process count
            
            if combined_score < min_load:
                min_load = combined_score
                best_gpu = gpu_index
        
        return best_gpu
    
    async def _update_gpu_load(self, gpu_index: int):
        """Cập nhật GPU load percentage"""
        try:
            if NVML_AVAILABLE and gpu_index < self.num_gpus:
                handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                self.gpu_load[gpu_index] = util.gpu
            else:
                # Estimate load based on process count
                num_pids = len(self.gpu_to_pids[gpu_index])
                self.gpu_load[gpu_index] = min(100, num_pids * 10)
        except Exception as e:
            self.logger.debug(f"Không thể update GPU load: {e}")
    
    async def _health_check_loop(self):
        """Background task để check process health"""
        while self._running:
            try:
                await asyncio.sleep(self.health_check_interval)
                await self._perform_health_check()
            except Exception as e:
                self.logger.error(f"Error in health check loop: {e}")
    
    async def _perform_health_check(self):
        """Thực hiện health check cho tất cả processes"""
        dead_pids = []
        
        for pid in list(self.pid_to_gpu.keys()):
            try:
                # Check if process still exists
                if not psutil.pid_exists(pid):
                    dead_pids.append(pid)
                    continue
                
                # Update process info
                await self._update_process_info(pid)
                
                # Check health score
                if pid in self.process_info:
                    info = self.process_info[pid]
                    if info.health_score < 20:
                        self.logger.warning(
                            f"⚠️ Process {pid} ({info.name}) có health score thấp: {info.health_score}"
                        )
                
            except Exception as e:
                self.logger.error(f"Error checking health of PID {pid}: {e}")
        
        # Clean up dead processes
        for pid in dead_pids:
            self.logger.info(f"🧹 Cleaning up dead process {pid}")
            await self.unmap_pid(pid)
    
    async def _zombie_cleanup_loop(self):
        """Background task để cleanup zombie processes"""
        while self._running:
            try:
                await asyncio.sleep(self.zombie_cleanup_interval)
                await self._cleanup_zombies()
            except Exception as e:
                self.logger.error(f"Error in zombie cleanup loop: {e}")
    
    async def _cleanup_zombies(self):
        """Cleanup zombie và stopped processes"""
        zombies = []
        
        for pid, info in self.process_info.items():
            if info.status in [ProcessStatus.ZOMBIE, ProcessStatus.DEAD]:
                zombies.append(pid)
            elif info.status == ProcessStatus.STOPPED and info.is_stale(120):
                # Stopped process quá 2 phút
                zombies.append(pid)
        
        for pid in zombies:
            self.logger.warning(f"🧟 Cleaning up zombie/dead process {pid}")
            await self.unmap_pid(pid)
    
    async def get_pid_info(self, pid: int) -> Optional[Dict[str, Any]]:
        """Lấy thông tin về một PID cụ thể"""
        if pid not in self.process_info:
            return None
        
        info = self.process_info[pid]
        return {
            "pid": pid,
            "name": info.name,
            "status": info.status.value,
            "gpu_index": info.gpu_index,
            "gpu_memory_mb": info.gpu_memory_mb,
            "cpu_percent": info.cpu_percent,
            "memory_percent": info.memory_percent,
            "health_score": info.health_score,
            "age_seconds": time.time() - info.create_time
        }
    
    async def get_all_mappings(self) -> Dict[str, Any]:
        """Lấy tất cả PID-GPU mappings"""
        return {
            "pid_to_gpu": dict(self.pid_to_gpu),
            "gpu_to_pids": {k: list(v) for k, v in self.gpu_to_pids.items()},
            "gpu_load": dict(self.gpu_load),
            "total_processes": len(self.pid_to_gpu),
            "num_gpus": self.num_gpus
        }
    
    async def rebalance_load(self) -> Dict[str, Any]:
        """
        Rebalance load giữa các GPU
        Rebalance load across GPUs
        """
        result = {
            "rebalanced": False,
            "migrations": []
        }
        
        if self.num_gpus <= 1:
            return result
        
        try:
            # Calculate average load
            avg_load = sum(self.gpu_load.values()) / self.num_gpus
            
            # Find overloaded and underloaded GPUs
            overloaded = []
            underloaded = []
            
            for gpu_index, load in self.gpu_load.items():
                diff = load - avg_load
                if diff > self.load_balance_threshold * 100:
                    overloaded.append((gpu_index, load))
                elif diff < -self.load_balance_threshold * 100:
                    underloaded.append((gpu_index, load))
            
            # Migrate processes if needed
            if overloaded and underloaded:
                for over_gpu, _ in overloaded:
                    for under_gpu, _ in underloaded:
                        # Move one process from overloaded to underloaded
                        pids = list(self.gpu_to_pids[over_gpu])
                        if pids:
                            pid_to_move = pids[0]  # Simple strategy: move first PID
                            
                            # Migrate PID
                            self.pid_to_gpu[pid_to_move] = under_gpu
                            self.gpu_to_pids[over_gpu].discard(pid_to_move)
                            self.gpu_to_pids[under_gpu].add(pid_to_move)
                            
                            if pid_to_move in self.process_info:
                                self.process_info[pid_to_move].gpu_index = under_gpu
                            
                            result["migrations"].append({
                                "pid": pid_to_move,
                                "from_gpu": over_gpu,
                                "to_gpu": under_gpu
                            })
                            
                            # Update loads
                            await self._update_gpu_load(over_gpu)
                            await self._update_gpu_load(under_gpu)
                            
                            result["rebalanced"] = True
                            break
            
            if result["rebalanced"]:
                self.logger.info(f"✅ Rebalanced {len(result['migrations'])} processes")
            
        except Exception as e:
            self.logger.error(f"❌ Error rebalancing load: {e}")
        
        return result
    
    async def shutdown(self):
        """Shutdown PID Mapper gracefully"""
        self.logger.info("🔄 Shutting down PID Mapper...")
        self._running = False
        
        # Cancel background tasks
        if self._health_check_task:
            self._health_check_task.cancel()
        if self._zombie_cleanup_task:
            self._zombie_cleanup_task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(
            self._health_check_task,
            self._zombie_cleanup_task,
            return_exceptions=True
        )
        
        # Cleanup NVML
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
        
        self.logger.info("✅ PID Mapper shutdown complete")