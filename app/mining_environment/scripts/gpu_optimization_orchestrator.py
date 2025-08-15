#!/usr/bin/env python3
"""
**GPU Optimization Orchestrator** (Bộ điều phối tối ưu GPU)

Central orchestration module that integrates:
- Cross-Process Coordination (điều phối liên tiến trình)
- Parallel Strategy Executor (thực thi chiến lược song song)  
- Performance Profiler (phân tích hiệu năng)

This module serves as the main entry point for GPU optimization tasks.
"""

import os
import logging
import time
import random
import json
import functools
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
import threading

# **Import core modules** (nhập module lõi)
try:
    from .cloak_strategies import StrategyEngine, MetricsCollectionHub
    from .resource_control import OptimizedHardwareController, GPUResourceManager
    from .cross_process_coordination import CrossProcessCoordinator, ResourceType
    from .parallel_strategy_executor import ParallelStrategyExecutor, StrategyTask
    from .performance_profiler import get_profiler, profile_function
    from .module_loggers import get_gpu_optimization_orchestrator_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity
except ImportError as e:
    # Fallback for standalone testing - use absolute imports
    import sys
    sys.path.insert(0, '/home/azureuser/opus-gpu/app')
    from mining_environment.scripts.cloak_strategies import StrategyEngine, MetricsCollectionHub
    from mining_environment.scripts.resource_control import OptimizedHardwareController, GPUResourceManager
    from mining_environment.scripts.cross_process_coordination import CrossProcessCoordinator, ResourceType
    from mining_environment.scripts.parallel_strategy_executor import ParallelStrategyExecutor, StrategyTask
    from mining_environment.scripts.performance_profiler import PerformanceProfiler, profile_function
    from mining_environment.scripts.module_loggers import get_gpu_optimization_orchestrator_logger
    from mining_environment.scripts.error_management import get_error_reporter, ErrorCode, ErrorSeverity

# **Logger setup** (thiết lập logger)
logger = get_gpu_optimization_orchestrator_logger()
error_reporter = get_error_reporter()

# **Global instances** (thực thể toàn cục)
_profiler = get_profiler()
_coordinator: Optional[CrossProcessCoordinator] = None
_parallel_executor: Optional[ParallelStrategyExecutor] = None
_metrics_hub: Optional[MetricsCollectionHub] = None


def _safe_preview(value: Any, maxlen: int = 300) -> str:
    try:
        if isinstance(value, (dict, list, tuple)):
            text = json.dumps(value, default=str)
        else:
            text = str(value)
    except Exception:
        text = repr(value)
    if len(text) > maxlen:
        text = text[:maxlen] + "…"
    return text


def trace_all(func):
    is_staticmethod = isinstance(func, staticmethod)
    is_classmethod = isinstance(func, classmethod)
    original = func.__func__ if (is_staticmethod or is_classmethod) else func

    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        active_logger = None
        try:
            if args and hasattr(args[0], 'logger'):
                active_logger = getattr(args[0], 'logger', None)
        except Exception:
            active_logger = None
        if active_logger is None:
            active_logger = logger
        try:
            arg_preview = ", ".join([_safe_preview(a) for a in list(args)[:3]])
            kw_preview = {k: _safe_preview(v) for k, v in list(kwargs.items())[:5]}
            active_logger.debug(f"[TRACE] → {original.__name__} args=[{arg_preview}] kwargs={kw_preview}")
        except Exception:
            pass
        try:
            result = original(*args, **kwargs)
            try:
                active_logger.debug(f"[TRACE] ← {original.__name__} result={_safe_preview(result)}")
            except Exception:
                pass
            return result
        except Exception as e:
            try:
                active_logger.exception(f"[TRACE] ✖ {original.__name__} error={e}")
            except Exception:
                pass
            raise

    if is_staticmethod:
        return staticmethod(wrapped)
    if is_classmethod:
        return classmethod(wrapped)
    return wrapped

