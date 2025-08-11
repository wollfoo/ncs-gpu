#!/usr/bin/env python3
"""
GPU Optimization Lifecycle Manager
===================================
Manages the complete lifecycle of GPU optimization processes
Quản lý toàn bộ vòng đời của các tiến trình tối ưu hóa GPU

Core responsibilities:
- Component initialization and dependency management
- Process lifecycle tracking (start/stop/restart)
- Resource allocation and cleanup
- Health monitoring and recovery
- Graceful shutdown coordination
"""

import os
import time
import signal
import threading
import multiprocessing as mp
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
import logging
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Setup logger
logger = logging.getLogger(__name__)


class LifecycleState(Enum):
    """Component lifecycle states"""
    UNINITIALIZED = "uninitialized"  # Chưa khởi tạo
    INITIALIZING = "initializing"    # Đang khởi tạo
    READY = "ready"                  # Sẵn sàng
    RUNNING = "running"              # Đang chạy
    PAUSED = "paused"                # Tạm dừng
    STOPPING = "stopping"            # Đang dừng
    STOPPED = "stopped"              # Đã dừng
    ERROR = "error"                  # Lỗi
    RECOVERING = "recovering"        # Đang phục hồi


@dataclass
class ComponentHealth:
    """Health status of a component"""
    name: str
    state: LifecycleState
    last_heartbeat: float
    error_count: int = 0
    last_error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def is_healthy(self) -> bool:
        """Check if component is healthy"""
        return (
            self.state in [LifecycleState.READY, LifecycleState.RUNNING] and
            time.time() - self.last_heartbeat < 60  # 60s timeout
        )


@dataclass
class ProcessInfo:
    """Process information tracking"""
    pid: int
    gpu_index: int
    name: str
    start_time: float
    state: LifecycleState
    optimization_count: int = 0
    last_optimization: Optional[float] = None
    resources: Dict[str, Any] = field(default_factory=dict)


