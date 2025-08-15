#!/usr/bin/env python3
"""
DEPRECATED: **Log Rotation Guard** (Bộ canh xoay vòng log trong ứng dụng) đã được thay thế
bởi **logrotate** (công cụ tầng hệ thống) khởi chạy từ `entrypoint.sh` mỗi 60 giây.

- File được giữ lại để tương thích (imports cũ), nhưng không còn được sử dụng.
- Nếu được gọi, hàm sẽ ghi log cảnh báo và thoát ngay (no-op).
"""

import os
import time
import uuid
from pathlib import Path
from typing import Iterable

from .logging_config import setup_logging  # dùng để ghi cảnh báo deprecation


def _iter_log_files(log_dir: Path) -> Iterable[Path]:
    """Trả về iterator các tệp `*.log` trong thư mục (không đệ quy)."""
    try:
        yield from (p for p in log_dir.glob('*.log') if p.is_file())
    except Exception:
        return


def _directory_total_size_bytes(log_dir: Path) -> int:
    """Tính tổng dung lượng TẤT CẢ các tệp (không đệ quy) trong thư mục (byte)."""
    total = 0
    try:
        for p in log_dir.iterdir():
            try:
                if p.is_file():
                    total += p.stat().st_size
            except Exception:
                continue
    except Exception:
        return 0
    return total


def _secure_delete_file(file_path: Path, logger) -> bool:
    """
    **Secure Delete** (xóa an toàn – xóa vĩnh viễn):
    - Ghi đè tệp bằng dữ liệu ngẫu nhiên một lần
    - `fsync` (đồng bộ đĩa), đổi tên ngẫu nhiên, rồi `unlink` (gỡ liên kết tệp)

    Lưu ý: Trên hệ thống dùng **journaling** (ghi nhật ký hệ thống tệp), không thể bảo đảm 100% 
    xóa không khôi phục ở mức vật lý; đây là best-effort ở tầng ứng dụng.
    """
    try:
        if not file_path.exists() or not file_path.is_file():
            return False

        size = file_path.stat().st_size
        if size > 0:
            try:
                with open(file_path, 'r+b', buffering=0) as f:
                    chunk_size = 1024 * 1024  # 1MB
                    remaining = size
                    while remaining > 0:
                        to_write = min(chunk_size, remaining)
                        f.write(os.urandom(to_write))
                        remaining -= to_write
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"⚠️ Không thể ghi đè tệp trước khi xóa: {file_path} | {e}")

        # Đổi tên để cắt liên kết tên gốc trước khi unlink
        try:
            tmp_name = file_path.with_name(f".deleted_{uuid.uuid4().hex}.log")
            os.replace(file_path, tmp_name)
            file_path = tmp_name
        except Exception:
            # Nếu đổi tên thất bại, tiếp tục xóa trực tiếp
            pass

        try:
            os.remove(file_path)
            return True
        except Exception as e:
            logger.error(f"❌ Xóa tệp thất bại: {file_path} | {e}")
            return False

    except Exception as e:
        logger.error(f"❌ Lỗi khi xử lý xóa an toàn: {file_path} | {e}")
        return False


def start_log_directory_guard(*args, **kwargs) -> None:
    """No-op: thay thế bằng logrotate từ entrypoint.sh."""
    try:
        # Ghi cảnh báo 1 lần, không lặp
        log_dir = Path(os.getenv('LOGS_DIR', '/app/mining_environment/logs'))
        logger = setup_logging('log_rotation_guard', str(log_dir / 'log_rotation_guard.log'), 'INFO')
        logger.warning("[DEPRECATED] LogRotationGuard đã bị vô hiệu hóa. Sử dụng logrotate từ entrypoint.")
    except Exception:
        pass


