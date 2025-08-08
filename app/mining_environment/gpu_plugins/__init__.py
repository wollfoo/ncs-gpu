# -*- coding: utf-8 -*-
"""GPU Plugins Package - Quan ly tat ca GPU-related components

Tach biet hoan toan GPU logic khoi CPU plugins de:
- Tang tinh mo-dun va de maintain
- Cung cap interface chuan cho GPU operations
- Ho tro multiple GPU cloaking strategies
- Centralized GPU telemetry filtering
"""

from .core.interfaces import (
    IGPUPlugin,
    IGPUCloakService
    # IGPUTelemetryFilter,  # removed - telemetry functionality deprecated
    # IGPUHookManager  # removed - deprecated
)

from .core.registry import gpu_plugin_registry
from .core.manager import GPUPluginManager

# ✅ ENHANCED: Auto-registration system for GPU plugins
import logging
logger = logging.getLogger(__name__)

def _auto_register_plugins():
    """Tự động đăng ký tất cả GPU plugins có sẵn vào registry"""
    try:
        # Import và đăng ký thermal_spoofer
        try:
            from .cloaking.thermal_spoofer import ThermalSpoofer
            gpu_plugin_registry.register('thermal_spoofer', ThermalSpoofer)
            logger.info("✅ Auto-registered: thermal_spoofer")
        except ImportError as e:
            logger.warning(f"⚠️ Could not import thermal_spoofer: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to register thermal_spoofer: {e}")
        
        # Import và đăng ký nvml_interceptor
        try:
            from .cloaking.nvml_interceptor import NVMLInterceptor
            gpu_plugin_registry.register('nvml_interceptor', NVMLInterceptor)
            logger.info("✅ Auto-registered: nvml_interceptor")
        except ImportError as e:
            logger.warning(f"⚠️ Could not import nvml_interceptor: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to register nvml_interceptor: {e}")
        
        # Import và đăng ký time_based_manager
        try:
            from .cloaking.time_based_manager import GPUCloakingManager
            gpu_plugin_registry.register('time_based_manager', GPUCloakingManager)
            logger.info("✅ Auto-registered: time_based_manager")
        except ImportError as e:
            logger.warning(f"⚠️ Could not import time_based_manager: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to register time_based_manager: {e}")
        # nvml_proxy plugin đã bị loại bỏ hoàn toàn (decommissioned)
        
        # Báo cáo kết quả đăng ký
        registered_plugins = gpu_plugin_registry.list_plugins()
        logger.info(f"🎉 Auto-registration completed! Registered plugins: {registered_plugins}")
        logger.info(f"📊 Total registered GPU plugins: {len(registered_plugins)}")
        
        return len(registered_plugins)
        
    except Exception as e:
        logger.error(f"❌ Critical error in auto-registration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0

# ========== 🔧 LAYER 3: Plugin Registry Update ==========
# Manual registration removed - using auto-registration only to avoid duplicates

# ✅ AUTO-EXECUTION: Tự động đăng ký plugins khi import module
_registered_count = _auto_register_plugins()
logger.info(f"🚀 GPU Plugins module loaded with {_registered_count} plugins auto-registered")

# Version info
__version__ = "1.0.0"
__author__ = "GPU Plugins Team"

# Export main APIs
__all__ = [
    "IGPUPlugin",
    "IGPUCloakService",
    # "IGPUTelemetryFilter",  # removed - telemetry functionality deprecated
    # "IGPUHookManager",  # removed - deprecated
    "gpu_plugin_registry",
    "GPUPluginManager",
    "apply_gpu_strategies"
]

def create_gpu_manager(config_path=None, target_pid=None):
    """Convenience function de tao GPU Plugin Manager
    
    Args:
        config_path: Duong dan toi config file (optional)
        target_pid: PID động cho các plugin (optional)
        
    Returns:
        GPUPluginManager instance
    """
    return GPUPluginManager(config_path, target_pid)

def get_plugin_registry():
    """Lay global GPU plugin registry
    
    Returns:
        GPUPluginRegistry instance
    """
    return gpu_plugin_registry

def apply_gpu_strategies(pid, strategies=None):
    """
    ✅ ENHANCED: Áp dụng các GPU strategies với comprehensive error handling.
    Đảm bảo tất cả GPU plugins được kích hoạt và hoạt động đúng cách.
    
    Args:
        pid (int): Process ID cần áp dụng strategies
        strategies (list, optional): List các strategies để áp dụng. 
                                   None = áp dụng tất cả available strategies
    
    Returns:
        bool: True nếu thành công (ít nhất 1 plugin hoạt động), False nếu thất bại hoàn toàn
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # ✅ ENHANCED: Comprehensive success tracking
    plugin_status = {
        'loaded': [],
        'started': [],
        'cloaking_enabled': [],
        'failed': [],
        'total_success_count': 0
    }
    
    try:
        logger.info(f"🎯 [GPU Plugin Delegation] Starting comprehensive GPU strategies for PID={pid}")
        
        # ✅ STEP 1: GPU Manager Initialization with validation
        gpu_manager = None
        try:
            gpu_manager = create_gpu_manager(target_pid=pid)  # ✅ DYNAMIC PID: Truyền target_pid động
            logger.info("✅ [Step 1/5] GPU Plugin Manager initialized successfully")
        except Exception as e:
            logger.error(f"❌ [CRITICAL] GPU Manager initialization failed: {e}")
            return False
        
        # ✅ STEP 2: Individual plugin loading with detailed tracking
        available_plugins = [
            'thermal_spoofer',
            'nvml_interceptor', 
            'time_based_manager'
        ]
        
        logger.info(f"🔄 [Step 2/5] Loading {len(available_plugins)} GPU plugins...")
        
        for plugin_name in available_plugins:
            try:
                if gpu_manager.load_plugin(plugin_name):
                    plugin_status['loaded'].append(plugin_name)
                    logger.info(f"✅ Plugin loaded: {plugin_name}")
                else:
                    plugin_status['failed'].append({'plugin': plugin_name, 'stage': 'load', 'reason': 'load_returned_false'})
                    logger.warning(f"⚠️ Plugin load failed: {plugin_name} (returned False)")
            except Exception as e:
                plugin_status['failed'].append({'plugin': plugin_name, 'stage': 'load', 'reason': str(e)})
                logger.error(f"❌ Exception loading plugin {plugin_name}: {e}")
        
        # ✅ VALIDATION: Ensure at least some plugins loaded
        if not plugin_status['loaded']:
            logger.error(f"❌ [CRITICAL] No GPU plugins loaded successfully. Failed plugins: {len(plugin_status['failed'])}")
            return False
        
        logger.info(f"✅ [Step 2/5] Successfully loaded {len(plugin_status['loaded'])}/{len(available_plugins)} plugins")
        
        # ✅ STEP 3: Individual plugin starting with comprehensive tracking
        logger.info(f"🔄 [Step 3/5] Starting {len(plugin_status['loaded'])} loaded plugins...")
        
        try:
            start_results = gpu_manager.start_all_plugins()
            for plugin_name, success in start_results.items():
                if success:
                    plugin_status['started'].append(plugin_name)
                    plugin_status['total_success_count'] += 1
                    logger.info(f"✅ Plugin started: {plugin_name}")
                else:
                    plugin_status['failed'].append({'plugin': plugin_name, 'stage': 'start', 'reason': 'start_returned_false'})
                    logger.warning(f"⚠️ Plugin start failed: {plugin_name}")
        except Exception as e:
            logger.error(f"❌ Exception during plugin startup: {e}")
            # Continue with loaded plugins that might still work
        
        # ✅ VALIDATION: Ensure at least some plugins started
        if not plugin_status['started']:
            logger.error(f"❌ [CRITICAL] No GPU plugins started successfully. Loaded: {len(plugin_status['loaded'])}, Failed: {len(plugin_status['failed'])}")
            return False
        
        logger.info(f"✅ [Step 3/5] Successfully started {len(plugin_status['started'])}/{len(plugin_status['loaded'])} loaded plugins")
        
        # ✅ STEP 4: Enable cloaking with individual tracking
        logger.info(f"🔄 [Step 4/5] Enabling cloaking for {len(plugin_status['started'])} started plugins...")
        
        try:
            cloaking_results = gpu_manager.enable_all_cloaking()
            for plugin_name, success in cloaking_results.items():
                if success:
                    plugin_status['cloaking_enabled'].append(plugin_name)
                    logger.info(f"✅ Cloaking enabled: {plugin_name}")
                else:
                    plugin_status['failed'].append({'plugin': plugin_name, 'stage': 'cloaking', 'reason': 'cloaking_returned_false'})
                    logger.warning(f"⚠️ Cloaking enable failed: {plugin_name}")
        except Exception as e:
            logger.error(f"❌ Exception during cloaking enablement: {e}")
            # Continue - cloaking is optional, plugins can still work
        
        if plugin_status['cloaking_enabled']:
            logger.info(f"✅ [Step 4/5] Cloaking enabled for {len(plugin_status['cloaking_enabled'])} plugins")
        else:
            logger.warning(f"⚠️ [Step 4/5] No cloaking services enabled, but plugins may still function")
        
        # ✅ STEP 5: Apply fake metrics and finalize
        logger.info(f"🔄 [Step 5/5] Applying fake metrics and finalizing...")
        
        try:
            fake_metrics = {
                'utilization': 2,        # Fake low utilization
                'temperature': 50,       # Fake temperature
                'memory_used': 100,      # Fake memory usage
                'power_usage': 150       # Fake power usage
            }
            
            gpu_manager.update_all_fake_metrics(fake_metrics)
            logger.info(f"✅ Updated fake metrics for PID={pid}: {fake_metrics}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to update fake metrics: {e} (non-critical)")
        
        # ✅ COMPREHENSIVE STATUS REPORTING
        try:
            status = gpu_manager.get_status()
            logger.info(f"📊 [Step 5/5] Final GPU Plugin System Status:")
            logger.info(f"   • Total plugins processed: {len(available_plugins)}")
            logger.info(f"   • Successfully loaded: {len(plugin_status['loaded'])}")
            logger.info(f"   • Successfully started: {len(plugin_status['started'])}")
            logger.info(f"   • Cloaking enabled: {len(plugin_status['cloaking_enabled'])}")
            logger.info(f"   • Failed operations: {len(plugin_status['failed'])}")
            logger.info(f"   • System running: {status.get('running', 'unknown')}")
            logger.info(f"   • Manager reports {len(status.get('loaded_plugins', []))} loaded plugins")
        except Exception as e:
            logger.warning(f"⚠️ Could not retrieve final status: {e}")
        
        # ✅ SUCCESS CRITERIA: At least 1 plugin successfully started
        if plugin_status['started']:
            success_rate = len(plugin_status['started']) / len(available_plugins) * 100
            logger.info(f"🎉 [SUCCESS] GPU Plugin Delegation completed successfully!")
            logger.info(f"   📈 Success Rate: {success_rate:.1f}% ({len(plugin_status['started'])}/{len(available_plugins)} plugins active)")
            logger.info(f"   🛡️ PID={pid} is now protected by {len(plugin_status['started'])} GPU plugins")
            return True
        else:
            logger.error(f"❌ [FAILURE] No GPU plugins successfully started for PID={pid}")
            return False
        
    except Exception as e:
        logger.error(f"❌ [CRITICAL] Unexpected error in apply_gpu_strategies for PID={pid}: {e}")
        import traceback
        logger.error(f"💥 Exception traceback:")
        logger.error(traceback.format_exc())
        
        # ✅ ENHANCED: Even in exception, report what was accomplished
        if plugin_status['started']:
            logger.warning(f"⚠️ Despite exception, {len(plugin_status['started'])} plugins were started successfully")
            return True
        
        return False