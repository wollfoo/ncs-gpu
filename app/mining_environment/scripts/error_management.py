"""
✅ **CENTRALIZED ERROR MANAGEMENT SYSTEM** (hệ thống quản lý lỗi tập trung – hệ thống xử lý lỗi trung tâm)
**Standardized error handling** (xử lý lỗi chuẩn hóa – cơ chế xử lý lỗi thống nhất), **propagation** (lan truyền – truyền tải lỗi) và **recovery mechanisms** (cơ chế phục hồi – cơ chế khôi phục) cho **mining environment** (môi trường đào coin – môi trường khai thác).
"""

import logging
import threading
import time
import traceback
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Union
from concurrent.futures import ThreadPoolExecutor
import json

# **Import new logging system** (nhập hệ thống ghi nhật ký mới – import hệ thống logging mới)
try:
    from .module_loggers import get_error_management_logger
except ImportError:
    # **Fallback for standalone execution** (dự phòng cho thực thi độc lập – phương án dự phòng khi chạy riêng lẻ)
    from module_loggers import get_error_management_logger

class ErrorSeverity(Enum):
    """✅ **STANDARDIZED: Error severity levels** (mức độ nghiêm trọng lỗi chuẩn hóa – cấp độ lỗi thống nhất) cho **consistent categorization** (phân loại nhất quán – phân nhóm đồng bộ)"""
    CRITICAL = "CRITICAL"    # **System-breaking errors** (lỗi phá vỡ hệ thống – lỗi làm sập hệ thống), **immediate attention required** (cần xử lý ngay lập tức – yêu cầu can thiệp khẩn cấp)
    HIGH = "HIGH"            # **Major functionality affected** (chức năng chính bị ảnh hưởng – tính năng quan trọng bị tác động), **urgent fix needed** (cần sửa gấp – yêu cầu khắc phục khẩn)
    MEDIUM = "MEDIUM"        # **Moderate impact** (tác động trung bình – ảnh hưởng vừa phải), **fix in next iteration** (sửa trong lần lặp tiếp theo – khắc phục trong chu kỳ kế tiếp)
    LOW = "LOW"              # **Minor issues** (vấn đề nhỏ – lỗi không quan trọng), **cosmetic problems** (lỗi giao diện – vấn đề về hình thức)
    INFO = "INFO"            # **Informational messages** (thông báo thông tin – tin nhắn mang tính thông báo), **not actual errors** (không phải lỗi thực sự – chỉ là thông tin)

class ErrorCode(Enum):
    """✅ **STANDARDIZED: Standardized error codes** (mã lỗi chuẩn hóa – mã định danh lỗi thống nhất) cho **system-wide error identification** (nhận diện lỗi toàn hệ thống – xác định lỗi trên toàn bộ hệ thống)"""
    
    # **Strategy-related errors** (lỗi liên quan chiến lược – lỗi về các chiến lược) (1000-1999)
    STRATEGY_APPLICATION_FAILED = 1001
    STRATEGY_NOT_FOUND = 1002
    STRATEGY_VALIDATION_FAILED = 1003
    STRATEGY_TIMEOUT = 1004
    
    # **Resource management errors** (lỗi quản lý tài nguyên – lỗi về quản lý nguồn lực) (2000-2999)
    RESOURCE_MANAGER_INIT_FAILED = 2001
    RESOURCE_ALLOCATION_FAILED = 2002
    RESOURCE_CLEANUP_FAILED = 2003
    RESOURCE_VALIDATION_FAILED = 2004
    
    # **Process-related errors** (lỗi liên quan tiến trình – lỗi về các process) (3000-3999)
    PROCESS_NOT_FOUND = 3001
    PROCESS_ACCESS_DENIED = 3002
    PROCESS_MONITORING_FAILED = 3003
    PROCESS_TERMINATION_FAILED = 3004
    
    # **System-level errors** (lỗi cấp hệ thống – lỗi ở mức hệ thống) (4000-4999)
    SYSTEM_RESOURCE_EXHAUSTED = 4001
    SYSTEM_CONFIGURATION_INVALID = 4002
    SYSTEM_DEPENDENCY_MISSING = 4003
    SYSTEM_PERMISSION_DENIED = 4004
    
    # **Communication errors** (lỗi giao tiếp – lỗi về truyền thông) (5000-5999) - **EventBus errors removed** (lỗi EventBus đã xóa – lỗi bus sự kiện đã loại bỏ)
    # 🗑️ **EventBus communication errors removed** (lỗi giao tiếp EventBus đã xóa) - **DirectPIDRegistry uses in-memory communication** (DirectPIDRegistry sử dụng giao tiếp trong bộ nhớ – registry PID trực tiếp dùng truyền thông RAM)
    DIRECT_REGISTRY_COMMUNICATION_FAILED = 5001
    DIRECT_REGISTRY_OBSERVER_FAILED = 5002
    DIRECT_REGISTRY_REGISTRATION_FAILED = 5003
    
    # **Unknown/Generic errors** (lỗi không xác định/chung – lỗi chưa biết/tổng quát) (9000-9999)
    UNKNOWN_ERROR = 9001
    INTERNAL_ERROR = 9002

