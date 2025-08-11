"""
GPU Controller Module
=====================
Direct GPU hardware control and management
Điều khiển và quản lý phần cứng GPU trực tiếp

Chức năng chính:
- Hardware control via NVML/nvidia-smi (Điều khiển phần cứng qua NVML/nvidia-smi)
- Clock frequency management (Quản lý tần số xung nhịp)
- Power limit controls (Điều khiển giới hạn công suất)
- Memory management (Quản lý bộ nhớ)
- Performance state control (Điều khiển trạng thái hiệu năng)
"""

import asyncio
import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Dict, List, Optional, Tuple, Any

try:
    import pynvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False
    logging.warning("⚠️ pynvml không khả dụng - sử dụng nvidia-smi fallback")


class ComputeMode(Enum):
    """GPU Compute Mode"""
    DEFAULT = 0  # Multiple contexts allowed
    EXCLUSIVE_THREAD = 1  # Only one context per thread
    PROHIBITED = 2  # Compute prohibited
    EXCLUSIVE_PROCESS = 3  # Only one context per process


@dataclass
class GPUMetrics:
    """
    GPU metrics snapshot
    Ảnh chụp metrics GPU
    """
    gpu_index: int
    timestamp: float = field(default_factory=time.time)
    temperature_c: float = 0.0
    power_watts: float = 0.0
    power_limit_watts: float = 0.0
    utilization_percent: float = 0.0
    memory_used_mb: float = 0.0
    memory_total_mb: float = 0.0
    sm_clock_mhz: int = 0
    memory_clock_mhz: int = 0
    pcie_throughput_mb: float = 0.0
    fan_speed_percent: float = 0.0
    compute_mode: ComputeMode = ComputeMode.DEFAULT
    persistence_mode: bool = False
    
    @property
    def memory_utilization_percent(self) -> float:
        """Tính phần trăm memory utilization"""
        if self.memory_total_mb > 0:
            return (self.memory_used_mb / self.memory_total_mb) * 100
        return 0.0
    
    @property
    def thermal_headroom(self) -> float:
        """Khoảng cách nhiệt độ an toàn (85°C max)"""
        return max(0, 85.0 - self.temperature_c)


@dataclass
class GPUControlResult:
    """
    Kết quả của thao tác điều khiển GPU
    Result of GPU control operation
    """
    success: bool
    operation: str
    gpu_index: int
    message: str = ""
    original_value: Optional[Any] = None
    new_value: Optional[Any] = None
    error: Optional[str] = None


