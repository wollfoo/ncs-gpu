#!/usr/bin/env python3
"""
✅ **ENHANCED LOGGING CONFIG** (cấu hình ghi log nâng cao – hệ thống nhật ký cải tiến) - **Phase 1 Foundation** (giai đoạn 1 nền tảng – bước xây dựng cơ bản)

**Merged functionality** (chức năng tích hợp – gộp tính năng) từ 3 **logging modules** (module ghi log – thành phần nhật ký):
- **logging_config.py** (API tương thích cốt lõi – giao diện lập trình cơ bản)
- **unified_logging.py** (singleton pattern – mẫu thiết kế đơn lẻ + hierarchy – cấu trúc phân cấp)
- **unified_log_aggregator.py** (event-driven aggregation – tổng hợp theo sự kiện)

Cung cấp **unified logging system** (hệ thống ghi log thống nhất – hệ thống nhật ký tập trung) cho **GPU mining environment** (môi trường khai thác GPU – hệ thống đào coin card đồ họa) với:
- **Backward compatible** (tương thích ngược – hoạt động với code cũ) **setup_logging() API** (giao diện thiết lập ghi log)
- **Thread-safe singleton pattern** (mẫu singleton an toàn luồng – thiết kế đơn lẻ không xung đột)
- **Real-time log aggregation** (tổng hợp log thời gian thực – gom nhật ký tức thì) (**event-driven** – điều khiển bởi sự kiện, not **polling** – không dò tìm)
- **Correlation ID system** (hệ thống ID tương quan – mã định danh liên kết)
- **Enhanced PID/TID tracking** (theo dõi PID/TID nâng cao – giám sát ID tiến trình/luồng)
"""

import os
import sys
import logging
import threading
import time
from logging import Logger
from logging.handlers import MemoryHandler, RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, Optional
from contextvars import ContextVar
from datetime import datetime
import re
import queue
import weakref

# **Legacy cryptography imports** (import mã hóa cũ – nhập thư viện bảo mật cũ) (**preserved for compatibility** – giữ lại để tương thích)
if TYPE_CHECKING:
    from cryptography.fernet import Fernet  # pragma: no cover
else:
    try:
        from cryptography.fernet import Fernet  # type: ignore
    except ImportError:  # **Library** (thư viện – module bên ngoài) có thể chưa cài khi **static check** (kiểm tra tĩnh – phân tích code không chạy)
        Fernet = Any  # type: ignore
import random
import string

###############################################################################
#        **ENHANCED LOGGING SYSTEM** (hệ thống ghi log nâng cao) - PHASE 1  #
###############################################################################

# ✅ **CORRELATION ID** (ID tương quan – mã định danh liên kết): **ContextVar system** (hệ thống biến ngữ cảnh – biến theo ngữ cảnh) (**preserved from original** – giữ nguyên từ bản gốc)
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='unknown')