@dataclass
class ErrorContext:
    """✅ **STANDARDIZED: Rich error context object** (đối tượng ngữ cảnh lỗi phong phú – object chứa thông tin lỗi chi tiết) cho **detailed error information** (thông tin lỗi chi tiết – dữ liệu lỗi cụ thể)"""
    
    error_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: float = field(default_factory=time.time)
    error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR
    severity: ErrorSeverity = ErrorSeverity.MEDIUM
    message: str = ""
    module: str = ""
    function: str = ""
    line_number: Optional[int] = None
    process_id: Optional[int] = None
    strategy_name: Optional[str] = None
    context_data: Dict[str, Any] = field(default_factory=dict)
    stack_trace: Optional[str] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    recovery_actions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """**Convert error context to dictionary** (chuyển đổi ngữ cảnh lỗi thành từ điển – biến đổi context lỗi sang dict) for **serialization** (tuần tự hóa – chuyển đổi để lưu trữ/truyền tải)"""
        return {
            'error_id': self.error_id,
            'timestamp': self.timestamp,
            'error_code': self.error_code.value,
            'severity': self.severity.value,
            'message': self.message,
            'module': self.module,
            'function': self.function,
            'line_number': self.line_number,
            'process_id': self.process_id,
            'strategy_name': self.strategy_name,
            'context_data': self.context_data,
            'stack_trace': self.stack_trace,
            'recovery_attempted': self.recovery_attempted,
            'recovery_successful': self.recovery_successful,
            'recovery_actions': self.recovery_actions
        }

