"""
**Mining Environment Package** (gói môi trường khai thác – bộ công cụ môi trường đào coin)

**Thư viện tổng hợp** (bộ thư viện tích hợp) cho **hệ thống khai thác tiền điện tử** (hệ thống đào coin) 
với **tính năng cloaking** (chức năng ẩn danh) và **resource management** (quản lý tài nguyên).
"""

import logging
import os
import sys
from pathlib import Path

# **Thiết lập logging** (cấu hình ghi log) cho **package** (gói)
logger = logging.getLogger(__name__)


def initialize_mining_environment():
    """**Kích hoạt lớp môi trường khai thác** (thiết lập môi trường đào coin)"""
    
    # **Kiểm tra biến môi trường cần thiết** (xác minh tham số hệ thống bắt buộc)
    # **GPU-Only Mode** (chế độ chỉ GPU): **CPU environment variables removed** (đã xóa biến môi trường CPU)
    required_env_vars = ['LOGS_DIR', 'CUDA_COMMAND', 'MINING_SERVER_GPU', 'MINING_WALLET_GPU']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.warning(f"**Thiếu biến môi trường** (thiếu tham số hệ thống): {missing_vars}")
    
    # **Tạo thư mục logs** (tạo thư mục nhật ký) nếu chưa tồn tại
    logs_dir = os.getenv('LOGS_DIR', '/tmp/mining_logs')
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info("**Môi trường mining** (môi trường khai thác) đã được **khởi tạo** (thiết lập)")


# **Khởi tạo tự động** (thiết lập tự động) khi **import package** (nhập gói)
initialize_mining_environment()
