# module_loggers.py

"""
**Module Loggers Configuration** (Cấu hình Logger Mô-đun)

Tạo và quản lý **dedicated loggers** (logger chuyên dụng) cho các **mining modules** (mô-đun khai thác)
và **plugin systems** (hệ thống plugin).
"""

import os
from pathlib import Path
from mining_environment.scripts.logging_config import setup_logging

# **Log directory setup** (thiết lập thư mục log)
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)

# **Dedicated Module Loggers** (Logger mô-đun chuyên dụng)
gpu_plugin_logger = setup_logging('gpu_plugin', str(Path(LOGS_DIR) / 'gpu_plugin.log'), 'INFO')
gpu_cloaking_logger = setup_logging('gpu_cloaking', str(Path(LOGS_DIR) / 'gpu_cloaking.log'), 'INFO')
gpu_optimization_logger = setup_logging('gpu_optimization', str(Path(LOGS_DIR) / 'gpu_optimization.log'), 'INFO')
mining_performance_logger = setup_logging('mining_performance', str(Path(LOGS_DIR) / 'mining_performance.log'), 'INFO')
audit_integration_logger = setup_logging('audit_integration', str(Path(LOGS_DIR) / 'audit_integration.log'), 'INFO')
gpu_monitoring_logger = setup_logging('gpu_monitoring', str(Path(LOGS_DIR) / 'gpu_monitoring.log'), 'INFO')

def get_gpu_plugin_logger():
    """
    **Get GPU plugin logger** (Lấy logger plugin GPU) - Dedicated logger cho **GPU plugin operations** (hoạt động plugin GPU).
    
    Returns:
        Logger: GPU plugin logger instance
    """
    return gpu_plugin_logger

def get_gpu_cloaking_logger():
    """
    **Get GPU cloaking logger** (Lấy logger che giấu GPU) - Dedicated logger cho **GPU cloaking operations** (hoạt động che giấu GPU).
    
    Returns:
        Logger: GPU cloaking logger instance
    """
    return gpu_cloaking_logger

def get_gpu_optimization_logger():
    """
    **Get GPU optimization logger** (Lấy logger tối ưu GPU) - Dedicated logger cho **GPU optimization operations** (hoạt động tối ưu GPU).
    
    Returns:
        Logger: GPU optimization logger instance
    """
    return gpu_optimization_logger

def get_mining_performance_logger():
    """
    **Get mining performance logger** (Lấy logger hiệu suất khai thác) - Dedicated logger cho **mining performance tracking** (theo dõi hiệu suất khai thác).
    
    Returns:
        Logger: Mining performance logger instance
    """
    return mining_performance_logger

def get_audit_integration_logger():
    """
    **Get audit integration logger** (Lấy logger tích hợp kiểm toán) - Dedicated logger cho **audit integration operations** (hoạt động tích hợp kiểm toán).
    
    Returns:
        Logger: Audit integration logger instance
    """
    return audit_integration_logger

def get_gpu_monitoring_logger():
    """
    **Get GPU monitoring logger** (Lấy logger giám sát GPU) - Dedicated logger cho **GPU monitoring operations** (hoạt động giám sát GPU).
    
    Returns:
        Logger: GPU monitoring logger instance
    """
    return gpu_monitoring_logger

