"""
Performance Profiler Module
===========================
Comprehensive performance profiling and analysis for GPU optimization.
Module phân tích hiệu năng toàn diện cho tối ưu GPU.

Implements:
- **Sampling** (lấy mẫu – thu thập định kỳ)
- **Event Markers** (đánh dấu sự kiện – theo dõi mốc thời gian)
- **Statistical Analysis** (phân tích thống kê – tính toán metrics)
- **Export Formats** (định dạng xuất – JSON/CSV/Prometheus)
"""

import logging
import time
import threading
import json
import csv
import uuid
from typing import Dict, List, Optional, Any, Union, IO, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from collections import deque, defaultdict
from pathlib import Path
from contextlib import contextmanager
from abc import ABC, abstractmethod
import statistics
import io

logger = logging.getLogger(__name__)


# === Exceptions ===

class ProfilingError(Exception):
    """Base profiling exception"""
    pass


class SamplerError(ProfilingError):
    """Sampler-related errors"""
    pass


class ExporterError(ProfilingError):
    """Export-related errors"""
    pass


# === Data Structures ===

@dataclass
class Sample:
    """
    Performance sample data point.
    Điểm dữ liệu mẫu hiệu năng.
    
    Attributes:
        timestamp: Sample timestamp
        pid: Process ID
        device_id: GPU device ID
        gpu_util: GPU utilization (%)
        gpu_memory_used: GPU memory used (MB)
        gpu_memory_total: GPU memory total (MB)
        gpu_power: GPU power draw (W)
        gpu_temp: GPU temperature (C)
        cpu_util: CPU utilization for PID (%)
        metadata: Additional metadata
    """
    timestamp: datetime
    pid: int
    device_id: int
    gpu_util: float = 0.0
    gpu_memory_used: float = 0.0
    gpu_memory_total: float = 0.0
    gpu_power: float = 0.0
    gpu_temp: float = 0.0
    cpu_util: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PhaseEvent:
    """
    Phase/event marker for timeline.
    Đánh dấu phase/sự kiện cho timeline.
    
    Attributes:
        name: Event name
        timestamp: Event timestamp
        phase: Event phase (begin/end/instant)
        metadata: Event metadata
    """
    name: str
    timestamp: datetime
    phase: str = "instant"  # begin, end, instant
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SummaryStats:
    """
    Statistical summary of profiling data.
    Tóm tắt thống kê dữ liệu profiling.
    
    Attributes:
        metric_name: Name of metric
        count: Number of samples
        mean: Average value
        min: Minimum value
        max: Maximum value
        p50: 50th percentile
        p95: 95th percentile
        p99: 99th percentile
        std_dev: Standard deviation
    """
    metric_name: str
    count: int = 0
    mean: float = 0.0
    min: float = float('inf')
    max: float = float('-inf')
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    std_dev: float = 0.0
    
    @classmethod
    def from_values(cls, name: str, values: List[float]) -> 'SummaryStats':
        """Create summary from values list"""
        if not values:
            return cls(metric_name=name)
        
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        
        return cls(
            metric_name=name,
            count=n,
            mean=statistics.mean(values),
            min=min(values),
            max=max(values),
            p50=sorted_vals[int(n * 0.50)],
            p95=sorted_vals[int(n * 0.95)] if n > 1 else sorted_vals[0],
            p99=sorted_vals[int(n * 0.99)] if n > 1 else sorted_vals[0],
            std_dev=statistics.stdev(values) if n > 1 else 0.0
        )


# === Exporters ===

class Exporter(ABC):
    """
    **Base Exporter Interface** (giao diện xuất cơ sở).
    """
    
    @abstractmethod
    def export(self, data: Dict[str, Any], sink: Union[IO, Path, Callable]) -> bool:
        """Export data to sink"""
        pass


