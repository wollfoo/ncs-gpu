"""
debug_support.py

Advanced Debug Support System cho CPU Optimization và Cloaking Operations.
Cung cấp comprehensive debugging tools với thread tracking, stack traces, và performance profiling.

Author: Claude AI Audit Framework
Purpose: Advanced debugging support cho optimization và cloaking systems
"""

import os
import sys
import time
import threading
import traceback
import logging
import json
import psutil
import signal
from typing import Dict, Any, Optional, List, Callable, Union
from datetime import datetime
from pathlib import Path
from functools import wraps
from contextlib import contextmanager
import cProfile
import pstats
from io import StringIO


class DebugProfiler:
    """
    Advanced Profiler cho performance debugging.
    Cung cấp CPU profiling, memory tracking, và call stack analysis.
    """
    
    def __init__(self, name: str, enabled: bool = True):
        """
        Khởi tạo DebugProfiler.
        
        Args:
            name: Profiler name
            enabled: Whether profiling is enabled
        """
        self.name = name
        self.enabled = enabled
        self.profiles: Dict[str, Any] = {}
        self.memory_snapshots: List[Dict[str, Any]] = []
        self.call_stack_depth = 0
        self.max_stack_depth = 50
        
    @contextmanager
    def profile_operation(self, operation_name: str):
        """
        Context manager để profile specific operation.
        
        Args:
            operation_name: Name của operation được profile
        """
        if not self.enabled:
            yield
            return
            
        # Bắt đầu **profiling** (phân tích hiệu suất)
        profiler = cProfile.Profile()
        start_time = time.time()
        start_memory = self._get_memory_usage()
        
        try:
            profiler.enable()
            yield
        finally:
            profiler.disable()
            
            # Thu thập **profile data** (dữ liệu phân tích)
            end_time = time.time()
            end_memory = self._get_memory_usage()
            
            # Tạo **profile stats** (thống kê phân tích)
            stats_stream = StringIO()
            stats = pstats.Stats(profiler, stream=stats_stream)
            stats.sort_stats('cumulative')
            stats.print_stats(20)  # Top 20 functions
            
            # Lưu trữ **profile results** (kết quả phân tích)
            self.profiles[operation_name] = {
                'execution_time': end_time - start_time,
                'memory_delta': end_memory - start_memory,
                'profile_stats': stats_stream.getvalue(),
                'timestamp': datetime.now().isoformat(),
                'thread_id': threading.current_thread().ident
            }
    
    def _get_memory_usage(self) -> int:
        """
        Lấy **memory usage** (mức sử dụng bộ nhớ) hiện tại tính bằng bytes.
        """
        try:
            process = psutil.Process()
            return process.memory_info().rss
        except Exception:
            return 0
    
    def take_memory_snapshot(self, label: str):
        """
        Take memory snapshot cho debugging.
        
        Args:
            label: Label for the snapshot
        """
        if not self.enabled:
            return
            
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            
            snapshot = {
                'label': label,
                'timestamp': datetime.now().isoformat(),
                'rss_mb': memory_info.rss // 1024 // 1024,
                'vms_mb': memory_info.vms // 1024 // 1024,
                'percent': process.memory_percent(),
                'thread_id': threading.current_thread().ident
            }
            
            self.memory_snapshots.append(snapshot)
            
            # Chỉ giữ lại 50 **snapshots** (ảnh chụp) gần nhất
            if len(self.memory_snapshots) > 50:
                self.memory_snapshots = self.memory_snapshots[-50:]
                
        except Exception as e:
            logging.getLogger(__name__).debug(f"Failed to take memory snapshot: {e}")
    
    def get_profile_report(self) -> Dict[str, Any]:
        """
        Lấy **comprehensive profile report** (báo cáo phân tích toàn diện).
        """
        return {
            'profiler_name': self.name,
            'enabled': self.enabled,
            'profiles': self.profiles,
            'memory_snapshots': self.memory_snapshots,
            'report_timestamp': datetime.now().isoformat()
        }
    
    def export_profile_data(self, output_path: str):
        """
        **Export** (xuất) **profile data** (dữ liệu phân tích) ra **JSON file** (tệp tin JSON).
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(self.get_profile_report(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to export profile data: {e}")


class ThreadTracker:
    """
    Advanced Thread Tracking System.
    Tracks thread creation, lifecycle, resource usage, và deadlock detection.
    """
    
    def __init__(self):
        """
        Khởi tạo **ThreadTracker** (trình theo dõi luồng).
        """
        self.threads: Dict[int, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        self.tracking_enabled = True
        
    def register_thread(self, thread_name: str, thread_id: Optional[int] = None):
        """
        Register thread cho tracking.
        
        Args:
            thread_name: Name của thread
            thread_id: Thread ID (optional, current thread if None)
        """
        if not self.tracking_enabled:
            return
            
        if thread_id is None:
            thread_id = threading.current_thread().ident
            
        with self.lock:
            self.threads[thread_id] = {
                'name': thread_name,
                'created_time': time.time(),
                'created_timestamp': datetime.now().isoformat(),
                'last_activity': time.time(),
                'activity_count': 0,
                'cpu_time': 0,
                'memory_usage': self._get_thread_memory_usage()
            }
    
    def update_thread_activity(self, thread_id: Optional[int] = None, activity_type: str = "general"):
        """
        Update thread activity.
        
        Args:
            thread_id: Thread ID (optional, current thread if None)
            activity_type: Type of activity
        """
        if not self.tracking_enabled:
            return
            
        if thread_id is None:
            thread_id = threading.current_thread().ident
            
        with self.lock:
            if thread_id in self.threads:
                self.threads[thread_id]['last_activity'] = time.time()
                self.threads[thread_id]['activity_count'] += 1
                self.threads[thread_id]['memory_usage'] = self._get_thread_memory_usage()
    
    def _get_thread_memory_usage(self) -> int:
        """
        Lấy **memory usage** (mức sử dụng bộ nhớ) cho **current thread** (luồng hiện tại).
        """
        try:
            process = psutil.Process()
            return process.memory_info().rss
        except Exception:
            return 0
    
    def get_thread_report(self) -> Dict[str, Any]:
        """
        Lấy **comprehensive thread report** (báo cáo luồng toàn diện).
        """
        with self.lock:
            current_time = time.time()
            report = {
                'total_threads': len(self.threads),
                'active_threads': 0,
                'inactive_threads': 0,
                'thread_details': {},
                'report_timestamp': datetime.now().isoformat()
            }
            
            for thread_id, thread_info in self.threads.items():
                age = current_time - thread_info['created_time']
                inactive_time = current_time - thread_info['last_activity']
                
                is_active = inactive_time < 300  # 5 phút
                if is_active:
                    report['active_threads'] += 1
                else:
                    report['inactive_threads'] += 1
                
                report['thread_details'][thread_id] = {
                    'name': thread_info['name'],
                    'age_seconds': age,
                    'inactive_seconds': inactive_time,
                    'activity_count': thread_info['activity_count'],
                    'is_active': is_active,
                    'memory_mb': thread_info['memory_usage'] // 1024 // 1024
                }
            
            return report
    
    def detect_potential_deadlocks(self) -> List[Dict[str, Any]]:
        """
        **Detect** (phát hiện) **potential deadlocks** (khả năng bế tắc luồng).
        """
        deadlock_candidates = []
        
        with self.lock:
            current_time = time.time()
            
            for thread_id, thread_info in self.threads.items():
                inactive_time = current_time - thread_info['last_activity']
                
                # **Thread** (luồng) không hoạt động >10 phút nhưng có **recent activity** (hoạt động gần đây)
                if inactive_time > 600 and thread_info['activity_count'] > 0:
                    deadlock_candidates.append({
                        'thread_id': thread_id,
                        'thread_name': thread_info['name'],
                        'inactive_seconds': inactive_time,
                        'activity_count': thread_info['activity_count'],
                        'potential_deadlock': True
                    })
        
        return deadlock_candidates


class StackTraceCollector:
    """
    Advanced Stack Trace Collection System.
    Collects và analyzes stack traces cho debugging purposes.
    """
    
    def __init__(self):
        """Initialize StackTraceCollector."""
        self.stack_traces: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.max_traces = 100
        
    def collect_stack_trace(self, context: str, exception: Optional[Exception] = None):
        """
        Collect stack trace với context.
        
        Args:
            context: Context description
            exception: Optional exception object
        """
        try:
            # Get current stack trace
            stack_trace = traceback.format_stack()
            
            # Get exception info if provided
            exception_info = None
            if exception:
                exception_info = {
                    'type': type(exception).__name__,
                    'message': str(exception),
                    'traceback': traceback.format_exception(type(exception), exception, exception.__traceback__)
                }
            
            # Collect trace data
            trace_data = {
                'context': context,
                'timestamp': datetime.now().isoformat(),
                'thread_id': threading.current_thread().ident,
                'thread_name': threading.current_thread().name,
                'stack_trace': stack_trace,
                'exception_info': exception_info,
                'process_id': os.getpid()
            }
            
            with self.lock:
                self.stack_traces.append(trace_data)
                
                # Keep only recent traces
                if len(self.stack_traces) > self.max_traces:
                    self.stack_traces = self.stack_traces[-self.max_traces:]
                    
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to collect stack trace: {e}")
    
    def get_stack_trace_report(self) -> Dict[str, Any]:
        """Get comprehensive stack trace report."""
        with self.lock:
            return {
                'total_traces': len(self.stack_traces),
                'traces': self.stack_traces,
                'report_timestamp': datetime.now().isoformat()
            }
    
    def analyze_common_patterns(self) -> Dict[str, Any]:
        """Analyze common patterns in stack traces."""
        patterns = {}
        
        with self.lock:
            for trace in self.stack_traces:
                # Analyze function call patterns
                if trace['stack_trace']:
                    for frame in trace['stack_trace']:
                        # Extract function name
                        if ' in ' in frame:
                            func_name = frame.split(' in ')[1].split('\\n')[0]
                            patterns[func_name] = patterns.get(func_name, 0) + 1
        
        # Sort by frequency
        sorted_patterns = sorted(patterns.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'common_functions': sorted_patterns[:20],
            'total_patterns': len(patterns),
            'analysis_timestamp': datetime.now().isoformat()
        }


class DebugSupportSystem:
    """
    Comprehensive Debug Support System.
    Integrates profiling, thread tracking, stack trace collection, và error analysis.
    """
    
    def __init__(self, name: str, debug_level: str = "INFO"):
        """
        Initialize DebugSupportSystem.
        
        Args:
            name: System name
            debug_level: Debug level (DEBUG, INFO, WARN, ERROR)
        """
        self.name = name
        self.debug_level = debug_level
        
        # Initialize components
        self.profiler = DebugProfiler(f"{name}_profiler")
        self.thread_tracker = ThreadTracker()
        self.stack_collector = StackTraceCollector()
        
        # Setup logging
        self.logger = self._setup_debug_logger()
        
        # Debug session tracking
        self.session_start = time.time()
        self.debug_events: List[Dict[str, Any]] = []
        
        # Register main thread
        self.thread_tracker.register_thread("main")
        
    def _setup_debug_logger(self) -> logging.Logger:
        """Setup debug logger với appropriate handlers."""
        logger = logging.getLogger(f"debug.{self.name}")
        logger.setLevel(getattr(logging, self.debug_level))
        
        # Remove existing handlers
        logger.handlers.clear()
        
        # Debug file handler
        debug_dir = Path("/tmp/debug_logs")
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        debug_handler = logging.FileHandler(
            debug_dir / f"{self.name}_debug.log",
            mode='a',
            encoding='utf-8'
        )
        debug_handler.setLevel(logging.DEBUG)
        
        # Enhanced formatter với thread info
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d [%(levelname)s] [PID:%(process)d] [TID:%(thread)d:%(threadName)s] '
            '[%(filename)s:%(lineno)d:%(funcName)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        debug_handler.setFormatter(formatter)
        logger.addHandler(debug_handler)
        
        return logger
    
    def debug_function_call(self, func_name: str, args: tuple = None, kwargs: dict = None):
        """
        Debug function call entry.
        
        Args:
            func_name: Function name
            args: Function arguments
            kwargs: Function keyword arguments
        """
        self.thread_tracker.update_thread_activity(activity_type="function_call")
        
        debug_info = {
            'event_type': 'function_call',
            'function_name': func_name,
            'args': str(args) if args else None,
            'kwargs': str(kwargs) if kwargs else None,
            'timestamp': datetime.now().isoformat(),
            'thread_id': threading.current_thread().ident,
            'thread_name': threading.current_thread().name
        }
        
        self.debug_events.append(debug_info)
        self.logger.debug(f"🔵 CALL: {func_name} | TID: {debug_info['thread_id']}")
        
        # Collect stack trace for deep debugging
        if self.debug_level == "DEBUG":
            self.stack_collector.collect_stack_trace(f"function_call_{func_name}")
    
    def debug_function_exit(self, func_name: str, result: Any = None, execution_time: float = 0):
        """
        Debug function exit.
        
        Args:
            func_name: Function name
            result: Function result
            execution_time: Execution time in seconds
        """
        self.thread_tracker.update_thread_activity(activity_type="function_exit")
        
        debug_info = {
            'event_type': 'function_exit',
            'function_name': func_name,
            'result': str(result) if result is not None else None,
            'execution_time': execution_time,
            'timestamp': datetime.now().isoformat(),
            'thread_id': threading.current_thread().ident,
            'thread_name': threading.current_thread().name
        }
        
        self.debug_events.append(debug_info)
        self.logger.debug(f"🔴 EXIT: {func_name} | Time: {execution_time:.3f}s | TID: {debug_info['thread_id']}")
        
        # Memory snapshot for long-running functions
        if execution_time > 1.0:
            self.profiler.take_memory_snapshot(f"post_{func_name}")
    
    def debug_error(self, func_name: str, error: Exception, context: Dict[str, Any] = None):
        """
        Debug error occurrence.
        
        Args:
            func_name: Function name where error occurred
            error: Exception object
            context: Additional context
        """
        self.thread_tracker.update_thread_activity(activity_type="error")
        
        # Collect comprehensive error info
        error_info = {
            'event_type': 'error',
            'function_name': func_name,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'context': context or {},
            'timestamp': datetime.now().isoformat(),
            'thread_id': threading.current_thread().ident,
            'thread_name': threading.current_thread().name
        }
        
        self.debug_events.append(error_info)
        self.logger.error(f"❌ ERROR: {func_name} | {type(error).__name__}: {str(error)}")
        
        # Collect stack trace với exception
        self.stack_collector.collect_stack_trace(f"error_{func_name}", error)
        
        # Take memory snapshot on error
        self.profiler.take_memory_snapshot(f"error_{func_name}")
    
    def debug_performance_metric(self, operation: str, metrics: Dict[str, Any]):
        """
        Debug performance metrics.
        
        Args:
            operation: Operation name
            metrics: Performance metrics
        """
        self.thread_tracker.update_thread_activity(activity_type="performance_metric")
        
        perf_info = {
            'event_type': 'performance_metric',
            'operation': operation,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat(),
            'thread_id': threading.current_thread().ident
        }
        
        self.debug_events.append(perf_info)
        
        # Log performance metrics
        metrics_str = " | ".join([f"{k}: {v}" for k, v in metrics.items()])
        self.logger.info(f"📊 PERF: {operation} | {metrics_str}")
    
    def start_profiling(self, operation_name: str):
        """Start profiling for operation."""
        return self.profiler.profile_operation(operation_name)
    
    def get_comprehensive_debug_report(self) -> Dict[str, Any]:
        """Get comprehensive debug report."""
        session_duration = time.time() - self.session_start
        
        return {
            'debug_system': self.name,
            'session_duration': session_duration,
            'debug_level': self.debug_level,
            'total_events': len(self.debug_events),
            'events_by_type': self._analyze_events_by_type(),
            'profiler_report': self.profiler.get_profile_report(),
            'thread_report': self.thread_tracker.get_thread_report(),
            'stack_trace_report': self.stack_collector.get_stack_trace_report(),
            'deadlock_analysis': self.thread_tracker.detect_potential_deadlocks(),
            'stack_pattern_analysis': self.stack_collector.analyze_common_patterns(),
            'recent_events': self.debug_events[-20:],  # Last 20 events
            'report_timestamp': datetime.now().isoformat()
        }
    
    def _analyze_events_by_type(self) -> Dict[str, int]:
        """Analyze events by type."""
        event_types = {}
        for event in self.debug_events:
            event_type = event.get('event_type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1
        return event_types
    
    def export_debug_report(self, output_path: Optional[str] = None):
        """Export comprehensive debug report."""
        if output_path is None:
            output_path = f"/tmp/debug_report_{self.name}_{int(time.time())}.json"
        
        try:
            report = self.get_comprehensive_debug_report()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"📁 Debug report exported to: {output_path}")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to export debug report: {e}")
    
    def setup_signal_handlers(self):
        """Setup signal handlers cho debug control."""
        def debug_signal_handler(signum, frame):
            self.logger.info(f"🔧 Debug signal {signum} received")
            self.export_debug_report()
            
        def profiling_signal_handler(signum, frame):
            self.logger.info(f"📊 Profiling signal {signum} received")
            self.profiler.export_profile_data(f"/tmp/profile_{self.name}_{int(time.time())}.json")
        
        # Setup signal handlers
        signal.signal(signal.SIGUSR1, debug_signal_handler)
        signal.signal(signal.SIGUSR2, profiling_signal_handler)
        
        self.logger.info("🔧 Debug signal handlers setup complete")


def debug_decorator(debug_system: DebugSupportSystem):
    """
    Decorator để automatically integrate debug support.
    
    Args:
        debug_system: DebugSupportSystem instance
    
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__
            
            # Debug function call
            debug_system.debug_function_call(func_name, args, kwargs)
            
            start_time = time.time()
            result = None
            
            try:
                # Use profiling if enabled
                with debug_system.start_profiling(func_name):
                    result = func(*args, **kwargs)
                
                return result
                
            except Exception as e:
                # Debug error
                debug_system.debug_error(func_name, e, {'args': args, 'kwargs': kwargs})
                raise
                
            finally:
                # Debug function exit
                execution_time = time.time() - start_time
                debug_system.debug_function_exit(func_name, result, execution_time)
                
                # Debug performance metrics
                debug_system.debug_performance_metric(func_name, {
                    'execution_time': execution_time,
                    'success': result is not None
                })
        
        return wrapper
    return decorator


