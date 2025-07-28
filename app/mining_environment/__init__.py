"""
Mining Environment Package

Thư viện tổng hợp cho hệ thống khai thác tiền điện tử
với tính năng cloaking và resource management.
"""

import logging
import os
import sys
from pathlib import Path

# Thiết lập logging cho package
logger = logging.getLogger(__name__)


def initialize_mining_environment():
    """Kích hoạt lớp môi trường khai thác"""
    
    # Kiểm tra biến môi trường cần thiết
    # **GPU-Only Mode**: CPU environment variables removed
    required_env_vars = ['LOGS_DIR', 'CUDA_COMMAND', 'MINING_SERVER_GPU', 'MINING_WALLET_GPU']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"Thiếu biến môi trường: {missing_vars}")
    
    # Tạo thư mục logs nếu chưa tồn tại
    logs_dir = os.getenv('LOGS_DIR', '/tmp/mining_logs')
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info("Môi trường mining đã được khởi tạo")


# Khởi tạo tự động khi import package
initialize_mining_environment()
