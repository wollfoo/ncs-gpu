# -*- coding: utf-8 -*-

"""
Cầu nối Python (Python Wrapper) cho Thư viện Khai thác Rust.

Module này cung cấp một lớp `MiningEngine` trong Python để tương tác
với thư viện Rust `mining_core` đã được biên dịch. Nó sử dụng `ctypes`
để tải thư viện động và gọi các hàm FFI.
"""

import ctypes
import os
import platform
from typing import Optional

class MiningEngine:
    """
    Một lớp bao bọc Pythonic cho MiningEngine của Rust.

    Quản lý việc tải thư viện, tạo, bắt đầu, dừng và giải phóng
    engine khai thác.
    """

    def __init__(self, library_path: str, pool_url: str, wallet_address: str, algorithm: str = "Ethash"):
        """
        Khởi tạo và tạo một engine khai thác mới.

        Args:
            library_path (str): Đường dẫn đến tệp thư viện động (.so, .dll, .dylib).
            pool_url (str): URL của pool khai thác.
            wallet_address (str): Địa chỉ ví.
            algorithm (str): Thuật toán để sử dụng (ví dụ: "Ethash").
        """
        self._lib = ctypes.CDLL(library_path)
        self._engine_ptr = None

        # --- Định nghĩa các kiểu đối số và kiểu trả về cho các hàm FFI ---
        # Điều này rất quan trọng để `ctypes` xử lý dữ liệu một cách chính xác.

        # mining_engine_new
        self._lib.mining_engine_new.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p]
        self._lib.mining_engine_new.restype = ctypes.c_void_p

        # mining_engine_start
        self._lib.mining_engine_start.argtypes = [ctypes.c_void_p]
        self._lib.mining_engine_start.restype = None

        # mining_engine_stop
        self._lib.mining_engine_stop.argtypes = [ctypes.c_void_p]
        self._lib.mining_engine_stop.restype = None

        # mining_engine_free
        self._lib.mining_engine_free.argtypes = [ctypes.c_void_p]
        self._lib.mining_engine_free.restype = None

        # --- Tạo engine ---
        self._engine_ptr = self._lib.mining_engine_new(
            pool_url.encode('utf-8'),
            wallet_address.encode('utf-8'),
            algorithm.encode('utf-8')
        )
        if not self._engine_ptr:
            raise RuntimeError("Không thể tạo MiningEngine từ thư viện Rust.")

        print("Đã tạo MiningEngine thành công.")

    def start(self):
        """Bắt đầu quá trình khai thác trong một luồng nền."""
        if not self._engine_ptr:
            raise RuntimeError("Engine chưa được khởi tạo.")
        print("Đang gửi lệnh bắt đầu đến engine...")
        self._lib.mining_engine_start(self._engine_ptr)

    def stop(self):
        """Dừng quá trình khai thác."""
        if not self._engine_ptr:
            return
        print("Đang gửi lệnh dừng đến engine...")
        self._lib.mining_engine_stop(self._engine_ptr)

    def free(self):
        """Giải phóng bộ nhớ được cấp phát bởi engine Rust."""
        if not self._engine_ptr:
            return
        self._lib.mining_engine_free(self._engine_ptr)
        self._engine_ptr = None
        print("Đã giải phóng tài nguyên của Engine.")

    def __del__(self):
        """
        Hàm hủy (destructor), đảm bảo tài nguyên được giải phóng khi đối tượng bị xóa.
        """
        print("Hàm hủy của Python đang được gọi...")
        self.free()

def find_library_path() -> str:
    """Tìm đường dẫn đến thư viện động đã được biên dịch."""
    lib_name = ""
    if platform.system() == "Linux":
        lib_name = "libmining_core.so"
    elif platform.system() == "Darwin":
        lib_name = "libmining_core.dylib"
    elif platform.system() == "Windows":
        lib_name = "mining_core.dll"
    else:
        raise RuntimeError(f"Hệ điều hành không được hỗ trợ: {platform.system()}")

    # Giả định thư viện nằm trong `target/release` ở thư mục gốc của dự án.
    # (Assuming the library is in `target/release` at the project root.)
    path = os.path.join(os.path.dirname(__file__), '..', 'target', 'release', lib_name)
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Không tìm thấy thư viện tại '{path}'. "
            "Hãy chắc chắn rằng bạn đã biên dịch dự án Rust với lệnh: "
            "`cargo build --release --features mining-core/ffi`"
        )
    return path


if __name__ == '__main__':
    """
    Một ví dụ về cách sử dụng lớp bao bọc.
    """
    import time

    try:
        lib_path = find_library_path()
        print(f"Đã tìm thấy thư viện tại: {lib_path}")

        engine = MiningEngine(
            library_path=lib_path,
            pool_url="stratum+tcp://simulated.pool:3333",
            wallet_address="MY_SIMULATED_WALLET"
        )

        engine.start()

        print("\nEngine đang chạy. Nhấn Ctrl+C để dừng.")
        # Giữ cho script chính chạy trong 30 giây
        time.sleep(30)

    except (RuntimeError, FileNotFoundError) as e:
        print(f"Lỗi: {e}")
    except KeyboardInterrupt:
        print("\nĐã nhận tín hiệu KeyboardInterrupt từ người dùng.")
    finally:
        # Lớp bao bọc sẽ tự động gọi `free` thông qua `__del__`.
        # (The wrapper will automatically call `free` via `__del__`.)
        print("Kết thúc chương trình ví dụ.")