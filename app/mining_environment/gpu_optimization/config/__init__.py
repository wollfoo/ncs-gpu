"""
GPU Optimization Configuration Module
======================================
Module cấu hình tối ưu hóa GPU.

This module provides centralized configuration management for the GPU optimization system.
Module này cung cấp quản lý cấu hình tập trung cho hệ thống tối ưu hóa GPU.

Features:
- Hierarchical configuration with override support
- Environment variable overrides with GPU_OPT_ prefix  
- Profile-based configurations (dev/staging/production)
- Schema validation with detailed error reporting
- Hot reload capability
- Thread-safe singleton access
- Configuration watching/notification system

Example usage:
    from gpu_optimization.config import load_config, get_config
    
    # Load full configuration
    config = load_config()
    
    # Get specific value  
    max_workers = get_config('orchestrator.max_workers', default=4)
    
    # Set runtime value
    set_config('monitoring.enabled', True)
"""

from .loader import (
    ConfigLoader,
    ConfigSchema,
    ConfigValidationResult,
    get_config_loader,
    load_config,
    get_config,
    set_config,
    validate_config
)

__all__ = [
    'ConfigLoader',
    'ConfigSchema',
    'ConfigValidationResult',
    'get_config_loader',
    'load_config',
    'get_config',
    'set_config', 
    'validate_config'
]

# Module version
__version__ = '2.0.0'