class CentralizedErrorReporter:
    """
    ✅ **CENTRALIZED: Central error reporting system** (hệ thống báo cáo lỗi trung tâm – hệ thống báo lỗi tập trung) với **DirectPIDRegistry integration** (tích hợp DirectPIDRegistry – kết nối với registry PID trực tiếp).
    **Handles error collection** (xử lý thu thập lỗi – quản lý việc thu gom lỗi), **propagation** (lan truyền – truyền tải), **recovery coordination** (điều phối phục hồi – phối hợp khôi phục).
    🗑️ **EventBus completely removed** (EventBus đã xóa hoàn toàn – bus sự kiện đã loại bỏ hết) - **using logging system for error reporting** (sử dụng hệ thống logging để báo cáo lỗi – dùng hệ thống ghi nhật ký để báo lỗi).
    """
    
    def __init__(self, legacy_event_bus: Optional[Any] = None):
        """**Initialize centralized error reporter** (khởi tạo trình báo cáo lỗi tập trung – thiết lập hệ thống báo lỗi trung tâm)
        
        Args:
            legacy_event_bus: **Legacy parameter for backward compatibility** (tham số cũ để tương thích ngược – tham số kế thừa cho tương thích với phiên bản cũ) **(ignored)** (bỏ qua)
        """
        self.logger = get_error_management_logger()
        # 🗑️ **EventBus completely removed** (EventBus đã xóa hoàn toàn) - **error reporting handled by logging system only** (báo cáo lỗi chỉ xử lý bởi hệ thống logging – báo lỗi chỉ qua hệ thống ghi nhật ký)
        
        # ✅ **ERROR STORAGE** (lưu trữ lỗi): **In-memory error storage** (lưu trữ lỗi trong bộ nhớ – lưu lỗi trong RAM) với **recent error tracking** (theo dõi lỗi gần đây – giám sát lỗi mới nhất)
        self.error_history: List[ErrorContext] = []
        self.error_lock = threading.RLock()
        self.max_history_size = 1000
        
        # ✅ **RECOVERY HANDLERS** (bộ xử lý phục hồi): **Registered recovery mechanisms** (cơ chế phục hồi đã đăng ký – cơ chế khôi phục đã thiết lập)
        self.recovery_handlers: Dict[ErrorCode, List[Callable]] = {}
        
        # ✅ **ERROR METRICS** (số liệu lỗi): **Track error statistics** (theo dõi thống kê lỗi – giám sát số liệu lỗi)
        self.error_metrics = {
            'total_errors': 0,
            'errors_by_severity': {sev.value: 0 for sev in ErrorSeverity},
            'errors_by_code': {code.value: 0 for code in ErrorCode},
            'recovery_success_rate': 0.0,
            'recent_errors': []  # **Last 10 errors for quick access** (10 lỗi cuối cùng để truy cập nhanh – 10 lỗi gần nhất để xem nhanh)
        }
        
        # ✅ **THREAD POOL** (nhóm luồng): **For async error handling** (để xử lý lỗi bất đồng bộ – cho xử lý lỗi không đồng bộ)
        self.error_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ErrorHandler")
        
        self.logger.info("✅ [ErrorReporter] **Centralized error reporter initialized** (Trình báo cáo lỗi tập trung đã khởi tạo – hệ thống báo lỗi trung tâm đã thiết lập)")
    
    def report_error(
        self, 
        error_code: ErrorCode,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        module: str = "",
        function: str = "",
        process_id: Optional[int] = None,
        strategy_name: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ) -> ErrorContext:
        """
        ✅ **PRIMARY METHOD: Report error** (phương thức chính: báo cáo lỗi – hàm chính: báo lỗi) với **comprehensive context** (ngữ cảnh toàn diện – thông tin đầy đủ).
        
        :param error_code: **Standardized error code** (mã lỗi chuẩn hóa – mã định danh lỗi thống nhất)
        :param message: **Human-readable error message** (thông báo lỗi dễ đọc – tin nhắn lỗi cho người đọc)
        :param severity: **Error severity level** (mức độ nghiêm trọng lỗi – cấp độ lỗi)
        :param module: **Module where error occurred** (module nơi xảy ra lỗi – mô-đun phát sinh lỗi)
        :param function: **Function where error occurred** (hàm nơi xảy ra lỗi – function phát sinh lỗi)
        :param process_id: **Related process ID** (ID tiến trình liên quan – mã định danh process) **(if applicable)** (nếu có)
        :param strategy_name: **Related strategy name** (tên chiến lược liên quan – tên strategy) **(if applicable)** (nếu có)
        :param context_data: **Additional context information** (thông tin ngữ cảnh bổ sung – dữ liệu context thêm)
        :param exception: **Python exception object** (đối tượng ngoại lệ Python – object exception) **(if available)** (nếu có)
        :return: **ErrorContext object** (đối tượng ErrorContext) với **unique error ID** (ID lỗi duy nhất – mã định danh lỗi không trùng)
        """
        try:
            # ✅ **CREATE ERROR CONTEXT** (tạo ngữ cảnh lỗi – khởi tạo context lỗi)
            error_context = ErrorContext(
                error_code=error_code,
                severity=severity,
                message=message,
                module=module,
                function=function,
                process_id=process_id,
                strategy_name=strategy_name,
                context_data=context_data or {},
                stack_trace=traceback.format_exc() if exception else None
            )
            
            # ✅ **ENHANCED CONTEXT** (ngữ cảnh nâng cao): **Add stack frame information** (thêm thông tin stack frame – bổ sung thông tin khung ngăn xếp)
            import inspect
            frame = inspect.currentframe()
            if frame and frame.f_back:
                caller_frame = frame.f_back
                error_context.line_number = caller_frame.f_lineno
                if not error_context.function:
                    error_context.function = caller_frame.f_code.co_name
                if not error_context.module:
                    error_context.module = caller_frame.f_code.co_filename.split('/')[-1]
            
            # ✅ **STORE ERROR** (lưu trữ lỗi – ghi nhận lỗi)
            with self.error_lock:
                self.error_history.append(error_context)
                
                # ✅ **CLEANUP** (dọn dẹp): **Maintain history size limit** (duy trì giới hạn kích thước lịch sử – giữ giới hạn số lượng lịch sử)
                if len(self.error_history) > self.max_history_size:
                    self.error_history.pop(0)
                
                # ✅ **UPDATE METRICS** (cập nhật số liệu – cập nhật thống kê)
                self._update_metrics(error_context)
            
            # ✅ **LOG ERROR** (ghi nhật ký lỗi – ghi log lỗi)
            log_level = {
                ErrorSeverity.CRITICAL: logging.CRITICAL,
                ErrorSeverity.HIGH: logging.ERROR,
                ErrorSeverity.MEDIUM: logging.WARNING,
                ErrorSeverity.LOW: logging.INFO,
                ErrorSeverity.INFO: logging.INFO
            }.get(severity, logging.WARNING)
            
            self.logger.log(
                log_level,
                f"🚨 [{severity.value}] {error_code.value}: {message} (ID: {error_context.error_id})"
            )
            
            # 🗑️ **EventBus removed** (EventBus đã xóa) - **error reporting handled by logging system only** (báo cáo lỗi chỉ xử lý bởi hệ thống logging – báo lỗi chỉ qua hệ thống ghi nhật ký)
            
            # ✅ **RECOVERY ATTEMPT** (thử phục hồi): **Try automated recovery** (thử phục hồi tự động – cố gắng khôi phục tự động)
            self.error_executor.submit(self._attempt_recovery, error_context)
            
            return error_context
            
        except Exception as e:
            # ✅ **FALLBACK** (dự phòng): **If error reporting fails, use basic logging** (nếu báo cáo lỗi thất bại, dùng logging cơ bản – khi báo lỗi lỗi, dùng ghi nhật ký đơn giản)
            self.logger.critical(f"💥 [ErrorReporter] Failed to report error: {e}")
            return ErrorContext(message=f"Error reporting failed: {e}")
    
    def _update_metrics(self, error_context: ErrorContext) -> None:
        """**Update internal error metrics** (cập nhật số liệu lỗi nội bộ – cập nhật thống kê lỗi bên trong)"""
        self.error_metrics['total_errors'] += 1
        self.error_metrics['errors_by_severity'][error_context.severity.value] += 1
        self.error_metrics['errors_by_code'][error_context.error_code.value] += 1
        
        # ✅ **RECENT ERRORS** (lỗi gần đây): **Keep track of recent errors for quick analysis** (theo dõi lỗi gần đây để phân tích nhanh – giám sát lỗi mới nhất để xem xét nhanh)
        self.error_metrics['recent_errors'].append({
            'error_id': error_context.error_id,
            'timestamp': error_context.timestamp,
            'severity': error_context.severity.value,
            'code': error_context.error_code.value,
            'message': error_context.message[:100]  # **Truncated for space** (cắt ngắn để tiết kiệm không gian – rút gọn để tiết kiệm bộ nhớ)
        })
        
        # **Keep only last 10 recent errors** (chỉ giữ 10 lỗi gần nhất – chỉ lưu 10 lỗi mới nhất)
        if len(self.error_metrics['recent_errors']) > 10:
            self.error_metrics['recent_errors'].pop(0)
    
    def _publish_error_event(self, error_context: ErrorContext) -> None:
        """🗑️ **REMOVED: EventBus error publishing removed** (ĐÃ XÓA: phát hành lỗi EventBus đã xóa) - **using logging system only** (chỉ dùng hệ thống logging – chỉ sử dụng hệ thống ghi nhật ký)"""
        # **All error events are now handled through the unified logging system** (tất cả sự kiện lỗi giờ được xử lý qua hệ thống logging thống nhất – mọi event lỗi giờ qua hệ thống ghi nhật ký hợp nhất)
        # **No external event publishing required with DirectPIDRegistry architecture** (không cần phát hành sự kiện ra ngoài với kiến trúc DirectPIDRegistry – không cần publish event bên ngoài với cấu trúc registry PID trực tiếp)
        pass
    
    def _attempt_recovery(self, error_context: ErrorContext) -> None:
        """**Attempt automated error recovery** (thử phục hồi lỗi tự động – cố gắng khôi phục lỗi tự động) với **enhanced coordination** (điều phối nâng cao – phối hợp cải tiến)"""
        try:
            error_context.recovery_attempted = True
            
            # ✅ **COORDINATED RECOVERY** (phục hồi phối hợp): **Try ErrorRecoveryCoordinator first for high/critical errors** (thử ErrorRecoveryCoordinator trước cho lỗi cao/nghiêm trọng – dùng bộ điều phối phục hồi trước cho lỗi quan trọng)
            if error_context.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                try:
                    self.logger.info(f"🎆 [Recovery] Initiating coordinated recovery for {error_context.error_code.value}")
                    
                    # **Import recovery coordinator locally to avoid circular imports** (import bộ điều phối phục hồi cục bộ để tránh import vòng – nhập coordinator phục hồi local để tránh import lặp)
                    try:
                        from .error_recovery_coordinator import get_recovery_coordinator
                    except ImportError:
                        from error_recovery_coordinator import get_recovery_coordinator
                    
                    coordinator = get_recovery_coordinator()
                    recovery_future = coordinator.initiate_recovery(error_context)
                    
                    # ✅ **ASYNC HANDLING** (xử lý bất đồng bộ): **Don't wait for result, let it run asynchronously** (không chờ kết quả, để chạy bất đồng bộ – không đợi kết quả, cho chạy không đồng bộ)
                    error_context.recovery_actions.append("Coordinated recovery initiated")
                    self.logger.info(f"✅ [Recovery] Coordinated recovery started for error {error_context.error_id}")
                    
                    # **Still run legacy recovery as backup** (vẫn chạy phục hồi cũ làm dự phòng – vẫn chạy recovery kế thừa làm backup)
                    
                except Exception as coord_error:
                    self.logger.warning(f"⚠️ [Recovery] Coordinated recovery failed, falling back: {coord_error}")
                    error_context.recovery_actions.append(f"Coordinated recovery failed: {coord_error}")
            
            # ✅ **LEGACY RECOVERY** (phục hồi kế thừa): **Original recovery logic as fallback** (logic phục hồi gốc làm dự phòng – luận lý khôi phục ban đầu làm fallback)
            recovery_handlers = self.recovery_handlers.get(error_context.error_code, [])
            
            if not recovery_handlers:
                self.logger.debug(f"🔧 [Recovery] No legacy recovery handlers for {error_context.error_code.value}")
                return
            
            for handler in recovery_handlers:
                try:
                    recovery_result = handler(error_context)
                    if recovery_result:
                        error_context.recovery_successful = True
                        error_context.recovery_actions.append(f"Legacy handler {handler.__name__} succeeded")
                        self.logger.info(f"✅ [Recovery] **Legacy recovery successful** (phục hồi kế thừa thành công – khôi phục cũ thành công) for error {error_context.error_id}")
                        break
                    else:
                        error_context.recovery_actions.append(f"Legacy handler {handler.__name__} failed")
                        
                except Exception as recovery_error:
                    error_context.recovery_actions.append(f"Legacy handler {handler.__name__} exception: {recovery_error}")
                    self.logger.warning(f"⚠️ [Recovery] Legacy recovery handler failed: {recovery_error}")
            
            # ✅ **UPDATE RECOVERY METRICS** (cập nhật số liệu phục hồi – cập nhật thống kê khôi phục)
            self._update_recovery_metrics()
            
        except Exception as e:
            self.logger.error(f"❌ [Recovery] Recovery attempt failed: {e}")
    
    def _update_recovery_metrics(self) -> None:
        """**Update recovery success rate metrics** (cập nhật số liệu tỷ lệ phục hồi thành công – cập nhật thống kê tỷ lệ khôi phục thành công)"""
        try:
            with self.error_lock:
                total_recovery_attempts = sum(1 for e in self.error_history if e.recovery_attempted)
                successful_recoveries = sum(1 for e in self.error_history if e.recovery_successful)
                
                if total_recovery_attempts > 0:
                    self.error_metrics['recovery_success_rate'] = (successful_recoveries / total_recovery_attempts) * 100
                    
        except Exception as e:
            self.logger.debug(f"Error updating recovery metrics: {e}")
    
    def register_recovery_handler(self, error_code: ErrorCode, handler: Callable) -> None:
        """
        ✅ **RECOVERY SYSTEM** (hệ thống phục hồi): **Register recovery handler** (đăng ký bộ xử lý phục hồi – thiết lập handler khôi phục) cho **specific error code** (mã lỗi cụ thể – error code đặc biệt).
        
        :param error_code: **ErrorCode to handle** (mã lỗi cần xử lý – ErrorCode cần xử lý)
        :param handler: **Callable recovery function** (hàm phục hồi có thể gọi – function khôi phục có thể thực thi) **(must accept ErrorContext, return bool)** (phải nhận ErrorContext, trả về bool)
        """
        try:
            if error_code not in self.recovery_handlers:
                self.recovery_handlers[error_code] = []
            
            self.recovery_handlers[error_code].append(handler)
            self.logger.info(f"✅ [Recovery] Registered handler for {error_code.value}")
            
        except Exception as e:
            self.logger.error(f"❌ [Recovery] Failed to register handler: {e}")
    
    def get_error_metrics(self) -> Dict[str, Any]:
        """
        ✅ **MONITORING** (giám sát): **Get comprehensive error metrics** (lấy số liệu lỗi toàn diện – thu thập thống kê lỗi đầy đủ) cho **system monitoring** (giám sát hệ thống – theo dõi hệ thống).
        
        :return: **Dictionary containing error statistics and recent errors** (từ điển chứa thống kê lỗi và lỗi gần đây – dict chứa số liệu lỗi và lỗi mới nhất)
        """
        try:
            with self.error_lock:
                return {
                    'timestamp': time.time(),
                    'total_errors': self.error_metrics['total_errors'],
                    'errors_by_severity': dict(self.error_metrics['errors_by_severity']),
                    'errors_by_code': dict(self.error_metrics['errors_by_code']),
                    'recovery_success_rate': self.error_metrics['recovery_success_rate'],
                    'recent_errors': list(self.error_metrics['recent_errors']),
                    'error_history_size': len(self.error_history),
                    'recovery_handlers_count': sum(len(handlers) for handlers in self.recovery_handlers.values())
                }
                
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Failed to get error metrics: {e}")
            return {'error': str(e)}
    
    def get_errors_by_severity(self, severity: ErrorSeverity, limit: int = 50) -> List[ErrorContext]:
        """**Get recent errors filtered by severity** (lấy lỗi gần đây lọc theo mức độ nghiêm trọng – thu thập lỗi mới nhất theo cấp độ)"""
        try:
            with self.error_lock:
                filtered_errors = [e for e in self.error_history if e.severity == severity]
                return filtered_errors[-limit:] if filtered_errors else []
                
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Failed to filter errors by severity: {e}")
            return []
    
    def cleanup_old_errors(self, days_to_keep: int = 7) -> int:
        """**Clean up old errors from history** (dọn dẹp lỗi cũ khỏi lịch sử – xóa lỗi cũ từ lịch sử)"""
        try:
            cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
            
            with self.error_lock:
                initial_count = len(self.error_history)
                self.error_history = [e for e in self.error_history if e.timestamp > cutoff_time]
                cleaned_count = initial_count - len(self.error_history)
                
                if cleaned_count > 0:
                    self.logger.info(f"🧹 [ErrorReporter] **Cleaned up** (dọn dẹp – đã xóa) {cleaned_count} **old errors** (lỗi cũ – lỗi quá hạn)")
                
                return cleaned_count
                
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Error cleanup failed: {e}")
            return 0
    
    def shutdown(self) -> None:
        """**Graceful shutdown of error reporter** (tắt trình báo cáo lỗi nhẹ nhàng – đóng hệ thống báo lỗi an toàn)"""
        try:
            self.logger.info("🛑 [ErrorReporter] Shutting down error reporter...")
            
            # ✅ SHUTDOWN EXECUTOR
            self.error_executor.shutdown(wait=True, timeout=10)
            
            # ✅ FINAL METRICS
            final_metrics = self.get_error_metrics()
            self.logger.info(f"📊 [ErrorReporter] Final metrics: {final_metrics['total_errors']} total errors")
            
        except Exception as e:
            self.logger.error(f"❌ [ErrorReporter] Shutdown error: {e}")

