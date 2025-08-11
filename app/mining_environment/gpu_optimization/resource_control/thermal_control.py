"""
Thermal Control Module
======================
GPU temperature monitoring and control
Giám sát và kiểm soát nhiệt độ GPU

Chức năng chính:
- Temperature monitoring and prediction (Giám sát và dự đoán nhiệt độ)
- Thermal throttling policies (Chính sách điều chỉnh nhiệt)
- Fan speed control (Điều khiển tốc độ quạt)
- Emergency thermal shutdown (Tắt khẩn cấp khi quá nhiệt)
"""

import asyncio
import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Dict, List, Optional, Tuple, Any


class ThermalPolicy(Enum):
    """Chính sách điều khiển nhiệt"""
    CONSERVATIVE = "conservative"  # Bảo thủ - ưu tiên nhiệt độ thấp
    BALANCED = "balanced"  # Cân bằng - giữa hiệu năng và nhiệt độ
    AGGRESSIVE = "aggressive"  # Mạnh mẽ - ưu tiên hiệu năng
    SILENT = "silent"  # Yên tĩnh - giảm tiếng ồn quạt
    EMERGENCY = "emergency"  # Khẩn cấp - giảm nhiệt độ ngay


class ThermalZone(Enum):
    """Vùng nhiệt độ GPU"""
    COLD = "cold"  # < 40°C
    NORMAL = "normal"  # 40-60°C
    WARM = "warm"  # 60-70°C
    HOT = "hot"  # 70-80°C
    CRITICAL = "critical"  # 80-85°C
    EMERGENCY = "emergency"  # > 85°C


@dataclass
class ThermalProfile:
    """
    Hồ sơ nhiệt độ GPU
    GPU thermal profile
    """
    gpu_index: int
    current_temp_c: float = 0.0
    target_temp_c: float = 65.0
    max_temp_c: float = 85.0
    min_temp_c: float = 30.0
    fan_speed_percent: float = 50.0
    thermal_zone: ThermalZone = ThermalZone.NORMAL
    policy: ThermalPolicy = ThermalPolicy.BALANCED
    timestamp: float = field(default_factory=time.time)
    cooling_rate: float = 0.0  # °C/sec
    heating_rate: float = 0.0  # °C/sec
    
    def get_thermal_headroom(self) -> float:
        """Khoảng cách an toàn đến nhiệt độ tối đa"""
        return self.max_temp_c - self.current_temp_c
    
    def is_overheating(self) -> bool:
        """Kiểm tra GPU có đang quá nóng không"""
        return self.current_temp_c >= self.max_temp_c


@dataclass
class TemperaturePrediction:
    """
    Dự đoán nhiệt độ
    Temperature prediction
    """
    predicted_temp_c: float
    time_horizon_sec: float
    confidence: float  # 0-1
    method: str = "newton_cooling"