###############################################################################
#     **CORRELATION ID FILTER** (bộ lọc ID tương quan) (PRESERVED – giữ nguyên) #
###############################################################################
class CorrelationIdFilter(logging.Filter):
    """
    ✅ **PRESERVED** (giữ nguyên – bảo toàn): **Logging filter** (bộ lọc ghi log – công cụ lọc nhật ký) để thêm **Correlation ID** (ID tương quan – mã định danh liên kết) vào mỗi **log record** (bản ghi log – mục nhật ký).
    **Maintained exact API compatibility** (duy trì tương thích API chính xác – giữ nguyên giao diện lập trình) từ **original logging_config.py** (file cấu hình gốc)
    """
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Thêm **Correlation ID** (ID tương quan – mã định danh liên kết) vào **log record** (bản ghi log – mục nhật ký).
        
        Args:
            record (logging.LogRecord): **Current log record** (bản ghi log hiện tại – mục nhật ký đang xử lý).
        
        Returns:
            bool: Luôn trả về **True** để cho phép **log record** (bản ghi log) được **processed** (xử lý – thực thi).
        """
        record.correlation_id = correlation_id.get()
        return True


###############################################################################
#     **ENHANCED LOG MANAGER CLASS** (lớp quản lý log nâng cao)             #
###############################################################################
class EnhancedLogManager:
    """
    ✅ **UNIFIED LOGGING MANAGER** (trình quản lý log thống nhất – hệ thống điều khiển nhật ký tập trung) - **Phase 1 Foundation** (giai đoạn 1 nền tảng)
    
    **Merges functionality** (tích hợp chức năng – gộp tính năng) từ 3 **modules** (mô-đun – thành phần):
    1. **logging_config.py**: **setup_logging() API** (giao diện thiết lập log) + **CorrelationIdFilter** (bộ lọc ID tương quan)
    2. **unified_logging.py**: **Singleton pattern** (mẫu đơn lẻ – thiết kế duy nhất) + **logger hierarchy** (phân cấp logger – cấu trúc cây nhật ký)
    3. **unified_log_aggregator.py**: **Event-driven log aggregation** (tổng hợp log theo sự kiện – gom nhật ký kích hoạt)
    
    **Features** (tính năng – chức năng chính):
    - **Thread-safe singleton pattern** (mẫu singleton an toàn luồng – thiết kế đơn lẻ không xung đột)
    - **Backward compatible** (tương thích ngược) **setup_logging() API** (giao diện thiết lập log)
    - **Enhanced PID/TID tracking** (theo dõi PID/TID nâng cao – giám sát ID tiến trình/luồng cải tiến)  
    - **Real-time log aggregation** (tổng hợp log thời gian thực – gom nhật ký tức thì) (**event-driven** – điều khiển bởi sự kiện)
    - **Centralized logger hierarchy management** (quản lý phân cấp logger tập trung – điều khiển cấu trúc nhật ký trung tâm)
    """
    
    # ✅ **SINGLETON** (đơn lẻ – duy nhất): **Thread-safe instance management** (quản lý thể hiện an toàn luồng – điều khiển đối tượng không xung đột)
    _instance: Optional['EnhancedLogManager'] = None
    _lock = threading.RLock()
    
    # ✅ **ENHANCED FORMATS** (định dạng nâng cao – cấu trúc cải tiến): **PID/TID tracking** (theo dõi PID/TID – giám sát ID tiến trình/luồng) từ **unified_logging.py**
    STANDARD_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(correlation_id)s - %(message)s'
    ENHANCED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - [PID:%(process)d|TID:%(thread)d] - %(correlation_id)s - %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    # ✅ **LOGGER HIERARCHY** (phân cấp logger – cấu trúc cây nhật ký): Từ **unified_logging.py** (**merged** – đã tích hợp)
    LOGGER_HIERARCHY = {
        'mining_environment': {
            'level': logging.INFO,
            'file': 'mining_environment.log',
            'description': '**Main mining environment logger** (logger môi trường khai thác chính – bộ ghi nhật ký hệ thống đào coin)'
        },
        'mining_environment.resource_manager': {
            'level': logging.INFO,
            'file': 'resource_manager.log',
            'description': '**Resource management operations** (hoạt động quản lý tài nguyên – điều khiển CPU/GPU/RAM)'
        },
        'mining_environment.cloak_strategies': {
            'level': logging.DEBUG,
            # Unified routing: send cloak strategies into gpu_optimization.log for single-pane operations
            'file': 'gpu_optimization.log',
            'description': '**Cloaking strategy implementations** (triển khai chiến lược ngụy trang – che giấu hoạt động khai thác) – unified to gpu_optimization'
        },
        'mining_environment.cpu_cloaking': {
            'level': logging.DEBUG,
            'file': 'cpu_cloaking_manager.log',
            'description': '**CPU cloaking legacy operations** (hoạt động ngụy trang CPU cũ – che giấu sử dụng vi xử lý)'
        },
        'mining_environment.gpu_cloaking': {
            'level': logging.DEBUG,
            'file': 'gpu_cloaking_manager.log',
            'description': '**GPU cloaking and thermal spoofing operations** (ngụy trang GPU và giả mạo nhiệt độ – che giấu card đồ họa)'
        },
        'mining_environment.resource_control': {
            'level': logging.DEBUG,
            # Unified routing: send OHC/hardware control into gpu_optimization.log
            'file': 'gpu_optimization.log',
            'description': '**Low-level resource control operations** (hoạt động điều khiển tài nguyên cấp thấp – quản lý trực tiếp phần cứng) – unified to gpu_optimization'
        },

        # GPU optimization orchestrator dedicated logger (ghi chi tiết orchestrator)
        'mining_environment.gpu_optimization': {
            'level': logging.DEBUG,
            'file': 'gpu_optimization.log',
            'description': '**GPU optimization orchestrator** (bộ điều phối tối ưu GPU – điều phối chiến lược tối ưu)'
        },
        # Route component modules to unified gpu_optimization log
        'mining_environment.scripts.parallel_strategy_executor': {
            'level': logging.DEBUG,
            'file': 'gpu_optimization.log',
            'description': '**Parallel Strategy Executor** (bộ thực thi chiến lược song song) – unified to gpu_optimization'
        },
        'mining_environment.scripts.dag_synchronization': {
            'level': logging.DEBUG,
            'file': 'gpu_optimization.log',
            'description': '**DAG Synchronizer** (đồng bộ DAG) – unified to gpu_optimization'
        },
        'mining_environment.scripts.performance_profiler': {
            'level': logging.DEBUG,
            'file': 'gpu_optimization.log',
            'description': '**Performance Profiler** (bộ phân tích hiệu năng) – unified to gpu_optimization'
        },
        'mining_environment.coordination': {
            'level': logging.DEBUG,
            'file': 'coordination.log',
            'description': '**Hook coordination** (điều phối hook – đồng bộ móc nối) và **PHASE 3++ sequencing operations** (hoạt động tuần tự giai đoạn 3++ – quy trình nâng cao)'
        },
        'ipc_bridge': {
            'level': logging.DEBUG,
            'file': 'ipc_bridge.log',
            'description': '**IPC Bridge operations** (hoạt động cầu IPC – giao tiếp liên tiến trình) - **🔥 PRODUCTION FIX**'
        },
        'ipc_bridge.server': {
            'level': logging.DEBUG,
            'file': 'ipc_bridge.log',
            'description': '**IPC Server** (máy chủ IPC – tiếp nhận tin nhắn liên tiến trình)'
        },
        'ipc_bridge.client': {
            'level': logging.DEBUG,
            'file': 'ipc_bridge.log',
            'description': '**IPC Client** (client IPC – gửi tin nhắn liên tiến trình)'
        },
    }
    
    def __new__(cls) -> 'EnhancedLogManager':
        """✅ **SINGLETON** (đơn lẻ – duy nhất): **Thread-safe singleton pattern implementation** (triển khai mẫu singleton an toàn luồng – thiết kế đối tượng duy nhất không xung đột)"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """✅ **INITIALIZE** (khởi tạo – thiết lập ban đầu): **Setup enhanced logging system** (thiết lập hệ thống ghi log nâng cao – cấu hình nhật ký cải tiến)"""
        if getattr(self, '_initialized', False):
            return
            
        self._initialized = True
        self._loggers: Dict[str, logging.Logger] = {}
        self._handlers: Dict[str, logging.Handler] = {}
        
        # ✅ **LOG DIRECTORY** (thư mục log – nơi lưu nhật ký): **Centralized log location** (vị trí log tập trung – thư mục nhật ký chung)  
        try:
            self.log_dir = Path('/app/mining_environment/logs')
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # **Fallback** (dự phòng – phương án thay thế) sang **local directory** (thư mục cục bộ) nếu **/app** không **accessible** (truy cập được – có quyền vào)
            self.log_dir = Path('./logs')
            self.log_dir.mkdir(parents=True, exist_ok=True)
            print(f"⚠️ [**EnhancedLogging** (ghi log nâng cao)] Sử dụng **fallback log directory** (thư mục log dự phòng – thư mục nhật ký thay thế): {self.log_dir.absolute()}")

        # ✅ **ENCRYPTION CONFIG** (cấu hình mã hoá – bật/tắt lớp mã hoá logging)
        self.encryption_enabled: bool = str(os.getenv('LOG_ENCRYPTION_ENABLED', '0')).lower() in ('1', 'true', 'yes')
        self.encryption_max_bytes: int = int(os.getenv('LOG_ENCRYPTION_MAX_MB', '50')) * 1024 * 1024
        self.fernet = None  # type: ignore
        if self.encryption_enabled:
            try:
                key_file = self.log_dir / '.fernet.key'
                key: Optional[bytes] = None
                # Ưu tiên: dùng khoá đã lưu, nếu chưa có thì sinh mới và lưu
                if key_file.exists():
                    try:
                        key = key_file.read_bytes().strip()
                    except Exception:
                        key = None
                if key is None:
                    try:
                        if hasattr(Fernet, 'generate_key'):
                            key = Fernet.generate_key()  # type: ignore[attr-defined]
                            try:
                                with open(key_file, 'wb') as f:
                                    f.write(key)
                                try:
                                    os.chmod(key_file, 0o600)
                                except Exception:
                                    pass
                            except Exception:
                                # Nếu không lưu được, vẫn dùng khoá trong bộ nhớ
                                pass
                    except Exception:
                        key = None
                if key is not None:
                    try:
                        self.fernet = Fernet(key)  # type: ignore[call-arg]
                    except Exception as e:
                        print(f"❌ [EnhancedLogging] Không thể khởi tạo Fernet: {e}. Tắt mã hoá logging.")
                        self.encryption_enabled = False
                else:
                    print("⚠️ [EnhancedLogging] Không thể tạo/lấy khoá Fernet. Tắt mã hoá logging.")
                    self.encryption_enabled = False
            except Exception as e:
                print(f"❌ [EnhancedLogging] Lỗi cấu hình mã hoá logging: {e}. Tắt mã hoá logging.")
                self.encryption_enabled = False
        
        # ✅ **AGGREGATION** (tổng hợp – gom nhật ký): **Event-driven log aggregation setup** (thiết lập tổng hợp log theo sự kiện – cấu hình gom nhật ký kích hoạt)
        self.unified_log_path = self.log_dir / "unified.log"
        self.last_positions: Dict[str, int] = {}
        self.aggregation_queue = queue.Queue()
        self.aggregation_thread: Optional[threading.Thread] = None
        self.aggregation_running = False
        self.timestamp_pattern = re.compile(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
        
        # ✅ **SETUP** (thiết lập – cấu hình): **Initialize logger hierarchy** (khởi tạo phân cấp logger – tạo cấu trúc cây nhật ký)
        self._setup_logger_hierarchy()
        self._start_aggregation()
        
        print(f"✅ [**EnhancedLogging** (ghi log nâng cao)] **Initialized** (đã khởi tạo) {len(self._loggers)} **loggers** (bộ ghi nhật ký) với **event-driven aggregation** (tổng hợp theo sự kiện – gom nhật ký kích hoạt)")
    
    def _setup_logger_hierarchy(self) -> None:
        """✅ **HIERARCHY** (phân cấp – cấu trúc cây): **Setup complete logger hierarchy** (thiết lập phân cấp logger hoàn chỉnh – tạo cấu trúc nhật ký đầy đủ) với **standardized configuration** (cấu hình chuẩn hóa – thiết lập thống nhất)"""
        try:
            for logger_name, config in self.LOGGER_HIERARCHY.items():
                self._create_hierarchical_logger(
                    name=logger_name,
                    level=config['level'],
                    log_file=config['file'],
                    description=config['description']
                )
            
            # ✅ **ROOT LOGGER** (logger gốc – bộ ghi nhật ký cấp cao nhất): **Setup root logger for fallback** (thiết lập logger gốc cho dự phòng – cấu hình nhật ký dự phòng)
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.WARNING)  # Chỉ **critical messages** (thông báo quan trọng – cảnh báo nghiêm trọng) tới **root** (gốc)
            
        except Exception as e:
            print(f"❌ [**EnhancedLogging** (ghi log nâng cao)] **Failed to setup** (thất bại thiết lập) **logger hierarchy** (phân cấp logger – cấu trúc cây nhật ký): {e}")
            raise
    
    def _create_hierarchical_logger(self, name: str, level: int, log_file: str, description: str) -> logging.Logger:
        """✅ **CREATE** (tạo – khởi tạo): **Individual logger** (logger riêng lẻ – bộ ghi nhật ký độc lập) với **standardized configuration** (cấu hình chuẩn hóa – thiết lập thống nhất)"""
        try:
            logger = logging.getLogger(name)
            
            # ✅ **PREVENT DUPLICATES** (ngăn trùng lặp – tránh nhân bản): **Clear existing handlers** (xóa handlers hiện có – loại bỏ bộ xử lý cũ)
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            
            logger.setLevel(level)
            logger.propagate = False  # **Prevent propagation** (ngăn lan truyền – không cho phép truyền lên) để **avoid duplicates** (tránh trùng lặp – không tạo bản sao)
            
            # ✅ **FILE HANDLER**: Chọn giữa RotatingFileHandler thường hoặc lớp mã hoá
            log_path = self.log_dir / log_file
            if self.encryption_enabled and self.fernet is not None:
                # Lớp mã hoá: sử dụng ObfuscatedEncryptedFileHandler làm đích
                file_handler = ObfuscatedEncryptedFileHandler(
                    filename=str(log_path),
                    fernet=self.fernet,  # type: ignore[arg-type]
                    level=level,
                    max_file_size=self.encryption_max_bytes
                )
                file_handler.setLevel(level)
                # MemoryHandler trỏ vào handler mã hoá
                memory_handler = MemoryHandler(
                    capacity=1,
                    target=file_handler,
                    flushLevel=logging.INFO
                )
                # Đặt formatter cho cả memory_handler và file_handler (emit của handler mã hoá dùng self.format)
                formatter = logging.Formatter(self.ENHANCED_FORMAT, self.DATE_FORMAT)
                file_handler.setFormatter(formatter)
                memory_handler.setFormatter(formatter)
                memory_handler.addFilter(CorrelationIdFilter())
            else:
                file_handler = RotatingFileHandler(
                    log_path,
                    maxBytes=10*1024*1024,
                    backupCount=5,
                    encoding='utf-8'
                )
                file_handler.setLevel(level)
                memory_handler = MemoryHandler(
                    capacity=1,
                    target=file_handler,
                    flushLevel=logging.INFO
                )
                formatter = logging.Formatter(self.ENHANCED_FORMAT, self.DATE_FORMAT)
                memory_handler.setFormatter(formatter)
                memory_handler.addFilter(CorrelationIdFilter())
            
            # ✅ **CONSOLE HANDLER** (bộ xử lý console – công cụ xuất màn hình): **Console output** (xuất ra console – hiển thị terminal) cho **important messages** (thông báo quan trọng – tin nhắn cần thiết)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.WARNING)  # Chỉ **warnings+** (cảnh báo trở lên – mức WARNING cao hơn) tới **console** (màn hình – terminal)
            console_formatter = logging.Formatter(self.STANDARD_FORMAT, self.DATE_FORMAT)
            console_handler.setFormatter(console_formatter)
            console_handler.addFilter(CorrelationIdFilter())
            
            # ✅ **ADD HANDLERS** (thêm bộ xử lý – gắn công cụ xử lý)
            logger.addHandler(memory_handler)
            logger.addHandler(console_handler)
            
            # ✅ **STORE REFERENCES** (lưu tham chiếu – giữ liên kết)
            self._loggers[name] = logger
            self._handlers[f"{name}_memory"] = memory_handler
            self._handlers[f"{name}_file"] = file_handler
            self._handlers[f"{name}_console"] = console_handler
            
            # ✅ AGGREGATION TRIGGER: Register logger for aggregation
            self._register_logger_for_aggregation(log_file)
            
            return logger
            
        except Exception as e:
            print(f"❌ [EnhancedLogging] Failed to create logger '{name}': {e}")
            raise
    
    def setup_logging(self, module_name: str, log_file: str, log_level: str = 'INFO', **kwargs) -> Logger:
        """
        ✅ BACKWARD COMPATIBLE API: Preserved exact signature từ original logging_config.py
        
        Args:
            module_name (str): Tên module (tên logger).
            log_file (str): Đường dẫn đến tệp log.
            log_level (str, optional): Mức log (DEBUG, INFO, WARN, ERROR...). Mặc định là 'INFO'.
        
        Returns:
            Logger: Đối tượng logger đã được thiết lập.
        """
        safe_log_level = getattr(logging, log_level.upper(), logging.INFO)
        logger = logging.getLogger(module_name)
        logger.setLevel(safe_log_level)

        # ✅ TEST MODE: Preserve original test mode behavior
        in_test = "TESTING" in os.environ
        logger.propagate = in_test

        # ✅ HANDLER SETUP: Only add if no handlers exist
        if not logger.handlers:
            # ✅ LOG DIRECTORY: Ensure log directory exists
            log_path = Path(log_file).parent
            log_path.mkdir(parents=True, exist_ok=True)

            # ✅ FILE HANDLER: tuỳ chọn mã hoá hoặc xoay vòng chuẩn
            if self.encryption_enabled and self.fernet is not None:
                file_handler = ObfuscatedEncryptedFileHandler(
                    filename=log_file,
                    fernet=self.fernet,  # type: ignore[arg-type]
                    level=safe_log_level,
                    max_file_size=self.encryption_max_bytes
                )
                file_handler.setLevel(safe_log_level)
                file_formatter = logging.Formatter(self.STANDARD_FORMAT)
                file_handler.setFormatter(file_formatter)
                file_handler.addFilter(CorrelationIdFilter())

                memory_handler = MemoryHandler(
                    capacity=1,
                    target=file_handler,
                    flushLevel=logging.INFO
                )
                memory_handler.addFilter(CorrelationIdFilter())
                memory_handler.setFormatter(file_formatter)
            else:
                file_handler = RotatingFileHandler(
                    log_file, 
                    maxBytes=10*1024*1024,
                    backupCount=5,
                    encoding='utf-8'
                )
                file_handler.setLevel(safe_log_level)
                formatter = logging.Formatter(self.STANDARD_FORMAT)
                file_handler.setFormatter(formatter)
                file_handler.addFilter(CorrelationIdFilter())

                # ✅ MEMORY HANDLER: Buffer và flush tự động (preserved pattern)
                memory_handler = MemoryHandler(
                    capacity=1,
                    target=file_handler,
                    flushLevel=logging.INFO
                )
                memory_handler.addFilter(CorrelationIdFilter())
            
            logger.addHandler(memory_handler)

            # ✅ STREAM HANDLER: Console với flush tự động
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setLevel(safe_log_level)
            stream_formatter = logging.Formatter(self.STANDARD_FORMAT)
            stream_handler.setFormatter(stream_formatter)
            stream_handler.addFilter(CorrelationIdFilter())
            logger.addHandler(stream_handler)
            
            # ✅ AGGREGATION: Register for real-time aggregation
            log_filename = Path(log_file).name
            self._register_logger_for_aggregation(log_filename)

        return logger
    
    def get_unified_logger(self, name: str) -> logging.Logger:
        """
        ✅ BRIDGE FUNCTION: Compatibility bridge từ unified_logging.py
        
        :param name: Logger name (can be full hierarchy or module name)
        :return: Configured logger instance
        """
        try:
            # ✅ DIRECT MATCH: Check if exact name exists in hierarchy
            if name in self._loggers:
                return self._loggers[name]
            
            # ✅ HIERARCHY MATCH: Try to find in hierarchy
            full_name = f"mining_environment.{name}"
            if full_name in self._loggers:
                return self._loggers[full_name]
            
            # ✅ FALLBACK: Create ad-hoc logger if not in hierarchy
            return self._create_adhoc_logger(name)
            
        except Exception as e:
            print(f"❌ [EnhancedLogging] Error getting unified logger '{name}': {e}")
            # ✅ SAFETY FALLBACK: Return basic logger
            return logging.getLogger(name)
    
    def _create_adhoc_logger(self, name: str) -> logging.Logger:
        """✅ AD-HOC: Create logger for modules not in predefined hierarchy"""
        try:
            logger_name = f"mining_environment.{name}" if not name.startswith('mining_environment') else name
            
            return self._create_hierarchical_logger(
                name=logger_name,
                level=logging.INFO,
                log_file=f"{name.replace('.', '_')}.log",
                description=f"Ad-hoc logger for {name}"
            )
            
        except Exception as e:
            print(f"❌ [EnhancedLogging] Failed to create ad-hoc logger '{name}': {e}")
            return logging.getLogger(name)
    
    def _register_logger_for_aggregation(self, log_file: str):
        """✅ REGISTER: Register log file for event-driven aggregation"""
        log_path = self.log_dir / log_file
        self.last_positions[str(log_path)] = 0
    
    def _start_aggregation(self):
        """✅ START: Event-driven log aggregation (replace polling)"""
        if self.aggregation_running:
            return
            
        self.aggregation_running = True
        self.aggregation_thread = threading.Thread(
            target=self._aggregation_worker,
            daemon=True,
            name="EnhancedLogAggregator"
        )
        self.aggregation_thread.start()
        print(f"✅ [EnhancedLogging] Event-driven aggregation started: {self.unified_log_path}")
    
    def _aggregation_worker(self):
        """✅ WORKER: Event-driven aggregation worker thread"""
        while self.aggregation_running:
            try:
                # ✅ EVENT-DRIVEN: Process aggregation requests from queue
                try:
                    # Wait for aggregation trigger với timeout
                    self.aggregation_queue.get(timeout=1.0)
                    self._aggregate_logs_immediate()
                except queue.Empty:
                    # ✅ FALLBACK: Periodic check every 1 second (not 5s polling)
                    self._aggregate_logs_immediate()
                    
            except Exception as e:
                print(f"❌ [EnhancedLogging] Aggregation worker error: {e}")
                time.sleep(1)  # Back off on error
    
    def _aggregate_logs_immediate(self):
        """✅ IMMEDIATE: Immediate log aggregation (event-driven)"""
        if not self.log_dir.exists():
            return
            
        # ✅ DISCOVER: Find all log files
        log_files = list(self.log_dir.glob("*.log"))
        if not log_files:
            return
            
        # ✅ COLLECT: Gather new entries từ each log file
        new_entries: List[Tuple[datetime, str, str]] = []
        
        for log_file in log_files:
            if log_file.name == "unified.log":
                continue  # Skip own file
                
            try:
                entries = self._read_new_entries(log_file)
                new_entries.extend(entries)
            except Exception as e:
                print(f"⚠️ [EnhancedLogging] Error reading {log_file.name}: {e}")
                
        # ✅ SORT: Sort by timestamp (chronological merging)
        new_entries.sort(key=lambda x: x[0])
        
        # ✅ WRITE: Append to unified.log
        if new_entries:
            self._write_unified_entries(new_entries)
    
    def _read_new_entries(self, log_file: Path) -> List[Tuple[datetime, str, str]]:
        """✅ READ: Extract new entries từ specific log file"""
        entries = []
        
        if not log_file.exists():
            return entries
            
        # ✅ TRACK: Get last read position
        last_pos = self.last_positions.get(str(log_file), 0)
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(last_pos)
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # ✅ EXTRACT: Parse timestamp
                    timestamp = self._extract_timestamp(line)
                    if timestamp:
                        entries.append((timestamp, log_file.name, line))
                        
                # ✅ UPDATE: Save new position
                self.last_positions[str(log_file)] = f.tell()
                
        except Exception as e:
            print(f"⚠️ [EnhancedLogging] Error reading {log_file}: {e}")
            
        return entries
    
    def _extract_timestamp(self, line: str) -> datetime:
        """✅ PARSE: Extract timestamp từ log line"""
        match = self.timestamp_pattern.search(line)
        if match:
            try:
                return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return datetime.now()  # Fallback to current time
    
    def _write_unified_entries(self, entries: List[Tuple[datetime, str, str]]):
        """✅ WRITE: Append entries to unified.log với chronological order"""
        try:
            with open(self.unified_log_path, 'a', encoding='utf-8') as f:
                for timestamp, source_file, log_line in entries:
                    # ✅ FORMAT: Add source file prefix (preserve format)
                    unified_line = f"[{source_file}] {log_line}\n"
                    f.write(unified_line)
                    
        except Exception as e:
            print(f"❌ [EnhancedLogging] Error writing unified.log: {e}")
    
    def trigger_aggregation(self):
        """✅ TRIGGER: Manual trigger cho immediate aggregation"""
        try:
            self.aggregation_queue.put_nowait("aggregate")
        except queue.Full:
            pass  # Queue full, aggregation will happen soon anyway
    
    def get_logging_status(self) -> Dict[str, Any]:
        """✅ STATUS: Get comprehensive logging system status"""
        try:
            status = {
                'timestamp': time.time(),
                'total_loggers': len(self._loggers),
                'total_handlers': len(self._handlers),
                'log_directory': str(self.log_dir),
                'aggregation_running': self.aggregation_running,
                'loggers': {},
                'disk_usage': {}
            }
            
            # ✅ LOGGER DETAILS
            for name, logger in self._loggers.items():
                status['loggers'][name] = {
                    'level': logging.getLevelName(logger.level),
                    'handlers': len(logger.handlers),
                    'propagate': logger.propagate
                }
            
            # ✅ DISK USAGE
            try:
                for log_file in self.log_dir.glob('*.log'):
                    size_mb = log_file.stat().st_size / (1024 * 1024)
                    status['disk_usage'][log_file.name] = f"{size_mb:.2f} MB"
            except Exception:
                status['disk_usage'] = "Unable to calculate"
            
            return status
            
        except Exception as e:
            return {'error': f"Failed to get logging status: {e}"}
    
    def cleanup_old_logs(self, days_to_keep: int = 7) -> int:
        """✅ CLEANUP: Clean up old log files để manage disk space"""
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            cleaned_count = 0
            
            for log_file in self.log_dir.glob('*.log*'):
                try:
                    if log_file.stat().st_mtime < cutoff_time:
                        log_file.unlink()
                        cleaned_count += 1
                except Exception:
                    continue  # Skip files that can't be deleted
            
            if cleaned_count > 0:
                # Log to main logger
                main_logger = self.get_unified_logger('mining_environment')
                main_logger.info(f"🧹 [EnhancedLogging] Cleaned up {cleaned_count} old log files")
            
            return cleaned_count
            
        except Exception as e:
            print(f"❌ [EnhancedLogging] Log cleanup failed: {e}")
            return 0

# ✅ GLOBAL INSTANCE: Thread-safe singleton instance
_enhanced_manager: Optional[EnhancedLogManager] = None
_manager_lock = threading.RLock()

def _get_enhanced_manager() -> EnhancedLogManager:
    """✅ FACTORY: Get singleton enhanced log manager instance"""
    global _enhanced_manager
    with _manager_lock:
        if _enhanced_manager is None:
            _enhanced_manager = EnhancedLogManager()
        return _enhanced_manager

###############################################################################
#                    BACKWARD COMPATIBLE API FUNCTIONS                       #
###############################################################################

def setup_logging(module_name: str, log_file: str, log_level: str = 'INFO', **kwargs) -> Logger:
    """
    ✅ BACKWARD COMPATIBLE: Exact API preservation từ original logging_config.py
    Now delegates to EnhancedLogManager để provide unified functionality.
    
    Args:
        module_name (str): Tên module (tên logger).
        log_file (str): Đường dẫn đến tệp log.
        log_level (str, optional): Mức log (DEBUG, INFO, WARN, ERROR...). Mặc định là 'INFO'.
    
    Returns:
        Logger: Đối tượng logger đã được thiết lập với enhanced functionality.
    """
    manager = _get_enhanced_manager()
    return manager.setup_logging(module_name, log_file, log_level, **kwargs)


def get_unified_logger(name: str) -> logging.Logger:
    """
    ✅ BRIDGE FUNCTION: Compatibility bridge từ unified_logging.py
    
    :param name: Module name (e.g., 'resource_manager', 'cloak_strategies')
    :return: Configured logger from enhanced hierarchy
    """
    manager = _get_enhanced_manager()
    return manager.get_unified_logger(name)


def get_logging_status() -> Dict[str, Any]:
    """
    ✅ STATUS FUNCTION: Get enhanced logging system status.
    
    :return: Comprehensive logging system metrics and status
    """
    manager = _get_enhanced_manager()
    return manager.get_logging_status()


def cleanup_logs(days_to_keep: int = 7) -> int:
    """
    ✅ CLEANUP FUNCTION: Clean up old log files.
    
    :param days_to_keep: Days to keep log files (default: 7)
    :return: Number of files cleaned up
    """
    manager = _get_enhanced_manager()
    return manager.cleanup_old_logs(days_to_keep)


def trigger_log_aggregation():
    """
    ✅ TRIGGER FUNCTION: Manual trigger cho immediate log aggregation
    Useful for forcing immediate unified.log update
    """
    manager = _get_enhanced_manager()
    manager.trigger_aggregation()


def start_unified_logging():
    """
    ✅ START FUNCTION: Compatibility bridge để start unified logging system
    EnhancedLogManager auto-starts aggregation, but this ensures initialization
    """
    _ = _get_enhanced_manager()  # Initialize manager (starts aggregation automatically)


def stop_unified_logging():
    """
    ✅ STOP FUNCTION: Stop unified logging aggregation
    """
    global _enhanced_manager
    if _enhanced_manager:
        _enhanced_manager.aggregation_running = False


###############################################################################
#                           LEGACY CODE (PRESERVED)                          #
###############################################################################
# The following classes are preserved for reference but not used in Phase 1
# They may be needed for future compatibility or specific use cases

class ObfuscatedEncryptedFileHandler(logging.Handler):
    """
    ⚠️ LEGACY: Custom logging handler để mã hóa và làm rối các log trước khi ghi vào tệp.
    Đồng thời tự động xóa file log khi dung lượng vượt quá ngưỡng cho phép.
    
    NOTE: This handler is preserved for compatibility but not used in Phase 1.
    The enhanced system uses MemoryHandler + RotatingFileHandler pattern.
    """
    def __init__(
        self,
        filename: str,
        fernet: Any,
        level: int = logging.NOTSET,
        max_file_size: int = 50 * 1024 * 1024  # 50MB mặc định
    ):
        """
        Khởi tạo ObfuscatedEncryptedFileHandler.
        
        Args:
            filename (str): Đường dẫn đến tệp log.
            fernet (Fernet): Đối tượng Fernet để mã hóa log.
            level (int, optional): Mức độ log để xử lý. Mặc định là NOTSET.
            max_file_size (int, optional): Ngưỡng dung lượng (byte) để tự động
                                           xóa log. Mặc định là 50MB.
        """
        super().__init__(level)
        self.filename = filename
        self.fernet = fernet
        self.max_file_size = max_file_size

        # Đảm bảo thư mục cha tồn tại
        file_parent = Path(filename).parent
        file_parent.mkdir(parents=True, exist_ok=True)

        # Mở file ở chế độ 'ab' (append-binary)
        self.file = open(self.filename, 'ab')

    def emit(self, record: logging.LogRecord):
        """
        Xử lý và ghi bản ghi log vào tệp sau khi mã hóa và làm rối.
        Đồng thời kiểm tra kích thước file, nếu vượt quá max_file_size thì xóa luôn.
        
        Args:
            record (logging.LogRecord): Bản ghi log cần xử lý.
        """
        try:
            # Format message
            msg = self.format(record)
            # Thêm chuỗi ngẫu nhiên để làm rối
            random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            obfuscated_msg = f"{msg} {random_suffix}"

            # Mã hóa thông điệp
            encrypted_msg = self.fernet.encrypt(obfuscated_msg.encode('utf-8'))

            # Ghi vào tệp (dạng nhị phân, thêm newline)
            self.file.write(encrypted_msg + b'\n')
            self.file.flush()

            # Kiểm tra kích thước file, nếu vượt ngưỡng thì xóa file, tạo lại
            self._check_file_size()
        except Exception:
            self.handleError(record)

    def _check_file_size(self):
        """
        Kiểm tra và xóa file nếu kích thước > self.max_file_size.
        """
        current_size = self.file.tell()  # Vị trí con trỏ => kích thước file hiện tại
        if current_size > self.max_file_size:
            self.file.close()
            os.remove(self.filename)
            # Tạo lại file rỗng
            self.file = open(self.filename, 'ab')

    def close(self):
        """
        Đóng tệp log khi handler được đóng.
        """
        if not self.file.closed:
            self.file.close()
        super().close()
