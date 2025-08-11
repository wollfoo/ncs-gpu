"""
GPU Optimization Central Manager
=================================
Main entry point and coordination hub for GPU optimization
Điểm vào chính và trung tâm điều phối cho tối ưu hóa GPU
"""

import os
import json
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import threading

# Import orchestrator and other components
# Fix circular import - sửa import vòng tròn
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gpu_optimization.orchestrator.orchestrator import GPUOrchestrator

# Optional imports - these modules may not be ready yet
try:
    from monitoring.collectors.metrics_collector import GPUMetricsCollector
except ImportError:
    GPUMetricsCollector = None

try:
    from strategies.strategy_selector import StrategySelector
except ImportError:
    StrategySelector = None

try:
    from resource_control.resource_manager import ResourceManager
except ImportError:
    ResourceManager = None

# Setup logger
logger = logging.getLogger(__name__)


class GPUOptimizationManager:
    """
    **Central Manager** (trình quản lý trung tâm) for GPU Optimization.
    
    Main responsibilities:
    - System initialization (khởi tạo hệ thống)
    - Component coordination (điều phối thành phần)
    - API exposure (cung cấp API)
    - State management (quản lý trạng thái)
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        """Initialize manager (only runs once due to singleton)"""
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self.config = {}
            self.orchestrator = None
            self.metrics_collector = None
            self.strategy_selector = None
            self.resource_manager = None
            self.state = {
                'status': 'uninitialized',
                'start_time': None,
                'optimizations_count': 0,
                'active_processes': {}
            }
            logger.info("GPU Optimization Manager instance created")
    
    def initialize(self, config_path: Optional[str] = None) -> bool:
        """
        Initialize the GPU optimization system.
        Khởi tạo hệ thống tối ưu hóa GPU.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Success status
        """
        if self._initialized:
            logger.warning("Manager already initialized")
            return True
        
        try:
            logger.info("🚀 Initializing GPU Optimization Manager...")
            
            # Load configuration
            self.config = self._load_config(config_path)
            
            # Initialize orchestrator
            logger.info("Initializing orchestrator...")
            orchestrator_config = self.config.get('orchestrator', {})
            self.orchestrator = GPUOrchestrator(orchestrator_config)
            
            # Initialize metrics collector (placeholder)
            logger.info("Initializing metrics collector...")
            self.metrics_collector = self._init_metrics_collector()
            
            # Initialize strategy selector (placeholder)
            logger.info("Initializing strategy selector...")
            self.strategy_selector = self._init_strategy_selector()
            
            # Initialize resource manager (placeholder)
            logger.info("Initializing resource manager...")
            self.resource_manager = self._init_resource_manager()
            
            # Update state
            self.state['status'] = 'ready'
            self.state['start_time'] = datetime.now().isoformat()
            self._initialized = True
            
            logger.info("✅ GPU Optimization Manager initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize manager: {e}")
            self.state['status'] = 'error'
            self.state['error'] = str(e)
            return False
    
    def optimize(self, 
                 pid: int,
                 gpu_index: int = 0,
                 strategy: Optional[str] = None) -> Dict[str, Any]:
        """
        **Main API method** - Optimize GPU for a process.
        Phương thức API chính - Tối ưu GPU cho một tiến trình.
        
        Args:
            pid: Process ID
            gpu_index: GPU index (default 0)
            strategy: Optional strategy override
            
        Returns:
            Optimization results
        """
        if not self._initialized:
            return {
                'success': False,
                'error': 'Manager not initialized'
            }
        
        try:
            logger.info(f"📊 Starting optimization for PID {pid} on GPU {gpu_index}")
            
            # Track active process
            self.state['active_processes'][pid] = {
                'gpu_index': gpu_index,
                'start_time': datetime.now().isoformat(),
                'status': 'optimizing'
            }
            
            # Prepare process info
            process_info = {
                'pid': pid,
                'gpu_index': gpu_index
            }
            
            # Determine strategies
            strategies = None
            if strategy:
                strategies = [strategy]
            elif self.strategy_selector:
                # Use strategy selector if available
                strategies = self._select_strategies(pid, gpu_index)
            
            # Run optimization through orchestrator
            results = self.orchestrator.optimize(
                process_info=process_info,
                strategies=strategies
            )
            
            # Update tracking
            self.state['optimizations_count'] += 1
            self.state['active_processes'][pid]['status'] = 'completed'
            self.state['active_processes'][pid]['end_time'] = datetime.now().isoformat()
            
            # Log results
            if results['success']:
                logger.info(f"✅ Optimization successful for PID {pid}")
            else:
                logger.warning(f"⚠️ Optimization failed for PID {pid}: {results.get('errors')}")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Optimization error: {e}")
            
            # Update tracking
            if pid in self.state['active_processes']:
                self.state['active_processes'][pid]['status'] = 'error'
                self.state['active_processes'][pid]['error'] = str(e)
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get manager status.
        Lấy trạng thái trình quản lý.
        """
        status = {
            'initialized': self._initialized,
            'state': self.state,
            'config': {
                'loaded': bool(self.config),
                'source': self.config.get('source', 'unknown')
            }
        }
        
        # Add orchestrator status if available
        if self.orchestrator:
            status['orchestrator'] = self.orchestrator.get_status()
        
        return status
    
    def shutdown(self) -> bool:
        """
        Graceful shutdown of the system.
        Tắt hệ thống một cách ổn định.
        """
        try:
            logger.info("🛑 Shutting down GPU Optimization Manager...")
            
            # Shutdown orchestrator
            if self.orchestrator:
                self.orchestrator.shutdown()
            
            # Cleanup other components
            if self.resource_manager:
                # Placeholder for resource manager cleanup
                pass
            
            # Update state
            self.state['status'] = 'shutdown'
            self.state['shutdown_time'] = datetime.now().isoformat()
            self._initialized = False
            
            logger.info("✅ Manager shut down successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Shutdown error: {e}")
            return False
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """
        Load configuration from file or use defaults.
        Tải cấu hình từ file hoặc dùng mặc định.
        """
        config = {
            'source': 'default',
            'orchestrator': {
                'max_workers': 4,
                'strategy_timeout': 30.0,
                'power_params': {'target_power': 200},
                'clock_params': {'target_clock': 1500},
                'temperature_params': {'target_temp': 70}
            },
            'metrics': {
                'sampling_rate': 1.0,  # seconds
                'buffer_size': 100
            },
            'strategies': {
                'default': 'balanced',
                'available': ['aggressive', 'balanced', 'stealth', 'power', 'clock', 'temperature']
            }
        }
        
        if config_path and Path(config_path).exists():
            try:
                with open(config_path, 'r') as f:
                    if config_path.endswith('.json'):
                        loaded_config = json.load(f)
                    else:
                        # Assume YAML for other extensions
                        import yaml
                        loaded_config = yaml.safe_load(f)
                
                # Merge loaded config with defaults
                config.update(loaded_config)
                config['source'] = config_path
                logger.info(f"Loaded configuration from {config_path}")
                
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}, using defaults")
        
        return config
    
    def _init_metrics_collector(self):
        """Initialize metrics collector (placeholder)"""
        try:
            return GPUMetricsCollector(self.config.get('metrics', {}))
        except:
            # Return None if module not ready
            logger.debug("Metrics collector not available, using orchestrator's collector")
            return None
    
    def _init_strategy_selector(self):
        """Initialize strategy selector (placeholder)"""
        try:
            return StrategySelector(self.config.get('strategies', {}))
        except:
            # Return None if module not ready
            logger.debug("Strategy selector not available, using orchestrator's selector")
            return None
    
    def _init_resource_manager(self):
        """Initialize resource manager (placeholder)"""
        try:
            return ResourceManager(self.config.get('resources', {}))
        except:
            # Return None if module not ready
            logger.debug("Resource manager not available")
            return None
    
    def _select_strategies(self, pid: int, gpu_index: int) -> List[str]:
        """
        Select strategies for optimization.
        Lựa chọn chiến lược cho tối ưu.
        """
        if self.strategy_selector:
            # Use dedicated selector if available
            return self.strategy_selector.select(pid, gpu_index)
        else:
            # Fallback to default
            default = self.config.get('strategies', {}).get('default', 'balanced')
            return [default]


# Public API functions
def get_manager() -> GPUOptimizationManager:
    """
    Get the singleton manager instance.
    Lấy instance singleton của manager.
    """
    return GPUOptimizationManager()


def initialize(config_path: Optional[str] = None) -> bool:
    """
    Initialize GPU optimization system.
    Khởi tạo hệ thống tối ưu hóa GPU.
    """
    manager = get_manager()
    return manager.initialize(config_path)


def optimize(pid: int, gpu_index: int = 0, strategy: Optional[str] = None) -> Dict[str, Any]:
    """
    Optimize GPU for a process.
    Tối ưu GPU cho một tiến trình.
    """
    manager = get_manager()
    return manager.optimize(pid, gpu_index, strategy)


def get_status() -> Dict[str, Any]:
    """
    Get system status.
    Lấy trạng thái hệ thống.
    """
    manager = get_manager()
    return manager.get_status()


def shutdown() -> bool:
    """
    Shutdown the system.
    Tắt hệ thống.
    """
    manager = get_manager()
    return manager.shutdown()
