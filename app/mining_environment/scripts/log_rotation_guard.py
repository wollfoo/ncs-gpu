#!/usr/bin/env python3
"""
**Log Rotation Guard** (Bộ canh xoay vòng log – tiến trình nền kiểm soát dung lượng)

- **Logging** (Ghi nhật ký – ghi sự kiện/lỗi hệ thống)
- **log rotation** (xoay vòng log – quản lý dung lượng tệp nhật ký)
- **loop** (vòng lặp – kiểm tra định kỳ đến khi dừng)
- **directory** (thư mục – nơi chứa tệp log)
- **size** (kích thước – tổng dung lượng tính theo MB)
- **delete** (xóa – loại bỏ tệp)
- **permanently** (vĩnh viễn – xóa không thể khôi phục)

Chức năng: Chạy một vòng lặp giám sát tổng dung lượng các tệp `*.log` trong thư mục log. 
Nếu tổng dung lượng vượt ngưỡng (mặc định 10MB), thực hiện xóa bảo mật toàn bộ tệp `*.log` 
trong thư mục đó (ghi đè dữ liệu rồi `unlink`).
"""

import os
import time
import uuid
from pathlib import Path
from typing import Iterable

from .logging_config import setup_logging  # **Logging config** (cấu hình nhật ký – tận dụng logger sẵn có)


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


def start_log_directory_guard(stop_event, log_directory: str, threshold_mb: int = 10, interval_seconds: float = 30.0) -> None:
    """
    Bắt đầu **loop** (vòng lặp – kiểm tra định kỳ) giám sát thư mục log.

    Args:
        stop_event: **threading.Event** (cờ dừng – đồng bộ dừng luồng)
        log_directory (str): **directory** (thư mục) chứa log, ví dụ: `/app/mining_environment/logs`
        threshold_mb (int): Ngưỡng tổng **size** (kích thước) tính theo MB để kích hoạt **log rotation** (xoay vòng/xóa)
        interval_seconds (float): Chu kỳ kiểm tra (giây)
    """
    log_dir = Path(log_directory)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = setup_logging('log_rotation_guard', str(log_dir / 'log_rotation_guard.log'), 'INFO')
    logger.info(f"🛡️ LogRotationGuard started | dir={log_dir} | threshold={threshold_mb}MB | interval={interval_seconds}s")

    threshold_bytes = threshold_mb * 1024 * 1024

    while not stop_event.is_set():
        try:
            total_bytes = _directory_total_size_bytes(log_dir)
            if total_bytes > threshold_bytes:
                logger.warning(
                    f"🚨 Tổng dung lượng *.log = {total_bytes/1024/1024:.2f}MB vượt ngưỡng {threshold_mb}MB – bắt đầu xóa vĩnh viễn các tệp .log"
                )

                # Xóa an toàn từng tệp *.log (không đệ quy)
                deleted = 0
                for p in _iter_log_files(log_dir):
                    if _secure_delete_file(p, logger):
                        deleted += 1

                logger.info(f"✅ Đã xóa an toàn {deleted} tệp .log trong {log_dir}")

            # Ngủ giữa các lần kiểm tra
            stop_event.wait(interval_seconds)

        except Exception as e:
            logger.error(f"❌ Lỗi vòng lặp LogRotationGuard: {e}")
            # Tránh spam log, vẫn tiếp tục sau một khoảng nghỉ ngắn
            stop_event.wait(max(5.0, interval_seconds))