# ✅ **GLOBAL INSTANCE** (thể hiện toàn cục): **Create global error reporter instance** (tạo thể hiện trình báo cáo lỗi toàn cục – khởi tạo instance báo lỗi global)
_global_error_reporter: Optional[CentralizedErrorReporter] = None
_reporter_lock = threading.RLock()

def get_error_reporter(legacy_event_bus: Optional[Any] = None) -> CentralizedErrorReporter:
    """
    ✅ CONVENIENCE FUNCTION: Get global error reporter instance.
    
    :param legacy_event_bus: Legacy parameter for backward compatibility (ignored)
    :return: CentralizedErrorReporter instance
    """
    global _global_error_reporter
    
    with _reporter_lock:
        if _global_error_reporter is None:
            _global_error_reporter = CentralizedErrorReporter()
        return _global_error_reporter

def report_error(
    error_code: ErrorCode,
    message: str,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    **kwargs
) -> ErrorContext:
    """
    ✅ CONVENIENCE FUNCTION: Quick error reporting using global reporter.
    
    :param error_code: Standardized error code
    :param message: Error message
    :param severity: Error severity
    :param kwargs: Additional context parameters
    :return: ErrorContext object
    """
    reporter = get_error_reporter()
    return reporter.report_error(error_code, message, severity, **kwargs)