class JSONExporter(Exporter):
    """
    **JSON Exporter** (xuất JSON – định dạng cấu trúc).
    """
    
    def export(self, data: Dict[str, Any], sink: Union[IO, Path, Callable]) -> bool:
        """
        Export data as JSON.
        Xuất dữ liệu dạng JSON.
        
        Args:
            data: Data to export
            sink: Output destination
            
        Returns:
            True if successful
        """
        try:
            # Convert datetime objects
            def serialize(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                if hasattr(obj, '__dict__'):
                    return obj.__dict__
                return str(obj)
            
            json_data = json.dumps(data, default=serialize, indent=2)
            
            if isinstance(sink, Path):
                sink.write_text(json_data)
                logger.info(f"✅ Exported JSON to {sink}")
            elif hasattr(sink, 'write'):
                sink.write(json_data)
                logger.info("✅ Exported JSON to stream")
            elif callable(sink):
                sink(json_data)
                logger.info("✅ Exported JSON to callback")
            else:
                raise ExporterError(f"Invalid sink type: {type(sink)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ JSON export failed: {e}")
            raise ExporterError(f"JSON export failed: {e}")


class CSVExporter(Exporter):
    """
    **CSV Exporter** (xuất CSV – bảng dữ liệu).
    """
    
    def export(self, data: Dict[str, Any], sink: Union[IO, Path, Callable]) -> bool:
        """
        Export data as CSV.
        Xuất dữ liệu dạng CSV.
        
        Args:
            data: Data to export (expects 'samples' key)
            sink: Output destination
            
        Returns:
            True if successful
        """
        try:
            samples = data.get('samples', [])
            if not samples:
                logger.warning("⚠️ No samples to export")
                return False
            
            # Convert to list of dicts
            rows = []
            for sample in samples:
                if isinstance(sample, Sample):
                    row = asdict(sample)
                    row['timestamp'] = row['timestamp'].isoformat()
                else:
                    row = sample
                rows.append(row)
            
            # Write CSV
            if isinstance(sink, Path):
                with open(sink, 'w', newline='') as f:
                    if rows:
                        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                        writer.writeheader()
                        writer.writerows(rows)
                logger.info(f"✅ Exported CSV to {sink}")
                
            elif hasattr(sink, 'write'):
                if rows:
                    output = io.StringIO()
                    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)
                    sink.write(output.getvalue())
                logger.info("✅ Exported CSV to stream")
                
            elif callable(sink):
                sink(rows)
                logger.info("✅ Exported CSV to callback")
                
            else:
                raise ExporterError(f"Invalid sink type: {type(sink)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ CSV export failed: {e}")
            raise ExporterError(f"CSV export failed: {e}")


# === Profiler Session ===

