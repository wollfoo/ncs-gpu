"""
GPU Optimization Package
========================
High-performance GPU optimization system for mining environments
Hệ thống tối ưu hóa GPU hiệu năng cao cho môi trường khai thác
"""

__version__ = "2.0.0"
__author__ = "GPU Optimization Team"

# Public API imports
from .core.manager import (
    GPUOptimizationManager,
    get_manager,
    initialize,
    optimize,
    get_status,
    shutdown
)

# Export public API
__all__ = [
    'GPUOptimizationManager',
    'get_manager', 
    'initialize',
    'optimize',
    'get_status',
    'shutdown',
    '__version__'
]

# Module metadata
def get_version():
    """Get package version"""
    return __version__

def get_info():
    """Get package information"""
    return {
        'name': 'gpu_optimization',
        'version': __version__,
        'author': __author__,
        'description': 'High-performance GPU optimization system',
        'api_version': '2.0'
    }