class GPUOptimizationOrchestrator:
    """
    **Main Orchestrator** (bộ điều phối chính) for GPU optimization workflow.
    
    Coordinates all optimization modules:
    - Resource coordination between processes
    - Parallel strategy execution
    - Performance monitoring and profiling
    """
    
    @trace_all
    @trace_all
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize orchestrator with configuration.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or self._get_default_config()
        self.logger = logger
        
        # **Initialize components** (khởi tạo thành phần)
        self._init_components()
        
        # **Performance tracking** (theo dõi hiệu năng)
        self.execution_stats = {
            'total_optimizations': 0,
            'successful': 0,
            'failed': 0,
            'avg_duration': 0.0
        }
        
        self.logger.info("🚀 **GPU Optimization Orchestrator initialized** "
                        "(bộ điều phối tối ưu GPU đã khởi tạo)")

        # ===== Continuous optimization configuration =====
        # Allow ENV overrides for enable/interval
        env_enabled = os.getenv('CONTINUOUS_OPT_ENABLED')
        if env_enabled is not None:
            try:
                self.config['continuous_optimization'] = str(env_enabled).lower() in ('1', 'true', 'yes')
            except Exception:
                pass
        env_interval = os.getenv('CONTINUOUS_OPT_INTERVAL_SEC')
        if env_interval is not None:
            try:
                self.config['loop_interval_sec'] = max(1, int(env_interval))
            except Exception:
                pass

        # Runtime state for continuous loop
        self._continuous_stop_event: Optional[threading.Event] = threading.Event()
        self._continuous_thread: Optional[threading.Thread] = None
        self._last_interval_tier: Optional[int] = None
        self._recent_error_count: int = 0
        # Interval control via ENV (optional)
        self.config['interval_mode'] = os.getenv('CONTINUOUS_OPT_MODE', 'adaptive').lower()
        try:
            self.config['interval_min_tier'] = int(os.getenv('INTERVAL_MIN_TIER')) if os.getenv('INTERVAL_MIN_TIER') else None
        except Exception:
            self.config['interval_min_tier'] = None
        try:
            self.config['interval_max_tier'] = int(os.getenv('INTERVAL_MAX_TIER')) if os.getenv('INTERVAL_MAX_TIER') else None
        except Exception:
            self.config['interval_max_tier'] = None
        try:
            self.config['interval_jitter_pct'] = float(os.getenv('INTERVAL_JITTER_PCT', '0.15'))
        except Exception:
            self.config['interval_jitter_pct'] = 0.15

        # Load interval choices from ENV (supports per-tier override or full JSON)
        self._interval_choices: List[Optional[Tuple[int, int]]] = self._load_interval_choices_from_env()
    
    @trace_all
    @trace_all
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'max_parallel_strategies': 4,
            'strategy_timeout': 30.0,
            'enable_profiling': True,
            'enable_coordination': True,
            'metrics_buffer_size': 1000,
            # Giảm nhịp để có báo cáo đều đặn hơn; có thể override bằng ENV/Config ngoài
            'profile_report_interval': 120,  # 2 minutes
            # Continuous optimization (tối ưu liên tục – lặp theo chu kỳ)
            'continuous_optimization': True,
            'loop_interval_sec': 30
        }

    # ===== Interval selection helpers (Adaptive interval with hysteresis & jitter) =====
    @staticmethod
    @trace_all
    def _get_time_bucket() -> str:
        hour = datetime.now().hour
        if 9 <= hour <= 17:
            return 'business'
        if 18 <= hour <= 22:
            return 'peak'
        return 'off_peak'

    @trace_all
    def _compute_state_from_metrics(self, pid: int, gpu_index: int, results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        # Try post metrics from results first
        metrics = None
        if results and isinstance(results, dict):
            metrics = (results.get('metrics') or {}).get('post')
        if not metrics:
            metrics = self._collect_gpu_metrics(gpu_index)

        temp = float(metrics.get('temperature', 0)) if isinstance(metrics, dict) else 0.0
        util = float(metrics.get('utilization', 0)) if isinstance(metrics, dict) else 0.0
        # Classify temperature status
        if temp >= 78:
            temp_status = 'CRITICAL'
        elif temp >= 72:
            temp_status = 'WARNING'
        else:
            temp_status = 'SAFE'
        return {
            'temp_status': temp_status,
            'gpu_util': util,
            'recent_errors': max(0, self._recent_error_count),
            'time_of_day': self._get_time_bucket(),
            'last_tier': self._last_interval_tier,
        }

    @trace_all
    def _load_interval_choices_from_env(self) -> List[Optional[Tuple[int, int]]]:
        """Load interval choices from ENV.
        Supports:
          - INTERVAL_CHOICES_JSON: full JSON list, e.g. "[[300,600],[600,1200],...]"
          - INTERVAL_CHOICE_TIER_{i}_LO / _HI per tier override (0..4)
          - INTERVAL_CHOICE_TIER_{i} to disable tier when set to empty string "" or "[]"
        Returns list length 5 with (lo, hi) or None to disable that tier.
        """
        # Default choices
        defaults: List[Optional[Tuple[int, int]]] = [
            (300, 600),
            (600, 1200),
            (1200, 1800),
            (1800, 3600),
            (3600, 7200),
        ]
        try:
            self.logger.debug("[Orchestrator] _load_interval_choices_from_env: start | defaults=%s | jitter_pct=%s | min_tier=%s | max_tier=%s",
                              defaults,
                              self.config.get('interval_jitter_pct'),
                              self.config.get('interval_min_tier'),
                              self.config.get('interval_max_tier'))
        except Exception:
            pass
        try:
            raw = os.getenv('INTERVAL_CHOICES_JSON')
            if raw:
                try:
                    self.logger.info("[Orchestrator] INTERVAL_CHOICES_JSON detected: %s", raw)
                except Exception:
                    pass
                data = json.loads(raw)
                parsed: List[Optional[Tuple[int, int]]] = []
                for item in data:
                    if not item:
                        try:
                            self.logger.debug("[Orchestrator] Tier from JSON disabled via empty item: %s", item)
                        except Exception:
                            pass
                        parsed.append(None)
                    else:
                        lo, hi = int(item[0]), int(item[1])
                        parsed.append((min(lo, hi), max(lo, hi)))
                        try:
                            self.logger.debug("[Orchestrator] Parsed JSON tier -> lo=%s hi=%s", min(lo, hi), max(lo, hi))
                        except Exception:
                            pass
                # Normalize to 5 tiers if possible
                if len(parsed) < 5:
                    try:
                        self.logger.debug("[Orchestrator] Parsed %s tiers; extending with defaults up to 5 tiers", len(parsed))
                    except Exception:
                        pass
                    parsed += defaults[len(parsed):]
                final_from_json = parsed[:5]
                try:
                    self.logger.info("[Orchestrator] Final interval choices from JSON -> %s", final_from_json)
                except Exception:
                    pass
                return final_from_json
        except Exception:
            pass
        # Per-tier overrides
        result: List[Optional[Tuple[int, int]]] = list(defaults)
        for i in range(5):
            key_disable = f'INTERVAL_CHOICE_TIER_{i}'
            key_lo = f'INTERVAL_CHOICE_TIER_{i}_LO'
            key_hi = f'INTERVAL_CHOICE_TIER_{i}_HI'
            val_disable = os.getenv(key_disable)
            if val_disable is not None and val_disable.strip() in ('', '[]', 'none', 'None', 'disable', 'DISABLE'):
                try:
                    self.logger.info("[Orchestrator] Tier %s disabled via %s=%s", i, key_disable, val_disable)
                except Exception:
                    pass
                result[i] = None
                continue
            val_lo = os.getenv(key_lo)
            val_hi = os.getenv(key_hi)
            if val_lo is not None and val_hi is not None:
                try:
                    lo = int(val_lo)
                    hi = int(val_hi)
                    result[i] = (min(lo, hi), max(lo, hi))
                    try:
                        self.logger.info("[Orchestrator] Tier %s override -> lo=%s hi=%s (from %s/%s)", i, min(lo, hi), max(lo, hi), key_lo, key_hi)
                    except Exception:
                        pass
                except Exception:
                    pass
            else:
                try:
                    self.logger.debug("[Orchestrator] Tier %s keeps default (or previously set) -> %s", i, result[i])
                except Exception:
                    pass
        try:
            self.logger.info("[Orchestrator] Final interval choices from ENV overrides -> %s", result)
        except Exception:
            pass
        return result

    @trace_all
    def _pick_next_interval_sec(self, state: Dict[str, Any]) -> int:
        # Load configured choices (with per-tier disable support)
        interval_choices = self._interval_choices
        # Base tier by state
        tier = 1
        if state.get('temp_status') == 'CRITICAL' or state.get('recent_errors', 0) > 0:
            tier = 4
        elif state.get('temp_status') == 'WARNING' or state.get('gpu_util', 0) >= 80:
            tier = 3
        elif state.get('gpu_util', 0) >= 50:
            tier = 2
        elif state.get('time_of_day') == 'off_peak':
            tier = 0
        else:
            tier = 1
        # Hysteresis: avoid flapping 1 tier difference
        last_tier = state.get('last_tier')
        if last_tier is not None and abs(tier - int(last_tier)) == 1:
            tier = int(last_tier)
        # Clamp by env min/max
        min_tier = self.config.get('interval_min_tier')
        max_tier = self.config.get('interval_max_tier')
        if isinstance(min_tier, int):
            tier = max(min_tier, tier)
        if isinstance(max_tier, int):
            tier = min(max_tier, tier)
        # Clamp to valid range and ensure tier enabled; if disabled, downgrade until found
        tier = max(0, min(tier, len(interval_choices) - 1))
        while tier >= 0 and (interval_choices[tier] is None):
            tier -= 1
        if tier < 0:
            # If all disabled, fall back to 30s
            return 30
        self._last_interval_tier = tier
        lo, hi = interval_choices[tier] or (30, 30)
        # Random selection within tier (natural jitter)
        base = random.randint(lo, hi)
        # Extra jitter pct around selected value
        jitter_pct = float(self.config.get('interval_jitter_pct', 0.15))
        jitter_span = int(base * jitter_pct)
        next_interval = max(lo, min(hi, base + random.randint(-jitter_span, jitter_span)))
        return int(next_interval)
    
    @trace_all
    def _init_components(self):
        """Initialize all orchestrator components"""
        global _coordinator, _parallel_executor, _metrics_hub
        
        # **Initialize Cross-Process Coordinator** (khởi tạo điều phối liên tiến trình)
        if self.config['enable_coordination']:
            pid = os.getpid()
            _coordinator = CrossProcessCoordinator(pid)
            self.coordinator = _coordinator
            self.logger.info(f"✅ Cross-Process Coordinator initialized for PID {pid}")
        else:
            self.coordinator = None
        
        # **Initialize Parallel Executor** (khởi tạo bộ thực thi song song)
        _parallel_executor = ParallelStrategyExecutor(
            max_workers=self.config['max_parallel_strategies'],
            default_timeout=self.config['strategy_timeout']
        )
        self.parallel_executor = _parallel_executor
        self.logger.info("✅ Parallel Strategy Executor initialized (Bộ thực thi chiến lược song song đã khởi tạo – cơ chế thực thi đồng thời)")
        
        # **Initialize Metrics Hub** (khởi tạo trung tâm số liệu)
        _metrics_hub = MetricsCollectionHub(
            buffer_size=self.config['metrics_buffer_size']
        )
        self.metrics_hub = _metrics_hub
        self.metrics_hub.start_background_logging()
        self.logger.info("✅ [MHub] Metrics Collection Hub initialized (Trung tâm thu thập số liệu đã khởi tạo – bộ gom chỉ số hoạt động)")
        
        # **Initialize core engines** (khởi tạo engine lõi) với fallback an toàn
        try:
            # Pass shared metrics hub into StrategyEngine so components share buffers
            self.strategy_engine = StrategyEngine(metrics_hub=self.metrics_hub)
            self.logger.info("✅ Strategy Engine initialized")
        except Exception as e:
            self.strategy_engine = None
            self.logger.warning(f"⚠️ StrategyEngine initialization failed, continuing without it: {e}")
        
        # **Initialize Hardware Controller** (khởi tạo điều khiển phần cứng)
        gpu_config = self.config.get('gpu_config', {})
        gpu_logger = logger.getChild('gpu')
        # Khởi tạo OptimizedHardwareController theo chữ ký (config, logger)
        safe_gpu_config = {**gpu_config, 'baseline_power': 300, 'baseline_temp': 70}
        self.hardware_controller = OptimizedHardwareController(safe_gpu_config, gpu_logger)
        self.logger.info("✅ Hardware Controller initialized")
    
    @profile_function(track_memory=True)
    @trace_all
    def optimize_gpu_for_process(self, 
                                 pid: int, 
                                 gpu_index: int = 0,
                                 strategies: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        **Main optimization entry point** (điểm vào tối ưu chính).
        
        Applies GPU optimization strategies to a process with:
        - Cross-process coordination
        - Parallel strategy execution
        - Performance profiling
        
        Args:
            pid: Process ID to optimize
            gpu_index: GPU index to use
            strategies: List of strategies to apply (None = all)
            
        Returns:
            Dictionary with optimization results
        """
        start_time = time.time()
        results = {
            'pid': pid,
            'gpu_index': gpu_index,
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'strategies_applied': [],
            'metrics': {},
            'errors': []
        }
        
        try:
            self.logger.info(f"🎯 **Starting GPU optimization** (bắt đầu tối ưu GPU – khởi động quá trình tối ưu) for PID {pid} on GPU {gpu_index}")
            
            # **Step 1: Request resource coordination** (yêu cầu điều phối tài nguyên)
            if self.coordinator:
                if not self._acquire_gpu_resources(pid, gpu_index):
                    results['errors'].append("Failed to acquire GPU resources")
                    return results
            
            # **Step 2: Collect baseline metrics** (thu thập số liệu cơ sở)
            baseline_metrics = self._collect_gpu_metrics(gpu_index)
            results['metrics']['baseline'] = baseline_metrics
            # Adapter: map orchestrator metrics to standardized hub schema with stage metadata
            self._push_standardized_metrics(baseline_metrics, stage='baseline')
            
            # **Step 3: Prepare strategy tasks** (chuẩn bị tác vụ chiến lược)
            if strategies is None:
                strategies = ['gpu_power', 'gpu_clock', 'temperature', 'memory']
            
            tasks = self._prepare_strategy_tasks(pid, gpu_index, strategies)
            
            # **Step 4: Execute strategies in parallel** (thực thi chiến lược song song)
            if tasks:
                self.logger.info(f"🔄 Executing {len(tasks)} strategies in parallel (thực thi {len(tasks)} chiến lược song song – chạy đồng thời)...")
                execution_results = self.parallel_executor.execute_parallel(tasks)
            else:
                execution_results = {}
            
            # **Step 5: Apply hardware optimizations** (áp dụng tối ưu phần cứng)
            try:
                from .utils import StrategyType
            except Exception:
                StrategyType = type('StrategyType', (), {'GPU': 'GPU'})
            hw_results = self.hardware_controller.optimize_for_pid(
                pid=pid,
                strategy=StrategyType.GPU,
                gpu_index=gpu_index
            )
            
            # **Step 6: Collect post-optimization metrics** (thu thập số liệu sau tối ưu)
            post_metrics = self._collect_gpu_metrics(gpu_index)
            results['metrics']['post'] = post_metrics
            # Adapter: standardized push with stage metadata
            self._push_standardized_metrics(post_metrics, stage='post')
            
            # **Step 7: Aggregate results** (tổng hợp kết quả)
            results['strategies_applied'] = list(execution_results.keys())
            results['execution_details'] = self.parallel_executor.aggregate_results()
            results['hardware_results'] = hw_results
            results['success'] = True
            
            # **Update statistics** (cập nhật thống kê)
            self.execution_stats['total_optimizations'] += 1
            self.execution_stats['successful'] += 1
            
        except Exception as e:
            self.logger.error(f"❌ Optimization failed for PID {pid} (tối ưu thất bại – lỗi áp dụng): {e}")
            results['errors'].append(str(e))
            self.execution_stats['failed'] += 1
            
            # **Report error** (báo cáo lỗi)
            error_reporter.report_error(
                ErrorCode.STRATEGY_APPLICATION_FAILED,
                f"Orchestrator optimization failed: {e}",
                severity=ErrorSeverity.HIGH,
                context={
                    'pid': pid,
                    'gpu_index': gpu_index,
                    'strategies': strategies
                }
            )
        
        finally:
            # **Release resources** (giải phóng tài nguyên)
            if self.coordinator:
                self._release_gpu_resources(gpu_index)
            
            # **Calculate duration** (tính thời gian)
            duration = time.time() - start_time
            results['duration'] = duration
            
            # **Update average duration** (cập nhật thời gian trung bình)
            total = self.execution_stats['total_optimizations']
            if total > 0:
                avg = self.execution_stats['avg_duration']
                self.execution_stats['avg_duration'] = (avg * (total - 1) + duration) / total
            
            self.logger.info(f"✅ **Optimization completed** (tối ưu hoàn thành – quy trình kết thúc) in {duration:.2f}s")
        
        # Auto-start continuous loop if enabled and not running (ensures real-time even when caller uses one-shot API)
        try:
            if self.config.get('continuous_optimization', False):
                if not hasattr(self, '_continuous_thread') or self._continuous_thread is None or not self._continuous_thread.is_alive():
                    # Lazy create loop using current call context
                    interval = max(1, int(self.config.get('loop_interval_sec', 30)))
                    stop_event = getattr(self, '_continuous_stop_event', None)
                    if stop_event is None:
                        self._continuous_stop_event = threading.Event()
                        stop_event = self._continuous_stop_event
                    def _loop() -> None:
                        self.logger.info(f"🔄 Continuous optimization loop started (interval={interval}s, pid={pid}, gpu={gpu_index})")
                        while stop_event and not stop_event.is_set():
                            try:
                                self.optimize_gpu_for_process(pid=pid, gpu_index=gpu_index, strategies=strategies)
                            except Exception as e:
                                self.logger.error(f"❌ Continuous optimization iteration failed: {e}")
                            finally:
                                for _ in range(interval):
                                    if stop_event.is_set():
                                        break
                                    time.sleep(1)
                        self.logger.info("🛑 Continuous optimization loop stopped")
                    self._continuous_thread = threading.Thread(target=_loop, daemon=True)
                    self._continuous_thread.start()
        except Exception as _e:
            self.logger.warning(f"⚠️ Unable to start continuous optimization loop: {_e}")

        return results
    
    @trace_all
    def start_continuous_optimization(self, 
                                      pid: int, 
                                      gpu_index: int = 0, 
                                      strategies: Optional[List[str]] = None) -> None:
        """
        **Start continuous optimization loop** (khởi động vòng lặp tối ưu liên tục)
        - Tạo `thread` (luồng nền) chạy lặp; chọn khoảng nghỉ theo `_pick_next_interval_sec` hoặc cấu hình cố định.
        """
        try:
            if self._continuous_thread is not None and self._continuous_thread.is_alive():
                self.logger.info("[Orchestrator] Continuous optimization loop already running")
                return
        except Exception:
            pass

        stop_event = getattr(self, '_continuous_stop_event', None)
        if stop_event is None:
            self._continuous_stop_event = threading.Event()
            stop_event = self._continuous_stop_event

        def _loop() -> None:
            mode = self.config.get('interval_mode', 'adaptive')
            base_interval = int(self.config.get('loop_interval_sec', 30))
            self.logger.info(f"🔄 Continuous optimization loop started (mode={mode}, base_interval={base_interval}s, pid={pid}, gpu={gpu_index})")
            while stop_event and not stop_event.is_set():
                interval = base_interval
                results: Optional[Dict[str, Any]] = None
                try:
                    results = self.optimize_gpu_for_process(pid=pid, gpu_index=gpu_index, strategies=strategies)
                except Exception as e:
                    self._recent_error_count = min(999999, self._recent_error_count + 1)
                    self.logger.error(f"❌ Continuous optimization iteration failed: {e}")
                try:
                    state = self._compute_state_from_metrics(pid=pid, gpu_index=gpu_index, results=results)
                    if self.config.get('interval_mode', 'adaptive') == 'fixed':
                        interval = max(1, int(self.config.get('loop_interval_sec', base_interval)))
                    else:
                        interval = max(1, int(self._pick_next_interval_sec(state)))
                    self.logger.info(f"[Orchestrator] Next interval selected: {interval}s | state={state} | tier={self._last_interval_tier} | choices={self._interval_choices}")
                except Exception as _e:
                    self.logger.warning(f"[Orchestrator] Failed to compute next interval; fallback to base {base_interval}s: {_e}")
                    interval = base_interval
                # Sleep with cooperative stop
                for _ in range(int(interval)):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
            self.logger.info("🛑 Continuous optimization loop stopped")

        self._continuous_thread = threading.Thread(target=_loop, daemon=True)
        self._continuous_thread.start()
    
    def _acquire_gpu_resources(self, pid: int, gpu_index: int) -> bool:
        """
        **Acquire GPU resources** (lấy tài nguyên GPU) through coordinator.
        
        Returns:
            True if resources acquired successfully
        """
        try:
            # Request compute resources
            compute_acquired = self.coordinator.request_resource(
                gpu_index,
                ResourceType.GPU_COMPUTE,
                amount=50.0,  # Request 50% compute
                priority=7
            )
            
            if not compute_acquired:
                self.logger.warning(f"⚠️ Failed to acquire GPU compute for PID {pid}")
                return False
            
            # Request memory resources
            memory_acquired = self.coordinator.request_resource(
                gpu_index,
                ResourceType.GPU_MEMORY,
                amount=30.0,  # Request 30% memory
                priority=7
            )
            
            if not memory_acquired:
                # Release compute if memory fails
                self.coordinator.release_resource(gpu_index, ResourceType.GPU_COMPUTE)
                self.logger.warning(f"⚠️ Failed to acquire GPU memory for PID {pid}")
                return False
            
            self.logger.info(f"✅ Acquired GPU resources for PID {pid} on GPU {gpu_index}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Resource acquisition error: {e}")
            return False
    
    def _release_gpu_resources(self, gpu_index: int):
        """**Release GPU resources** (giải phóng tài nguyên GPU)"""
        try:
            self.coordinator.release_resource(gpu_index, ResourceType.GPU_COMPUTE)
            self.coordinator.release_resource(gpu_index, ResourceType.GPU_MEMORY)
            self.logger.info(f"✅ Released GPU resources for GPU {gpu_index}")
        except Exception as e:
            self.logger.error(f"❌ Resource release error: {e}")
    
    def _collect_gpu_metrics(self, gpu_index: int) -> Dict[str, Any]:
        """**Collect GPU metrics** (thu thập số liệu GPU)"""
        try:
            import pynvml
            pynvml.nvmlInit()
            handle = pynvml.nvmlDeviceGetHandleByIndex(gpu_index)
            
            metrics = {
                'timestamp': time.time(),
                'gpu_index': gpu_index,
                'temperature': pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU),
                'power': pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0,  # Convert to watts
                'utilization': pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
                'memory_info': {
                    'used': pynvml.nvmlDeviceGetMemoryInfo(handle).used / (1024**3),  # GB
                    'total': pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024**3)  # GB
                },
                'clocks': {
                    'sm': pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM),
                    'mem': pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                }
            }
            
            return metrics
            
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to collect GPU metrics: {e}")
            return {
                'timestamp': time.time(),
                'gpu_index': gpu_index,
                'error': str(e)
            }

    def _push_standardized_metrics(self, metrics: Dict[str, Any], stage: str) -> None:
        """
        Adapter: chuẩn hóa field/đơn vị và đẩy vào 8 nhóm chuẩn của Metrics Hub.
        stage: 'baseline' | 'post' (ghi vào metadata)
        """
        try:
            if not self.metrics_hub:
                return

            # Common metadata
            ts = metrics.get('timestamp', time.time())
            meta = {'stage': stage, 'timestamp': ts}

            # gpu_usage
            util = metrics.get('utilization')
            if isinstance(util, (int, float)):
                self.metrics_hub.add_metric('gpu_usage', {**meta, 'utilization': float(util)})

            # temperature (°C)
            temp = metrics.get('temperature')
            if isinstance(temp, (int, float)):
                self.metrics_hub.add_metric('temperature', {**meta, 'temperature': float(temp)})

            # power (W)
            power = metrics.get('power')
            if isinstance(power, (int, float)):
                self.metrics_hub.add_metric('power', {**meta, 'power_draw': float(power)})

            # clock_speeds (MHz)
            clocks = metrics.get('clocks') or {}
            sm_clk = clocks.get('sm')
            mem_clk = clocks.get('mem')
            clk_payload = {}
            if isinstance(sm_clk, (int, float)):
                clk_payload['graphics_clock'] = int(sm_clk)
            if isinstance(mem_clk, (int, float)):
                clk_payload['memory_clock'] = int(mem_clk)
            if clk_payload:
                self.metrics_hub.add_metric('clock_speeds', {**meta, **clk_payload})

            # memory_usage (MB)
            mem = metrics.get('memory_info') or {}
            used_gb = mem.get('used')
            total_gb = mem.get('total')
            mem_payload = {}
            if isinstance(used_gb, (int, float)):
                mem_payload['memory_usage_mb'] = float(used_gb) * 1024.0
            if isinstance(total_gb, (int, float)):
                mem_payload['gpu_memory_mb'] = float(total_gb) * 1024.0
            if mem_payload:
                self.metrics_hub.add_metric('memory_usage', {**meta, **mem_payload})
        except Exception as _e:
            self.logger.debug(f"[Adapter] Failed to push standardized metrics: {_e}")
    
    def _prepare_strategy_tasks(self, 
                                pid: int, 
                                gpu_index: int,
                                strategies: List[str]) -> List[StrategyTask]:
        """
        **Prepare strategy tasks** (chuẩn bị tác vụ chiến lược) for parallel execution.
        
        Returns:
            List of StrategyTask objects
        """
        tasks = []
        
        for strategy in strategies:
            # Create task function
            def execute_strategy(s=strategy, p=pid, g=gpu_index):
                """Execute single strategy"""
                try:
                    # Apply through strategy engine nếu sẵn sàng (API align: strategy_name, params)
                    result = None
                    if self.strategy_engine is not None:
                        result = self.strategy_engine.apply_strategy(
                            strategy_name=s,
                            params={'pid': p, 'gpu_index': g}
                        )
                    
                    # Collect metrics after strategy
                    metrics = self._collect_gpu_metrics(g)
                    
                    return {
                        'strategy': s,
                        'result': result,
                        'metrics': metrics
                    }
                except Exception as e:
                    return {
                        'strategy': s,
                        'error': str(e)
                    }
            
            # Create task
            task = StrategyTask(
                name=f"{strategy}_pid{pid}_gpu{gpu_index}",
                function=execute_strategy,
                timeout=self.config['strategy_timeout'],
                priority=self._get_strategy_priority(strategy)
            )
            
            tasks.append(task)
        
        # Add dependencies nếu có tasks
        if tasks:
            self._add_task_dependencies(tasks)
        
        return tasks
    
    def _get_strategy_priority(self, strategy: str) -> int:
        """Get priority for strategy (higher = more important)"""
        priority_map = {
            'gpu_power': 10,      # Highest priority
            'temperature': 9,
            'gpu_clock': 8,
            'memory': 7,
            'network': 5,
            'cache': 4
        }
        return priority_map.get(strategy, 5)
    
    def _add_task_dependencies(self, tasks: List[StrategyTask]):
        """Add dependencies between tasks"""
        # Example: memory depends on gpu_power
        task_map = {t.name.split('_')[0]: t for t in tasks}
        
        if 'memory' in task_map and 'gpu' in task_map:
            task_map['memory'].dependencies = [task_map['gpu'].name]
        
        if 'temperature' in task_map and 'gpu' in task_map:
            task_map['temperature'].dependencies = [task_map['gpu'].name]
    
    def generate_performance_report(self, 
                                   output_path: Optional[Path] = None) -> Path:
        """
        **Generate performance report** (tạo báo cáo hiệu năng).
        
        Args:
            output_path: Optional output path for report
            
        Returns:
            Path to generated report
        """
        # Generate profiler report
        dashboard = _profiler.generate_dashboard()
        
        # Add orchestrator statistics
        dashboard['orchestrator_stats'] = self.execution_stats
        
        # Add metrics summary
        dashboard['metrics_summary'] = self.metrics_hub.aggregate_all_metrics()
        
        # Export report
        if output_path is None:
            output_path = Path(f"/tmp/gpu_optimization_report_{datetime.now():%Y%m%d_%H%M%S}.json")
        
        with open(output_path, 'w') as f:
            json.dump(dashboard, f, indent=2, default=str)
        
        self.logger.info(f"📊 Performance report generated: {output_path}")
        return output_path
    
    def shutdown(self):
        """**Shutdown orchestrator** (tắt bộ điều phối) and cleanup resources"""
        self.logger.info("🛑 Shutting down GPU Optimization Orchestrator...")
        # Stop continuous loop if running
        try:
            if hasattr(self, '_continuous_stop_event') and self._continuous_stop_event:
                self._continuous_stop_event.set()
            if hasattr(self, '_continuous_thread') and self._continuous_thread and self._continuous_thread.is_alive():
                self._continuous_thread.join(timeout=5)
        except Exception as _e:
            self.logger.warning(f"⚠️ Error while stopping continuous loop: {_e}")
        
        # Stop coordinator
        if self.coordinator:
            self.coordinator.stop()
        
        # Shutdown parallel executor
        self.parallel_executor.shutdown(wait=True)
        
        # Stop metrics hub
        self.metrics_hub.stop_background_logging()
        
        # Generate final report
        self.generate_performance_report()
        
        self.logger.info("✅ Orchestrator shutdown complete")


def optimize_gpu(pid: int, 
                 gpu_index: int = 0,
                 strategies: Optional[List[str]] = None,
                 config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    **Main entry point** (điểm vào chính) for GPU optimization.
    
    Convenience function that creates orchestrator and runs optimization.
    
    Args:
        pid: Process ID to optimize
        gpu_index: GPU index to use
        strategies: List of strategies to apply
        config: Optional configuration
        
    Returns:
        Optimization results dictionary
    """
    orchestrator = GPUOptimizationOrchestrator(config)
    
    try:
        # If continuous optimization enabled, start background loop and return immediately
        if orchestrator.config.get('continuous_optimization', False):
            orchestrator.start_continuous_optimization(pid=pid, gpu_index=gpu_index, strategies=strategies)
            return {
                'success': True,
                'message': 'Continuous optimization started',
                'pid': pid,
                'gpu_index': gpu_index,
                'interval_sec': orchestrator.config.get('loop_interval_sec', 30)
            }
        # One-shot optimization (default)
        results = orchestrator.optimize_gpu_for_process(pid, gpu_index, strategies)
        return results
    finally:
        # Do not shutdown orchestrator immediately if continuous loop is running
        if not orchestrator.config.get('continuous_optimization', False):
            orchestrator.shutdown()


# **Test function** (hàm kiểm thử)
def test_orchestrator():
    """Test the GPU Optimization Orchestrator"""
    import multiprocessing
    
    # Get current process PID
    test_pid = os.getpid()
    
    logger.info("="*60)
    logger.info("🧪 **Testing GPU Optimization Orchestrator**")
    logger.info("="*60)
    
    # Test configuration
    config = {
        'max_parallel_strategies': 3,
        'strategy_timeout': 20.0,
        'enable_profiling': True,
        'enable_coordination': True
    }
    
    # Run optimization
    results = optimize_gpu(
        pid=test_pid,
        gpu_index=0,
        strategies=['gpu_power', 'temperature', 'memory'],
        config=config
    )
    
    # Display results
    logger.info("\n📊 **Optimization Results**:")
    logger.info(f"Success: {results['success']}")
    logger.info(f"Strategies applied: {results['strategies_applied']}")
    logger.info(f"Duration: {results.get('duration', 0):.2f}s")
    
    if results.get('metrics'):
        baseline = results['metrics'].get('baseline', {})
        post = results['metrics'].get('post', {})
        
        if baseline and post:
            logger.info("\n📈 **Metrics Comparison**:")
            logger.info(f"Temperature: {baseline.get('temperature', 'N/A')}°C → "
                       f"{post.get('temperature', 'N/A')}°C")
            logger.info(f"Power: {baseline.get('power', 'N/A')}W → "
                       f"{post.get('power', 'N/A')}W")
            logger.info(f"Utilization: {baseline.get('utilization', 'N/A')}% → "
                       f"{post.get('utilization', 'N/A')}%")
    
    logger.info("="*60)
    logger.info("✅ **Test completed successfully**")
    logger.info("="*60)
    
    return results


if __name__ == "__main__":
    # Run test when executed directly
    test_orchestrator()