def initialize_plugin_logging():
    """
    **Initialize plugin logging system** (Khởi tạo hệ thống ghi log plugin).
    Tạo **initial log entries** (mục log ban đầu) trong các **plugin log files** (tệp log plugin).
    """
    # **GPU Plugin Logging Initialization** (Khởi tạo ghi log plugin GPU)
    gpu_plugin_logger.info("===== GPU PLUGIN LOGGING SYSTEM STARTED =====")
    gpu_plugin_logger.info("GPU Plugin Logger initialized and ready")
    gpu_plugin_logger.info("Available for logging GPU plugin operations")
    gpu_plugin_logger.info("============================================")
    
    # **GPU Cloaking Logging Initialization** (Khởi tạo ghi log che giấu GPU)
    gpu_cloaking_logger.info("===== GPU CLOAKING LOGGING SYSTEM STARTED =====")
    gpu_cloaking_logger.info("GPU Cloaking Logger initialized and ready")
    gpu_cloaking_logger.info("Available for logging GPU cloaking operations")
    gpu_cloaking_logger.info("============================================")
    
    # **GPU Optimization Logging Initialization** (Khởi tạo ghi log tối ưu GPU)
    gpu_optimization_logger.info("===== GPU OPTIMIZATION LOGGING SYSTEM STARTED =====")
    gpu_optimization_logger.info("GPU Optimization Logger initialized and ready")
    gpu_optimization_logger.info("Available for logging GPU optimization operations")
    gpu_optimization_logger.info("============================================")
    
    # **Mining Performance Logging Initialization** (Khởi tạo ghi log hiệu suất khai thác)
    mining_performance_logger.info("===== MINING PERFORMANCE LOGGING SYSTEM STARTED =====")
    mining_performance_logger.info("Mining Performance Logger initialized and ready")
    mining_performance_logger.info("Available for logging mining performance operations")
    mining_performance_logger.info("============================================")
    
    # **Audit Integration Logging Initialization** (Khởi tạo ghi log tích hợp kiểm toán)
    audit_integration_logger.info("===== AUDIT INTEGRATION LOGGING SYSTEM STARTED =====")
    audit_integration_logger.info("Audit Integration Logger initialized and ready")
    audit_integration_logger.info("Available for logging audit integration operations")
    audit_integration_logger.info("============================================")
    
    # **GPU Monitoring Logging Initialization** (Khởi tạo ghi log giám sát GPU)
    gpu_monitoring_logger.info("===== GPU MONITORING LOGGING SYSTEM STARTED =====")
    gpu_monitoring_logger.info("GPU Monitoring Logger initialized and ready")
    gpu_monitoring_logger.info("Available for logging GPU monitoring operations")
    gpu_monitoring_logger.info("============================================")

def log_gpu_plugin_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log GPU plugin operation** (Ghi log hoạt động plugin GPU).
    
    Args:
        operation (str): **Operation name** (tên hoạt động)
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(gpu_plugin_logger, level.lower(), gpu_plugin_logger.info)
    log_method(f"🎮 GPU Plugin - {operation}: {details}")

def log_gpu_cloaking_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log GPU cloaking operation** (Ghi log hoạt động che giấu GPU).
    
    Args:
        operation (str): **Operation name** (tên hoạt động)
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(gpu_cloaking_logger, level.lower(), gpu_cloaking_logger.info)
    log_method(f"🔒 GPU Cloaking - {operation}: {details}")

def log_gpu_optimization_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log GPU optimization operation** (Ghi log hoạt động tối ưu GPU).
    
    Args:
        operation (str): **Operation name** (tên hoạt động)
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(gpu_optimization_logger, level.lower(), gpu_optimization_logger.info)
    log_method(f"⚡ GPU Optimization - {operation}: {details}")

def log_mining_performance_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log mining performance operation** (Ghi log hoạt động hiệu suất khai thác).
    
    Args:
        operation (str): **Operation name** (tên hoạt động)
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(mining_performance_logger, level.lower(), mining_performance_logger.info)
    log_method(f"📊 Mining Performance - {operation}: {details}")

def log_audit_integration_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log audit integration operation** (Ghi log hoạt động tích hợp kiểm toán).
    
    Args:
        operation (str): **Operation name** (tên hoạt động)
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(audit_integration_logger, level.lower(), audit_integration_logger.info)
    log_method(f"🔍 Audit Integration - {operation}: {details}")

def log_gpu_monitoring_operation(operation: str, details: str, level: str = "INFO"):
    """
    **Log GPU monitoring operation** (Ghi log hoạt động giám sát GPU).
    
    Args:
        operation (str): **Operation name** (tên hoạt động)
        details (str): **Operation details** (chi tiết hoạt động)
        level (str): **Log level** (mức log) (INFO, WARNING, ERROR, DEBUG)
    """
    log_method = getattr(gpu_monitoring_logger, level.lower(), gpu_monitoring_logger.info)
    log_method(f"📈 GPU Monitoring - {operation}: {details}")

# **Auto-initialize** (tự động khởi tạo) khi module được import
initialize_plugin_logging()