class ProfilerSession:
    """
    **Profiler Session** (phiên profiling) - Context manager for profiling.
    
    Manages lifecycle of a profiling session with automatic cleanup.
    """
    
    def __init__(self, profiler: 'PerformanceProfiler', 
                 pid: int, device_id: int, **options):
        """
        Initialize profiler session.
        
        Args:
            profiler: Parent profiler instance
            pid: Process ID to profile
            device_id: GPU device ID
            **options: Session options
        """
        self.profiler = profiler
        self.session_id = str(uuid.uuid4())[:8]
        self.pid = pid
        self.device_id = device_id
        self.options = options
        
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.samples: List[Sample] = []
        self.events: List[PhaseEvent] = []
        
        logger.info(f"✅ Created session {self.session_id} cho PID {pid}, device {device_id}")
    
    def __enter__(self):
        """Start profiling session"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop profiling session"""
        self.stop()
    
    def start(self):
        """
        Start the profiling session.
        Bắt đầu phiên profiling.
        """
        self.start_time = datetime.now()
        self.profiler._active_sessions[self.session_id] = self
        
        # Record start event
        self.record_event("session_start", phase="begin")
        
        logger.info(f"▶️ Started session {self.session_id}")
    
    def stop(self):
        """
        Stop the profiling session.
        Dừng phiên profiling.
        """
        if self.session_id in self.profiler._active_sessions:
            del self.profiler._active_sessions[self.session_id]
        
        self.end_time = datetime.now()
        
        # Record end event
        self.record_event("session_end", phase="end")
        
        duration = (self.end_time - self.start_time).total_seconds()
        logger.info(f"⏹️ Stopped session {self.session_id}, duration: {duration:.2f}s")
    
    def record_sample(self, sample: Sample):
        """Record a performance sample"""
        self.samples.append(sample)
    
    def record_event(self, name: str, phase: str = "instant", **metadata):
        """
        Record an event marker.
        Ghi nhận đánh dấu sự kiện.
        
        Args:
            name: Event name
            phase: Event phase (begin/end/instant)
            **metadata: Event metadata
        """
        event = PhaseEvent(
            name=name,
            timestamp=datetime.now(),
            phase=phase,
            metadata=metadata
        )
        self.events.append(event)
        
        logger.debug(f"📍 Event {name} ({phase}) in session {self.session_id}")
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get session summary statistics.
        Lấy thống kê tóm tắt phiên.
        
        Returns:
            Summary dictionary
        """
        if not self.samples:
            return {
                'session_id': self.session_id,
                'pid': self.pid,
                'device_id': self.device_id,
                'status': 'no_samples'
            }
        
        # Calculate statistics for each metric
        gpu_utils = [s.gpu_util for s in self.samples]
        mem_useds = [s.gpu_memory_used for s in self.samples]
        powers = [s.gpu_power for s in self.samples]
        temps = [s.gpu_temp for s in self.samples]
        cpu_utils = [s.cpu_util for s in self.samples]
        
        return {
            'session_id': self.session_id,
            'pid': self.pid,
            'device_id': self.device_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': (self.end_time - self.start_time).total_seconds() 
                              if self.end_time and self.start_time else 0,
            'sample_count': len(self.samples),
            'event_count': len(self.events),
            'stats': {
                'gpu_util': SummaryStats.from_values('gpu_util', gpu_utils),
                'gpu_memory': SummaryStats.from_values('gpu_memory_used', mem_useds),
                'gpu_power': SummaryStats.from_values('gpu_power', powers),
                'gpu_temp': SummaryStats.from_values('gpu_temp', temps),
                'cpu_util': SummaryStats.from_values('cpu_util', cpu_utils)
            }
        }


# === Main Profiler ===

class PerformanceProfiler:
    """
    **Performance Profiler** (bộ phân tích hiệu năng) - Main profiling manager.
    
    Features:
    - **Sampling** (lấy mẫu định kỳ)
    - **Event Tracking** (theo dõi sự kiện)
    - **Statistical Analysis** (phân tích thống kê)
    - **Multiple Export Formats** (nhiều định dạng xuất)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize performance profiler.
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self._active_sessions: Dict[str, ProfilerSession] = {}
        self._exporters: Dict[str, Exporter] = {
            'json': JSONExporter(),
            'csv': CSVExporter()
        }
        
        # Sampling configuration
        self.sampling_interval_ms = self.config.get('sampling_interval_ms', 1000)
        self.max_buffer_size = self.config.get('max_buffer_size', 10000)
        self.overhead_target = self.config.get('overhead_percent', 5.0)
        
        # Sampler thread
        self._sampler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False
        
        # Sample buffer
        self._sample_buffer = deque(maxlen=self.max_buffer_size)
        self._buffer_lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'sessions_created': 0,
            'samples_collected': 0,
            'events_recorded': 0,
            'exports_completed': 0,
            'sampling_errors': 0
        }
        
        # Start sampler if enabled
        if self.config.get('auto_start', True):
            self._start_sampler()
        
        logger.info("✅ Performance Profiler initialized")
    
    def start_session(self, pid: int, device_id: int, **options) -> ProfilerSession:
        """
        Start a new profiling session.
        Bắt đầu phiên profiling mới.
        
        Args:
            pid: Process ID to profile
            device_id: GPU device ID
            **options: Session options
            
        Returns:
            ProfilerSession context manager
        """
        session = ProfilerSession(self, pid, device_id, **options)
        self.stats['sessions_created'] += 1
        
        return session
    
    def record_event(self, name: str, **metadata):
        """
        Record global event marker.
        Ghi nhận đánh dấu sự kiện toàn cục.
        
        Args:
            name: Event name
            **metadata: Event metadata
        """
        # Record in all active sessions
        for session in self._active_sessions.values():
            session.record_event(name, **metadata)
        
        self.stats['events_recorded'] += 1
        
        logger.debug(f"📍 Global event: {name}")
    
    def _collect_sample(self, session: ProfilerSession) -> Optional[Sample]:
        """
        Collect a performance sample.
        Thu thập mẫu hiệu năng.
        
        Args:
            session: Profiling session
            
        Returns:
            Sample if successful, None otherwise
        """
        try:
            # Simulate collecting metrics (would integrate with monitoring module)
            # Trong thực tế sẽ gọi API từ monitoring module
            
            import random  # For simulation
            
            sample = Sample(
                timestamp=datetime.now(),
                pid=session.pid,
                device_id=session.device_id,
                gpu_util=random.uniform(0, 100),
                gpu_memory_used=random.uniform(1000, 8000),
                gpu_memory_total=8192,
                gpu_power=random.uniform(50, 250),
                gpu_temp=random.uniform(40, 85),
                cpu_util=random.uniform(0, 100)
            )
            
            return sample
            
        except Exception as e:
            logger.error(f"❌ Failed to collect sample: {e}")
            self.stats['sampling_errors'] += 1
            return None
    
    def _sampler_loop(self):
        """
        Sampler thread main loop.
        Vòng lặp chính của luồng sampler.
        """
        logger.info("🔄 Sampler thread started")
        
        while not self._stop_event.is_set():
            start_time = time.time()
            
            # Collect samples for all active sessions
            for session in list(self._active_sessions.values()):
                sample = self._collect_sample(session)
                
                if sample:
                    session.record_sample(sample)
                    
                    with self._buffer_lock:
                        self._sample_buffer.append(sample)
                    
                    self.stats['samples_collected'] += 1
            
            # Sleep for remaining interval
            elapsed = (time.time() - start_time) * 1000  # ms
            sleep_time = max(0, self.sampling_interval_ms - elapsed) / 1000
            
            if sleep_time > 0:
                self._stop_event.wait(sleep_time)
        
        logger.info("🛑 Sampler thread stopped")
    
    def _start_sampler(self):
        """
        Start sampler thread.
        Bắt đầu luồng sampler.
        """
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        
        self._sampler_thread = threading.Thread(
            target=self._sampler_loop,
            daemon=True,
            name="ProfilerSampler"
        )
        self._sampler_thread.start()
        
        logger.info("✅ Started sampler thread")
    
    def _stop_sampler(self):
        """
        Stop sampler thread.
        Dừng luồng sampler.
        """
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._sampler_thread:
            self._sampler_thread.join(timeout=5)
            self._sampler_thread = None
        
        logger.info("✅ Stopped sampler thread")
    
    def export(self, format: str, sink: Union[IO, Path, Callable],
              session_id: Optional[str] = None) -> bool:
        """
        Export profiling data.
        Xuất dữ liệu profiling.
        
        Args:
            format: Export format (json/csv)
            sink: Output destination
            session_id: Specific session to export (None for all)
            
        Returns:
            True if successful
        """
        try:
            exporter = self._exporters.get(format)
            if not exporter:
                raise ExporterError(f"Unknown format: {format}")
            
            # Prepare export data
            if session_id:
                if session_id not in self._active_sessions:
                    raise ExporterError(f"Session {session_id} not found")
                
                session = self._active_sessions[session_id]
                data = {
                    'session': session.get_summary(),
                    'samples': session.samples,
                    'events': session.events
                }
            else:
                # Export all data
                data = {
                    'sessions': [s.get_summary() for s in self._active_sessions.values()],
                    'samples': list(self._sample_buffer),
                    'stats': self.stats.copy()
                }
            
            # Export
            result = exporter.export(data, sink)
            
            if result:
                self.stats['exports_completed'] += 1
                logger.info(f"✅ Exported {format} successfully")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Export failed: {e}")
            raise ExporterError(f"Export failed: {e}")
    
    def close(self):
        """
        Close profiler and cleanup resources.
        Đóng profiler và dọn dẹp tài nguyên.
        """
        # Stop all sessions
        for session_id in list(self._active_sessions.keys()):
            session = self._active_sessions[session_id]
            session.stop()
        
        # Stop sampler
        self._stop_sampler()
        
        # Clear buffers
        self._sample_buffer.clear()
        
        logger.info("✅ Performance Profiler closed")
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get profiler status.
        Lấy trạng thái profiler.
        
        Returns:
            Status dictionary
        """
        return {
            'running': self._running,
            'active_sessions': len(self._active_sessions),
            'buffer_size': len(self._sample_buffer),
            'max_buffer_size': self.max_buffer_size,
            'sampling_interval_ms': self.sampling_interval_ms,
            'stats': self.stats.copy()
        }