def register_recovery_handler(error_code: ErrorCode, handler: Callable) -> None:
    """
    ✅ CONVENIENCE FUNCTION: Register recovery handler using global reporter.
    
    :param error_code: ErrorCode to handle
    :param handler: Recovery handler function
    """
    reporter = get_error_reporter()
    reporter.register_recovery_handler(error_code, handler)

def get_error_metrics() -> Dict[str, Any]:
    """
    ✅ CONVENIENCE FUNCTION: Get error metrics using global reporter.
    
    :return: Error metrics dictionary
    """
    reporter = get_error_reporter()
    return reporter.get_error_metrics()

# ✅ ADVANCED RECOVERY: Delayed import to avoid circular imports

def initiate_coordinated_recovery(
    error_context: ErrorContext,
    retry_config = None,  # Optional[RetryConfig] - avoid forward ref
    priority: int = 5
) -> Any:
    """
    ✅ COORDINATED RECOVERY: Initiate advanced recovery using ErrorRecoveryCoordinator.
    
    :param error_context: Error context from error reporter
    :param retry_config: Custom retry configuration
    :param priority: Recovery priority (1-10)
    :return: Future object for async recovery result
    """
    try:
        from .error_recovery_coordinator import get_recovery_coordinator
    except ImportError:
        from error_recovery_coordinator import get_recovery_coordinator
    
    coordinator = get_recovery_coordinator()
    return coordinator.initiate_recovery(error_context, retry_config, priority)

