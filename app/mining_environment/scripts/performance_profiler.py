#!/usr/bin/env python3
"""
**Performance Profiler** (Bộ phân tích hiệu năng)

Comprehensive performance profiling for GPU strategy optimization with:
- cProfile for function-level profiling
- tracemalloc for memory tracking
- Timing decorators for precise measurements
- Performance dashboard for visualization
- Bottleneck detection and analysis
"""

import os
import time
import cProfile
import pstats
import tracemalloc
import functools
import threading
import json
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque
from io import StringIO
import psutil

# Import từ các modules hiện có
try:
    from module_loggers import get_optimization_logger
    logger = get_optimization_logger()
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)


@dataclass
class ProfileMetrics:
    """
    **Profile Metrics** (chỉ số phân tích - thông số đo lường)
    
    Stores performance metrics for a profiled function.
    """
    function_name: str
    total_calls: int = 0
    total_time: float = 0.0  # seconds
    average_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    
    # Memory metrics
    memory_peak: int = 0  # bytes
    memory_allocated: int = 0
    memory_freed: int = 0
    
    # Detailed timing
    cpu_time: float = 0.0
    wall_time: float = 0.0
    
    # Call stack info
    call_stack: List[str] = field(default_factory=list)
    
    # Historical data (for trend analysis)
    time_history: deque = field(default_factory=lambda: deque(maxlen=100))
    memory_history: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def update(self, execution_time: float, memory_usage: int = 0):
        """Update metrics with new execution data"""
        self.total_calls += 1
        self.total_time += execution_time
        self.average_time = self.total_time / self.total_calls
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)
        
        self.time_history.append(execution_time)
        
        if memory_usage > 0:
            self.memory_peak = max(self.memory_peak, memory_usage)
            self.memory_history.append(memory_usage)