class GPUController:
    """
    GPU Hardware Controller
    Bộ điều khiển phần cứng GPU
    
    Features:
    - Direct hardware control (Điều khiển phần cứng trực tiếp)
    - Safety guards (Bảo vệ an toàn)
    - Fallback mechanisms (Cơ chế dự phòng)
    - Thread-safe operations (Thao tác an toàn luồng)
    """
    
    # Safety limits
    MAX_POWER_LIMIT = 300  # Watts
    MIN_POWER_LIMIT = 50   # Watts
    MAX_TEMPERATURE = 85    # Celsius
    MAX_SM_CLOCK = 2100     # MHz
    MAX_MEM_CLOCK = 2000    # MHz
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Khởi tạo GPU Controller
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # GPU tracking
        self.num_gpus = 0
        self.gpu_handles = {}  # GPU index -> NVML handle
        self.gpu_metrics = {}  # GPU index -> GPUMetrics
        self.original_settings = {}  # GPU index -> original settings for rollback
        
        # Thread safety
        self.gpu_locks = {}  # GPU index -> RLock
        self.executor = ThreadPoolExecutor(max_workers=self.config.get("max_workers", 4))
        
        # Configuration
        self.smooth_power_transition = self.config.get("smooth_power_transition", True)
        self.power_transition_steps = self.config.get("power_transition_steps", 3)
        self.safety_checks_enabled = self.config.get("safety_checks", True)
        
        # Telemetry
        self.telemetry_enabled = self.config.get("telemetry", True)
        self.telemetry_interval = self.config.get("telemetry_interval", 5)  # seconds
        self.telemetry_history = {}  # GPU index -> list of metrics
        self._telemetry_task = None
        self._running = False
        
        # Error tracking
        self.error_counts = {}  # GPU index -> error count
        
    async def initialize(self) -> bool:
        """
        Khởi tạo controller và phát hiện GPUs
        Initialize controller and detect GPUs
        
        Returns:
            bool: True nếu khởi tạo thành công
        """
        try:
            # Initialize NVML if available
            if NVML_AVAILABLE:
                try:
                    pynvml.nvmlInit()
                    self.num_gpus = pynvml.nvmlDeviceGetCount()
                    
                    # Get GPU handles
                    for i in range(self.num_gpus):
                        self.gpu_handles[i] = pynvml.nvmlDeviceGetHandleByIndex(i)
                        self.gpu_locks[i] = RLock()
                        self.error_counts[i] = 0
                        self.telemetry_history[i] = []
                        
                        # Store original settings
                        await self._store_original_settings(i)
                    
                    self.logger.info(f"✅ Initialized {self.num_gpus} GPUs via NVML")
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ NVML init failed: {e}, using fallback")
                    NVML_AVAILABLE = False
                    self.num_gpus = await self._detect_gpus_fallback()
            else:
                self.num_gpus = await self._detect_gpus_fallback()
            
            if self.num_gpus == 0:
                self.logger.warning("⚠️ Không phát hiện GPU, sử dụng virtual GPU")
                self.num_gpus = 1
            
            # Initialize locks for fallback mode
            for i in range(self.num_gpus):
                if i not in self.gpu_locks:
                    self.gpu_locks[i] = RLock()
                    self.error_counts[i] = 0
                    self.telemetry_history[i] = []
            
            # Start telemetry collection
            if self.telemetry_enabled:
                self._running = True
                self._telemetry_task = asyncio.create_task(self._telemetry_loop())
            
            self.logger.info(f"✅ GPU Controller initialized với {self.num_gpus} GPUs")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi khởi tạo GPU Controller: {e}")
            return False
    
    async def _detect_gpus_fallback(self) -> int:
        """Detect GPUs using nvidia-smi fallback"""
        try:
            result = await asyncio.create_subprocess_shell(
                "nvidia-smi --query-gpu=index --format=csv,noheader",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                gpu_count = len(stdout.decode().strip().split('\n'))
                self.logger.info(f"✅ Detected {gpu_count} GPUs via nvidia-smi")
                return gpu_count
        except Exception:
            pass
        return 0
    
    async def _store_original_settings(self, gpu_index: int):
        """Lưu settings gốc để rollback"""
        try:
            if NVML_AVAILABLE and gpu_index in self.gpu_handles:
                handle = self.gpu_handles[gpu_index]
                
                settings = {
                    "power_limit": pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0,
                    "persistence_mode": pynvml.nvmlDeviceGetPersistenceMode(handle),
                    "compute_mode": pynvml.nvmlDeviceGetComputeMode(handle)
                }
                
                # Try to get clock settings
                try:
                    settings["sm_clock"] = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
                    settings["mem_clock"] = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                except:
                    pass
                
                self.original_settings[gpu_index] = settings
                
        except Exception as e:
            self.logger.debug(f"Không thể lưu original settings cho GPU {gpu_index}: {e}")
    
    async def get_gpu_metrics(self, gpu_index: int) -> Optional[GPUMetrics]:
        """
        Lấy metrics hiện tại của GPU
        Get current GPU metrics
        
        Args:
            gpu_index: GPU index
            
        Returns:
            GPUMetrics object hoặc None
        """
        if gpu_index >= self.num_gpus:
            return None
        
        with self.gpu_locks[gpu_index]:
            try:
                if NVML_AVAILABLE and gpu_index in self.gpu_handles:
                    return await self._get_metrics_nvml(gpu_index)
                else:
                    return await self._get_metrics_fallback(gpu_index)
                    
            except Exception as e:
                self.logger.error(f"Lỗi lấy metrics GPU {gpu_index}: {e}")
                self.error_counts[gpu_index] += 1
                return None
    
    async def _get_metrics_nvml(self, gpu_index: int) -> GPUMetrics:
        """Lấy metrics qua NVML"""
        handle = self.gpu_handles[gpu_index]
        
        metrics = GPUMetrics(gpu_index=gpu_index)
        
        # Temperature
        try:
            metrics.temperature_c = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except:
            pass
        
        # Power
        try:
            metrics.power_watts = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
            metrics.power_limit_watts = pynvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0
        except:
            pass
        
        # Utilization
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            metrics.utilization_percent = util.gpu
        except:
            pass
        
        # Memory
        try:
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            metrics.memory_used_mb = mem_info.used / (1024 * 1024)
            metrics.memory_total_mb = mem_info.total / (1024 * 1024)
        except:
            pass
        
        # Clocks
        try:
            metrics.sm_clock_mhz = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
            metrics.memory_clock_mhz = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
        except:
            pass
        
        # Fan speed
        try:
            metrics.fan_speed_percent = pynvml.nvmlDeviceGetFanSpeed(handle)
        except:
            pass
        
        # Compute mode
        try:
            mode = pynvml.nvmlDeviceGetComputeMode(handle)
            metrics.compute_mode = ComputeMode(mode)
        except:
            pass
        
        # Persistence mode
        try:
            metrics.persistence_mode = bool(pynvml.nvmlDeviceGetPersistenceMode(handle))
        except:
            pass
        
        self.gpu_metrics[gpu_index] = metrics
        return metrics
    
    async def _get_metrics_fallback(self, gpu_index: int) -> GPUMetrics:
        """Lấy metrics qua nvidia-smi fallback"""
        metrics = GPUMetrics(gpu_index=gpu_index)
        
        try:
            # Query multiple metrics at once
            query_fields = [
                "temperature.gpu",
                "power.draw",
                "power.limit",
                "utilization.gpu",
                "memory.used",
                "memory.total",
                "clocks.sm",
                "clocks.mem",
                "fan.speed"
            ]
            
            cmd = f"nvidia-smi --query-gpu={','.join(query_fields)} --format=csv,noheader,nounits -i {gpu_index}"
            
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await result.communicate()
            
            if result.returncode == 0:
                values = stdout.decode().strip().split(', ')
                if len(values) >= 9:
                    metrics.temperature_c = float(values[0]) if values[0] != 'N/A' else 0
                    metrics.power_watts = float(values[1]) if values[1] != 'N/A' else 0
                    metrics.power_limit_watts = float(values[2]) if values[2] != 'N/A' else 0
                    metrics.utilization_percent = float(values[3]) if values[3] != 'N/A' else 0
                    metrics.memory_used_mb = float(values[4]) if values[4] != 'N/A' else 0
                    metrics.memory_total_mb = float(values[5]) if values[5] != 'N/A' else 0
                    metrics.sm_clock_mhz = int(values[6]) if values[6] != 'N/A' else 0
                    metrics.memory_clock_mhz = int(values[7]) if values[7] != 'N/A' else 0
                    metrics.fan_speed_percent = float(values[8]) if values[8] != 'N/A' else 0
        except Exception as e:
            self.logger.debug(f"nvidia-smi fallback error: {e}")
        
        self.gpu_metrics[gpu_index] = metrics
        return metrics
    
    async def set_power_limit(
        self,
        gpu_index: int,
        power_watts: float,
        smooth_transition: Optional[bool] = None
    ) -> GPUControlResult:
        """
        Đặt giới hạn công suất GPU
        Set GPU power limit
        
        Args:
            gpu_index: GPU index
            power_watts: Power limit in watts
            smooth_transition: Use smooth transition (optional)
            
        Returns:
            GPUControlResult
        """
        if gpu_index >= self.num_gpus:
            return GPUControlResult(
                success=False,
                operation="set_power_limit",
                gpu_index=gpu_index,
                error="Invalid GPU index"
            )
        
        # Validate power limit
        power_watts = max(self.MIN_POWER_LIMIT, min(self.MAX_POWER_LIMIT, power_watts))
        
        with self.gpu_locks[gpu_index]:
            try:
                # Get current power limit
                current_metrics = await self.get_gpu_metrics(gpu_index)
                if not current_metrics:
                    raise Exception("Không thể lấy metrics hiện tại")
                
                original_power = current_metrics.power_limit_watts
                
                # Safety check - temperature
                if self.safety_checks_enabled and current_metrics.temperature_c > self.MAX_TEMPERATURE:
                    return GPUControlResult(
                        success=False,
                        operation="set_power_limit",
                        gpu_index=gpu_index,
                        error=f"GPU quá nóng ({current_metrics.temperature_c}°C), không thể tăng power"
                    )
                
                # Apply smooth transition if needed
                use_smooth = smooth_transition if smooth_transition is not None else self.smooth_power_transition
                
                if use_smooth and abs(power_watts - original_power) > 20:
                    # Gradual transition
                    steps = self.power_transition_steps
                    for i in range(steps):
                        intermediate = original_power + (power_watts - original_power) * (i + 1) / steps
                        await self._apply_power_limit(gpu_index, intermediate)
                        await asyncio.sleep(0.5)  # Small delay between steps
                else:
                    # Direct application
                    await self._apply_power_limit(gpu_index, power_watts)
                
                return GPUControlResult(
                    success=True,
                    operation="set_power_limit",
                    gpu_index=gpu_index,
                    message=f"Power limit set to {power_watts}W",
                    original_value=original_power,
                    new_value=power_watts
                )
                
            except Exception as e:
                self.error_counts[gpu_index] += 1
                return GPUControlResult(
                    success=False,
                    operation="set_power_limit",
                    gpu_index=gpu_index,
                    error=str(e)
                )
    
    async def _apply_power_limit(self, gpu_index: int, power_watts: float):
        """Apply power limit internally"""
        if NVML_AVAILABLE and gpu_index in self.gpu_handles:
            handle = self.gpu_handles[gpu_index]
            power_milliwatts = int(power_watts * 1000)
            pynvml.nvmlDeviceSetPowerManagementLimit(handle, power_milliwatts)
        else:
            # nvidia-smi fallback
            cmd = f"nvidia-smi -i {gpu_index} -pl {int(power_watts)}"
            result = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            if result.returncode != 0:
                raise Exception(f"nvidia-smi power limit failed")
    
    async def set_clocks(
        self,
        gpu_index: int,
        sm_clock_mhz: Optional[int] = None,
        memory_clock_mhz: Optional[int] = None
    ) -> GPUControlResult:
        """
        Đặt tần số xung nhịp GPU
        Set GPU clock frequencies
        
        Args:
            gpu_index: GPU index
            sm_clock_mhz: SM clock in MHz (optional)
            memory_clock_mhz: Memory clock in MHz (optional)
            
        Returns:
            GPUControlResult
        """
        if gpu_index >= self.num_gpus:
            return GPUControlResult(
                success=False,
                operation="set_clocks",
                gpu_index=gpu_index,
                error="Invalid GPU index"
            )
        
        with self.gpu_locks[gpu_index]:
            try:
                # Validate clocks
                if sm_clock_mhz is not None:
                    sm_clock_mhz = min(sm_clock_mhz, self.MAX_SM_CLOCK)
                if memory_clock_mhz is not None:
                    memory_clock_mhz = min(memory_clock_mhz, self.MAX_MEM_CLOCK)
                
                # Apply clock settings
                if NVML_AVAILABLE and gpu_index in self.gpu_handles:
                    handle = self.gpu_handles[gpu_index]
                    
                    if sm_clock_mhz is not None and memory_clock_mhz is not None:
                        pynvml.nvmlDeviceSetApplicationsClocks(handle, memory_clock_mhz, sm_clock_mhz)
                    elif sm_clock_mhz is not None:
                        # Lock SM clock
                        pynvml.nvmlDeviceSetGpuLockedClocks(handle, sm_clock_mhz, sm_clock_mhz)
                else:
                    # nvidia-smi fallback
                    if sm_clock_mhz is not None:
                        cmd = f"nvidia-smi -i {gpu_index} -lgc {sm_clock_mhz}"
                        result = await asyncio.create_subprocess_shell(
                            cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        await result.communicate()
                        
                        if result.returncode != 0:
                            raise Exception("Failed to set SM clock")
                    
                    if memory_clock_mhz is not None:
                        cmd = f"nvidia-smi -i {gpu_index} -lmc {memory_clock_mhz}"
                        result = await asyncio.create_subprocess_shell(
                            cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        await result.communicate()
                        
                        if result.returncode != 0:
                            raise Exception("Failed to set memory clock")
                
                return GPUControlResult(
                    success=True,
                    operation="set_clocks",
                    gpu_index=gpu_index,
                    message=f"Clocks set: SM={sm_clock_mhz}MHz, Mem={memory_clock_mhz}MHz",
                    new_value={"sm": sm_clock_mhz, "memory": memory_clock_mhz}
                )
                
            except Exception as e:
                self.error_counts[gpu_index] += 1
                return GPUControlResult(
                    success=False,
                    operation="set_clocks",
                    gpu_index=gpu_index,
                    error=str(e)
                )
    
    async def set_persistence_mode(self, gpu_index: int, enabled: bool) -> GPUControlResult:
        """
        Bật/tắt GPU persistence mode
        Enable/disable GPU persistence mode
        """
        if gpu_index >= self.num_gpus:
            return GPUControlResult(
                success=False,
                operation="set_persistence_mode",
                gpu_index=gpu_index,
                error="Invalid GPU index"
            )
        
        with self.gpu_locks[gpu_index]:
            try:
                if NVML_AVAILABLE and gpu_index in self.gpu_handles:
                    handle = self.gpu_handles[gpu_index]
                    mode = pynvml.NVML_FEATURE_ENABLED if enabled else pynvml.NVML_FEATURE_DISABLED
                    pynvml.nvmlDeviceSetPersistenceMode(handle, mode)
                else:
                    # nvidia-smi fallback
                    mode_str = "1" if enabled else "0"
                    cmd = f"nvidia-smi -i {gpu_index} -pm {mode_str}"
                    result = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.communicate()
                    
                    if result.returncode != 0:
                        raise Exception("Failed to set persistence mode")
                
                return GPUControlResult(
                    success=True,
                    operation="set_persistence_mode",
                    gpu_index=gpu_index,
                    message=f"Persistence mode {'enabled' if enabled else 'disabled'}",
                    new_value=enabled
                )
                
            except Exception as e:
                self.error_counts[gpu_index] += 1
                return GPUControlResult(
                    success=False,
                    operation="set_persistence_mode",
                    gpu_index=gpu_index,
                    error=str(e)
                )
    
    async def set_compute_mode(self, gpu_index: int, mode: ComputeMode) -> GPUControlResult:
        """
        Đặt GPU compute mode
        Set GPU compute mode
        """
        if gpu_index >= self.num_gpus:
            return GPUControlResult(
                success=False,
                operation="set_compute_mode",
                gpu_index=gpu_index,
                error="Invalid GPU index"
            )
        
        with self.gpu_locks[gpu_index]:
            try:
                if NVML_AVAILABLE and gpu_index in self.gpu_handles:
                    handle = self.gpu_handles[gpu_index]
                    pynvml.nvmlDeviceSetComputeMode(handle, mode.value)
                else:
                    # nvidia-smi fallback
                    cmd = f"nvidia-smi -i {gpu_index} -c {mode.value}"
                    result = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    await result.communicate()
                    
                    if result.returncode != 0:
                        raise Exception("Failed to set compute mode")
                
                return GPUControlResult(
                    success=True,
                    operation="set_compute_mode",
                    gpu_index=gpu_index,
                    message=f"Compute mode set to {mode.name}",
                    new_value=mode.value
                )
                
            except Exception as e:
                self.error_counts[gpu_index] += 1
                return GPUControlResult(
                    success=False,
                    operation="set_compute_mode",
                    gpu_index=gpu_index,
                    error=str(e)
                )
    
    async def apply_controls(
        self,
        gpu_index: int,
        controls: Dict[str, Any]
    ) -> Dict[str, GPUControlResult]:
        """
        Áp dụng nhiều controls cùng lúc
        Apply multiple controls at once
        
        Args:
            gpu_index: GPU index
            controls: Dictionary of controls to apply
            
        Returns:
            Dictionary of results
        """
        results = {}
        
        # Apply power limit
        if "power_limit" in controls:
            results["power_limit"] = await self.set_power_limit(
                gpu_index,
                controls["power_limit"],
                controls.get("smooth_transition", None)
            )
        
        # Apply clocks
        if "sm_clock" in controls or "memory_clock" in controls:
            results["clocks"] = await self.set_clocks(
                gpu_index,
                controls.get("sm_clock"),
                controls.get("memory_clock")
            )
        
        # Apply persistence mode
        if "persistence_mode" in controls:
            results["persistence_mode"] = await self.set_persistence_mode(
                gpu_index,
                controls["persistence_mode"]
            )
        
        # Apply compute mode
        if "compute_mode" in controls:
            mode = ComputeMode(controls["compute_mode"])
            results["compute_mode"] = await self.set_compute_mode(gpu_index, mode)
        
        return results
    
    async def reset_gpu_settings(self, gpu_index: int) -> GPUControlResult:
        """
        Reset GPU về settings gốc
        Reset GPU to original settings
        """
        if gpu_index >= self.num_gpus:
            return GPUControlResult(
                success=False,
                operation="reset_settings",
                gpu_index=gpu_index,
                error="Invalid GPU index"
            )
        
        with self.gpu_locks[gpu_index]:
            try:
                if gpu_index in self.original_settings:
                    settings = self.original_settings[gpu_index]
                    
                    # Restore power limit
                    if "power_limit" in settings:
                        await self.set_power_limit(gpu_index, settings["power_limit"], smooth_transition=False)
                    
                    # Restore persistence mode
                    if "persistence_mode" in settings:
                        await self.set_persistence_mode(gpu_index, bool(settings["persistence_mode"]))
                    
                    # Restore compute mode
                    if "compute_mode" in settings:
                        await self.set_compute_mode(gpu_index, ComputeMode(settings["compute_mode"]))
                    
                    # Reset clocks
                    if NVML_AVAILABLE and gpu_index in self.gpu_handles:
                        handle = self.gpu_handles[gpu_index]
                        pynvml.nvmlDeviceResetApplicationsClocks(handle)
                        pynvml.nvmlDeviceResetGpuLockedClocks(handle)
                    else:
                        # nvidia-smi reset
                        cmd = f"nvidia-smi -i {gpu_index} -rgc"
                        await asyncio.create_subprocess_shell(cmd)
                
                return GPUControlResult(
                    success=True,
                    operation="reset_settings",
                    gpu_index=gpu_index,
                    message="GPU settings reset to original"
                )
                
            except Exception as e:
                return GPUControlResult(
                    success=False,
                    operation="reset_settings",
                    gpu_index=gpu_index,
                    error=str(e)
                )
    
    async def _telemetry_loop(self):
        """Background telemetry collection loop"""
        while self._running:
            try:
                await asyncio.sleep(self.telemetry_interval)
                
                # Collect metrics for all GPUs
                for gpu_index in range(self.num_gpus):
                    metrics = await self.get_gpu_metrics(gpu_index)
                    if metrics:
                        # Add to history (keep last 1000 points)
                        history = self.telemetry_history[gpu_index]
                        history.append(metrics)
                        if len(history) > 1000:
                            history.pop(0)
                        
                        # Check for critical conditions
                        if metrics.temperature_c > self.MAX_TEMPERATURE:
                            self.logger.warning(
                                f"⚠️ GPU {gpu_index} quá nóng: {metrics.temperature_c}°C"
                            )
                            # Emergency power reduction
                            if self.safety_checks_enabled:
                                new_power = metrics.power_limit_watts * 0.7
                                await self.set_power_limit(gpu_index, new_power, smooth_transition=False)
                
            except Exception as e:
                self.logger.error(f"Telemetry loop error: {e}")
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Lấy trạng thái tổng quan của controller
        Get overall controller status
        """
        status = {
            "num_gpus": self.num_gpus,
            "nvml_available": NVML_AVAILABLE,
            "telemetry_enabled": self.telemetry_enabled,
            "safety_checks": self.safety_checks_enabled,
            "gpu_status": {}
        }
        
        for gpu_index in range(self.num_gpus):
            metrics = await self.get_gpu_metrics(gpu_index)
            status["gpu_status"][gpu_index] = {
                "metrics": metrics.__dict__ if metrics else None,
                "error_count": self.error_counts.get(gpu_index, 0),
                "history_points": len(self.telemetry_history.get(gpu_index, []))
            }
        
        return status
    
    async def shutdown(self):
        """Shutdown controller gracefully"""
        self.logger.info("🔄 Shutting down GPU Controller...")
        self._running = False
        
        # Stop telemetry
        if self._telemetry_task:
            self._telemetry_task.cancel()
            await asyncio.gather(self._telemetry_task, return_exceptions=True)
        
        # Reset all GPUs to original settings
        for gpu_index in range(self.num_gpus):
            try:
                await self.reset_gpu_settings(gpu_index)
            except:
                pass
        
        # Cleanup NVML
        if NVML_AVAILABLE:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
        
        self.logger.info("✅ GPU Controller shutdown complete")