class LifecycleManager:
    """
    Central lifecycle management for GPU optimization system
    Quản lý vòng đời trung tâm cho hệ thống tối ưu hóa GPU
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize lifecycle manager
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._get_default_config()
        
        # Component registry
        self.components: Dict[str, ComponentHealth] = {}
        self.component_locks = defaultdict(threading.Lock)
        
        # Process tracking
        self.processes: Dict[int, ProcessInfo] = {}
        self.process_lock = threading.Lock()
        
        # Lifecycle hooks
        self.startup_hooks: List[Callable] = []
        self.shutdown_hooks: List[Callable] = []
        self.error_hooks: List[Callable] = []
        
        # State management
        self.state = LifecycleState.UNINITIALIZED
        self.start_time = None
        self.stop_event = threading.Event()
        
        # Resource pools
        self.thread_pool = None
        self.max_workers = self.config.get('max_workers', 4)
        
        # Health monitoring
        self.health_check_interval = self.config.get('health_check_interval', 30)
        self.health_thread = None
        
        # Signal handling
        self._setup_signal_handlers()
        
        logger.info("🔄 Lifecycle Manager created")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'max_workers': 4,
            'health_check_interval': 30,
            'heartbeat_timeout': 60,
            'max_retries': 3,
            'recovery_delay': 5,
            'enable_auto_recovery': True,
            'graceful_shutdown_timeout': 30
        }
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            logger.info(f"⚠️ Received signal {signum}, initiating shutdown...")
            self.shutdown()
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    # ============ Component Management ============
    
    def register_component(self, name: str, 
                          initializer: Optional[Callable] = None,
                          shutdown_handler: Optional[Callable] = None) -> bool:
        """
        Register a component with lifecycle manager
        
        Args:
            name: Component name
            initializer: Initialization function
            shutdown_handler: Shutdown function
            
        Returns:
            True if registered successfully
        """
        with self.component_locks[name]:
            if name in self.components:
                logger.warning(f"Component {name} already registered")
                return False
            
            self.components[name] = ComponentHealth(
                name=name,
                state=LifecycleState.UNINITIALIZED,
                last_heartbeat=time.time()
            )
            
            # Store handlers
            if initializer:
                self.startup_hooks.append((name, initializer))
            if shutdown_handler:
                self.shutdown_hooks.append((name, shutdown_handler))
            
            logger.info(f"✅ Component '{name}' registered")
            return True
    
    def update_component_state(self, name: str, state: LifecycleState,
                              error: Optional[str] = None) -> bool:
        """Update component state"""
        with self.component_locks[name]:
            if name not in self.components:
                logger.error(f"Component {name} not registered")
                return False
            
            component = self.components[name]
            component.state = state
            component.last_heartbeat = time.time()
            
            if error:
                component.error_count += 1
                component.last_error = error
                logger.error(f"❌ Component {name} error: {error}")
                
                # Trigger recovery if needed
                if self.config['enable_auto_recovery']:
                    self._schedule_recovery(name)
            
            return True
    
    def _schedule_recovery(self, component_name: str):
        """Schedule component recovery"""
        if self.thread_pool:
            self.thread_pool.submit(self._recover_component, component_name)
    
    def _recover_component(self, name: str):
        """Attempt to recover a failed component"""
        component = self.components.get(name)
        if not component:
            return
        
        logger.info(f"🔄 Attempting recovery for component '{name}'...")
        
        with self.component_locks[name]:
            component.state = LifecycleState.RECOVERING
        
        # Wait before retry
        time.sleep(self.config['recovery_delay'])
        
        # Find and execute initializer
        for comp_name, initializer in self.startup_hooks:
            if comp_name == name:
                try:
                    initializer()
                    self.update_component_state(name, LifecycleState.READY)
                    logger.info(f"✅ Component '{name}' recovered")
                    return
                except Exception as e:
                    logger.error(f"Recovery failed for '{name}': {e}")
                    self.update_component_state(name, LifecycleState.ERROR, str(e))
    
    # ============ Process Lifecycle ============
    
    def track_process(self, pid: int, gpu_index: int = 0, 
                     name: Optional[str] = None) -> bool:
        """
        Start tracking a process
        
        Args:
            pid: Process ID
            gpu_index: GPU index for optimization
            name: Process name
            
        Returns:
            True if tracking started
        """
        with self.process_lock:
            if pid in self.processes:
                logger.debug(f"Process {pid} already tracked")
                return False
            
            self.processes[pid] = ProcessInfo(
                pid=pid,
                gpu_index=gpu_index,
                name=name or f"process_{pid}",
                start_time=time.time(),
                state=LifecycleState.READY
            )
            
            logger.info(f"📊 Tracking process {pid} on GPU {gpu_index}")
            return True
    
    def untrack_process(self, pid: int) -> bool:
        """Stop tracking a process"""
        with self.process_lock:
            if pid not in self.processes:
                return False
            
            process = self.processes[pid]
            process.state = LifecycleState.STOPPED
            
            # Cleanup resources
            self._cleanup_process_resources(pid)
            
            del self.processes[pid]
            logger.info(f"🛑 Stopped tracking process {pid}")
            return True
    
    def _cleanup_process_resources(self, pid: int):
        """Cleanup resources for a process"""
        process = self.processes.get(pid)
        if not process:
            return
        
        # Release GPU resources
        if process.resources.get('gpu_allocated'):
            logger.debug(f"Releasing GPU resources for process {pid}")
            # Actual GPU cleanup would go here
        
        # Clear any pending optimizations
        process.resources.clear()
    
    def update_process_metrics(self, pid: int, metrics: Dict[str, Any]):
        """Update process optimization metrics"""
        with self.process_lock:
            if pid not in self.processes:
                return
            
            process = self.processes[pid]
            process.optimization_count += 1
            process.last_optimization = time.time()
            process.resources.update(metrics)
    
    # ============ Lifecycle Control ============
    
    def initialize(self) -> bool:
        """
        Initialize all components and start lifecycle
        
        Returns:
            True if initialization successful
        """
        if self.state != LifecycleState.UNINITIALIZED:
            logger.warning("Lifecycle already initialized")
            return False
        
        logger.info("🚀 Initializing Lifecycle Manager...")
        self.state = LifecycleState.INITIALIZING
        self.start_time = time.time()
        
        try:
            # Create thread pool
            self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
            
            # Initialize components
            success_count = 0
            for name, initializer in self.startup_hooks:
                try:
                    logger.info(f"Initializing component '{name}'...")
                    initializer()
                    self.update_component_state(name, LifecycleState.READY)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to initialize '{name}': {e}")
                    self.update_component_state(name, LifecycleState.ERROR, str(e))
            
            # Start health monitoring
            if self.config.get('enable_health_check', True):
                self._start_health_monitoring()
            
            self.state = LifecycleState.READY
            logger.info(f"✅ Lifecycle initialized ({success_count}/{len(self.startup_hooks)} components)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            self.state = LifecycleState.ERROR
            return False
    
    def start(self) -> bool:
        """Start lifecycle operations"""
        if self.state != LifecycleState.READY:
            logger.error(f"Cannot start from state {self.state}")
            return False
        
        self.state = LifecycleState.RUNNING
        self.stop_event.clear()
        
        logger.info("▶️ Lifecycle Manager started")
        return True
    
    def pause(self) -> bool:
        """Pause lifecycle operations"""
        if self.state != LifecycleState.RUNNING:
            return False
        
        self.state = LifecycleState.PAUSED
        logger.info("⏸️ Lifecycle Manager paused")
        return True
    
    def resume(self) -> bool:
        """Resume lifecycle operations"""
        if self.state != LifecycleState.PAUSED:
            return False
        
        self.state = LifecycleState.RUNNING
        logger.info("▶️ Lifecycle Manager resumed")
        return True
    
    def shutdown(self, timeout: Optional[float] = None) -> bool:
        """
        Graceful shutdown of all components
        
        Args:
            timeout: Maximum time to wait for shutdown
            
        Returns:
            True if shutdown successful
        """
        if self.state == LifecycleState.STOPPED:
            return True
        
        logger.info("🛑 Initiating graceful shutdown...")
        self.state = LifecycleState.STOPPING
        self.stop_event.set()
        
        timeout = timeout or self.config['graceful_shutdown_timeout']
        shutdown_start = time.time()
        
        try:
            # Stop health monitoring
            if self.health_thread and self.health_thread.is_alive():
                self.health_thread.join(timeout=5)
            
            # Execute shutdown hooks in reverse order
            for name, handler in reversed(self.shutdown_hooks):
                remaining = timeout - (time.time() - shutdown_start)
                if remaining <= 0:
                    logger.warning("Shutdown timeout reached")
                    break
                
                try:
                    logger.info(f"Shutting down component '{name}'...")
                    handler()
                    self.update_component_state(name, LifecycleState.STOPPED)
                except Exception as e:
                    logger.error(f"Error shutting down '{name}': {e}")
            
            # Cleanup processes
            with self.process_lock:
                for pid in list(self.processes.keys()):
                    self.untrack_process(pid)
            
            # Shutdown thread pool
            if self.thread_pool:
                self.thread_pool.shutdown(wait=True, timeout=remaining)
            
            self.state = LifecycleState.STOPPED
            
            # Log final statistics
            self._log_statistics()
            
            logger.info("✅ Lifecycle Manager shutdown complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")
            self.state = LifecycleState.ERROR
            return False
    
    # ============ Health Monitoring ============
    
    def _start_health_monitoring(self):
        """Start health monitoring thread"""
        self.health_thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True
        )
        self.health_thread.start()
        logger.info("🏥 Health monitoring started")
    
    def _health_monitor_loop(self):
        """Health monitoring loop"""
        while not self.stop_event.is_set():
            try:
                self._check_component_health()
                self._check_process_health()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            self.stop_event.wait(self.health_check_interval)
    
    def _check_component_health(self):
        """Check health of all components"""
        unhealthy = []
        
        for name, component in self.components.items():
            if not component.is_healthy:
                unhealthy.append(name)
                
                # Attempt recovery
                if (component.state == LifecycleState.ERROR and 
                    self.config['enable_auto_recovery']):
                    self._schedule_recovery(name)
        
        if unhealthy:
            logger.warning(f"Unhealthy components: {unhealthy}")
    
    def _check_process_health(self):
        """Check health of tracked processes"""
        with self.process_lock:
            stale_processes = []
            
            for pid, process in self.processes.items():
                # Check if process still exists
                try:
                    os.kill(pid, 0)
                except OSError:
                    stale_processes.append(pid)
                    continue
                
                # Check optimization staleness
                if process.last_optimization:
                    stale_time = time.time() - process.last_optimization
                    if stale_time > 300:  # 5 minutes
                        logger.warning(f"Process {pid} optimization stale ({stale_time:.1f}s)")
            
            # Clean up stale processes
            for pid in stale_processes:
                logger.info(f"Removing stale process {pid}")
                self.untrack_process(pid)
    
    # ============ Status and Metrics ============
    
    def get_status(self) -> Dict[str, Any]:
        """Get current lifecycle status"""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        return {
            'state': self.state.value,
            'uptime': uptime,
            'start_time': self.start_time,
            'components': {
                name: {
                    'state': comp.state.value,
                    'healthy': comp.is_healthy,
                    'error_count': comp.error_count,
                    'last_error': comp.last_error
                }
                for name, comp in self.components.items()
            },
            'processes': {
                pid: {
                    'name': proc.name,
                    'gpu_index': proc.gpu_index,
                    'state': proc.state.value,
                    'optimizations': proc.optimization_count,
                    'runtime': time.time() - proc.start_time
                }
                for pid, proc in self.processes.items()
            },
            'config': self.config
        }
    
    def _log_statistics(self):
        """Log final statistics"""
        if not self.start_time:
            return
        
        runtime = time.time() - self.start_time
        total_optimizations = sum(p.optimization_count for p in self.processes.values())
        
        stats = {
            'runtime': f"{runtime:.1f}s",
            'total_processes': len(self.processes),
            'total_optimizations': total_optimizations,
            'components': len(self.components),
            'errors': sum(c.error_count for c in self.components.values())
        }
        
        logger.info(f"📊 Final statistics: {json.dumps(stats, indent=2)}")
    
    def export_metrics(self, filepath: Optional[str] = None) -> Dict[str, Any]:
        """Export lifecycle metrics"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'status': self.get_status(),
            'statistics': {
                'uptime': time.time() - self.start_time if self.start_time else 0,
                'total_processes': len(self.processes),
                'active_components': sum(1 for c in self.components.values() if c.is_healthy),
                'total_errors': sum(c.error_count for c in self.components.values())
            }
        }
        
        if filepath:
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w') as f:
                json.dump(metrics, f, indent=2)
            logger.info(f"📁 Metrics exported to {filepath}")
        
        return metrics