@dataclass
class BottleneckInfo:
    """
    **Bottleneck Info** (thông tin tắc nghẽn - điểm nghẽn hiệu năng)
    
    Information about detected performance bottlenecks.
    """
    type: str  # 'cpu', 'memory', 'io', 'gpu'
    severity: str  # 'low', 'medium', 'high', 'critical'
    function_name: str
    description: str
    impact_score: float  # 0-100
    recommendations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    """
    **Performance Profiler** (bộ phân tích hiệu năng)
    
    Main class for comprehensive performance profiling.
    """
    
    def __init__(self, enable_memory_tracking: bool = True):
        """
        Initialize performance profiler.
        
        Args:
            enable_memory_tracking: Whether to track memory usage
        """
        self.enable_memory = enable_memory_tracking
        
        # Metrics storage
        self.metrics: Dict[str, ProfileMetrics] = {}
        self.bottlenecks: List[BottleneckInfo] = []
        
        # Profiling state
        self.profiler: Optional[cProfile.Profile] = None
        self.is_profiling = False
        
        # Memory tracking
        if self.enable_memory:
            tracemalloc.start()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Dashboard data
        self.dashboard_data = {
            'start_time': datetime.now().isoformat(),
            'total_functions_profiled': 0,
            'total_execution_time': 0.0,
            'peak_memory_usage': 0,
            'bottlenecks_detected': 0
        }
        
        logger.info("🔍 **Performance Profiler initialized** "
                   f"(bộ phân tích hiệu năng đã khởi tạo): "
                   f"memory_tracking={'enabled' if enable_memory_tracking else 'disabled'}")
    
    def timing_decorator(self, track_memory: bool = True):
        """
        **Timing decorator** (decorator đo thời gian - bộ trang trí đo lường).
        
        Decorator to measure function execution time and memory.
        
        Args:
            track_memory: Whether to track memory for this function
            
        Returns:
            Decorated function
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                func_name = f"{func.__module__}.{func.__name__}"
                
                # Start timing
                start_time = time.perf_counter()
                start_cpu = time.process_time()
                
                # Memory snapshot before
                if self.enable_memory and track_memory:
                    snapshot_before = tracemalloc.take_snapshot()
                
                try:
                    # Execute function
                    result = func(*args, **kwargs)
                    
                    # Calculate timing
                    wall_time = time.perf_counter() - start_time
                    cpu_time = time.process_time() - start_cpu
                    
                    # Memory snapshot after
                    memory_usage = 0
                    if self.enable_memory and track_memory:
                        snapshot_after = tracemalloc.take_snapshot()
                        stats = snapshot_after.compare_to(snapshot_before, 'lineno')
                        
                        # Calculate memory change
                        for stat in stats:
                            memory_usage += stat.size_diff
                    
                    # Update metrics
                    with self.lock:
                        if func_name not in self.metrics:
                            self.metrics[func_name] = ProfileMetrics(func_name)
                        
                        metrics = self.metrics[func_name]
                        metrics.update(wall_time, abs(memory_usage))
                        metrics.cpu_time += cpu_time
                        metrics.wall_time += wall_time
                    
                    # Log if slow
                    if wall_time > 1.0:  # More than 1 second
                        logger.warning(f"⚠️ **Slow function** (hàm chậm): {func_name} "
                                     f"took {wall_time:.3f}s")
                    
                    return result
                    
                except Exception as e:
                    logger.error(f"❌ Error in {func_name}: {e}")
                    raise
            
            return wrapper
        return decorator
    
    def start_profiling(self):
        """
        **Start profiling** (bắt đầu phân tích).
        
        Start cProfile profiling session.
        """
        with self.lock:
            if self.is_profiling:
                logger.warning("⚠️ Profiling already started")
                return
            
            self.profiler = cProfile.Profile()
            self.profiler.enable()
            self.is_profiling = True
            
            logger.info("📊 **Profiling started** (bắt đầu phân tích)")
    
    def stop_profiling(self) -> Optional[str]:
        """
        **Stop profiling** (dừng phân tích).
        
        Stop profiling and return statistics.
        
        Returns:
            Profiling statistics as string
        """
        with self.lock:
            if not self.is_profiling or not self.profiler:
                logger.warning("⚠️ Profiling not started")
                return None
            
            self.profiler.disable()
            self.is_profiling = False
            
            # Generate statistics
            string_io = StringIO()
            stats = pstats.Stats(self.profiler, stream=string_io)
            stats.sort_stats('cumulative')
            stats.print_stats(20)  # Top 20 functions
            
            result = string_io.getvalue()
            
            logger.info("📊 **Profiling stopped** (dừng phân tích)")
            
            return result
    
    def detect_bottlenecks(self, threshold_ms: float = 100.0) -> List[BottleneckInfo]:
        """
        **Detect bottlenecks** (phát hiện điểm nghẽn).
        
        Analyze metrics to detect performance bottlenecks.
        
        Args:
            threshold_ms: Time threshold in milliseconds
            
        Returns:
            List of detected bottlenecks
        """
        bottlenecks = []
        
        with self.lock:
            for func_name, metrics in self.metrics.items():
                # Check for slow functions
                if metrics.average_time * 1000 > threshold_ms:
                    severity = self._calculate_severity(metrics.average_time * 1000)
                    
                    bottleneck = BottleneckInfo(
                        type='cpu',
                        severity=severity,
                        function_name=func_name,
                        description=f"Function takes {metrics.average_time*1000:.2f}ms on average",
                        impact_score=min(100, (metrics.average_time * 1000 / threshold_ms) * 50),
                        recommendations=[
                            "Consider optimizing algorithm complexity",
                            "Check for unnecessary loops or recursion",
                            "Consider caching results",
                            "Profile sub-functions to identify specific slow parts"
                        ],
                        metrics={
                            'average_time_ms': metrics.average_time * 1000,
                            'max_time_ms': metrics.max_time * 1000,
                            'total_calls': metrics.total_calls
                        }
                    )
                    bottlenecks.append(bottleneck)
                
                # Check for memory issues
                if self.enable_memory and metrics.memory_peak > 100 * 1024 * 1024:  # 100MB
                    severity = self._calculate_memory_severity(metrics.memory_peak)
                    
                    bottleneck = BottleneckInfo(
                        type='memory',
                        severity=severity,
                        function_name=func_name,
                        description=f"High memory usage: {metrics.memory_peak / (1024*1024):.2f}MB peak",
                        impact_score=min(100, (metrics.memory_peak / (100 * 1024 * 1024)) * 50),
                        recommendations=[
                            "Check for memory leaks",
                            "Consider using generators instead of lists",
                            "Free unused objects explicitly",
                            "Use memory-efficient data structures"
                        ],
                        metrics={
                            'peak_memory_mb': metrics.memory_peak / (1024*1024),
                            'total_calls': metrics.total_calls
                        }
                    )
                    bottlenecks.append(bottleneck)
                
                # Check for high frequency calls
                if metrics.total_calls > 1000 and metrics.average_time > 0.001:  # 1ms
                    bottleneck = BottleneckInfo(
                        type='cpu',
                        severity='medium',
                        function_name=func_name,
                        description=f"High frequency calls: {metrics.total_calls} calls",
                        impact_score=min(100, (metrics.total_calls / 1000) * 30),
                        recommendations=[
                            "Consider batching operations",
                            "Implement result caching",
                            "Reduce unnecessary function calls"
                        ],
                        metrics={
                            'total_calls': metrics.total_calls,
                            'total_time_s': metrics.total_time
                        }
                    )
                    bottlenecks.append(bottleneck)
        
        # Sort by impact score
        bottlenecks.sort(key=lambda b: b.impact_score, reverse=True)
        
        self.bottlenecks = bottlenecks
        self.dashboard_data['bottlenecks_detected'] = len(bottlenecks)
        
        logger.info(f"🔍 **Bottlenecks detected** (phát hiện điểm nghẽn): {len(bottlenecks)}")
        
        return bottlenecks
    
    def _calculate_severity(self, time_ms: float) -> str:
        """Calculate severity based on execution time"""
        if time_ms > 1000:  # > 1 second
            return 'critical'
        elif time_ms > 500:  # > 500ms
            return 'high'
        elif time_ms > 200:  # > 200ms
            return 'medium'
        else:
            return 'low'
    
    def _calculate_memory_severity(self, memory_bytes: int) -> str:
        """Calculate severity based on memory usage"""
        mb = memory_bytes / (1024 * 1024)
        if mb > 1000:  # > 1GB
            return 'critical'
        elif mb > 500:  # > 500MB
            return 'high'
        elif mb > 200:  # > 200MB
            return 'medium'
        else:
            return 'low'
    
    def generate_dashboard(self) -> Dict[str, Any]:
        """
        **Generate dashboard** (tạo bảng điều khiển).
        
        Generate performance dashboard data.
        
        Returns:
            Dashboard data dictionary
        """
        with self.lock:
            # Update dashboard data
            self.dashboard_data['total_functions_profiled'] = len(self.metrics)
            self.dashboard_data['total_execution_time'] = sum(
                m.total_time for m in self.metrics.values()
            )
            
            if self.enable_memory:
                self.dashboard_data['peak_memory_usage'] = max(
                    (m.memory_peak for m in self.metrics.values()),
                    default=0
                )
            
            # Top slow functions
            top_slow = sorted(
                self.metrics.items(),
                key=lambda x: x[1].average_time,
                reverse=True
            )[:10]
            
            # Top memory consumers
            top_memory = []
            if self.enable_memory:
                top_memory = sorted(
                    self.metrics.items(),
                    key=lambda x: x[1].memory_peak,
                    reverse=True
                )[:10]
            
            # Build dashboard
            dashboard = {
                'summary': self.dashboard_data,
                'top_slow_functions': [
                    {
                        'name': name,
                        'average_time_ms': metrics.average_time * 1000,
                        'total_calls': metrics.total_calls,
                        'total_time_s': metrics.total_time
                    }
                    for name, metrics in top_slow
                ],
                'top_memory_consumers': [
                    {
                        'name': name,
                        'peak_memory_mb': metrics.memory_peak / (1024*1024),
                        'total_calls': metrics.total_calls
                    }
                    for name, metrics in top_memory
                ],
                'bottlenecks': [
                    {
                        'type': b.type,
                        'severity': b.severity,
                        'function': b.function_name,
                        'description': b.description,
                        'impact': b.impact_score,
                        'recommendations': b.recommendations
                    }
                    for b in self.bottlenecks
                ],
                'system_info': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'timestamp': datetime.now().isoformat()
                }
            }
        
        logger.info("📊 **Dashboard generated** (bảng điều khiển đã tạo)")
        
        return dashboard
    
    def export_report(self, filename: str = None) -> str:
        """
        **Export report** (xuất báo cáo).
        
        Export performance report to file.
        
        Args:
            filename: Output filename (auto-generated if None)
            
        Returns:
            Path to exported report
        """
        if filename is None:
            filename = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        dashboard = self.generate_dashboard()
        
        # Add detailed metrics
        detailed_metrics = {}
        with self.lock:
            for name, metrics in self.metrics.items():
                detailed_metrics[name] = {
                    'total_calls': metrics.total_calls,
                    'total_time': metrics.total_time,
                    'average_time': metrics.average_time,
                    'min_time': metrics.min_time,
                    'max_time': metrics.max_time,
                    'cpu_time': metrics.cpu_time,
                    'wall_time': metrics.wall_time,
                    'memory_peak': metrics.memory_peak,
                    'time_history': list(metrics.time_history),
                    'memory_history': list(metrics.memory_history)
                }
        
        report = {
            'dashboard': dashboard,
            'detailed_metrics': detailed_metrics,
            'export_time': datetime.now().isoformat()
        }
        
        # Write to file
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"📄 **Report exported** (báo cáo đã xuất): {filename}")
        
        return filename
    
    def reset(self):
        """
        **Reset profiler** (đặt lại bộ phân tích).
        
        Clear all metrics and reset profiler.
        """
        with self.lock:
            self.metrics.clear()
            self.bottlenecks.clear()
            self.dashboard_data = {
                'start_time': datetime.now().isoformat(),
                'total_functions_profiled': 0,
                'total_execution_time': 0.0,
                'peak_memory_usage': 0,
                'bottlenecks_detected': 0
            }
            
            if self.is_profiling:
                self.stop_profiling()
            
            logger.info("🔄 **Profiler reset** (bộ phân tích đã đặt lại)")


# Global profiler instance
_global_profiler: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """
    **Get global profiler** (lấy bộ phân tích toàn cục).
    
    Get or create global profiler instance.
    
    Returns:
        Global profiler instance
    """
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler


# Convenience decorator
def profile_function(track_memory: bool = True):
    """
    **Profile function** (phân tích hàm).
    
    Convenience decorator using global profiler.
    
    Args:
        track_memory: Whether to track memory
        
    Returns:
        Decorated function
    """
    profiler = get_profiler()
    return profiler.timing_decorator(track_memory)


# Test function
def test_performance_profiler():
    """
    **Test performance profiler** (kiểm tra bộ phân tích hiệu năng).
    """
    import random
    
    profiler = PerformanceProfiler()
    
    # Test function 1: CPU intensive
    @profiler.timing_decorator()
    def cpu_intensive_task(n: int = 1000000):
        """Simulate CPU intensive task"""
        result = 0
        for i in range(n):
            result += i ** 2
        return result
    
    # Test function 2: Memory intensive
    @profiler.timing_decorator()
    def memory_intensive_task(size: int = 1000000):
        """Simulate memory intensive task"""
        data = [random.random() for _ in range(size)]
        return sum(data)
    
    # Test function 3: Matrix operations (without numpy)
    @profiler.timing_decorator()
    def matrix_task(size: int = 100):
        """Simulate matrix operations without numpy"""
        # Create random matrix
        matrix = [[random.random() for _ in range(size)] for _ in range(size)]
        
        # Simple matrix multiplication (smaller size for performance)
        result = [[0 for _ in range(size)] for _ in range(size)]
        for i in range(size):
            for j in range(size):
                for k in range(size):
                    result[i][j] += matrix[i][k] * matrix[k][j]
        
        # Return average
        total = sum(sum(row) for row in result)
        return total / (size * size)
    
    # Start profiling
    profiler.start_profiling()
    
    # Run test functions multiple times
    logger.info("🧪 **Running test functions** (chạy hàm kiểm tra)...")
    
    for i in range(5):
        cpu_intensive_task()
        memory_intensive_task()
        matrix_task()
    
    # Stop profiling
    profile_stats = profiler.stop_profiling()
    
    # Detect bottlenecks
    bottlenecks = profiler.detect_bottlenecks(threshold_ms=10.0)
    
    # Generate dashboard
    dashboard = profiler.generate_dashboard()
    
    # Export report
    report_file = profiler.export_report()
    
    # Display results
    logger.info("\n" + "="*60)
    logger.info("📊 **Test Results** (kết quả kiểm tra):")
    logger.info(f"Functions profiled: {dashboard['summary']['total_functions_profiled']}")
    logger.info(f"Total execution time: {dashboard['summary']['total_execution_time']:.3f}s")
    
    if dashboard['top_slow_functions']:
        logger.info("\n🐌 **Top Slow Functions** (hàm chậm nhất):")
        for func in dashboard['top_slow_functions']:
            logger.info(f"  {func['name']}: {func['average_time_ms']:.2f}ms "
                       f"({func['total_calls']} calls)")
    
    if bottlenecks:
        logger.info(f"\n⚠️ **Bottlenecks Found** (phát hiện điểm nghẽn): {len(bottlenecks)}")
        for b in bottlenecks[:3]:  # Top 3
            logger.info(f"  [{b.severity}] {b.function_name}: {b.description}")
    
    logger.info(f"\n📄 Report saved to: {report_file}")
    logger.info("="*60)
    
    return dashboard


if __name__ == "__main__":
    # Run test if executed directly
    test_performance_profiler()
