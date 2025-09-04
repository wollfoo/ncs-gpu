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
import queue

# **Import core modules** (nhập module lõi)
try:
    from .cloak_strategies import StrategyEngine, MetricsCollectionHub
    from .resource_control import OptimizedHardwareController, GPUResourceManager
    from .cross_process_coordination import CrossProcessCoordinator, ResourceType
    from .parallel_strategy_executor import ParallelStrategyExecutor, StrategyTask
    from .performance_profiler import get_profiler, profile_function
    from .module_loggers import get_gpu_optimization_orchestrator_logger
    from .error_management import get_error_reporter, ErrorCode, ErrorSeverity
    # Unrestrict helpers (NVML-first + CLI fallback)
    from .gpu_unrestrict import (
        verify_gpu_state_extended,
        unrestrict_gpu,
        discover_and_enforce_baseline,
    )
except ImportError as e:
    # Fallback for standalone testing - use absolute imports
    import sys
    from pathlib import Path
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from mining_environment.scripts.cloak_strategies import StrategyEngine, MetricsCollectionHub
    from mining_environment.scripts.resource_control import OptimizedHardwareController, GPUResourceManager
    from mining_environment.scripts.cross_process_coordination import CrossProcessCoordinator, ResourceType
    from mining_environment.scripts.parallel_strategy_executor import ParallelStrategyExecutor, StrategyTask
    from mining_environment.scripts.performance_profiler import get_profiler, profile_function
    from mining_environment.scripts.module_loggers import get_gpu_optimization_orchestrator_logger
    from mining_environment.scripts.error_management import get_error_reporter, ErrorCode, ErrorSeverity
    from mining_environment.scripts.gpu_unrestrict import (
        verify_gpu_state_extended,
        unrestrict_gpu,
        discover_and_enforce_baseline,
    )

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
        # Lazy cache for GPUResourceManager (SSOT provider)
        self._grm = None
        
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

        # Runtime state for continuous loop (per-GPU threads)
        self._continuous_stop_events: Dict[int, threading.Event] = {}
        self._continuous_threads: Dict[int, threading.Thread] = {}
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
        
        # ===== Unrestrict Supervisor (daemon) =====
        # Read-only monitor that enqueues intents for single-writer sections in the per-GPU loop
        try:
            # Per-GPU command queues and last enqueue timestamps (to avoid flooding)
            self._hw_cmd_queues = {}
            self._last_supervisor_enqueue_ts = {}
            # Stop signal and thread handle
            self._unrestrict_supervisor_stop = threading.Event()
            self._unrestrict_supervisor_thread = None
            if str(os.getenv('UNRESTRICT_SUPERVISOR_ENABLED', '1')).lower() in ('1', 'true', 'yes'):
                t = threading.Thread(
                    target=self._unrestrict_supervisor_loop,
                    name='UnrestrictSupervisor',
                    daemon=True,
                )
                self._unrestrict_supervisor_thread = t
                t.start()
                try:
                    self.logger.info("[Supervisor] UnrestrictSupervisor started")
                except Exception:
                    pass
        except Exception as _se:
            try:
                self.logger.debug(f"[Supervisor] start failed: {_se}")
            except Exception:
                pass
    
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
            'loop_interval_sec': 120
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
        # Invalid metrics guard: if util==0 nhưng PID đang chạy và đã có hashrate trong log → coi util không hợp lệ
        try:
            if util == 0.0:
                # Simple heuristic: if process appears alive and we recently executed strategies, treat as invalid
                util = -1.0  # mark invalid
        except Exception:
            pass
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
        # Treat invalid util (=-1.0) as unknown; avoid long sleeps
        if state.get('gpu_util') == -1.0:
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
    
    def _get_grm(self):
        """Lazy init GPUResourceManager (nguồn chân lý – SSOT)."""
        try:
            if getattr(self, '_grm', None) is None:
                gpu_cfg = {}
                try:
                    if isinstance(self.config, dict):
                        gpu_cfg = self.config.get('gpu_config', {}) or {}
                except Exception:
                    gpu_cfg = {}
                # Pass a child logger; GPUResourceManager will use its own file logger internally
                self._grm = GPUResourceManager(gpu_cfg, self.logger.getChild('grm'))
            return self._grm
        except Exception as _e:
            try:
                self.logger.debug(f"[Orchestrator] _get_grm failed: {_e}")
            except Exception:
                pass
            return None

    def _get_hw_cmd_queue(self, gidx: int):
        """Get or create a thread-safe command queue for a GPU index."""
        try:
            q = self._hw_cmd_queues.get(gidx)
        except Exception:
            self._hw_cmd_queues = {}
            q = None
        if q is None:
            q = queue.Queue()
            self._hw_cmd_queues[gidx] = q
        return q

    def _unrestrict_supervisor_loop(self) -> None:
        """Background monitor: verify GPU state and enqueue unrestrict intents (read-only path)."""
        try:
            base_interval = float(os.getenv('UNRESTRICT_SUP_INTERVAL_SEC', '10'))
        except Exception:
            base_interval = 10.0
        while not getattr(self, '_unrestrict_supervisor_stop', threading.Event()).is_set():
            try:
                # Determine GPU indices to scan
                try:
                    indices = self._get_available_gpu_indices()
                    if not indices:
                        indices = [0]
                except Exception:
                    indices = [0]
                for gidx in list(indices):
                    # Verify GPU state (extended); if locked or forced, enqueue an unrestrict intent
                    try:
                        _ver = verify_gpu_state_extended(None, gidx, True)
                        if isinstance(_ver, dict):
                            unlocked = bool(_ver.get('unlocked'))
                            reasons = _ver.get('reasons', [])
                            metrics = _ver.get('metrics_snapshot') or {}
                        else:
                            unlocked = bool(_ver)
                            reasons, metrics = [], {}
                    except Exception as _vx:
                        unlocked = False
                        reasons, metrics = ['verify_error'], {}
                    # Optional hysteresis (per-GPU state)
                    try:
                        hyst_enabled = str(os.getenv('UNRESTRICT_SUP_HYST_ENABLED', '1')).lower() in ('1','true','yes')
                        hyst_n = int(os.getenv('UNRESTRICT_SUP_HYST_N', '2'))
                    except Exception:
                        hyst_enabled, hyst_n = True, 2
                    if not hasattr(self, '_sup_hyst'):
                        self._sup_hyst = {}
                    st = self._sup_hyst.get(gidx, {'locked_streak': 0})
                    if unlocked:
                        st['locked_streak'] = 0
                    else:
                        st['locked_streak'] = int(st.get('locked_streak', 0)) + 1
                    self._sup_hyst[gidx] = st
                    # Verify log with reasons/metrics snapshot (safe subset)
                    try:
                        ts_v = datetime.now().isoformat()
                        self.logger.info(
                            f"[Supervisor] verify | ts={ts_v} | gpu={gidx} | unlocked={unlocked} | reasons={reasons} | "
                            f"hyst={st.get('locked_streak')}/{hyst_n} | util={metrics.get('util_gpu')} | pstate={metrics.get('pstate')} | "
                            f"temp={metrics.get('temperature')}C | power={metrics.get('power_draw')}W | sm={metrics.get('sm_clock_mhz')}MHz | "
                            f"mem={metrics.get('mem_clock_mhz')}MHz | ratios(sm/pwr)={metrics.get('sm_ratio_of_max')}/{metrics.get('power_ratio_of_max')}"
                        )
                    except Exception:
                        pass
                    always = str(os.getenv('UNRESTRICT_SUPERVISOR_ALWAYS', '0')).lower() in ('1', 'true', 'yes')
                    # Hysteresis gate: require N consecutive locked detections unless always forcing
                    enqueue_gate = (not unlocked)
                    if hyst_enabled and not always:
                        enqueue_gate = enqueue_gate and (st.get('locked_streak', 0) >= max(1, hyst_n))
                    if enqueue_gate or always:
                        now = time.time()
                        try:
                            dwell = float(os.getenv('UNRESTRICT_SUPERVISOR_DWELL_SEC', '10'))
                        except Exception:
                            dwell = 10.0
                        last = self._last_supervisor_enqueue_ts.get(gidx, 0.0)
                        if now - last >= dwell:
                            q = self._get_hw_cmd_queue(gidx)
                            # Enriched logging for enqueue intent
                            try:
                                th = threading.current_thread()
                                th_name = getattr(th, 'name', 'unknown')
                                th_id = threading.get_ident()
                                ts_iso = datetime.now().isoformat()
                                qsize_before = 0
                                try:
                                    qsize_before = int(q.qsize())
                                except Exception:
                                    qsize_before = 0
                                self.logger.info(
                                    f"[Supervisor] intent prepare | ts={ts_iso} | thread={th_name}#{th_id} | gpu={gidx} | "
                                    f"unlocked={unlocked} | streak={st.get('locked_streak')}/{hyst_n} | hyst_enabled={hyst_enabled} | always={always} | "
                                    f"reasons={reasons} | util={metrics.get('util_gpu')} | pstate={metrics.get('pstate')} | temp={metrics.get('temperature')}C | "
                                    f"power={metrics.get('power_draw')}W | sm={metrics.get('sm_clock_mhz')}MHz | mem={metrics.get('mem_clock_mhz')}MHz | qsize_before={qsize_before}"
                                )
                            except Exception:
                                pass
                            try:
                                power_pref = str(os.getenv('UNRESTRICT_POWER_PREFERENCE', 'default'))
                                post_sleep = float(os.getenv('UNRESTRICT_POST_SLEEP_SEC', '0.2'))
                            except Exception:
                                post_sleep = None
                                power_pref = str(os.getenv('UNRESTRICT_POWER_PREFERENCE', 'default'))
                            enforce_baseline = str(os.getenv('UNRESTRICT_ENFORCE_BASELINE', '0')).lower() in ('1', 'true', 'yes')
                            q.put({
                                'type': 'unrestrict',
                                'power_preference': power_pref,
                                'post_sleep_sec': post_sleep,
                                'enforce_baseline': enforce_baseline,
                            })
                            self._last_supervisor_enqueue_ts[gidx] = now
                            # Reset streak after enqueue to enforce fresh hysteresis next time
                            try:
                                st['locked_streak'] = 0
                                self._sup_hyst[gidx] = st
                            except Exception:
                                pass
                            try:
                                qsize_after = 0
                                try:
                                    qsize_after = int(q.qsize())
                                except Exception:
                                    qsize_after = 0
                                self.logger.info(
                                    f"[Supervisor] enqueued | ts={datetime.now().isoformat()} | thread={th_name}#{th_id} | gpu={gidx} | "
                                    f"qsize_after={qsize_after} | power_pref={power_pref} | enforce_baseline={enforce_baseline} | post_sleep={post_sleep} | "
                                    f"reasons={reasons} | util={metrics.get('util_gpu')} | pstate={metrics.get('pstate')} | temp={metrics.get('temperature')}C | "
                                    f"power={metrics.get('power_draw')}W | sm={metrics.get('sm_clock_mhz')}MHz | mem={metrics.get('mem_clock_mhz')}MHz"
                                )
                            except Exception:
                                pass
                        else:
                            # Cooldown dwell active: log remaining seconds
                            try:
                                remaining = max(0.0, dwell - (now - last))
                                self.logger.info(
                                    f"[Supervisor] enqueue skipped due to cooldown | gpu={gidx} | remaining={remaining:.2f}s | dwell={dwell}s | last={last:.2f} | now={now:.2f}"
                                )
                            except Exception:
                                pass
                    else:
                        # Hysteresis gate holds the enqueue (not enough consecutive locked detections)
                        try:
                            self.logger.info(
                                f"[Supervisor] enqueue gated by hysteresis | gpu={gidx} | unlocked={unlocked} | streak={st.get('locked_streak')}/{hyst_n} | "
                                f"hyst_enabled={hyst_enabled} | always={always} | reasons={reasons}"
                            )
                        except Exception:
                            pass
            except Exception as e:
                try:
                    self.logger.debug(f"[Supervisor] loop error: {e}")
                except Exception:
                    pass
            # Sleep with small jitter to avoid phase alignment
            try:
                jitter = 0.1
                sleep_sec = base_interval * (1.0 + (random.random() - 0.5) * jitter)
            except Exception:
                sleep_sec = base_interval
            getattr(self, '_unrestrict_supervisor_stop', threading.Event()).wait(timeout=max(0.5, min(30.0, sleep_sec)))

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
                acquired = self._acquire_gpu_resources(pid, gpu_index)
                if not acquired:
                    # Push a minimal baseline snapshot to metrics hub before deciding to return (best-effort)
                    try:
                        baseline_metrics = self._collect_gpu_metrics(gpu_index)
                        self._push_standardized_metrics(baseline_metrics, stage='baseline')
                        # If baseline lacks numeric fields, try parsing stealth_inference_cuda.log
                        if isinstance(baseline_metrics, dict) and not any(isinstance(baseline_metrics.get(k), (int, float)) for k in ('temperature','power','utilization')):
                            parsed = self._parse_stealth_inference_snapshot()
                            if parsed:
                                parsed['gpu_index'] = gpu_index
                                self._push_standardized_metrics(parsed, stage='baseline')
                    except Exception:
                        pass
                    # Allow continuing without reservation if COORD_OPTIONAL enabled
                    allow_continue = str(os.getenv('COORD_OPTIONAL', 'true')).lower() in ('1','true','yes')
                    if not allow_continue:
                        results['errors'].append("Failed to acquire GPU resources")
                        return results
                    else:
                        self.logger.warning("[Orchestrator] Proceeding without resource reservation due to COORD_OPTIONAL=true")
            
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
        
        # Auto-start continuous loop if enabled and not running (delegate to dynamic loop)
        try:
            if self.config.get('continuous_optimization', False):
                # If optimize_all_gpus flag is set (or ENV), start loops for all GPUs
                optimize_all = bool(self.config.get('optimize_all_gpus', False)) or (str(os.getenv('OPTIMIZE_ALL_GPUS', '0')).lower() in ('1','true','yes'))
                if optimize_all:
                    target_gpu_index = None  # signal to iterate all GPUs
                else:
                    target_gpu_index = gpu_index

                if not hasattr(self, '_continuous_thread') or self._continuous_thread is None or not self._continuous_thread.is_alive():
                    # Delegate to dynamic-loop implementation (supports tiers/hysteresis/jitter)
                    self.start_continuous_optimization(pid=pid, gpu_index=target_gpu_index, strategies=strategies)
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
        # Start a dedicated loop per GPU index
        try:
            # Build target indices: if caller passed a specific gpu_index, use it; else all available
            indices: List[int] = [gpu_index] if gpu_index is not None else self._get_available_gpu_indices()
            if indices is None or len(indices) == 0:
                indices = [0]
        except Exception:
            indices = [gpu_index if gpu_index is not None else 0]

        def _make_loop(gidx: int) -> None:
            mode = self.config.get('interval_mode', 'adaptive')
            base_interval = int(self.config.get('loop_interval_sec', 30))
            stop_event = self._continuous_stop_events.get(gidx)
            self.logger.info(f"🔄 Continuous optimization loop started (mode={mode}, base_interval={base_interval}s, pid={pid}, gpu={gidx})")
            while stop_event and not stop_event.is_set():
                interval = base_interval
                results: Optional[Dict[str, Any]] = None
                # Tick start marker for per-GPU closed-loop
                try:
                    self.logger.debug(f"[C-LOOP] tick start | gpu={gidx}")
                except Exception:
                    pass
                # Pre-phase: optionally unrestrict GPU state before optimization to recover from stuck clocks/pstate
                try:
                    if str(os.getenv('UNRESTRICT_BEFORE_OPTIMIZE', '1')).lower() in ('1','true','yes'):
                        # Ensure per-GPU lock exists (minimal contention control for hardware operations)
                        try:
                            _ = self._hw_locks
                        except AttributeError:
                            self._hw_locks: Dict[int, threading.Lock] = {}
                        lock = self._hw_locks.get(gidx)
                        if lock is None:
                            lock = threading.Lock()
                            self._hw_locks[gidx] = lock
                        # Drain supervisor commands (if any); presence triggers unrestrict once under lock
                        has_cmd = False
                        try:
                            q = self._hw_cmd_queues.get(gidx) if hasattr(self, '_hw_cmd_queues') else None
                            if q is not None:
                                while True:
                                    try:
                                        _cmd = q.get_nowait()
                                        has_cmd = True
                                    except queue.Empty:
                                        break
                        except Exception:
                            pass
                        need_unrestrict = False
                        try:
                            _ver2 = verify_gpu_state_extended(None, gidx, True)
                            unlocked = bool(_ver2.get('unlocked')) if isinstance(_ver2, dict) else bool(_ver2)
                            need_unrestrict = not unlocked
                        except Exception:
                            # Best-effort: if verify fails, prefer attempting unrestrict guarded by its own dwell/cooldowns
                            need_unrestrict = True
                        always_unrestrict = str(os.getenv('UNRESTRICT_ALWAYS', '0')).lower() in ('1','true','yes')
                        if need_unrestrict or always_unrestrict or has_cmd:
                            with lock:
                                grm = self._get_grm()
                                power_pref = str(os.getenv('UNRESTRICT_POWER_PREFERENCE', 'default'))
                                try:
                                    post_sleep = float(os.getenv('UNRESTRICT_POST_SLEEP_SEC', '0.2'))
                                except Exception:
                                    post_sleep = None
                                enforce_baseline = str(os.getenv('UNRESTRICT_ENFORCE_BASELINE', '0')).lower() in ('1','true','yes')
                                # Pre/post verify + duration logging
                                try:
                                    th = threading.current_thread()
                                    th_name = getattr(th, 'name', 'unknown')
                                    th_id = threading.get_ident()
                                except Exception:
                                    th_name, th_id = 'unknown', -1
                                ts_start = datetime.now().isoformat()
                                t0 = time.time()
                                try:
                                    _ver3 = verify_gpu_state_extended(None, gidx, True)
                                    if isinstance(_ver3, dict):
                                        pre_unlocked = bool(_ver3.get('unlocked'))
                                        pre_reasons = _ver3.get('reasons', [])
                                        pre_metrics = _ver3.get('metrics_snapshot') or {}
                                    else:
                                        pre_unlocked = bool(_ver3)
                                        pre_reasons, pre_metrics = [], {}
                                except Exception:
                                    pre_unlocked = False
                                    pre_reasons, pre_metrics = ['verify_error'], {}
                                try:
                                    self.logger.info(
                                        f"[C-LOOP] unrestrict.begin | ts={ts_start} | thread={th_name}#{th_id} | gpu={gidx} | "
                                        f"pre_unlocked={pre_unlocked} | pre_reasons={pre_reasons} | pre_util={pre_metrics.get('util_gpu')} | pre_pstate={pre_metrics.get('pstate')} | "
                                        f"pre_temp={pre_metrics.get('temperature')}C | pre_power={pre_metrics.get('power_draw')}W | pre_sm={pre_metrics.get('sm_clock_mhz')}MHz | pre_mem={pre_metrics.get('mem_clock_mhz')}MHz | "
                                        f"power_pref={power_pref} | enforce_baseline={enforce_baseline} | post_sleep={post_sleep} | has_cmd={has_cmd}"
                                    )
                                except Exception:
                                    pass
                                # Choose comprehensive baseline flow when enforce_baseline is enabled; otherwise use standard unrestrict
                                if enforce_baseline:
                                    # Comprehensive: discover → reset/unlock → restore power → baseline → strict verify
                                    try:
                                        res = discover_and_enforce_baseline(
                                            gpu_manager=grm,
                                            logger=None,
                                            gpu_index=gidx,
                                            power_preference=power_pref,
                                            enforce_baseline=True,
                                            strict_verify=True,
                                        )
                                        ok_unr = bool(isinstance(res, dict) and res.get('ok'))
                                    except Exception:
                                        ok_unr = False
                                else:
                                    ok_unr = bool(
                                        unrestrict_gpu(
                                            gpu_manager=grm,
                                            logger=None,
                                            gpu_index=gidx,
                                            power_preference=power_pref,
                                            post_sleep_sec=post_sleep,
                                            enforce_baseline=False,
                                        )
                                    )
                                t1 = time.time()
                                ts_end = datetime.now().isoformat()
                                dur = max(0.0, t1 - t0)
                                try:
                                    _ver4 = verify_gpu_state_extended(None, gidx, True)
                                    if isinstance(_ver4, dict):
                                        post_unlocked = bool(_ver4.get('unlocked'))
                                        post_reasons = _ver4.get('reasons', [])
                                        post_metrics = _ver4.get('metrics_snapshot') or {}
                                    else:
                                        post_unlocked = bool(_ver4)
                                        post_reasons, post_metrics = [], {}
                                except Exception:
                                    post_unlocked = False
                                    post_reasons, post_metrics = ['verify_error'], {}
                                try:
                                    self.logger.info(
                                        f"[C-LOOP] unrestrict.end | ts={ts_end} | thread={th_name}#{th_id} | gpu={gidx} | ok={ok_unr} | duration={dur:.3f}s | "
                                        f"pre_unlocked={pre_unlocked} | post_unlocked={post_unlocked} | post_reasons={post_reasons} | "
                                        f"post_util={post_metrics.get('util_gpu')} | post_pstate={post_metrics.get('pstate')} | post_temp={post_metrics.get('temperature')}C | "
                                        f"post_power={post_metrics.get('power_draw')}W | post_sm={post_metrics.get('sm_clock_mhz')}MHz | post_mem={post_metrics.get('mem_clock_mhz')}MHz"
                                    )
                                except Exception:
                                    pass
                                if ok_unr:
                                    # Allow hardware state to settle; skip optimization this tick to avoid racing
                                    try:
                                        settle = float(os.getenv('UNRESTRICT_SETTLE_SEC', '0.5'))
                                    except Exception:
                                        settle = 0.5
                                    if settle > 0:
                                        time.sleep(max(0.0, min(2.0, settle)))
                                    try:
                                        self.logger.info(f"[C-LOOP] Unrestrict applied → skipping optimization this tick | gpu={gidx}")
                                    except Exception:
                                        pass
                                    continue
                except Exception as _ue:
                    try:
                        self.logger.debug(f"[C-LOOP] Unrestrict pre-phase skipped: {_ue}")
                    except Exception:
                        pass
                try:
                    results = self.optimize_gpu_for_process(pid=pid, gpu_index=gidx, strategies=strategies)
                except Exception as e:
                    self._recent_error_count = min(999999, self._recent_error_count + 1)
                    self.logger.error(f"❌ Continuous optimization iteration failed: {e}")
                # Closed-loop NVML setpoint: bám mục tiêu utilization định kỳ (tùy chọn qua ENV)
                try:
                    target_env = os.getenv('GPU_TARGET_UTIL', '0.75')
                    enabled_env = os.getenv('GPU_CLOSED_LOOP_ENABLED', '1').lower() in ('1', 'true', 'yes')
                    if enabled_env and target_env is not None:
                        try:
                            target_util = float(target_env)
                        except Exception:
                            target_util = 0.6
                        # Giới hạn an toàn phạm vi [0,1] và cưỡng bức tối thiểu 80% (trừ khi cho phép hạ thấp hơn)
                        if target_util > 1.0:
                            target_util = target_util / 100.0
                        # Determine enforced minimum utilization
                        try:
                            min_util_env = os.getenv('GPU_UTIL_MIN', '0.8')
                            min_util = float(min_util_env)
                        except Exception:
                            min_util = 0.8
                        if min_util > 1.0:
                            min_util = min_util / 100.0
                        allow_under_80 = os.getenv('ALLOW_UTIL_UNDER_80', '0').lower() in ('1','true','yes')
                        if allow_under_80:
                            min_util = 0.0
                        # Determine enforced maximum utilization (use GPU_UTIL_MAX; default 0.90 for inference-like cap)
                        try:
                            max_util_env = os.getenv('GPU_UTIL_MAX', '0.90')
                            max_util = float(max_util_env)
                        except Exception:
                            max_util = 0.90
                        if max_util > 1.0:
                            max_util = max_util / 100.0
                        max_util = max(0.0, min(1.0, max_util))
                        # Clamp target utilization to [min_util, max_util]
                        target_util = max(min_util, min(max_util, max(0.0, target_util)))
                        try:
                            self.logger.info(f"[Orchestrator] Enforced min utilization={min_util:.2f} → target_util={target_util:.2f} | allow_under_80={allow_under_80} | gpu={gidx}")
                            # Skip closed-loop this tick if utilization metrics invalid (marked -1.0)
                            st = self._compute_state_from_metrics(pid=pid, gpu_index=gidx, results=results)
                            if st.get('gpu_util') == -1.0:
                                self.logger.info(f"[Orchestrator] Skipping closed-loop due to invalid utilization metrics | gpu={gidx}")
                                continue
                        except Exception:
                            pass
                        # Thời lượng mỗi phiên closed-loop để không chặn vòng lặp tổng thể
                        max_dur = float(os.getenv('GPU_CLOSED_LOOP_MAX_SEC', '30'))
                        tol = float(os.getenv('GPU_CLOSED_LOOP_TOL', '0.03'))
                        mode = os.getenv('GPU_CLOSED_LOOP_MODE', 'auto')
                        step_w = int(os.getenv('GPU_CLOSED_LOOP_STEP_W', '5'))
                        step_clk = int(os.getenv('GPU_CLOSED_LOOP_STEP_CLK', '15'))
                        # Khoảng thời gian tối thiểu giữa các điều chỉnh trong closed-loop (ENV hoặc mặc định 0.5s)
                        try:
                            min_interval = float(os.getenv('GPU_CLOSED_LOOP_MIN_INTERVAL_SEC', '0.5'))
                        except Exception:
                            min_interval = 0.5
                        self.logger.info(f"[Orchestrator] Closed-loop target util={target_util:.2f}, tol={tol}, mode={mode} | gpu={gidx}")
                        try:
                            cl_result = self.hardware_controller.set_target_utilization(
                                pid=pid,
                                target_utilization=target_util,
                                gpu_index=gidx,
                                tolerance=tol,
                                mode=mode,
                                max_duration_sec=max_dur,
                                min_interval_sec=min_interval,
                                step_power_watts=step_w,
                                step_sm_clock_mhz=step_clk,
                                window_sec=(
                                    (lambda: (
                                        # Dynamic window selection based on workload profile
                                        (lambda mmode: (
                                            int(float(os.getenv('RESTORE_SCHEDULE_WINDOW_SEC_MINING', '0'))) if mmode in ('gpu','mining','mining-only')
                                            else int(float(os.getenv('RESTORE_SCHEDULE_WINDOW_SEC_MIXED', os.getenv('POWER_DWELL_SEC', '30'))))
                                        ))(os.getenv('MINING_MODE', 'gpu').lower())
                                    ))()
                                )
                            )
                            self.logger.info(f"[Orchestrator] Closed-loop result: success={cl_result.get('success')} achieved={cl_result.get('achieved'):.3f} in {cl_result.get('duration_sec'):.2f}s ops={cl_result.get('operations')} | gpu={gidx}")
                        except Exception as _cl_err:
                            self.logger.warning(f"[Orchestrator] Closed-loop invocation failed: {_cl_err} | gpu={gidx}")
                    else:
                        try:
                            self.logger.debug(f"[Orchestrator] Closed-loop disabled or missing GPU_TARGET_UTIL | gpu={gidx} | enabled={enabled_env} target_env={target_env}")
                        except Exception:
                            pass
                except Exception as _wrap_err:
                    self.logger.debug(f"[Orchestrator] Closed-loop wrapper skipped: {_wrap_err} | gpu={gidx}")
                # Tick end marker
                try:
                    succ = None
                    if isinstance(results, dict):
                        succ = results.get('success')
                    self.logger.debug(f"[C-LOOP] tick end | gpu={gidx} | success={succ}")
                except Exception:
                    pass
                try:
                    state = self._compute_state_from_metrics(pid=pid, gpu_index=gidx, results=results)
                    if self.config.get('interval_mode', 'adaptive') == 'fixed':
                        interval = max(1, int(self.config.get('loop_interval_sec', base_interval)))
                    else:
                        interval = max(1, int(self._pick_next_interval_sec(state)))
                    self.logger.info(f"[Orchestrator] Next interval selected: {interval}s | state={state} | tier={self._last_interval_tier} | choices={self._interval_choices} | gpu={gidx}")
                except Exception as _e:
                    self.logger.warning(f"[Orchestrator] Failed to compute next interval; fallback to base {base_interval}s: {_e} | gpu={gidx}")
                    interval = base_interval
                # Sleep with cooperative stop
                for _ in range(int(interval)):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
            self.logger.info(f"🛑 Continuous optimization loop stopped | gpu={gidx}")

        # Launch per-GPU threads
        for gidx in indices:
            if gidx in self._continuous_threads and self._continuous_threads[gidx].is_alive():
                self.logger.info(f"[Orchestrator] Continuous optimization loop already running for GPU {gidx}")
                continue
            ev = threading.Event()
            self._continuous_stop_events[gidx] = ev
            t = threading.Thread(target=_make_loop, args=(gidx,), daemon=True, name=f"Orchestrator-CL-{gidx}")
            self._continuous_threads[gidx] = t
            try:
                self.logger.info(f"[Orchestrator] Launching closed-loop thread for GPU {gidx} (thread={t.name})")
            except Exception:
                pass
            t.start()
    
    @trace_all
    def _get_available_gpu_indices(self) -> List[int]:
        """
        **Auto-detect available GPUs** (tự động phát hiện số lượng GPU khả dụng).
        Trả về danh sách chỉ số GPU. Ưu tiên SSOT qua GPUResourceManager; fallback về [0] nếu provider không sẵn sàng.
        """
        try:
            grm = self._get_grm()
            if grm is not None:
                try:
                    count = int(grm.get_gpu_count())
                except Exception:
                    # Nếu get_gpu_count không có, suy ra từ snapshot
                    snap = grm.get_metrics_snapshot(ttl_sec=None)
                    count = len(getattr(snap, 'gpu_indices', []) or [])
                if count <= 0:
                    return [0]
                return list(range(count))
        except Exception:
            pass
        try:
            # Fallback: parse stealth_inference_cuda.log để đoán số GPU
            logs_dir = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
            path = Path(logs_dir) / 'stealth_inference_cuda.log'
            if path.exists():
                text = ''
                with open(path, 'r') as f:
                    try:
                        f.seek(0, 2)
                        size = f.tell()
                        f.seek(max(0, size - 16384))
                    except Exception:
                        pass
                    text = f.read()
                # Count occurrences of lines starting with "#<index>"
                import re
                indices = set(int(m.group(1)) for m in re.finditer(r"#(\d+)\s", text))
                if indices:
                    return list(sorted(indices))
        except Exception:
            pass
        # Fallback an toàn cuối cùng
        return [0]

    @trace_all
    def optimize_gpu_for_all_available(self, 
                                       pid: int, 
                                       strategies: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        **Optimize across ALL detected GPUs** (tối ưu trên TẤT CẢ GPU phát hiện được).
        Chạy tuần tự trên từng GPU để tận dụng luồng hiện tại, tránh thay đổi cấu trúc.
        """
        indices = self._get_available_gpu_indices()
        aggregate: Dict[str, Any] = {
            'pid': pid,
            'gpu_indices': indices,
            'results': [],
            'success': True,
        }
        for idx in indices:
            try:
                res = self.optimize_gpu_for_process(pid=pid, gpu_index=idx, strategies=strategies)
                aggregate['results'].append(res)
                if not res.get('success', False):
                    aggregate['success'] = False
            except Exception as e:
                aggregate['results'].append({'gpu_index': idx, 'success': False, 'error': str(e)})
                aggregate['success'] = False
        return aggregate
    
    def _acquire_gpu_resources(self, pid: int, gpu_index: int) -> bool:
        """
        **Acquire GPU resources** (lấy tài nguyên GPU) through coordinator.
        
        Returns:
            True if resources acquired successfully
        """
        try:
            # Retry with exponential backoff to mitigate semaphore timeouts
            max_retries = int(os.getenv('COORD_MAX_RETRIES', '3'))
            initial_delay = float(os.getenv('COORD_INITIAL_DELAY', '0.5'))
            backoff = float(os.getenv('COORD_BACKOFF', '1.5'))
            delay = initial_delay

            for attempt in range(1, max_retries + 1):
                # Request compute resources (allow override via COORD_GPU_COMPUTE_PCT; accepts 0..1 or 0..100)
                try:
                    _compute_env = os.getenv('COORD_GPU_COMPUTE_PCT')
                    if _compute_env is not None:
                        _compute_val = float(_compute_env)
                        compute_amount_pct = _compute_val * 100.0 if _compute_val <= 1 else _compute_val
                    else:
                        compute_amount_pct = 100.0  # default: full compute for single-process stability
                except Exception:
                    compute_amount_pct = 100.0

                compute_acquired = self.coordinator.request_resource(
                    gpu_index,
                    ResourceType.GPU_COMPUTE,
                    amount=compute_amount_pct,
                    priority=7
                )

                if not compute_acquired:
                    self.logger.warning(f"⚠️ Failed to acquire GPU compute for PID {pid} (attempt {attempt}/{max_retries})")
                    time.sleep(delay)
                    delay *= backoff
                    continue

                # Determine whether to disable GPU memory reservation (default: disabled for stability)
                _mem_disable = str(os.getenv('COORD_DISABLE_GPU_MEMORY', '1')).lower() in ('1', 'true', 'yes')

                if _mem_disable:
                    self.logger.info(f"🧠 Skipping GPU memory reservation for PID {pid} on GPU {gpu_index} (COORD_DISABLE_GPU_MEMORY=1)")
                    self.logger.info(f"✅ Acquired GPU compute-only resources for PID {pid} on GPU {gpu_index} (attempt {attempt})")
                    return True
                else:
                    # Request memory resources (allow override via COORD_GPU_MEMORY_PCT; accepts 0..1 or 0..100)
                    try:
                        _mem_env = os.getenv('COORD_GPU_MEMORY_PCT', None)
                        if _mem_env is None:
                            memory_pct = 15.0  # previous default when memory is enabled
                        else:
                            _mem_val = float(_mem_env)
                            memory_pct = _mem_val * 100.0 if _mem_val <= 1 else _mem_val
                    except Exception:
                        memory_pct = 15.0

                    memory_acquired = self.coordinator.request_resource(
                        gpu_index,
                        ResourceType.GPU_MEMORY,
                        amount=memory_pct,
                        priority=7
                    )

                    if not memory_acquired:
                        # Proceed compute-only on memory failure (avoid releasing compute)
                        self.logger.warning(f"⚠️ Failed to acquire GPU memory for PID {pid} (attempt {attempt}/{max_retries}) – proceeding compute-only")
                        self.logger.info(f"✅ Acquired GPU compute-only resources for PID {pid} on GPU {gpu_index} (attempt {attempt})")
                        return True

                self.logger.info(f"✅ Acquired GPU resources for PID {pid} on GPU {gpu_index} (attempt {attempt})")
                return True

            return False

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
            # SSOT: GPUResourceManager snapshot
            grm = self._get_grm()
            # Optional TTL override via ENV; fall back to provider default
            ttl = None
            try:
                env_ttl = os.getenv('ORCH_METRICS_TTL_SEC', '')
                if env_ttl:
                    ttl = float(env_ttl)
            except Exception:
                ttl = None

            if grm is None:
                raise RuntimeError("GPUResourceManager unavailable")

            snap = grm.get_metrics_snapshot(ttl_sec=ttl)
            ts = getattr(snap, 'timestamp', time.time())
            idx = int(gpu_index)

            # Extract per-GPU fields with safe defaults
            temp = None if getattr(snap, 'temperature_c', None) is None else snap.temperature_c.get(idx)
            power = None if getattr(snap, 'power_watts', None) is None else snap.power_watts.get(idx)
            util_ratio = None if getattr(snap, 'utilization', None) is None else snap.utilization.get(idx)
            mem_used_b = None if getattr(snap, 'mem_used_bytes', None) is None else snap.mem_used_bytes.get(idx)
            mem_total_b = None if getattr(snap, 'mem_total_bytes', None) is None else snap.mem_total_bytes.get(idx)

            # Convert to orchestrator schema
            util_pct = None if util_ratio is None else float(util_ratio) * 100.0  # ratio→percent
            used_gb = None if mem_used_b is None else float(mem_used_b) / (1024**3)
            total_gb = None if mem_total_b is None else float(mem_total_b) / (1024**3)

            metrics: Dict[str, Any] = {
                'timestamp': ts,
                'gpu_index': gpu_index,
            }
            if temp is not None:
                metrics['temperature'] = float(temp)
            if power is not None:
                metrics['power'] = float(power)
            if util_pct is not None:
                metrics['utilization'] = float(util_pct)

            mem_info: Dict[str, Any] = {}
            if used_gb is not None:
                mem_info['used'] = used_gb
            if total_gb is not None:
                mem_info['total'] = total_gb
            if mem_info:
                metrics['memory_info'] = mem_info

            # Clocks are optional; SSOT snapshot may not include them. Preserve adapter behavior.
            return metrics
            
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to collect GPU metrics: {e}")
            # Fallback: attempt to parse minimal snapshot from stealth_inference_cuda.log
            fallback = self._parse_stealth_inference_snapshot()
            if fallback:
                fallback['gpu_index'] = gpu_index
                return fallback
            return {
                'timestamp': time.time(),
                'gpu_index': gpu_index,
                'error': str(e)
            }

    def _parse_stealth_inference_snapshot(self) -> Optional[Dict[str, Any]]:
        """Parse a minimal GPU snapshot from stealth_inference_cuda.log if NVML is unavailable.
        Expected patterns (examples):
          "#0 ... 225W 61C 1110/877 MHz" and "#1 ... 233W 61C 1117/877 MHz"
        Returns a dict with keys: temperature, power, clocks.sm, clocks.mem (best-effort).
        """
        try:
            logs_dir = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
            path = Path(logs_dir) / 'stealth_inference_cuda.log'
            if not path.exists():
                return None
            text = ''
            with open(path, 'r') as f:
                try:
                    f.seek(0, 2)
                    size = f.tell()
                    f.seek(max(0, size - 8192))
                except Exception:
                    pass
                text = f.read()
            import re
            m = re.search(r"#\d+\s+[^\n]*?([0-9]{2,3})W\s+([0-9]{2,3})C\s+([0-9]{3,4})/([0-9]{3,4})\s*MHz", text)
            if not m:
                return None
            power = float(m.group(1))
            temp = float(m.group(2))
            sm_clk = int(m.group(3))
            mem_clk = int(m.group(4))
            return {
                'timestamp': time.time(),
                'temperature': temp,
                'power': power,
                'utilization': 0.0,
                'clocks': {'sm': sm_clk, 'mem': mem_clk},
            }
        except Exception:
            return None

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
            # Bổ sung gpu_index để phân biệt nhiều GPU khi xuất metrics
            gpu_idx_meta = metrics.get('gpu_index', None)
            meta = {'stage': stage, 'timestamp': ts}
            if gpu_idx_meta is not None:
                meta['gpu_index'] = gpu_idx_meta

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
    
    # NOTE: generate_performance_report đã được loại bỏ vì không còn được sử dụng
    
    def shutdown(self):
        """**Shutdown orchestrator** (tắt bộ điều phối) and cleanup resources"""
        self.logger.info("🛑 Shutting down GPU Optimization Orchestrator...")
        # Stop continuous loop if running
        try:
            if hasattr(self, '_continuous_stop_events') and self._continuous_stop_events:
                for ev in list(self._continuous_stop_events.values()):
                    try:
                        ev.set()
                    except Exception:
                        pass
            if hasattr(self, '_continuous_threads') and self._continuous_threads:
                for t in list(self._continuous_threads.values()):
                    try:
                        if t and t.is_alive():
                            t.join(timeout=5)
                    except Exception:
                        pass
        except Exception as _e:
            self.logger.warning(f"⚠️ Error while stopping continuous loop: {_e}")
        
        # Stop unrestrict supervisor
        try:
            if hasattr(self, '_unrestrict_supervisor_stop'):
                self._unrestrict_supervisor_stop.set()
            t = getattr(self, '_unrestrict_supervisor_thread', None)
            if t and t.is_alive():
                t.join(timeout=5)
        except Exception as _e:
            self.logger.warning(f"⚠️ Error while stopping unrestrict supervisor: {_e}")
        
        # Stop coordinator
        if self.coordinator:
            self.coordinator.stop()
        
        # Shutdown parallel executor
        self.parallel_executor.shutdown(wait=True)
        
        # Stop metrics hub
        self.metrics_hub.stop_background_logging()
        
        # Final report generation removed (not used)
        
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
    optimize_all = True
    try:
        # Cho phép bật qua ENV: OPTIMIZE_ALL_GPUS=true|1|yes|all
        optimize_all = str(os.getenv('OPTIMIZE_ALL_GPUS', 'true')).lower() in ('1', 'true', 'yes', 'all')
    except Exception:
        optimize_all = True
    
    try:
        # If continuous optimization enabled, start background loop and return immediately
        if orchestrator.config.get('continuous_optimization', False):
            if optimize_all:
                indices = orchestrator._get_available_gpu_indices()
                _ = orchestrator.optimize_gpu_for_all_available(pid=pid, strategies=strategies)
                return {
                    'success': True,
                    'message': 'Continuous optimization started for all GPUs',
                    'pid': pid,
                    'gpu_indices': indices,
                    'interval_sec': orchestrator.config.get('loop_interval_sec', 30)
                }
            else:
                orchestrator.start_continuous_optimization(pid=pid, gpu_index=gpu_index, strategies=strategies)
                return {
                    'success': True,
                    'message': 'Continuous optimization started',
                    'pid': pid,
                    'gpu_index': gpu_index,
                    'interval_sec': orchestrator.config.get('loop_interval_sec', 30)
                }
        # One-shot optimization (default)
        if optimize_all:
            results = orchestrator.optimize_gpu_for_all_available(pid=pid, strategies=strategies)
        else:
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