# ============ Module Testing ============

def test_lifecycle_manager():
    """Test lifecycle manager functionality"""
    import random
    
    logger.info("🧪 Testing Lifecycle Manager...")
    
    # Create manager
    manager = LifecycleManager()
    
    # Register mock components
    def init_orchestrator():
        logger.info("Orchestrator initialized")
        time.sleep(0.1)
    
    def shutdown_orchestrator():
        logger.info("Orchestrator shutdown")
    
    def init_monitor():
        logger.info("Monitor initialized")
        time.sleep(0.1)
    
    def shutdown_monitor():
        logger.info("Monitor shutdown")
    
    manager.register_component("orchestrator", init_orchestrator, shutdown_orchestrator)
    manager.register_component("monitor", init_monitor, shutdown_monitor)
    
    # Initialize
    assert manager.initialize(), "Initialization failed"
    
    # Start
    assert manager.start(), "Start failed"
    
    # Track processes
    for i in range(3):
        pid = random.randint(10000, 99999)
        manager.track_process(pid, gpu_index=i % 2)
        manager.update_process_metrics(pid, {'power': 250, 'temp': 65})
    
    # Get status
    status = manager.get_status()
    logger.info(f"Status: {json.dumps(status, indent=2)}")
    
    # Test pause/resume
    assert manager.pause(), "Pause failed"
    assert manager.resume(), "Resume failed"
    
    # Shutdown
    assert manager.shutdown(timeout=10), "Shutdown failed"
    
    logger.info("✅ All lifecycle tests passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_lifecycle_manager()