def register_coordinated_recovery_handler(
    error_code: ErrorCode,
    recovery_handler: Callable,
    strategy = None,  # RecoveryStrategy - avoid forward ref
    retry_config = None  # Optional[RetryConfig] - avoid forward ref
) -> None:
    """
    ✅ COORDINATED HANDLER: Register recovery handler with ErrorRecoveryCoordinator.
    
    :param error_code: Error code to handle
    :param recovery_handler: Recovery handler function
    :param strategy: Recovery strategy to use
    :param retry_config: Custom retry configuration
    """
    try:
        from .error_recovery_coordinator import get_recovery_coordinator, RecoveryStrategy
    except ImportError:
        from error_recovery_coordinator import get_recovery_coordinator, RecoveryStrategy
    
    if strategy is None:
        strategy = RecoveryStrategy.EXPONENTIAL_BACKOFF
    
    coordinator = get_recovery_coordinator()
    coordinator.register_recovery_handler(error_code, recovery_handler, strategy, retry_config)

def get_recovery_performance_metrics() -> Dict[str, Any]:
    """
    ✅ RECOVERY METRICS: Get comprehensive recovery performance metrics.
    
    :return: Recovery performance metrics dictionary
    """
    try:
        from .error_recovery_coordinator import get_recovery_coordinator
    except ImportError:
        from error_recovery_coordinator import get_recovery_coordinator
    
    coordinator = get_recovery_coordinator()
    return coordinator.get_recovery_metrics()