class ThermalController:
    """
    GPU Thermal Controller
    Bộ điều khiển nhiệt độ GPU
    
    Features:
    - Temperature monitoring (Giám sát nhiệt độ)
    - Predictive thermal management (Quản lý nhiệt dự đoán)
    - Fan control (Điều khiển quạt)
    - Emergency shutdown (Tắt khẩn cấp)
    """
    
    # Temperature thresholds
    ZONE_THRESHOLDS = {
        ThermalZone.COLD: (0, 40),
        ThermalZone.NORMAL: (40, 60),
        ThermalZone.WARM: (60, 70),
        ThermalZone.HOT: (70, 80),
        ThermalZone.CRITICAL: (80, 85),
        ThermalZone.EMERGENCY: (85, 100)
    }
    
    # Fan curves for different policies
    FAN_CURVES = {
        ThermalPolicy.CONSERVATIVE: {
            40: 30, 50: 40, 60: 60, 70: 80, 80: 100
        },
        ThermalPolicy.BALANCED: {
            40: 20, 50: 30, 60: 50, 70: 70, 80: 90
        },
        ThermalPolicy.AGGRESSIVE: {
            40: 10, 50: 20, 60: 40, 70: 60, 80: 80
        },
        ThermalPolicy.SILENT: {
            40: 10, 50: 15, 60: 25, 70: 40, 80: 60
        }
    }
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        gpu_controller=None,
        power_manager=None
    ):
        """
        Khởi tạo Thermal Controller
        
        Args:
            config: Configuration dictionary
            gpu_controller: GPUController instance
            power_manager: PowerManager instance
        """
        self.config = config or {}
        self.gpu_controller = gpu_controller
        self.power_manager = power_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Thermal tracking
        self.thermal_profiles: Dict[int, ThermalProfile] = {}
        self.temperature_history: Dict[int, deque] = {}
        self.predictions: Dict[int, TemperaturePrediction] = {}
        
        # Configuration
        self.monitoring_interval = self.config.get("monitoring_interval", 2)  # seconds
        self.prediction_interval = self.config.get("prediction_interval", 10)  # seconds
        self.max_safe_temp = self.config.get("max_safe_temp", 85.0)  # °C
        self.target_temp = self.config.get("target_temp", 65.0)  # °C
        self.emergency_shutdown_temp = self.config.get("emergency_shutdown_temp", 90.0)  # °C
        
        # Newton's cooling law parameters
        self.ambient_temp = self.config.get("ambient_temp", 25.0)  # °C
        self.cooling_coefficient = self.config.get("cooling_coefficient", 0.1)
        
        # Thread safety
        self.profile_lock = RLock()
        
        # Background tasks
        self._monitoring_task = None
        self._prediction_task = None
        self._running = False
        
    async def initialize(self) -> bool:
        """
        Khởi tạo Thermal Controller
        Initialize Thermal Controller
        
        Returns:
            bool: True nếu khởi tạo thành công
        """
        try:
            # Initialize thermal profiles for each GPU
            if self.gpu_controller:
                num_gpus = self.gpu_controller.num_gpus
                for gpu_index in range(num_gpus):
                    self.thermal_profiles[gpu_index] = ThermalProfile(
                        gpu_index=gpu_index,
                        target_temp_c=self.target_temp,
                        max_temp_c=self.max_safe_temp
                    )
                    self.temperature_history[gpu_index] = deque(maxlen=100)
            
            # Start background tasks
            self._running = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._prediction_task = asyncio.create_task(self._prediction_loop())
            
            self.logger.info("✅ Thermal Controller initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi khởi tạo Thermal Controller: {e}")
            return False
    
    async def apply_thermal_policy(
        self,
        gpu_index: int,
        policy: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Áp dụng chính sách điều khiển nhiệt
        Apply thermal control policy
        
        Args:
            gpu_index: GPU index
            policy: Thermal policy name
            
        Returns:
            Dict with application result
        """
        with self.profile_lock:
            try:
                # Parse policy
                thermal_policy = ThermalPolicy(policy)
                
                # Update profile
                if gpu_index in self.thermal_profiles:
                    profile = self.thermal_profiles[gpu_index]
                    profile.policy = thermal_policy
                    
                    # Apply fan curve based on current temperature
                    if self.gpu_controller:
                        metrics = await self.gpu_controller.get_gpu_metrics(gpu_index)
                        if metrics:
                            profile.current_temp_c = metrics.temperature_c
                            
                            # Calculate target fan speed
                            target_fan_speed = self._calculate_fan_speed(
                                profile.current_temp_c,
                                thermal_policy
                            )
                            
                            # Apply fan speed (if supported)
                            # Note: Fan control may require privileged access
                            profile.fan_speed_percent = target_fan_speed
                    
                    self.logger.info(
                        f"✅ Applied {policy} thermal policy to GPU {gpu_index}"
                    )
                    
                    return {
                        "success": True,
                        "gpu_index": gpu_index,
                        "policy": policy,
                        "current_temp": profile.current_temp_c,
                        "target_fan_speed": profile.fan_speed_percent
                    }
                
                raise Exception(f"No thermal profile for GPU {gpu_index}")
                
            except Exception as e:
                self.logger.error(f"❌ Lỗi áp dụng thermal policy: {e}")
                return {
                    "success": False,
                    "gpu_index": gpu_index,
                    "error": str(e)
                }
    
    def _calculate_fan_speed(self, temp_c: float, policy: ThermalPolicy) -> float:
        """
        Tính tốc độ quạt dựa trên nhiệt độ và chính sách
        Calculate fan speed based on temperature and policy
        """
        if policy == ThermalPolicy.EMERGENCY:
            return 100.0  # Max fan speed for emergency
        
        curve = self.FAN_CURVES.get(policy, self.FAN_CURVES[ThermalPolicy.BALANCED])
        
        # Interpolate fan speed from curve
        temps = sorted(curve.keys())
        
        if temp_c <= temps[0]:
            return curve[temps[0]]
        if temp_c >= temps[-1]:
            return curve[temps[-1]]
        
        # Linear interpolation
        for i in range(len(temps) - 1):
            if temps[i] <= temp_c <= temps[i + 1]:
                t1, t2 = temps[i], temps[i + 1]
                f1, f2 = curve[t1], curve[t2]
                ratio = (temp_c - t1) / (t2 - t1)
                return f1 + ratio * (f2 - f1)
        
        return 50.0  # Default
    
    def _determine_thermal_zone(self, temp_c: float) -> ThermalZone:
        """Xác định vùng nhiệt độ"""
        for zone, (min_temp, max_temp) in self.ZONE_THRESHOLDS.items():
            if min_temp <= temp_c < max_temp:
                return zone
        return ThermalZone.NORMAL
    
    async def predict_temperature(
        self,
        gpu_index: int,
        time_horizon_sec: float = 30.0
    ) -> Optional[TemperaturePrediction]:
        """
        Dự đoán nhiệt độ GPU trong tương lai
        Predict future GPU temperature
        
        Uses Newton's law of cooling: dT/dt = -k(T - T_ambient)
        
        Args:
            gpu_index: GPU index
            time_horizon_sec: Time horizon for prediction
            
        Returns:
            TemperaturePrediction object or None
        """
        try:
            if gpu_index not in self.thermal_profiles:
                return None
            
            profile = self.thermal_profiles[gpu_index]
            history = self.temperature_history.get(gpu_index, [])
            
            if len(history) < 2:
                return None
            
            # Calculate heating/cooling rate from history
            recent_temps = list(history)[-5:]  # Last 5 measurements
            if len(recent_temps) >= 2:
                dt = self.monitoring_interval
                dT = recent_temps[-1]["temp"] - recent_temps[-2]["temp"]
                rate = dT / dt
                
                # Newton's cooling law
                current_temp = profile.current_temp_c
                k = self.cooling_coefficient
                
                # Predict temperature
                # T(t) = T_ambient + (T0 - T_ambient) * exp(-kt)
                temp_diff = current_temp - self.ambient_temp
                predicted_temp = self.ambient_temp + temp_diff * math.exp(-k * time_horizon_sec)
                
                # Adjust for current trend
                if rate > 0:  # Heating
                    predicted_temp += rate * time_horizon_sec * 0.5  # Dampen prediction
                
                # Bound prediction
                predicted_temp = max(self.ambient_temp, min(100, predicted_temp))
                
                prediction = TemperaturePrediction(
                    predicted_temp_c=predicted_temp,
                    time_horizon_sec=time_horizon_sec,
                    confidence=min(0.9, len(recent_temps) / 10.0)
                )
                
                self.predictions[gpu_index] = prediction
                return prediction
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error predicting temperature: {e}")
            return None
    
    async def apply_thermal_throttling(self, gpu_index: int):
        """
        Áp dụng điều chỉnh nhiệt khi cần
        Apply thermal throttling when needed
        """
        try:
            if gpu_index not in self.thermal_profiles:
                return
            
            profile = self.thermal_profiles[gpu_index]
            
            # Check if throttling needed
            if profile.current_temp_c > profile.target_temp_c:
                overage = profile.current_temp_c - profile.target_temp_c
                
                # Calculate power reduction
                if overage > 20:  # Very hot
                    reduction_percent = 30
                elif overage > 10:  # Hot
                    reduction_percent = 20
                elif overage > 5:  # Warm
                    reduction_percent = 10
                else:
                    reduction_percent = 5
                
                # Apply power reduction via power manager
                if self.power_manager:
                    await self.power_manager.apply_emergency_power_reduction(
                        gpu_index,
                        reduction_percent
                    )
                
                # Also reduce clocks if very hot
                if overage > 15 and self.gpu_controller:
                    # Reduce clocks by 10%
                    metrics = await self.gpu_controller.get_gpu_metrics(gpu_index)
                    if metrics:
                        new_sm_clock = int(metrics.sm_clock_mhz * 0.9)
                        await self.gpu_controller.set_clocks(
                            gpu_index,
                            sm_clock_mhz=new_sm_clock
                        )
                
                self.logger.warning(
                    f"🌡️ Thermal throttling GPU {gpu_index}: "
                    f"{profile.current_temp_c:.1f}°C → {reduction_percent}% power reduction"
                )
                
        except Exception as e:
            self.logger.error(f"Error applying thermal throttling: {e}")
    
    async def emergency_thermal_shutdown(self, gpu_index: int):
        """
        Tắt khẩn cấp GPU khi quá nóng
        Emergency shutdown GPU when overheating
        """
        try:
            self.logger.critical(
                f"🚨🔥 EMERGENCY THERMAL SHUTDOWN GPU {gpu_index}!"
            )
            
            # Set emergency policy
            if gpu_index in self.thermal_profiles:
                self.thermal_profiles[gpu_index].policy = ThermalPolicy.EMERGENCY
            
            # Maximum power reduction
            if self.power_manager:
                await self.power_manager.apply_emergency_power_reduction(
                    gpu_index,
                    reduction_percent=50
                )
            
            # Set minimum clocks
            if self.gpu_controller:
                await self.gpu_controller.set_clocks(
                    gpu_index,
                    sm_clock_mhz=300,  # Minimum
                    memory_clock_mhz=300
                )
                
                # Set power limit to minimum
                await self.gpu_controller.set_power_limit(
                    gpu_index,
                    power_watts=50,  # Minimum
                    smooth_transition=False
                )
            
        except Exception as e:
            self.logger.error(f"Error in emergency thermal shutdown: {e}")
    
    async def _monitoring_loop(self):
        """Background temperature monitoring loop"""
        while self._running:
            try:
                await asyncio.sleep(self.monitoring_interval)
                
                if self.gpu_controller:
                    for gpu_index in range(self.gpu_controller.num_gpus):
                        metrics = await self.gpu_controller.get_gpu_metrics(gpu_index)
                        if metrics:
                            profile = self.thermal_profiles.get(gpu_index)
                            if profile:
                                # Update profile
                                profile.current_temp_c = metrics.temperature_c
                                profile.fan_speed_percent = metrics.fan_speed_percent
                                profile.thermal_zone = self._determine_thermal_zone(
                                    metrics.temperature_c
                                )
                                
                                # Store history
                                self.temperature_history[gpu_index].append({
                                    "timestamp": time.time(),
                                    "temp": metrics.temperature_c,
                                    "fan_speed": metrics.fan_speed_percent
                                })
                                
                                # Check for emergency conditions
                                if metrics.temperature_c >= self.emergency_shutdown_temp:
                                    await self.emergency_thermal_shutdown(gpu_index)
                                elif metrics.temperature_c > profile.target_temp_c + 5:
                                    await self.apply_thermal_throttling(gpu_index)
                                
                                # Log zone changes
                                if profile.thermal_zone in [ThermalZone.CRITICAL, ThermalZone.EMERGENCY]:
                                    self.logger.warning(
                                        f"⚠️ GPU {gpu_index} in {profile.thermal_zone.value} zone: "
                                        f"{metrics.temperature_c:.1f}°C"
                                    )
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
    
    async def _prediction_loop(self):
        """Background temperature prediction loop"""
        while self._running:
            try:
                await asyncio.sleep(self.prediction_interval)
                
                for gpu_index in self.thermal_profiles.keys():
                    prediction = await self.predict_temperature(gpu_index, 30.0)
                    if prediction and prediction.predicted_temp_c > self.max_safe_temp:
                        self.logger.warning(
                            f"📈 GPU {gpu_index} predicted to reach "
                            f"{prediction.predicted_temp_c:.1f}°C in {prediction.time_horizon_sec}s"
                        )
                        # Proactive throttling
                        await self.apply_thermal_throttling(gpu_index)
                
            except Exception as e:
                self.logger.error(f"Prediction loop error: {e}")
    
    async def get_thermal_status(self) -> Dict[str, Any]:
        """
        Lấy trạng thái nhiệt hiện tại
        Get current thermal status
        """
        status = {
            "profiles": {},
            "predictions": {},
            "config": {
                "max_safe_temp": self.max_safe_temp,
                "target_temp": self.target_temp,
                "emergency_shutdown_temp": self.emergency_shutdown_temp
            }
        }
        
        for gpu_index, profile in self.thermal_profiles.items():
            status["profiles"][gpu_index] = {
                "current_temp_c": profile.current_temp_c,
                "target_temp_c": profile.target_temp_c,
                "thermal_zone": profile.thermal_zone.value,
                "policy": profile.policy.value,
                "fan_speed_percent": profile.fan_speed_percent,
                "thermal_headroom": profile.get_thermal_headroom()
            }
        
        for gpu_index, prediction in self.predictions.items():
            status["predictions"][gpu_index] = {
                "predicted_temp_c": prediction.predicted_temp_c,
                "time_horizon_sec": prediction.time_horizon_sec,
                "confidence": prediction.confidence
            }
        
        return status
    
    async def shutdown(self):
        """Shutdown Thermal Controller gracefully"""
        self.logger.info("🔄 Shutting down Thermal Controller...")
        self._running = False
        
        # Cancel background tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._prediction_task:
            self._prediction_task.cancel()
        
        await asyncio.gather(
            self._monitoring_task,
            self._prediction_task,
            return_exceptions=True
        )
        
        self.logger.info("✅ Thermal Controller shutdown complete")