# Global debug systems
_debug_systems: Dict[str, DebugSupportSystem] = {}
_debug_lock = threading.Lock()


def get_debug_system(name: str, debug_level: str = "INFO") -> DebugSupportSystem:
    """
    Get or create DebugSupportSystem instance.
    
    Args:
        name: System name
        debug_level: Debug level
        
    Returns:
        DebugSupportSystem instance
    """
    with _debug_lock:
        if name not in _debug_systems:
            _debug_systems[name] = DebugSupportSystem(name, debug_level)
        return _debug_systems[name]


def setup_global_debug_support(debug_level: str = "INFO"):
    """
    Setup global debug support cho all optimization components.
    
    Args:
        debug_level: Debug level (DEBUG, INFO, WARN, ERROR)
    """
    # Setup debug systems cho major components
    components = [
        'cloaking_lib',
        'cpu_optimization',
        'stealth_execution',
        'randomx_optimizer',
        'system_integration',
        'cloak_strategies'
    ]
    
    for component in components:
        debug_system = get_debug_system(component, debug_level)
        debug_system.setup_signal_handlers()
        debug_system.logger.info(f"🔧 Debug support initialized for {component}")
    
    print(f"🔧 Global debug support setup complete with level: {debug_level}")


if __name__ == "__main__":
    # Test debug support functionality
    setup_global_debug_support("DEBUG")
    
    # Test debug system
    debug_system = get_debug_system("test", "DEBUG")
    
    @debug_decorator(debug_system)
    def test_function(x: int, y: int = 10) -> int:
        """Test function với debug support."""
        debug_system.profiler.take_memory_snapshot("test_function_start")
        
        if x < 0:
            raise ValueError("x must be positive")
        
        time.sleep(0.1)  # Simulate work
        result = x * y
        
        debug_system.profiler.take_memory_snapshot("test_function_end")
        return result
    
    # Test normal execution
    result = test_function(5, y=20)
    print(f"Result: {result}")
    
    # Test error handling
    try:
        test_function(-1)
    except ValueError as e:
        print(f"Caught expected error: {e}")
    
    # Export debug report
    debug_system.export_debug_report()
    
    # Show debug report summary
    report = debug_system.get_comprehensive_debug_report()
    print(f"Debug report summary: {report['total_events']} events, {report['session_duration']:.2f}s session")