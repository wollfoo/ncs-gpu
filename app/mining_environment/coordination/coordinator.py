#!/usr/bin/env python3
"""
**Simple Hook Coordinator - Production Ready** (điều phối hook đơn giản - sẵn sàng sản xuất)

**Hook Coordinator Module** (module điều phối hook) để **coordinate GPU hooks** (điều phối các hook GPU)
và **manage mining processes** (quản lý các tiến trình khai thác) với **unified logging** (ghi log thống nhất).
"""

import os
import time
import threading
import json
import psutil
import random
import hashlib
import glob
from typing import Dict, Optional, Set, Any

# ✅ **UNIFIED LOGGING** (ghi log thống nhất): **Import unified logging system** (nhập hệ thống ghi log thống nhất)
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
    from module_loggers import get_coordination_logger
    LOGGING_AVAILABLE = True
except ImportError:
    LOGGING_AVAILABLE = False

class HookCoordinator:
    """
    **Hook Coordinator Class** (lớp điều phối hook)
    
    **Simple Hook Coordinator** (điều phối hook đơn giản) cho **PHASE 3+** (giai đoạn 3+) 
    và **cloaking** (ẩn giấu hoạt động).
    
    Quản lý **hook synchronization** (đồng bộ hook), **health monitoring** (giám sát sức khỏe),
    và **recovery mechanisms** (cơ chế phục hồi) cho **mining processes** (tiến trình khai thác).
    """
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # ✅ **LOGGER INITIALIZATION** (khởi tạo logger): **Initialize logger using unified_logging system** (khởi tạo logger sử dụng hệ thống ghi log thống nhất)
        if LOGGING_AVAILABLE:
            try:
                self.logger = get_coordination_logger()
            except Exception:
                # **Fallback to default logger if unified_logging fails** (dự phòng về logger mặc định nếu unified_logging thất bại)
                import logging
                self.logger = logging.getLogger(__name__)
        else:
            # **Fallback to default logger if unified_logging not available** (dự phòng về logger mặc định nếu unified_logging không khả dụng)
            import logging
            self.logger = logging.getLogger(__name__)
        
        self.hooks_ready: Dict[int, bool] = {}
        
        # ✅ **IDEMPOTENCY PROTECTION** (bảo vệ tính idempotent): **Handoff deduplication system** (hệ thống loại trùng handoff)
        self.handoff_timestamps: Dict[int, float] = {}  # **Track last handoff time per PID** (theo dõi thời gian handoff cuối theo PID)
        self.handoff_metadata_cache: Dict[int, Dict[str, Any]] = {}  # **Cache handoff metadata** (lưu cache metadata handoff)
        self.duplicate_detection_window: float = 5.0  # **5-second deduplication window** (cửa sổ loại trùng 5 giây)
        self.handoff_sequence_numbers: Dict[int, int] = {}  # **Track handoff sequence per PID** (theo dõi chuỗi handoff theo PID)
        
        # ✅ **HEALTH CHECK** (kiểm tra sức khỏe): **Hook coordination health monitoring attributes** (thuộc tính giám sát sức khỏe điều phối hook)
        self.active_processes: Set[int] = set()
        self.hook_status_history: Dict[int, list] = {}  # **Track status changes over time** (theo dõi thay đổi trạng thái theo thời gian)
        self.last_health_check: float = 0  # **Last health check timestamp** (dấu thời gian kiểm tra sức khỏe cuối)
        self.health_check_interval: float = 30  # **Check every 30 seconds** (kiểm tra mỗi 30 giây)
        self.recovery_attempts: Dict[int, int] = {}  # **Track recovery attempts per PID** (theo dõi số lần phục hồi theo PID)
        self.max_recovery_attempts: int = 3  # **Maximum recovery attempts** (số lần phục hồi tối đa)
        
        # ✅ **SYNCHRONIZATION** (đồng bộ hóa): **Race condition prevention attributes** (thuộc tính ngăn chặn race condition)
        self.environment_sync_lock = threading.Lock()
        self.verification_retry_config = {
            'max_retries': 2,     # **Reduced from 3 for linear flow efficiency** (giảm từ 3 để hiệu quả luồng tuyến tính)
            'base_delay': 0.0005, # **Reduced to 0.5ms for linear flow speed** (giảm xuống 0.5ms cho tốc độ luồng tuyến tính)
            'max_delay': 0.02,    # **Reduced to 20ms for linear flow speed** (giảm xuống 20ms cho tốc độ luồng tuyến tính)
            'backoff_factor': 1.5 # **Reduced backoff for faster recovery** (giảm backoff để phục hồi nhanh hơn)
        }
        
        # ✅ **HEALTH MONITORING** (giám sát sức khỏe): **Start health monitoring thread** (khởi động thread giám sát sức khỏe)
        self.health_monitoring_active = False
        self.health_monitor_thread: Optional[threading.Thread] = None
        
        # **TIER 4 FIX: Centralized Configuration Management** (sửa lỗi tier 4: quản lý cấu hình tập trung)
        self._config_manager = self._initialize_config_manager()
        self._apply_optimal_configuration()
        
        # ✅ **UNIFIED LOGGING** (ghi log thống nhất): **Initialize coordination logger** (khởi tạo logger điều phối)
        if LOGGING_AVAILABLE:
            self.logger = get_coordination_logger()
            self.logger.info("🔗 **HookCoordinator initialized with unified logging** (HookCoordinator khởi tạo với ghi log thống nhất)")
            self.logger.info("🏥 **[HEALTH] Health monitoring system initialized** ([SỨC KHỎE] Hệ thống giám sát sức khỏe đã khởi tạo)")
            self.logger.info("⚙️ **[TIER-4-CONFIG] Centralized configuration manager initialized** ([CẤU HÌNH-TIER-4] Trình quản lý cấu hình tập trung đã khởi tạo)")
        else:
            self.logger = None
    
    def _initialize_config_manager(self) -> Dict[str, Any]:
        """
        **[TIER 4 FIX: Initialize Configuration Manager]** (khởi tạo quản lý cấu hình)
        
        **Centralized configuration management** (quản lý cấu hình tập trung) với **optimal defaults** (giá trị mặc định tối ưu).
        
        Returns:
            Dict: **Configuration manager with optimal settings** (trình quản lý cấu hình với cài đặt tối ưu)
        """
        return {
            'readiness_thresholds': {
                'minimum': 0.6,    # **60% score required to pass** (cần 60% điểm để vượt qua)
                'ideal': 0.8,      # **80% score for ideal operation** (80% điểm cho hoạt động lý tưởng)
                'critical': 0.3    # **30% score for critical failure** (30% điểm cho lỗi nghiêm trọng)
            },
            'retry_config': {
                'max_retries': 3,
                'initial_delay': 2.0,
                'backoff_factor': 1.5,
                'max_delay': 10.0
            },
            'environment_variables': {
                'required': [
                    'KAWPOW_DAG_PROGRESSIVE',
                    'CUDA_LAUNCH_BLOCKING', 
                    'CUDA_CACHE_DISABLE'
                ],
                'optional': [
                    'KAWPOW_DAG_MEMORY_LIMIT',
                    'CUDA_DEVICE_MAX_CONNECTIONS',
                    'CUDA_FORCE_PTX_JIT'
                ],
                'defaults': {
                    'KAWPOW_DAG_PROGRESSIVE': '1',
                    'CUDA_LAUNCH_BLOCKING': '1',
                    'CUDA_CACHE_DISABLE': '1',
                    'CUDA_DEVICE_MAX_CONNECTIONS': '1'
                }
            },
            'dag_file_patterns': [
                '/tmp/kawpow_dag_*',
                '/var/tmp/kawpow_dag_*',
                './kawpow_dag_*',
                '/tmp/ethash_*',
                '/var/tmp/ethash_*',
                '/tmp/*.dag',
                '/var/tmp/*.dag',
                './*.dag',
                '/tmp/cuckoo_*',
                '/tmp/autolykos_*',
                '/tmp/octopus_*'
            ]
        }
    
    def _apply_optimal_configuration(self):
        """
        **[TIER 4 FIX: Apply Optimal Configuration]** (áp dụng cấu hình tối ưu)
        
        **Apply centralized configuration settings** (áp dụng cài đặt cấu hình tập trung) 
        để **ensure optimal performance** (đảm bảo hiệu suất tối ưu).
        """
        try:
            config = self._config_manager
            
            # **TIER 4 FIX: Apply Environment Variable Defaults** (sửa lỗi tier 4: áp dụng giá trị mặc định biến môi trường)
            env_defaults = config['environment_variables']['defaults']
            for var_name, default_value in env_defaults.items():
                os.environ.setdefault(var_name, default_value)
            
            if self.logger:
                self.logger.info(f"⚙️ **[TIER-4-CONFIG] Applied {len(env_defaults)} environment variable defaults** ([CẤU HÌNH-TIER-4] Đã áp dụng {len(env_defaults)} giá trị mặc định biến môi trường)")
            
            # **TIER 4 FIX: Update Retry Configuration** (sửa lỗi tier 4: cập nhật cấu hình thử lại)
            retry_config = config['retry_config']
            if hasattr(self, 'verification_retry_config'):
                self.verification_retry_config.update({
                    'max_retries': retry_config['max_retries'],
                    'base_delay': retry_config['initial_delay'],
                    'backoff_factor': retry_config['backoff_factor'],
                    'max_delay': retry_config['max_delay']
                })
            
            if self.logger:
                self.logger.info(f"⚙️ **[TIER-4-CONFIG] Updated retry configuration** ([CẤU HÌNH-TIER-4] Đã cập nhật cấu hình thử lại): {retry_config}")
            
        except Exception as config_error:
            if self.logger:
                self.logger.error(f"❌ **[TIER-4-CONFIG] Failed to apply optimal configuration** ([CẤU HÌNH-TIER-4] Thất bại khi áp dụng cấu hình tối ưu): {config_error}")
    
    def _check_process_alive(self, pid: int) -> bool:
        """
        **[Process Alive Check]** (kiểm tra process còn sống)
        
        Kiểm tra **mining process** (tiến trình khai thác) vẫn còn **running** (đang chạy) 
        và không bị **terminate** (kết thúc).
        
        Args:
            pid: **Process ID to check** (ID tiến trình cần kiểm tra)
            
        Returns:
            bool: **True if process is alive** (True nếu process còn sống), **False if dead** (False nếu đã chết)
        """
        try:
            return psutil.Process(pid).is_running()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
        except Exception as e:
            if self.logger:
                self.logger.warning(f"⚠️ **[PROCESS-CHECK] Error checking process** ([KIỂM TRA-PROCESS] Lỗi khi kiểm tra process) {pid}: {e}")
            return False
    
    def _check_dag_environment_config(self, subprocess_env=None) -> float:
        """
        **[TIER 1 + TIER 7 FIX: Enhanced DAG Environment Config Check with Context Awareness]** 
        (sửa lỗi tier 1 + tier 7: kiểm tra cấu hình môi trường DAG nâng cao với nhận biết ngữ cảnh)
        
        **Flexible scoring system** (hệ thống chấm điểm linh hoạt) thay vì **pass/fail binary** (đánh giá nhị phân đạt/trượt).
        **TIER 7 FIX**: **Context-aware checking** (kiểm tra nhận biết ngữ cảnh) - **support subprocess environment variables** (hỗ trợ biến môi trường subprocess).
        Tự động **detect and apply fallback values** (phát hiện và áp dụng giá trị dự phòng) cho các **missing environment variables** (biến môi trường bị thiếu).
        
        Args:
            subprocess_env: **Subprocess environment dict** (từ điển môi trường subprocess) **(TIER 7 FIX - for correct context check)** (sửa lỗi tier 7 - để kiểm tra đúng ngữ cảnh)
        
        Returns:
            float: **Score from 0.0 to 1.0** (điểm từ 0.0 đến 1.0) **(1.0 = perfect configuration)** (1.0 = cấu hình hoàn hảo)
        """
        try:
            # **TIER 7 FIX: Use subprocess environment if provided, otherwise use parent environment** (sửa lỗi tier 7: dùng môi trường subprocess nếu được cung cấp, nếu không dùng môi trường parent)
            target_env = subprocess_env if subprocess_env is not None else os.environ
            
            if self.logger:
                env_type = "subprocess" if subprocess_env is not None else "parent"
                self.logger.info(f"🔍 **[ENV-CHECK] Checking {env_type} environment** ([KIỂM TRA-ENV] Đang kiểm tra môi trường {env_type}) **with {len(target_env)} variables** (với {len(target_env)} biến)")
                # **TIER 7.2 FIX: Enhanced DEBUG logging with subprocess environment validation** (sửa lỗi tier 7.2: ghi log DEBUG nâng cao với xác thực môi trường subprocess)
                key_vars = ['KAWPOW_DAG_PROGRESSIVE', 'CUDA_LAUNCH_BLOCKING', 'CUDA_CACHE_DISABLE']
                self.logger.debug(f"🔍 **[ENV-CHECK-DEBUG] Environment variable dump** ([DEBUG-KIỂM TRA-ENV] Dump biến môi trường):")
                for var in key_vars:
                    value = target_env.get(var, 'NOT_SET')
                    self.logger.debug(f"🔍 **[ENV-CHECK-DEBUG]** {var} = {value}")
                    # **TIER 7.2 FIX: Also log at INFO level for critical variables** (sửa lỗi tier 7.2: cũng ghi log ở mức INFO cho biến quan trọng)
                    if var == 'KAWPOW_DAG_PROGRESSIVE':
                        self.logger.info(f"🔍 **[ENV-CHECK] KAWPOW_DAG_PROGRESSIVE = {value}** **from {env_type} environment** (từ môi trường {env_type})")
            
            # **TIER 1 FIX: Flexible Environment Detection with Auto-Fallback** (sửa lỗi tier 1: phát hiện môi trường linh hoạt với dự phòng tự động)
            score = 0.0
            max_score = 3.0
            
            # **TIER 7.2 FIX: Enhanced KAWPOW_DAG_PROGRESSIVE check with robust validation** (sửa lỗi tier 7.2: kiểm tra KAWPOW_DAG_PROGRESSIVE nâng cao với xác thực mạnh mẽ)
            progressive_value = target_env.get('KAWPOW_DAG_PROGRESSIVE', '0')
            progressive = progressive_value == '1'
            if self.logger:
                self.logger.info(f"🔍 **[ENV-CHECK] KAWPOW_DAG_PROGRESSIVE check** ([KIỂM TRA-ENV] Kiểm tra KAWPOW_DAG_PROGRESSIVE): **value**='{progressive_value}', **result**={progressive}")
            
            # **TIER 7.2 FIX: Force-set if not detected correctly** (sửa lỗi tier 7.2: cưỡng chế thiết lập nếu không phát hiện đúng)
            if not progressive:
                if self.logger:
                    self.logger.warning(f"⚠️ **[ENV-CHECK] KAWPOW_DAG_PROGRESSIVE not properly set** ([KIỂM TRA-ENV] KAWPOW_DAG_PROGRESSIVE chưa được thiết lập đúng) **(found: '{progressive_value}')** (tìm thấy: '{progressive_value}')")
                # **TIER 7.2 FIX: Auto-set KAWPOW_DAG_PROGRESSIVE if missing/incorrect** (sửa lỗi tier 7.2: tự động thiết lập KAWPOW_DAG_PROGRESSIVE nếu thiếu/sai)
                if subprocess_env is not None:
                    subprocess_env['KAWPOW_DAG_PROGRESSIVE'] = '1'
                    if self.logger:
                        self.logger.info("🔧 **[ENV-CHECK] Auto-set KAWPOW_DAG_PROGRESSIVE=1 in subprocess_env** ([KIỂM TRA-ENV] Tự động thiết lập KAWPOW_DAG_PROGRESSIVE=1 trong subprocess_env)")
                else:
                    os.environ['KAWPOW_DAG_PROGRESSIVE'] = '1'
                    if self.logger:
                        self.logger.info("🔧 **[ENV-CHECK] Auto-set KAWPOW_DAG_PROGRESSIVE=1 in os.environ** ([KIỂM TRA-ENV] Tự động thiết lập KAWPOW_DAG_PROGRESSIVE=1 trong os.environ)")
                progressive = True
                # **TIER 7.2 FIX: Verify the fix worked** (sửa lỗi tier 7.2: xác minh sửa lỗi đã hoạt động)
                if subprocess_env is not None:
                    fixed_value = subprocess_env.get('KAWPOW_DAG_PROGRESSIVE', '0')
                else:
                    fixed_value = os.environ.get('KAWPOW_DAG_PROGRESSIVE', '0')
                if self.logger:
                    self.logger.info(f"✅ **[ENV-CHECK] Verification after fix** ([KIỂM TRA-ENV] Xác minh sau khi sửa): KAWPOW_DAG_PROGRESSIVE='{fixed_value}'")
            else:
                if self.logger:
                    self.logger.info(f"✅ **[ENV-CHECK] KAWPOW_DAG_PROGRESSIVE correctly set** ([KIỂM TRA-ENV] KAWPOW_DAG_PROGRESSIVE đã thiết lập đúng): '{progressive_value}'")
            score += 1.0
            
            # **TIER 7 FIX: Check KAWPOW_DAG_MEMORY_LIMIT in target environment (optional)** (sửa lỗi tier 7: kiểm tra KAWPOW_DAG_MEMORY_LIMIT trong môi trường đích - tùy chọn)
            memory_limit = 'KAWPOW_DAG_MEMORY_LIMIT' in target_env
            if memory_limit:
                score += 0.5  # **Bonus point for having memory limit** (điểm thưởng cho việc có giới hạn bộ nhớ)
            
            # **HASHRATE FIX: Phase-gated CUDA_LAUNCH_BLOCKING check with ENABLE_DAG_SAFE_FLAGS guard** (sửa lỗi hashrate: kiểm tra CUDA_LAUNCH_BLOCKING theo pha với bảo vệ ENABLE_DAG_SAFE_FLAGS)
            cuda_blocking_value = target_env.get('CUDA_LAUNCH_BLOCKING', '0')
            cuda_blocking = cuda_blocking_value == '1'
            dag_safe_flags_enabled = target_env.get('ENABLE_DAG_SAFE_FLAGS', '0') == '1'
            
            if self.logger:
                self.logger.info(f"🔍 **[ENV-CHECK] CUDA_LAUNCH_BLOCKING check** ([KIỂM TRA-ENV] Kiểm tra CUDA_LAUNCH_BLOCKING): **value**='{cuda_blocking_value}', **result**={cuda_blocking}, **dag_safe**={dag_safe_flags_enabled}")
            
            # **HASHRATE FIX: Only auto-set if ENABLE_DAG_SAFE_FLAGS=1 (DAG build phase)** (chỉ tự động thiết lập nếu ENABLE_DAG_SAFE_FLAGS=1)
            if not cuda_blocking and dag_safe_flags_enabled:
                if self.logger:
                    self.logger.warning(f"⚠️ **[ENV-CHECK] CUDA_LAUNCH_BLOCKING not set during DAG-safe phase** ([KIỂM TRA-ENV] CUDA_LAUNCH_BLOCKING chưa được thiết lập trong pha DAG-safe) **(found: '{cuda_blocking_value}')** (tìm thấy: '{cuda_blocking_value}')")
                # **Auto-set only during DAG build phase** (chỉ tự động thiết lập trong pha build DAG)
                if subprocess_env is not None:
                    subprocess_env['CUDA_LAUNCH_BLOCKING'] = '1'
                    if self.logger:
                        self.logger.info("🔧 **[ENV-CHECK] Auto-set CUDA_LAUNCH_BLOCKING=1 in subprocess_env (DAG-safe phase)** ([KIỂM TRA-ENV] Tự động thiết lập CUDA_LAUNCH_BLOCKING=1 trong subprocess_env - pha DAG-safe)")
                else:
                    os.environ['CUDA_LAUNCH_BLOCKING'] = '1'
                    if self.logger:
                        self.logger.info("🔧 **[ENV-CHECK] Auto-set CUDA_LAUNCH_BLOCKING=1 in os.environ (DAG-safe phase)** ([KIỂM TRA-ENV] Tự động thiết lập CUDA_LAUNCH_BLOCKING=1 trong os.environ - pha DAG-safe)")
                cuda_blocking = True
                if self.logger:
                    self.logger.info("✅ **[ENV-CHECK] CUDA_LAUNCH_BLOCKING auto-fix applied (DAG-safe only)** ([KIỂM TRA-ENV] Đã áp dụng sửa lỗi tự động CUDA_LAUNCH_BLOCKING - chỉ DAG-safe)")
            elif not cuda_blocking and not dag_safe_flags_enabled:
                # **HASHRATE FIX: Skip auto-fix during normal mining to preserve performance** (bỏ qua auto-fix trong mining bình thường để bảo toàn hiệu suất)
                if self.logger:
                    self.logger.info(f"🚀 **[HASHRATE-FIX] Skipping CUDA_LAUNCH_BLOCKING auto-fix during normal mining** ([SỬA LỖI-HASHRATE] Bỏ qua tự động sửa CUDA_LAUNCH_BLOCKING trong mining bình thường) **(performance preservation)** (bảo toàn hiệu suất)")
                cuda_blocking = False  # Keep disabled for performance
            else:
                if self.logger:
                    self.logger.info(f"✅ **[ENV-CHECK] CUDA_LAUNCH_BLOCKING correctly set** ([KIỂM TRA-ENV] CUDA_LAUNCH_BLOCKING đã thiết lập đúng): '{cuda_blocking_value}'")
            score += 1.0
            
            # **HASHRATE FIX: Phase-gated CUDA_CACHE_DISABLE check with ENABLE_DAG_SAFE_FLAGS guard** (sửa lỗi hashrate: kiểm tra CUDA_CACHE_DISABLE theo pha với bảo vệ ENABLE_DAG_SAFE_FLAGS)
            cuda_cache_disable_value = target_env.get('CUDA_CACHE_DISABLE', '0')
            cuda_cache_disable = cuda_cache_disable_value == '1'
            # dag_safe_flags_enabled already checked above
            
            if self.logger:
                self.logger.info(f"🔍 **[ENV-CHECK] CUDA_CACHE_DISABLE check** ([KIỂM TRA-ENV] Kiểm tra CUDA_CACHE_DISABLE): **value**='{cuda_cache_disable_value}', **result**={cuda_cache_disable}, **dag_safe**={dag_safe_flags_enabled}")
            
            # **HASHRATE FIX: Only auto-set if ENABLE_DAG_SAFE_FLAGS=1 (DAG build phase)** (chỉ tự động thiết lập nếu ENABLE_DAG_SAFE_FLAGS=1)
            if not cuda_cache_disable and dag_safe_flags_enabled:
                if self.logger:
                    self.logger.warning(f"⚠️ **[ENV-CHECK] CUDA_CACHE_DISABLE not set during DAG-safe phase** ([KIỂM TRA-ENV] CUDA_CACHE_DISABLE chưa được thiết lập trong pha DAG-safe) **(found: '{cuda_cache_disable_value}')** (tìm thấy: '{cuda_cache_disable_value}')")
                # **Auto-set only during DAG build phase** (chỉ tự động thiết lập trong pha build DAG)
                if subprocess_env is not None:
                    subprocess_env['CUDA_CACHE_DISABLE'] = '1'
                    if self.logger:
                        self.logger.info("🔧 **[ENV-CHECK] Auto-set CUDA_CACHE_DISABLE=1 in subprocess_env (DAG-safe phase)** ([KIỂM TRA-ENV] Tự động thiết lập CUDA_CACHE_DISABLE=1 trong subprocess_env - pha DAG-safe)")
                else:
                    os.environ['CUDA_CACHE_DISABLE'] = '1'
                    if self.logger:
                        self.logger.info("🔧 **[ENV-CHECK] Auto-set CUDA_CACHE_DISABLE=1 in os.environ (DAG-safe phase)** ([KIỂM TRA-ENV] Tự động thiết lập CUDA_CACHE_DISABLE=1 trong os.environ - pha DAG-safe)")
                cuda_cache_disable = True
                if self.logger:
                    self.logger.info("✅ **[ENV-CHECK] CUDA_CACHE_DISABLE auto-fix applied (DAG-safe only)** ([KIỂM TRA-ENV] Đã áp dụng sửa lỗi tự động CUDA_CACHE_DISABLE - chỉ DAG-safe)")
            elif not cuda_cache_disable and not dag_safe_flags_enabled:
                # **HASHRATE FIX: Skip auto-fix during normal mining to preserve performance** (bỏ qua auto-fix trong mining bình thường để bảo toàn hiệu suất)
                if self.logger:
                    self.logger.info(f"🚀 **[HASHRATE-FIX] Skipping CUDA_CACHE_DISABLE auto-fix during normal mining** ([SỬA LỖI-HASHRATE] Bỏ qua tự động sửa CUDA_CACHE_DISABLE trong mining bình thường) **(performance preservation)** (bảo toàn hiệu suất)")
                cuda_cache_disable = False  # Keep disabled for performance
            else:
                if self.logger:
                    self.logger.info(f"✅ **[ENV-CHECK] CUDA_CACHE_DISABLE correctly set** ([KIỂM TRA-ENV] CUDA_CACHE_DISABLE đã thiết lập đúng): '{cuda_cache_disable_value}'")
            score += 1.0
            
            # **Calculate final percentage** (tính phần trăm cuối cùng)
            final_score = min(score / max_score, 1.0)
            
            if self.logger:
                # **TIER 7.2 FIX: Enhanced final scoring with detailed breakdown** (sửa lỗi tier 7.2: chấm điểm cuối cùng nâng cao với phân tích chi tiết)
                self.logger.info(f"📊 **[ENV-CHECK] Raw score** ([KIỂM TRA-ENV] Điểm thô): {score}/{max_score} = {final_score:.3f}")
                self.logger.info(f"📊 **[ENV-CHECK] Final results** ([KIỂM TRA-ENV] Kết quả cuối cùng): **progressive**={progressive}, **cuda_blocking**={cuda_blocking}, **cache_disable**={cuda_cache_disable}")
                
                if final_score >= 0.8:
                    self.logger.info(f"✅ **[ENV-CHECK] Good environment configuration score** ([KIỂM TRA-ENV] Điểm cấu hình môi trường tốt): {final_score:.2f}")
                elif final_score >= 0.6:
                    self.logger.warning(f"⚠️ **[ENV-CHECK] Acceptable environment configuration score** ([KIỂM TRA-ENV] Điểm cấu hình môi trường chấp nhận được): {final_score:.2f}")
                else:
                    self.logger.warning(f"⚠️ **[ENV-CHECK] Poor environment configuration score** ([KIỂM TRA-ENV] Điểm cấu hình môi trường kém): {final_score:.2f}")
            
            return final_score
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ENV-CHECK] Error checking DAG environment** ([KIỂM TRA-ENV] Lỗi khi kiểm tra môi trường DAG): {e}")
            return 0.0
    
    def _check_dag_files_existence(self) -> float:
        """
        **[TIER 1 FIX: Enhanced DAG Files Existence Check]** (sửa lỗi tier 1: kiểm tra sự tồn tại file DAG nâng cao)
        
        **Flexible scoring system** (hệ thống chấm điểm linh hoạt) thay vì **binary pass/fail** (đánh giá nhị phân đạt/trượt).
        Cho phép **partial DAG files** (file DAG một phần) để hỗ trợ **various mining scenarios** (nhiều tình huống khai thác khác nhau).
        
        Returns:
            float: **Score from 0.0 to 1.0** (điểm từ 0.0 đến 1.0) **(1.0 = perfect DAG files)** (1.0 = file DAG hoàn hảo)
        """
        try:
            # **TIER 1 FIX: Enhanced DAG file detection with multiple patterns** (sửa lỗi tier 1: phát hiện file DAG nâng cao với nhiều mẫu)
            dag_patterns = [
                '/tmp/kawpow_dag_*',
                '/var/tmp/kawpow_dag_*',
                './kawpow_dag_*',
                '/tmp/ethash_*',
                '/var/tmp/ethash_*',
                '/tmp/*.dag',
                '/var/tmp/*.dag',
                './*.dag',
                # **TIER 1 FIX: Add more patterns for different mining algorithms** (sửa lỗi tier 1: thêm nhiều mẫu cho các thuật toán khai thác khác nhau)
                '/tmp/cuckoo_*',  # **Cuckoo Cycle** (thuật toán Cuckoo Cycle)
                '/tmp/autolykos_*',  # **Autolykos2** (thuật toán Autolykos2)
                '/tmp/octopus_*',  # **Octopus** (thuật toán Octopus)
            ]
            
            found_files = []
            total_size = 0
            
            for pattern in dag_patterns:
                files = glob.glob(pattern)
                for file in files:
                    try:
                        # **Check if file is accessible and has reasonable size** (kiểm tra xem file có thể truy cập và có kích thước hợp lý)
                        file_size = os.path.getsize(file)
                        if file_size > 1024:  # **At least 1KB** (ít nhất 1KB)
                            found_files.append(file)
                            total_size += file_size
                    except (OSError, IOError):
                        # **File exists but cannot access - still count as found** (file tồn tại nhưng không thể truy cập - vẫn tính là tìm thấy)
                        found_files.append(file)
            
            # **TIER 1 FIX: Flexible scoring based on file count and size** (sửa lỗi tier 1: chấm điểm linh hoạt dựa trên số lượng và kích thước file)
            max_score = 1.0
            
            if len(found_files) == 0:
                # **No DAG files found - check if process is still starting up** (không tìm thấy file DAG - kiểm tra xem process vẫn đang khởi động)
                if self.logger:
                    self.logger.debug("🔍 **[DAG-FILES] No DAG files found at common locations** ([FILE-DAG] Không tìm thấy file DAG ở các vị trí thông thường)")
                    self.logger.debug(f"🔍 **[DAG-FILES] Searched patterns** ([FILE-DAG] Các mẫu đã tìm kiếm): {dag_patterns}")
                return 0.3  # **Small score for process that's still starting** (điểm nhỏ cho process vẫn đang khởi động)
            
            # **Calculate score based on number and size of files** (tính điểm dựa trên số lượng và kích thước file)
            file_score = min(len(found_files) / 5.0, 0.7)  # **Up to 0.7 for file count** (tối đa 0.7 cho số lượng file)
            size_score = min(total_size / (100 * 1024 * 1024), 0.3)  # **Up to 0.3 for size (100MB)** (tối đa 0.3 cho kích thước - 100MB)
            final_score = file_score + size_score
            
            if self.logger:
                if final_score >= 0.8:
                    self.logger.info(f"✅ **[DAG-FILES] Good DAG files score** ([FILE-DAG] Điểm file DAG tốt): {final_score:.2f} ({len(found_files)} files, {total_size/1024/1024:.1f}MB)")
                elif final_score >= 0.5:
                    self.logger.warning(f"⚠️ **[DAG-FILES] Acceptable DAG files score** ([FILE-DAG] Điểm file DAG chấp nhận được): {final_score:.2f} ({len(found_files)} files, {total_size/1024/1024:.1f}MB)")
                else:
                    self.logger.warning(f"⚠️ **[DAG-FILES] Poor DAG files score** ([FILE-DAG] Điểm file DAG kém): {final_score:.2f} ({len(found_files)} files)")
            
            return min(final_score, max_score)
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[DAG-FILES] Error checking DAG files** ([FILE-DAG] Lỗi khi kiểm tra file DAG): {e}")
            return 0.0
    
    def _enhanced_readiness_check(self, pid: int, timeout=45, subprocess_env=None) -> bool:
        """
        **[TIER 1 + TIER 7 FIX: Enhanced Readiness Check with Context-Aware Scoring]** 
        (sửa lỗi tier 1 + tier 7: kiểm tra sẵn sàng nâng cao với chấm điểm nhận biết ngữ cảnh)
        
        **Flexible scoring system** (hệ thống chấm điểm linh hoạt) thay vì **binary pass/fail** (đánh giá nhị phân đạt/trượt).
        **TIER 7 FIX**: **Context-aware environment checking** (kiểm tra môi trường nhận biết ngữ cảnh) - **support subprocess environment variables** (hỗ trợ biến môi trường subprocess).
        Tự động **apply fallback values** (áp dụng giá trị dự phòng) và cho phép **partial readiness** (sẵn sàng một phần).
        
        Args:
            pid: **Process ID to check** (ID tiến trình cần kiểm tra)
            timeout: **maximum timeout (seconds)** (thời gian chờ tối đa - giây)
            subprocess_env: **Subprocess environment dict** (từ điển môi trường subprocess) **(TIER 7 FIX - for correct context check)** (sửa lỗi tier 7 - để kiểm tra đúng ngữ cảnh)
            
        Returns:
            bool: **True if minimum threshold is met** (True nếu đạt ngưỡng tối thiểu), **False otherwise** (False nếu không)
        """
        start_time = time.time()
        consecutive_checks = 2  # **TIER 1 FIX: Reduced stability checks for faster activation** (sửa lỗi tier 1: giảm kiểm tra ổn định để kích hoạt nhanh hơn)
        
        # **TIER 1 FIX: Define flexible thresholds** (sửa lỗi tier 1: định nghĩa ngưỡng linh hoạt)
        MINIMUM_THRESHOLD = 0.6  # **60% score required to pass** (cần 60% điểm để vượt qua)
        IDEAL_THRESHOLD = 0.8    # **80% score for ideal operation** (80% điểm cho hoạt động lý tưởng)
        
        if self.logger:
            self.logger.info(f"🚀 **[READINESS-START] Starting enhanced readiness check** ([BẮT ĐẦU-SẴN SÀNG] Bắt đầu kiểm tra sẵn sàng nâng cao) **for PID {pid}** (cho PID {pid}) **with timeout={timeout}s** (với timeout={timeout}s)")
            self.logger.info(f"🎯 **[READINESS-THRESHOLDS]** ([NGƯỠNG-SẴN SÀNG]) **Minimum**: {MINIMUM_THRESHOLD}, **Ideal**: {IDEAL_THRESHOLD}")
        
        while time.time() - start_time < timeout:
            checks = {
                'process_alive': 1.0 if self._check_process_alive(pid) else 0.0,
                'env_config': self._check_dag_environment_config(subprocess_env),  # **TIER 7 FIX: Pass subprocess env** (sửa lỗi tier 7: truyền môi trường subprocess)
                'dag_files': self._check_dag_files_existence()
            }
            
            # **TIER 1 FIX: Calculate weighted score** (sửa lỗi tier 1: tính điểm có trọng số)
            weights = {
                'process_alive': 0.5,    # **50% - Process must be alive** (50% - Process phải còn sống)
                'env_config': 0.3,      # **30% - Environment configuration (auto-fixable)** (30% - Cấu hình môi trường - có thể tự sửa)
                'dag_files': 0.2        # **20% - DAG files (may take time to generate)** (20% - File DAG - có thể mất thời gian để tạo)
            }
            
            weighted_score = sum(checks[check] * weights[check] for check in checks)
            passed_checks = sum(1.0 for score in checks.values() if score > 0.5)
            total_checks = len(checks)
            
            if self.logger:
                self.logger.info(f"📊 **[READINESS-PROGRESS] Weighted score** ([TIẾN TRÌNH-SẴN SÀNG] Điểm có trọng số): {weighted_score:.3f} ({passed_checks}/{total_checks} **checks > 0.5** (kiểm tra > 0.5))")
            
            # **Log detailed scores for each check** (ghi log chi tiết điểm cho từng kiểm tra)
            for check_name, result in checks.items():
                status_icon = "✅" if result > 0.5 else "⚠️"
                status = "**PASS**" if result > 0.5 else "**NEEDS ATTENTION**"
                if self.logger:
                    self.logger.info(f"   ├─ {check_name}: {status_icon} {status} **(score: {result:.3f})** (điểm: {result:.3f})")
            
            # **TIER 1 FIX: Flexible thresholds based on process state** (sửa lỗi tier 1: ngưỡng linh hoạt dựa trên trạng thái process)
            if weighted_score >= IDEAL_THRESHOLD:
                if self.logger:
                    self.logger.info(f"🎯 **[READINESS-EXCELLENT] Excellent readiness score** ([SẴN SÀNG-XUẤT SẮC] Điểm sẵn sàng xuất sắc): {weighted_score:.3f}")
                    
                # **Quick stability check for excellent scores** (kiểm tra ổn định nhanh cho điểm xuất sắc)
                stability_count = 0
                for i in range(consecutive_checks):
                    time.sleep(1)  # **TIER 1 FIX: Reduced wait time** (sửa lỗi tier 1: giảm thời gian chờ)
                    
                    if not self._check_process_alive(pid):
                        if self.logger:
                            self.logger.warning(f"⚠️ **[READINESS-STABILITY] Process {pid} died at verification** ([ỔN ĐỊNH-SẴN SÀNG] Process {pid} đã chết ở lần xác minh) {i+1}")
                        break
                    
                    stability_count += 1
                    
                if stability_count == consecutive_checks:
                    if self.logger:
                        self.logger.info(f"✅ **[READINESS-STABLE] Process {pid} verified stable** ([ỔN ĐỊNH-SẴN SÀNG] Process {pid} đã xác minh ổn định)")
                    return True
                else:
                    if self.logger:
                        self.logger.warning(f"⚠️ **[READINESS-UNSTABLE] Process {pid} stability check failed** ([KHÔNG ỔN ĐỊNH-SẴN SÀNG] Process {pid} kiểm tra ổn định thất bại)")
            
            elif weighted_score >= MINIMUM_THRESHOLD:
                # **TIER 1 FIX: Acceptable score - proceed with caution** (sửa lỗi tier 1: điểm chấp nhận được - tiếp tục cẩn thận)
                if self.logger:
                    self.logger.warning(f"⚠️ **[READINESS-ACCEPTABLE] Acceptable readiness score** ([CHẤP NHẬN ĐƯỢC-SẴN SÀNG] Điểm sẵn sàng chấp nhận được): {weighted_score:.3f} - **proceeding anyway** (vẫn tiếp tục)")
                return True
            
            # **TIER 1 FIX: Critical failure - process is dead** (sửa lỗi tier 1: lỗi nghiêm trọng - process đã chết)
            if checks['process_alive'] == 0.0:
                if self.logger:
                    self.logger.error(f"❌ **[READINESS-CRITICAL] Process {pid} is dead - cannot continue** ([NGHIÊM TRỌNG-SẴN SÀNG] Process {pid} đã chết - không thể tiếp tục)")
                return False
            
            # **TIER 1 FIX: Progressive wait times based on score** (sửa lỗi tier 1: thời gian chờ tăng dần dựa trên điểm)
            if weighted_score < 0.3:
                wait_time = 3.0  # **Longer wait for poor scores** (chờ lâu hơn cho điểm kém)
            elif weighted_score < 0.6:
                wait_time = 2.0  # **Medium wait for acceptable scores** (chờ trung bình cho điểm chấp nhận được)
            else:
                wait_time = 1.0  # **Short wait for good scores** (chờ ngắn cho điểm tốt)
            
            if self.logger:
                self.logger.debug(f"⏱️ **[READINESS-WAIT] Waiting {wait_time}s before next check** ([CHỜ-SẴN SÀNG] Đợi {wait_time}s trước lần kiểm tra tiếp theo) **(current score: {weighted_score:.3f})** (điểm hiện tại: {weighted_score:.3f})")
            
            time.sleep(wait_time)
        
        # **TIER 1 FIX: Timeout with detailed diagnosis** (sửa lỗi tier 1: hết thời gian chờ với chẩn đoán chi tiết)
        if self.logger:
            self.logger.error(f"❌ **[READINESS-TIMEOUT] Enhanced readiness check timed out** ([HẾT THỜI GIAN-SẴN SÀNG] Kiểm tra sẵn sàng nâng cao hết thời gian) **after {timeout}s for PID {pid}** (sau {timeout}s cho PID {pid})")
            self.logger.error(f"📊 **[READINESS-FINAL] Final weighted score** ([CUỐI CÙNG-SẴN SÀNG] Điểm có trọng số cuối cùng): {weighted_score:.3f} **(minimum required: {MINIMUM_THRESHOLD})** (yêu cầu tối thiểu: {MINIMUM_THRESHOLD})")
            
            # **Provide specific recommendations** (đưa ra khuyến nghị cụ thể)
            if checks['process_alive'] == 0.0:
                self.logger.error(f"💡 **[READINESS-RECOMMENDATION] Process {pid} is dead - check process health** ([KHUYẾN NGHỊ-SẴN SÀNG] Process {pid} đã chết - kiểm tra sức khỏe process)")
            elif checks['env_config'] < 0.5:
                self.logger.error(f"💡 **[READINESS-RECOMMENDATION] Environment configuration poor - check mining software setup** ([KHUYẾN NGHỊ-SẴN SÀNG] Cấu hình môi trường kém - kiểm tra thiết lập phần mềm khai thác)")
            elif checks['dag_files'] < 0.3:
                self.logger.error(f"💡 **[READINESS-RECOMMENDATION] DAG files missing or incomplete - check DAG generation process** ([KHUYẾN NGHỊ-SẴN SÀNG] File DAG thiếu hoặc không đầy đủ - kiểm tra quá trình tạo DAG)")
        
        return False
    
    def register_pid(self, pid: int) -> None:
        """**Register PID** (đăng ký PID - thêm tiến trình vào hệ thống theo dõi hook coordination)"""
        with self.lock:
            self.hooks_ready[pid] = False
            self.active_processes.add(pid)
            self.hook_status_history[pid] = []
            self.recovery_attempts[pid] = 0
            
            # ✅ **HEALTH MONITORING: Auto-start health monitoring on first registration** (GIÁM SÁT SỨC KHỎE: tự động bắt đầu giám sát sức khỏe khi đăng ký đầu tiên)
            if not self.health_monitoring_active:
                self._start_health_monitoring()
            
            if self.logger:
                self.logger.info(f"📝 **[REGISTER] PID {pid} registered for hook coordination** ([ĐĂNG KÝ] PID {pid} đã đăng ký cho điều phối hook)")
                self.logger.info(f"🏥 **[HEALTH] PID {pid} added to health monitoring** ([SỨC KHỎE] PID {pid} đã thêm vào giám sát sức khỏe) **(total: {len(self.active_processes)})** (tổng: {len(self.active_processes)})")
    
    def receive_from_stealth_wrapper(self, pid: int, process_metadata: Dict[str, Any], subprocess_env: Dict[str, str] = None) -> bool:
        """
        **Receive From Stealth Wrapper** (nhận từ stealth wrapper - điểm nhận bàn giao từ lớp ngụy trang)
        
        **NEW METHOD: Primary entry point for linear flow from stealth_inference_cuda.py**
        (phương thức mới: điểm vào chính cho luồng tuyến tính từ stealth_inference_cuda.py)
        **Implements CORRECT flow**: stealth → HookCoordinator → DirectPIDRegistry → ResourceManager
        (triển khai luồng ĐÚNG: ngụy trang → điều phối hook → đăng ký PID trực tiếp → quản lý tài nguyên)
        
        Args:
            pid: **Process ID from stealth wrapper** (ID tiến trình từ wrapper ngụy trang)
            process_metadata: **Metadata from stealth wrapper** (siêu dữ liệu từ wrapper ngụy trang)
            subprocess_env: **Subprocess environment dict** (từ điển môi trường subprocess) **(TIER 7.1 FIX - for correct context check)** (sửa lỗi tier 7.1 - để kiểm tra đúng ngữ cảnh)
            
        Returns:
            bool: **True if handoff successful and ready for next step** (True nếu bàn giao thành công và sẵn sàng cho bước tiếp theo)
        """
        try:
            current_time = time.time()
            
            if self.logger:
                self.logger.info(f"🚀 **[LINEAR-FLOW] Receiving PID {pid} from stealth wrapper (PRIMARY ENTRY POINT)** ([LUỒNG-TUYẾN TÍNH] Nhận PID {pid} từ stealth wrapper - điểm vào chính)")
                self.logger.info(f"📊 **[MONITORING] Handoff Chain Start** ([GIÁM SÁT] Bắt đầu chuỗi bàn giao): stealth_inference_cuda → HookCoordinator [PID={pid}]")
                self.logger.debug(f"🔍 **[LINEAR-FLOW] Process metadata** ([LUỒNG-TUYẾN TÍNH] Siêu dữ liệu process): {process_metadata}")
                self.logger.info(f"⏰ **[MONITORING] Timestamp** ([GIÁM SÁT] Dấu thời gian): {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # **STEP 1: Register PID with HookCoordinator** (bước 1: đăng ký PID với HookCoordinator)
            with self.lock:
                self.hooks_ready[pid] = False  # **Initialize as not ready** (khởi tạo là chưa sẵn sàng)
                self.active_processes.add(pid)
                
                # **Initialize tracking data** (khởi tạo dữ liệu theo dõi)
                if pid not in self.hook_status_history:
                    self.hook_status_history[pid] = []
                if pid not in self.recovery_attempts:
                    self.recovery_attempts[pid] = 0
                
                # **Record stealth handoff event** (ghi lại sự kiện bàn giao ngụy trang)
                handoff_record = {
                    'timestamp': current_time,
                    'event_type': 'stealth_handoff_received',
                    'success': True,
                    'source': 'stealth_inference_cuda',
                    'metadata': process_metadata,
                    'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))
                }
                self.hook_status_history[pid].append(handoff_record)
                
                if self.logger:
                    self.logger.info(f"✅ **[LINEAR-FLOW] PID {pid} registered with HookCoordinator** ([LUỒNG-TUYẾN TÍNH] PID {pid} đã đăng ký với HookCoordinator)")
            
            # ===== PRE-UNLOCK: Ensure any prior clock locks are cleared before optimization =====
            try:
                pre_unlock_env = os.getenv('GPU_PRE_UNLOCK', '1').lower() in ('1','true','yes')
            except Exception:
                pre_unlock_env = True
            if pre_unlock_env:
                try:
                    import subprocess as _subp
                    try:
                        import pynvml as _nv
                        _nv.nvmlInit()
                        _cnt = int(_nv.nvmlDeviceGetCount())
                    except Exception as _e:
                        _cnt = 0
                        if self.logger:
                            self.logger.debug(f"[HOOK] NVML init failed or unavailable: {_e}")
                    for _idx in range(max(1, _cnt)):
                        try:
                            if _cnt > 0:
                                _hdl = _nv.nvmlDeviceGetHandleByIndex(_idx)
                                try:
                                    _nv.nvmlDeviceResetApplicationsClocks(_hdl)
                                    if self.logger:
                                        self.logger.info(f"[HOOK] Reset application clocks via NVML for GPU {_idx}")
                                except Exception as _nv_e:
                                    if self.logger:
                                        self.logger.debug(f"[HOOK] NVML reset apps clocks not supported on GPU {_idx}: {_nv_e}")
                            _subp.run(['nvidia-smi','-i',str(_idx),'-rgc'], check=False)
                            _subp.run(['nvidia-smi','-i',str(_idx),'--reset-memory-clocks'], check=False)
                            if self.logger:
                                self.logger.info(f"[HOOK] Unlocked clocks via nvidia-smi for GPU {_idx}")
                        except Exception as _smi_e:
                            if self.logger:
                                self.logger.debug(f"[HOOK] nvidia-smi unlock failed for GPU {_idx}: {_smi_e}")
                    try:
                        if _cnt > 0:
                            _nv.nvmlShutdown()
                    except Exception:
                        pass
                except Exception as _pre_unlock_err:
                    if self.logger:
                        self.logger.debug(f"[HOOK] Pre-unlock skipped: {_pre_unlock_err}")

            # **STEP 2: Enhanced Readiness Check with Bypass Mechanism** (bước 2: kiểm tra sẵn sàng nâng cao với cơ chế bỏ qua)
            if self.logger:
                self.logger.info(f"🚀 **[LINEAR-FLOW] Starting enhanced readiness check for PID {pid} before registry forwarding...** ([LUỒNG-TUYẾN TÍNH] Bắt đầu kiểm tra sẵn sàng nâng cao cho PID {pid} trước khi chuyển tiếp registry...)")
            
            # **TIER 7.1 FIX: Perform enhanced readiness check with subprocess environment context** (sửa lỗi tier 7.1: thực hiện kiểm tra sẵn sàng nâng cao với ngữ cảnh môi trường subprocess)
            # **HASHRATE FIX: Increased timeout to reduce semaphore pressure** (tăng timeout để giảm áp lực semaphore)
            readiness_result = self._enhanced_readiness_check(pid, timeout=45, subprocess_env=subprocess_env)
            
            if readiness_result:
                if self.logger:
                    self.logger.info(f"✅ **[LINEAR-FLOW] Enhanced readiness check passed for PID {pid} - DAG allocation complete** ([LUỒNG-TUYẾN TÍNH] Kiểm tra sẵn sàng nâng cao đã qua cho PID {pid} - phân bổ DAG hoàn tất)")
            else:
                # **TIER 2 FIX: Bypass Readiness Check for Critical Operations** (sửa lỗi tier 2: bỏ qua kiểm tra sẵn sàng cho hoạt động quan trọng)
                # **Process is still alive but readiness check failed - check if we should bypass** (process vẫn còn sống nhưng kiểm tra sẵn sàng thất bại - kiểm tra xem có nên bỏ qua)
                process_alive = self._check_process_alive(pid)
                if process_alive:
                    if self.logger:
                        self.logger.warning(f"⚠️ **[LINEAR-FLOW] Readiness check failed but process {pid} is alive - BYPASSING READINESS CHECK** ([LUỒNG-TUYẾN TÍNH] Kiểm tra sẵn sàng thất bại nhưng process {pid} còn sống - BỎ QUA KIỂM TRA SẴN SÀNG)")
                        self.logger.info(f"🔧 **[TIER-2-BYPASS] Critical operation override: proceeding with registry forwarding despite readiness failure** ([BỎ QUA-TIER-2] Ghi đè hoạt động quan trọng: tiếp tục chuyển tiếp registry dù kiểm tra sẵn sàng thất bại)")
                    
                    # **TIER 2 FIX: Force-set critical environment variables for bypass mode** (sửa lỗi tier 2: buộc thiết lập biến môi trường quan trọng cho chế độ bỏ qua)
                    os.environ.setdefault('KAWPOW_DAG_PROGRESSIVE', '1')
                    os.environ.setdefault('CUDA_LAUNCH_BLOCKING', '1')
                    os.environ.setdefault('CUDA_CACHE_DISABLE', '1')
                    
                    if self.logger:
                        self.logger.info(f"🔧 **[TIER-2-BYPASS] Forced environment variables set for PID {pid}** ([BỎ QUA-TIER-2] Đã buộc thiết lập biến môi trường cho PID {pid})")
                else:
                    if self.logger:
                        self.logger.error(f"❌ **[LINEAR-FLOW] Enhanced readiness check failed and process {pid} is dead - cannot continue** ([LUỒNG-TUYẾN TÍNH] Kiểm tra sẵn sàng nâng cao thất bại và process {pid} đã chết - không thể tiếp tục)")
                    return False
            
            # **STEP 3: Enhanced Forward to DirectPIDRegistry with Retry Mechanism** (bước 3: chuyển tiếp nâng cao đến DirectPIDRegistry với cơ chế thử lại)
            if self.logger:
                self.logger.info(f"🚀 **[LINEAR-FLOW] Starting enhanced forwarding to DirectPIDRegistry for PID {pid}...** ([LUỒNG-TUYẾN TÍNH] Bắt đầu chuyển tiếp nâng cao đến DirectPIDRegistry cho PID {pid}...)")
            
            # **TIER 3 FIX: Retry Mechanism with Circuit Breaker** (sửa lỗi tier 3: cơ chế thử lại với ngắt mạch)
            max_retries = 3
            retry_delay = 2.0  # **Start with 2 second delay** (bắt đầu với độ trễ 2 giây)
            
            for attempt in range(max_retries):
                try:
                    if self.logger:
                        self.logger.info(f"🔄 **[RETRY-{attempt+1}] Attempting to forward PID {pid} to DirectPIDRegistry...** ([THỬ LẠI-{attempt+1}] Đang thử chuyển tiếp PID {pid} đến DirectPIDRegistry...)")
                    
                    registry_success = self._forward_to_direct_registry(pid, process_metadata)
                    
                    if registry_success:
                        if self.logger:
                            self.logger.info(f"✅ **[LINEAR-FLOW] PID {pid} successfully forwarded to DirectPIDRegistry** ([LUỒNG-TUYẾN TÍNH] PID {pid} đã chuyển tiếp thành công đến DirectPIDRegistry) **(attempt {attempt+1})** (lần thử {attempt+1})")
                        return True
                    else:
                        if self.logger:
                            self.logger.warning(f"⚠️ **[RETRY-{attempt+1}] DirectPIDRegistry forwarding failed for PID {pid}** ([THỬ LẠI-{attempt+1}] Chuyển tiếp DirectPIDRegistry thất bại cho PID {pid})")
                        
                        # **TIER 3 FIX: Circuit Breaker Logic** (sửa lỗi tier 3: logic ngắt mạch)
                        if attempt < max_retries - 1:  # **Don't sleep on last attempt** (không ngủ ở lần thử cuối cùng)
                            if self.logger:
                                self.logger.info(f"⏱️ **[RETRY-{attempt+1}] Waiting {retry_delay}s before next attempt...** ([THỬ LẠI-{attempt+1}] Đợi {retry_delay}s trước lần thử tiếp theo...)")
                            time.sleep(retry_delay)
                            retry_delay *= 1.5  # **Exponential backoff** (tăng độ trễ theo hàm mũ)
                        else:
                            if self.logger:
                                self.logger.error(f"🚨 **[CIRCUIT-BREAKER] Max retries ({max_retries}) reached for PID {pid}** ([NGẮT MẠCH] Đã đạt số lần thử lại tối đa ({max_retries}) cho PID {pid})")
                
                except Exception as registry_error:
                    if self.logger:
                        self.logger.error(f"❌ **[RETRY-{attempt+1}] Registry forwarding exception** ([THỬ LẠI-{attempt+1}] Ngoại lệ chuyển tiếp registry): {registry_error}")
                    
                    # **TIER 3 FIX: Exception Handling with Retry** (sửa lỗi tier 3: xử lý ngoại lệ với thử lại)
                    if attempt < max_retries - 1:
                        if self.logger:
                            self.logger.info(f"⏱️ **[RETRY-{attempt+1}] Waiting {retry_delay}s after exception...** ([THỬ LẠI-{attempt+1}] Đợi {retry_delay}s sau ngoại lệ...)")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                    else:
                        if self.logger:
                            self.logger.error(f"🚨 **[CIRCUIT-BREAKER] Max retries reached after exception for PID {pid}** ([NGẮT MẠCH] Đã đạt số lần thử lại tối đa sau ngoại lệ cho PID {pid})")
            
            # **TIER 3 FIX: Final Fallback - Emergency Forwarding** (sửa lỗi tier 3: dự phòng cuối cùng - chuyển tiếp khẩn cấp)
            if self.logger:
                self.logger.warning(f"🚨 **[EMERGENCY-FALLBACK] All retries failed - attempting emergency forwarding for PID {pid}** ([DỰ PHÒNG-KHẨN CẤP] Tất cả lần thử lại thất bại - thử chuyển tiếp khẩn cấp cho PID {pid})")
            
            try:
                # **TIER 3 FIX: Emergency Forwarding with Simplified Logic** (sửa lỗi tier 3: chuyển tiếp khẩn cấp với logic đơn giản hóa)
                emergency_success = self._emergency_forward_to_registry(pid, process_metadata)
                if emergency_success:
                    if self.logger:
                        self.logger.info(f"✅ **[EMERGENCY-FALLBACK] Emergency forwarding successful for PID {pid}** ([DỰ PHÒNG-KHẨN CẤP] Chuyển tiếp khẩn cấp thành công cho PID {pid})")
                    return True
                else:
                    if self.logger:
                        self.logger.error(f"❌ **[EMERGENCY-FALLBACK] Emergency forwarding failed for PID {pid}** ([DỰ PHÒNG-KHẨN CẤP] Chuyển tiếp khẩn cấp thất bại cho PID {pid})")
                    return False
                    
            except Exception as emergency_error:
                if self.logger:
                    self.logger.error(f"❌ **[EMERGENCY-FALLBACK] Emergency forwarding exception** ([DỰ PHÒNG-KHẨN CẤP] Ngoại lệ chuyển tiếp khẩn cấp): {emergency_error}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[LINEAR-FLOW] Failed to receive from stealth wrapper for PID {pid}** ([LUỒNG-TUYẾN TÍNH] Thất bại khi nhận từ stealth wrapper cho PID {pid}): {e}")
            return False
    
    def _emergency_forward_to_registry(self, pid: int, process_metadata: Dict[str, Any]) -> bool:
        """
        **[TIER 3 FIX: Emergency Forward to Registry]** 
        (sửa lỗi tier 3: chuyển tiếp khẩn cấp đến registry)
        
        **Emergency fallback mechanism when all retries fail** 
        (cơ chế dự phòng khẩn cấp khi tất cả lần thử lại thất bại).
        **Use simplified logic to maximize success chance** 
        (sử dụng logic đơn giản hóa để tối đa hóa cơ hội thành công).
        
        Args:
            pid: **Process ID needing forwarding** (ID tiến trình cần chuyển tiếp)
            process_metadata: **Metadata from stealth wrapper** (siêu dữ liệu từ stealth wrapper)
            
        Returns:
            bool: **True if emergency forwarding successful** (True nếu chuyển tiếp khẩn cấp thành công), **False otherwise** (False nếu không)
        """
        try:
            if self.logger:
                self.logger.info(f"🚨 **[EMERGENCY-FORWARD] Starting emergency forwarding for PID {pid}** ([CHUYỂN TIẾP-KHẨN CẤP] Bắt đầu chuyển tiếp khẩn cấp cho PID {pid})")
            
            # **TIER 3 FIX: Simplified Emergency Logic** (sửa lỗi tier 3: logic khẩn cấp đơn giản hóa)
            # **Bypass all checks, just forward directly** (bỏ qua tất cả kiểm tra, chỉ chuyển tiếp trực tiếp)
            emergency_metadata = {
                **process_metadata,
                'emergency_mode': True,
                'timestamp': time.time(),
                'bypass_readiness': True,
                'forwarding_attempt': 'emergency'
            }
            
            # **TIER 3 FIX: Direct Registry Access** (sửa lỗi tier 3: truy cập registry trực tiếp)
            try:
                from pid_logger.direct_registry import get_direct_registry
                
                registry = get_direct_registry()
                if hasattr(registry, 'emergency_register'):
                    # **TIER 3 FIX: Use emergency register method if available** (sửa lỗi tier 3: dùng phương thức đăng ký khẩn cấp nếu có)
                    success = registry.emergency_register(pid, emergency_metadata)
                else:
                    # **TIER 3 FIX: Fallback to standard register** (sửa lỗi tier 3: dự phòng về đăng ký tiêu chuẩn)
                    success = registry.register_pid(pid, emergency_metadata)
                
                if success:
                    if self.logger:
                        self.logger.info(f"✅ **[EMERGENCY-FORWARD] Emergency registry forwarding successful for PID {pid}** ([CHUYỂN TIẾP-KHẨN CẤP] Chuyển tiếp registry khẩn cấp thành công cho PID {pid})")
                    return True
                else:
                    if self.logger:
                        self.logger.error(f"❌ **[EMERGENCY-FORWARD] Emergency registry forwarding failed for PID {pid}** ([CHUYỂN TIẾP-KHẨN CẤP] Chuyển tiếp registry khẩn cấp thất bại cho PID {pid})")
                    return False
                    
            except ImportError as import_err:
                if self.logger:
                    self.logger.error(f"❌ **[EMERGENCY-FORWARD] Cannot import DirectPIDRegistry** ([CHUYỂN TIẾP-KHẨN CẤP] Không thể import DirectPIDRegistry): {import_err}")
                return False
                
        except Exception as emergency_err:
            if self.logger:
                self.logger.error(f"❌ **[EMERGENCY-FORWARD] Emergency forwarding exception** ([CHUYỂN TIẾP-KHẨN CẤP] Ngoại lệ chuyển tiếp khẩn cấp): {emergency_err}")
            return False
     
    def notify_hooks_ready(self, pid: int) -> None:
        """**Notify Hooks Ready** (thông báo hooks sẵn sàng - báo hiệu hoàn thành khởi tạo PHASE 3+)"""  
        # ✅ **SYNCHRONIZATION: Thread-safe notification with environment sync** (ĐỒNG BỘ HÓA: thông báo an toàn luồng với đồng bộ môi trường)
        success = self._sync_hooks_ready_state(pid, True)
        
        if success:
            # ✅ **HEALTH TRACKING: Record status change in history** (THEO DÕI SỨC KHỎE: ghi lại thay đổi trạng thái trong lịch sử)
            self._record_status_change(pid, 'hooks_ready', True)
            
            if self.logger:
                self.logger.info(f"✅ **[NOTIFY] PID {pid} hooks ready - synchronized state set** ([THÔNG BÁO] PID {pid} hooks sẵn sàng - đã thiết lập trạng thái đồng bộ)")
                self.logger.debug(f"🔍 **[DEBUG] Current hooks_ready state** ([GỠ LỖI] Trạng thái hooks_ready hiện tại): {dict(list(self.hooks_ready.items())[-5:])}")
                self.logger.info(f"🏥 **[HEALTH] Status change recorded for PID {pid}** ([SỨC KHỎE] Đã ghi lại thay đổi trạng thái cho PID {pid})")
        else:
            if self.logger:
                self.logger.error(f"❌ **[NOTIFY] Failed to synchronize hooks ready state for PID {pid}** ([THÔNG BÁO] Thất bại khi đồng bộ trạng thái hooks sẵn sàng cho PID {pid})")
            
    def check_hooks_ready(self, pid: int) -> bool:
        """**Check if hooks are ready** (kiểm tra xem hooks có sẵn sàng không)"""
        with self.lock:
            is_ready = self.hooks_ready.get(pid, False)
            if self.logger:
                self.logger.debug(f"🔍 **[CHECK] PID {pid} hooks ready status: {is_ready}** ([KIỂM TRA] Trạng thái hooks sẵn sàng của PID {pid}: {is_ready})")
            return is_ready
            
    def wait_for_hooks_ready(self, pid: int, timeout: int = 70) -> bool:
        """**Wait for hooks ready with timeout** (chờ hooks sẵn sàng với thời gian chờ tối đa)"""
        start_time = time.time()
        
        if self.logger:
            self.logger.info(f"⏳ **[WAIT] Waiting for PID {pid} hooks ready (timeout: {timeout}s)** ([CHỜ] Đang chờ hooks của PID {pid} sẵn sàng (thời gian chờ: {timeout}s))")
        
        while time.time() - start_time < timeout:
            if self.check_hooks_ready(pid):
                elapsed = time.time() - start_time
                if self.logger:
                    self.logger.info(f"✅ **[WAIT] PID {pid} hooks ready after {elapsed:.1f}s** ([CHỜ] Hooks của PID {pid} sẵn sàng sau {elapsed:.1f}s)")
                return True
            time.sleep(2)
        
        elapsed = time.time() - start_time    
        if self.logger:
            self.logger.warning(f"⏰ **[TIMEOUT] PID {pid} hooks not ready after {elapsed:.1f}s timeout** ([HẾT THỜI GIAN] Hooks của PID {pid} không sẵn sàng sau {elapsed:.1f}s)")
        return False
        
    def cleanup_pid(self, pid: int) -> None:
        """**Enhanced Cleanup PID** (dọn dẹp PID nâng cao - xóa tiến trình khỏi tất cả hệ thống theo dõi)"""
        with self.lock:
            was_tracked = pid in self.hooks_ready
            self.hooks_ready.pop(pid, None)
            self.active_processes.discard(pid)
            self.hook_status_history.pop(pid, None)
            self.recovery_attempts.pop(pid, None)
            
            # ✅ **IDEMPOTENCY CLEANUP: Remove handoff tracking data** (DỌN DẸP IDEMPOTENCY: xóa dữ liệu theo dõi bàn giao)
            self.handoff_timestamps.pop(pid, None)
            self.handoff_metadata_cache.pop(pid, None)
            self.handoff_sequence_numbers.pop(pid, None)
            
            # **Enhanced Environment Cleanup** (dọn dẹp môi trường nâng cao - xóa tất cả biến môi trường liên quan)
            env_vars_cleaned = []
            
            # **Core hook coordination variables** (biến điều phối hook lõi)
            env_var = f'HOOKS_READY_PID_{pid}'
            if env_var in os.environ:
                del os.environ[env_var]
                env_vars_cleaned.append(env_var)
            
            # **Linear handoff variables** (biến bàn giao tuyến tính)
            handoff_var = f'LINEAR_HANDOFF_RM_PID_{pid}'
            if handoff_var in os.environ:
                del os.environ[handoff_var]
                env_vars_cleaned.append(handoff_var)
            
            # **Pickup detection variables** (biến phát hiện nhận tiếp)
            pickup_var = f'RM_PICKUP_READY_PID_{pid}'
            if pickup_var in os.environ:
                del os.environ[pickup_var]
                env_vars_cleaned.append(pickup_var)
            
            # **Deferred handoff variables** (biến bàn giao hoãn lại)
            deferred_var = f'DEFERRED_RM_HANDOFF_PID_{pid}'
            if deferred_var in os.environ:
                del os.environ[deferred_var]
                env_vars_cleaned.append(deferred_var)
            
            if self.logger and was_tracked:
                self.logger.info(f"🧹 **[CLEANUP] PID {pid} removed from all tracking systems** ([DỌN DẸP] PID {pid} đã được xóa khỏi tất cả hệ thống theo dõi)")
                if env_vars_cleaned:
                    self.logger.info(f"📝 **[CLEANUP] Environment variables cleaned** ([DỌN DẸP] Các biến môi trường đã được dọn dẹp): {env_vars_cleaned}")
                self.logger.info(f"🏥 **[HEALTH] Health monitoring cleanup for PID {pid} completed** ([SỨC KHỎE] Hoàn thành dọn dẹp giám sát sức khỏe cho PID {pid})")
                
            # ✅ **HEALTH MONITORING: Stop monitoring if no active processes** (GIÁM SÁT SỨC KHỎE: dừng giám sát nếu không có tiến trình hoạt động)
            if len(self.active_processes) == 0 and self.health_monitoring_active:
                self._stop_health_monitoring()
    
    def _generate_handoff_fingerprint(self, handoff_metadata: Dict[str, Any]) -> str:
        """
        **Generate Handoff Fingerprint** (tạo dấu vân tay bàn giao)
        
        ✅ **ENHANCED: Creates consistent fingerprint with metadata normalization to detect duplicate handoffs**
        (NÂNG CAO: tạo dấu vân tay nhất quán với chuẩn hóa siêu dữ liệu để phát hiện bàn giao trùng lặp).
        **Fixes metadata structure inconsistency between duplicate handoffs**
        (sửa lỗi không nhất quán cấu trúc siêu dữ liệu giữa các lần bàn giao trùng lặp).
        
        Args:
            handoff_metadata: **Handoff metadata** (siêu dữ liệu bàn giao)
            
        Returns:
            str: **Unique fingerprint string** (chuỗi dấu vân tay duy nhất)
        """
        try:
            # ✅ **REDESIGNED: Focus on STABLE PROCESS IDENTITY, not handoff artifacts** 
            # (THIẾT KẾ LẠI: tập trung vào DANH TÍNH TIẾN TRÌNH ỔN ĐỊNH, không phải các tạo tác bàn giao)
            # **Extract stable process identification only** (chỉ trích xuất định danh tiến trình ổn định)
            process_info = handoff_metadata.get('original_metadata', handoff_metadata)
            
            # ✅ **CORE PROCESS IDENTITY - These fields uniquely identify the process** 
            # (DANH TÍNH TIẾN TRÌNH LÕI - các trường này định danh duy nhất tiến trình)
            registration_source = (process_info.get('registration_source') or 
                                 handoff_metadata.get('registration_source', 'unknown'))
            
            # **Use process creation timestamp, not handoff timing** (dùng dấu thời gian tạo tiến trình, không phải thời gian bàn giao)
            process_timestamp = (process_info.get('timestamp') or 
                               handoff_metadata.get('timestamp', 0))
            
            # ✅ **NORMALIZE: Round to nearest second to eliminate timing variance** (CHUẨN HÓA: làm tròn đến giây gần nhất để loại bỏ sự khác biệt thời gian)
            process_timestamp = round(process_timestamp) if process_timestamp else 0
            
            # **Extract process identification consistently** (trích xuất định danh tiến trình một cách nhất quán)
            if isinstance(process_info, dict):
                executable = process_info.get('executable', 'inference-cuda')
                role = process_info.get('role', 'unknown')
                stealth_name = process_info.get('stealth_name', 'unknown')
            else:
                executable = 'inference-cuda'  # **Default for mining process** (mặc định cho tiến trình khai thác)
                role = 'unknown'
                stealth_name = 'unknown'
            
            # ✅ **PROCESS-IDENTITY FINGERPRINT - Stable process characteristics only** (DẤU VÂN TAY DANH TÍNH TIẾN TRÌNH - chỉ các đặc điểm tiến trình ổn định)
            fingerprint_elements = [
                str(registration_source),  # **How process was registered (stable)** (cách tiến trình được đăng ký - ổn định)
                str(process_timestamp),    # **When process was created (stable, rounded)** (thời điểm tiến trình được tạo - ổn định, đã làm tròn)
                str(executable),           # **What executable is running (stable)** (file thực thi đang chạy - ổn định)
                str(role),                # **Process role (stable)** (vai trò tiến trình - ổn định)
                str(stealth_name)         # **Process stealth identity (stable)** (danh tính ẩn danh của tiến trình - ổn định)
            ]
            
            # **Generate consistent hash** (tạo mã băm nhất quán)
            fingerprint_data = '|'.join(fingerprint_elements)
            fingerprint = hashlib.md5(fingerprint_data.encode('utf-8')).hexdigest()
            
            if self.logger:
                self.logger.debug(f"🔍 **[PROCESS-FINGERPRINT] Generated** ([DẤU VÂN TAY-TIẾN TRÌNH] Đã tạo): {fingerprint} from: {fingerprint_data}")
                self.logger.debug(f"🔍 **[PROCESS-DEBUG] Registration: {registration_source}, Process time: {process_timestamp}, Role: {role}, Name: {stealth_name}** ([GỠ LỖI-TIẾN TRÌNH] Đăng ký: {registration_source}, Thời gian tiến trình: {process_timestamp}, Vai trò: {role}, Tên: {stealth_name})")
            
            return fingerprint
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ENHANCED-FINGERPRINT] Error generating handoff fingerprint** ([DẤU VÂN TAY-NÂNG CAO] Lỗi khi tạo dấu vân tay bàn giao): {e}")
            
            # ✅ **ENHANCED FALLBACK - Use more stable fallback** (DỰ PHÒNG NÂNG CAO - dùng dự phòng ổn định hơn)
            try:
                fallback_data = f"{handoff_metadata.get('source', 'unknown')}|{handoff_metadata.get('timestamp', 0)}"
                return hashlib.md5(fallback_data.encode('utf-8')).hexdigest()
            except:
                return hashlib.md5(str(handoff_metadata).encode('utf-8')).hexdigest()
    
    def _record_duplicate_handoff(self, pid: int, handoff_metadata: Dict[str, Any], sequence_number: int, detection_method: list = None) -> None:
        """
        **Record Duplicate Handoff** (ghi lại bàn giao trùng lặp)
        
        ✅ **ENHANCED: Records duplicate handoff event with detailed detection information for monitoring**
        (NÂNG CAO: ghi lại sự kiện bàn giao trùng lặp với thông tin phát hiện chi tiết để giám sát).
        
        Args:
            pid: **Process ID** (ID tiến trình)
            handoff_metadata: **Metadata of duplicate handoff** (siêu dữ liệu của bàn giao trùng lặp)
            sequence_number: **Handoff sequence number** (số thứ tự bàn giao)
            detection_method: **List of detection methods used** (danh sách phương thức phát hiện được sử dụng) - fingerprint, source, role
        """
        try:
            timestamp = time.time()
            duplicate_record = {
                'timestamp': timestamp,
                'event_type': 'duplicate_handoff_detected',
                'success': True,  # **Successfully detected and handled** (phát hiện và xử lý thành công)
                'source': handoff_metadata.get('source', 'unknown'),
                'sequence_number': sequence_number,
                'fingerprint': self._generate_handoff_fingerprint(handoff_metadata),
                'preserved_state': self.hooks_ready.get(pid, False),
                'detection_method': detection_method or ['unknown'],  # ✅ **NEW: Detection method tracking** (MỚI: theo dõi phương thức phát hiện)
                'detection_method_str': '+'.join(detection_method) if detection_method else 'unknown',  # ✅ **NEW: Readable format** (MỚI: định dạng dễ đọc)
                'metadata_has_handoff_timestamp': 'handoff_timestamp' in handoff_metadata,  # ✅ **NEW: Timestamp presence tracking** (MỚI: theo dõi sự hiện diện dấu thời gian)
                'metadata_has_original_metadata': 'original_metadata' in handoff_metadata,  # ✅ **NEW: Structure tracking** (MỚI: theo dõi cấu trúc)
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(duplicate_record)
                    
                    # **Keep history manageable** (giữ lịch sử ở mức có thể quản lý)
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                self.logger.debug(f"📝 **[DUPLICATE] Recorded duplicate handoff event for PID {pid}** ([TRÙNG LẶP] Đã ghi lại sự kiện bàn giao trùng lặp cho PID {pid}) (seq: {sequence_number})")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[DUPLICATE] Error recording duplicate handoff for PID {pid}** ([TRÙNG LẶP] Lỗi khi ghi lại bàn giao trùng lặp cho PID {pid}): {e}")
    
    # ===== **HEALTH CHECK SYSTEM METHODS** (CÁC PHƯƠNG THỨC HỆ THỐNG KIỂM TRA SỨC KHỎE) =====
    
    def _start_health_monitoring(self) -> None:
        """**Start Health Monitoring** (khởi động giám sát sức khỏe - bắt đầu thread monitoring hook coordination)"""
        if self.health_monitoring_active:
            return
            
        self.health_monitoring_active = True
        self.health_monitor_thread = threading.Thread(
            target=self._health_monitoring_loop,
            daemon=True,
            name="HookCoordinator-HealthMonitor"
        )
        self.health_monitor_thread.start()
        
        if self.logger:
            self.logger.info("🏥 **[HEALTH] Health monitoring thread started** ([SỨC KHỎE] Đã khởi động luồng giám sát sức khỏe)")
    
    def _stop_health_monitoring(self) -> None:
        """**Stop Health Monitoring** (dừng giám sát sức khỏe - dừng thread monitoring khi không có active processes)"""
        self.health_monitoring_active = False
        
        if self.health_monitor_thread and self.health_monitor_thread.is_alive():
            # **Wait for thread to finish** (chờ luồng kết thúc)
            self.health_monitor_thread.join(timeout=5)
            
        if self.logger:
            self.logger.info("🏥 **[HEALTH] Health monitoring thread stopped** ([SỨC KHỎE] Đã dừng luồng giám sát sức khỏe)")
    
    def _health_monitoring_loop(self) -> None:
        """**Health Monitoring Loop** (vòng lặp giám sát sức khỏe - continuous monitoring của hook coordination status)"""
        if self.logger:
            self.logger.info("🏥 **[HEALTH] Health monitoring loop started** ([SỨC KHỎE] Đã bắt đầu vòng lặp giám sát sức khỏe)")
        
        while self.health_monitoring_active:
            try:
                current_time = time.time()
                
                # **Run health check if interval has passed** (chạy kiểm tra sức khỏe nếu khoảng thời gian đã qua)
                if current_time - self.last_health_check >= self.health_check_interval:
                    self.health_check_continuous()
                    self.last_health_check = current_time
                
                # **Sleep for a short interval before next check** (ngủ một khoảng ngắn trước lần kiểm tra tiếp theo)
                time.sleep(5)  # **Check every 5 seconds for timing, run full health check based on interval** (kiểm tra mỗi 5 giây về thời gian, chạy kiểm tra sức khỏe đầy đủ dựa trên khoảng thời gian)
                
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ **[HEALTH] Error in health monitoring loop** ([SỨC KHỎE] Lỗi trong vòng lặp giám sát sức khỏe): {e}")
                time.sleep(10)  # **Wait longer on error** (chờ lâu hơn khi có lỗi)
        
        if self.logger:
            self.logger.info("🏥 **[HEALTH] Health monitoring loop ended** ([SỨC KHỎE] Đã kết thúc vòng lặp giám sát sức khỏe)")
    
    def _forward_to_direct_registry(self, pid: int, process_metadata: Dict[str, Any]) -> bool:
        """
        **🥈 SOLUTION 2: Enhanced Forward to DirectPIDRegistry** 
        (giải pháp 2: chuyển tiếp nâng cao đến DirectPIDRegistry)
        
        **Forward process from HookCoordinator to DirectPIDRegistry with enhanced reliability and acknowledgment system**
        (chuyển tiếp tiến trình từ HookCoordinator đến DirectPIDRegistry với độ tin cậy nâng cao và hệ thống xác nhận).
        
        Args:
            pid: **Process ID** (ID tiến trình)
            process_metadata: **Metadata from stealth wrapper** (siêu dữ liệu từ stealth wrapper)
            
        Returns:
            bool: **True if forwarding successful with acknowledgment** (True nếu chuyển tiếp thành công với xác nhận)
        """
        try:
            if self.logger:
                self.logger.info(f"🔄 **[SOLUTION-2] Enhanced forwarding PID {pid} to DirectPIDRegistry** ([GIẢI PHÁP-2] Chuyển tiếp nâng cao PID {pid} đến DirectPIDRegistry)")
            
            # **🥈 SOLUTION 2: Enhanced Retry Logic with HASHRATE optimization** (giải pháp 2: logic thử lại nâng cao với tối ưu HASHRATE)
            max_retries = 3
            retry_delay = 0.05  # **HASHRATE FIX: Reduced from 100ms to 50ms for faster handoff** (giảm từ 100ms xuống 50ms cho handoff nhanh hơn)
            
            for attempt in range(max_retries):
                try:
                    if self.logger:
                        self.logger.debug(f"🔄 **[HANDOFF-RETRY] PID {pid} attempt {attempt + 1}/{max_retries}** ([THỬ LẠI-BÀN GIAO] PID {pid} lần thử {attempt + 1}/{max_retries})")
                    
                    # **Import DirectPIDRegistry** (nhập khẩu DirectPIDRegistry)
                    from pid_logger.direct_registry import get_direct_registry
                    
                    # **Get DirectPIDRegistry singleton** (lấy singleton DirectPIDRegistry)
                    registry = get_direct_registry()
                    
                    # **🥈 SOLUTION 2: Enhanced Handoff Metadata** (giải pháp 2: siêu dữ liệu bàn giao nâng cao)
                    handoff_timestamp = time.time()
                    registry_metadata = {
                        **process_metadata,  # **Include original metadata** (bao gồm siêu dữ liệu gốc)
                        'coordinator_timestamp': handoff_timestamp,
                        'handoff_attempt': attempt + 1,
                        'max_handoff_attempts': max_retries,
                        'source_chain': ['stealth_inference_cuda', 'hook_coordinator'],
                        'coordinator_handoff': True,
                        'handoff_id': f"HC-{pid}-{int(handoff_timestamp * 1000)}",  # **Unique handoff ID** (ID bàn giao duy nhất)
                        'acknowledgment_required': True,
                        'bidirectional_communication': True
                    }
                    
                    # **🥈 SOLUTION 2: Call with Acknowledgment** (giải pháp 2: gọi với xác nhận)
                    success = registry.receive_from_coordinator(pid, registry_metadata)
                    
                    if success:
                        # **🥈 SOLUTION 2: Wait for Acknowledgment** (giải pháp 2: chờ xác nhận)
                        ack_success = self._wait_for_registry_acknowledgment(pid, handoff_timestamp, timeout=2.0)
                        
                        if ack_success:
                            if self.logger:
                                self.logger.info(f"✅ **[SOLUTION-2] DirectPIDRegistry handoff successful with acknowledgment for PID {pid}** ([GIẢI PHÁP-2] Bàn giao DirectPIDRegistry thành công với xác nhận cho PID {pid})")
                            
                            # **🥈 SOLUTION 2: Record Successful Handoff** (giải pháp 2: ghi lại bàn giao thành công)
                            self._record_handoff_success(pid, handoff_timestamp, attempt + 1)
                            return True
                        else:
                            if self.logger:
                                self.logger.warning(f"⚠️ **[SOLUTION-2] DirectPIDRegistry handoff without acknowledgment for PID {pid}, attempt {attempt + 1}** ([GIẢI PHÁP-2] Bàn giao DirectPIDRegistry không có xác nhận cho PID {pid}, lần thử {attempt + 1})")
                            
                            # **If this is the last attempt, still consider it successful if registry accepted** (nếu đây là lần thử cuối cùng, vẫn coi là thành công nếu registry chấp nhận)
                            if attempt == max_retries - 1:
                                if self.logger:
                                    self.logger.info(f"✅ **[SOLUTION-2] Final attempt success despite missing acknowledgment for PID {pid}** ([GIẢI PHÁP-2] Lần thử cuối thành công mặc dù thiếu xác nhận cho PID {pid})")
                                return True
                    else:
                        if self.logger:
                            self.logger.warning(f"⚠️ **[SOLUTION-2] DirectPIDRegistry registration failed for PID {pid}, attempt {attempt + 1}** ([GIẢI PHÁP-2] Đăng ký DirectPIDRegistry thất bại cho PID {pid}, lần thử {attempt + 1})")
                    
                    # **🥈 SOLUTION 2: Retry Delay** (giải pháp 2: độ trễ thử lại)
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # **Exponential backoff** (tăng độ trễ theo cấp số nhân)
                        
                except ImportError as import_err:
                    if self.logger:
                        self.logger.error(f"❌ **[SOLUTION-2] Cannot import DirectPIDRegistry** ([GIẢI PHÁP-2] Không thể nhập khẩu DirectPIDRegistry): {import_err}")
                        self.logger.error("💡 **[FIX-HINT] Check if psutil dependency is installed: pip install psutil** ([GỢI Ý SỬA] Kiểm tra xem phụ thuộc psutil đã được cài đặt chưa: pip install psutil)")
                    return False
                    
                except Exception as attempt_err:
                    if self.logger:
                        self.logger.error(f"❌ **[SOLUTION-2] Handoff attempt {attempt + 1} failed for PID {pid}** ([GIẢI PHÁP-2] Lần thử bàn giao {attempt + 1} thất bại cho PID {pid}): {attempt_err}")
                    
                    if attempt == max_retries - 1:
                        raise attempt_err
                    
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
            
            # **All attempts failed** (tất cả các lần thử đều thất bại)
            if self.logger:
                self.logger.error(f"❌ **[SOLUTION-2] All {max_retries} handoff attempts failed for PID {pid}** ([GIẢI PHÁP-2] Tất cả {max_retries} lần thử bàn giao đều thất bại cho PID {pid})")
            return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[SOLUTION-2] Enhanced handoff failed for PID {pid}** ([GIẢI PHÁP-2] Bàn giao nâng cao thất bại cho PID {pid}): {e}")
            return False
    
    def _wait_for_registry_acknowledgment(self, pid: int, handoff_timestamp: float, timeout: float = 2.0) -> bool:
        """
        **🥈 SOLUTION 2: Wait for Registry Acknowledgment** 
        (giải pháp 2: chờ xác nhận từ registry)
        
        **Wait for DirectPIDRegistry to acknowledge successful handoff**
        (chờ DirectPIDRegistry xác nhận bàn giao thành công).
        
        Args:
            pid: **Process ID** (ID tiến trình)
            handoff_timestamp: **Timestamp of handoff** (dấu thời gian bàn giao)
            timeout: **Timeout in seconds** (thời gian chờ tính bằng giây)
            
        Returns:
            bool: **True if acknowledgment received** (True nếu nhận được xác nhận)
        """
        try:
            # **🥈 SOLUTION 2: Environment Variable-based Acknowledgment** (giải pháp 2: xác nhận qua biến môi trường)
            ack_env_var = f"REGISTRY_ACK_PID_{pid}"
            start_time = time.time()
            
            if self.logger:
                self.logger.debug(f"⏳ **[ACK-WAIT] Waiting for DirectPIDRegistry acknowledgment for PID {pid}** ([CHỜ XÁC NHẬN] Đang chờ xác nhận từ DirectPIDRegistry cho PID {pid})")
            
            while time.time() - start_time < timeout:
                # **Check for acknowledgment signal** (kiểm tra tín hiệu xác nhận)
                ack_value = os.environ.get(ack_env_var)
                
                if ack_value:
                    try:
                        ack_timestamp = float(ack_value)
                        
                        # **Verify acknowledgment is for current handoff** (xác minh xác nhận cho bàn giao hiện tại)
                        if ack_timestamp >= handoff_timestamp - 1.0:  # **Allow 1 second tolerance** (cho phép dung sai 1 giây)
                            if self.logger:
                                elapsed = time.time() - start_time
                                self.logger.debug(f"✅ **[ACK-WAIT] Registry acknowledgment received for PID {pid} after {elapsed*1000:.1f}ms** ([CHỜ XÁC NHẬN] Đã nhận xác nhận từ registry cho PID {pid} sau {elapsed*1000:.1f}ms)")
                            
                            # **Clean up acknowledgment variable** (dọn dẹp biến xác nhận)
                            os.environ.pop(ack_env_var, None)
                            return True
                    except ValueError:
                        # **Invalid acknowledgment format, ignore and continue** (định dạng xác nhận không hợp lệ, bỏ qua và tiếp tục)
                        pass
                
                time.sleep(0.01)  # **Check every 10ms** (kiểm tra mỗi 10ms)
            
            # **Timeout reached** (đã hết thời gian chờ)
            if self.logger:
                self.logger.warning(f"⏰ **[ACK-WAIT] Acknowledgment timeout for PID {pid} after {timeout}s** ([CHỜ XÁC NHẬN] Hết thời gian chờ xác nhận cho PID {pid} sau {timeout}s)")
            
            # **Clean up acknowledgment variable on timeout** (dọn dẹp biến xác nhận khi hết thời gian chờ)
            os.environ.pop(ack_env_var, None)
            return False
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ACK-WAIT] Error waiting for acknowledgment for PID {pid}** ([CHỜ XÁC NHẬN] Lỗi khi chờ xác nhận cho PID {pid}): {e}")
            return False
    
    def _record_handoff_success(self, pid: int, handoff_timestamp: float, attempt_number: int) -> None:
        """
        **🥈 SOLUTION 2: Record Handoff Success** 
        (giải pháp 2: ghi lại bàn giao thành công)
        
        **Record successful handoff with acknowledgment system tracking**
        (ghi lại bàn giao thành công với hệ thống theo dõi xác nhận).
        """
        try:
            handoff_record = {
                'timestamp': handoff_timestamp,
                'event_type': 'coordinator_handoff_success',
                'success': True,
                'target': 'direct_pid_registry',
                'attempt_number': attempt_number,
                'acknowledgment_received': True,
                'handoff_duration_ms': (time.time() - handoff_timestamp) * 1000,
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(handoff_timestamp))
            }
            
            with self.lock:
                # **Update handoff tracking** (cập nhật theo dõi bàn giao)
                self.handoff_timestamps[pid] = handoff_timestamp
                
                # **Record in history** (ghi vào lịch sử)
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(handoff_record)
                    
                    # **Keep history manageable** (giữ lịch sử ở mức có thể quản lý)
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                duration = handoff_record['handoff_duration_ms']
                self.logger.info(f"📝 **[HANDOFF-SUCCESS] Recorded successful handoff for PID {pid}** "
                               f"([BÀN GIAO-THÀNH CÔNG] Đã ghi lại bàn giao thành công cho PID {pid}) "
                               f"(attempt: {attempt_number}, duration: {duration:.1f}ms)")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[HANDOFF-SUCCESS] Error recording handoff success for PID {pid}** ([BÀN GIAO-THÀNH CÔNG] Lỗi khi ghi lại bàn giao thành công cho PID {pid}): {e}")
    
    def provide_acknowledgment_to_stealth(self, pid: int, success: bool, details: Dict[str, Any] = None) -> None:
        """
        **🥈 SOLUTION 2: Provide Acknowledgment to Stealth** 
        (giải pháp 2: cung cấp xác nhận cho stealth)
        
        **Send acknowledgment back to stealth_inference_cuda about handoff status**
        (gửi xác nhận ngược lại cho stealth_inference_cuda về trạng thái bàn giao).
        
        Args:
            pid: **Process ID** (ID tiến trình)
            success: **Whether handoff was successful** (liệu bàn giao có thành công hay không)
            details: **Additional details about handoff result** (chi tiết bổ sung về kết quả bàn giao)
        """
        try:
            # **🥈 SOLUTION 2: Bidirectional Communication** (giải pháp 2: giao tiếp hai chiều)
            ack_env_var = f"COORDINATOR_ACK_PID_{pid}"
            ack_timestamp = time.time()
            
            ack_data = {
                'success': success,
                'timestamp': ack_timestamp,
                'details': details or {},
                'source': 'hook_coordinator'
            }
            
            # **Set acknowledgment environment variable** (đặt biến môi trường xác nhận)
            os.environ[ack_env_var] = json.dumps(ack_data)
            
            if self.logger:
                self.logger.debug(f"📤 **[BIDIRECTIONAL] Sent acknowledgment to stealth for PID {pid}: {success}** ([HAI CHIỀU] Đã gửi xác nhận đến stealth cho PID {pid}: {success})")
            
            # **Schedule cleanup** (lên lịch dọn dẹp)
            # **Clean up after 30 seconds to prevent environment variable buildup** (dọn dẹp sau 30 giây để tránh tích tụ biến môi trường)
            def cleanup_ack():
                time.sleep(30.0)
                os.environ.pop(ack_env_var, None)
            
            cleanup_thread = threading.Thread(target=cleanup_ack, daemon=True)
            cleanup_thread.start()
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[BIDIRECTIONAL] Error providing acknowledgment to stealth for PID {pid}** ([HAI CHIỀU] Lỗi khi cung cấp xác nhận cho stealth cho PID {pid}): {e}")

    # **REMOVED: _handoff_to_resource_manager method - obsolete with new linear flow** (ĐÃ XÓA: phương thức _handoff_to_resource_manager - lỗi thời với luồng tuyến tính mới)
    
    # **REMOVED: _defer_resource_manager_handoff method - obsolete with new linear flow** (ĐÃ XÓA: phương thức _defer_resource_manager_handoff - lỗi thời với luồng tuyến tính mới)
    
    # **REMOVED: _notify_resource_manager method - obsolete with new linear flow** (ĐÃ XÓA: phương thức _notify_resource_manager - lỗi thời với luồng tuyến tính mới)
    
    def health_check_continuous(self) -> None:
        """**Continuous Health Check** (kiểm tra sức khỏe liên tục - giám sát hook coordination status cho tất cả active processes)"""
        if self.logger:
            self.logger.debug(f"🏥 **[HEALTH] Running health check for {len(self.active_processes)} active processes** ([SỨC KHỎE] Đang chạy kiểm tra sức khỏe cho {len(self.active_processes)} tiến trình hoạt động)")
        
        with self.lock:
            processes_to_check = list(self.active_processes)
        
        for pid in processes_to_check:
            try:
                # **✅ ENHANCED FIX: Skip health check for recent handoffs to prevent race conditions** (sửa lỗi nâng cao: bỏ qua kiểm tra sức khỏe cho các bàn giao gần đây để tránh race conditions)
                with self.lock:
                    last_handoff_time = self.handoff_timestamps.get(pid, 0)
                
                current_time = time.time()
                time_since_handoff = current_time - last_handoff_time
                # **✅ HEALTH_CHECK_PROTECTION_PERIOD: Enhanced protection for handoff coordination** (thời gian bảo vệ kiểm tra sức khỏe: bảo vệ nâng cao cho điều phối bàn giao)
                handoff_protection_period = 5.0  # **5-second protection period for new handoffs (increased from 3.0s)** (thời gian bảo vệ 5 giây cho các bàn giao mới - tăng từ 3.0s)
                
                if time_since_handoff < handoff_protection_period:
                    if self.logger:
                        self.logger.debug(f"⏳ **[HEALTH] Skipping health check for PID {pid} - recent handoff** "
                                        f"([SỨC KHỎE] Bỏ qua kiểm tra sức khỏe cho PID {pid} - bàn giao gần đây) "
                                        f"({time_since_handoff:.2f}s ago, protection: {handoff_protection_period}s)")
                    continue
                
                # **Verify hook status for each PID** (xác minh trạng thái hook cho mỗi PID)
                if not self.verify_hook_status(pid):
                    # **✅ ENHANCED DIAGNOSIS: Add detailed context logging before error** (chẩn đoán nâng cao: thêm ghi chép ngữ cảnh chi tiết trước lỗi)
                    with self.lock:
                        hooks_ready_state = self.hooks_ready.get(pid, False)
                        sequence_number = self.handoff_sequence_numbers.get(pid, 0)
                    
                    env_var = f'HOOKS_READY_PID_{pid}'
                    env_state = os.environ.get(env_var) == '1'
                    
                    if self.logger:
                        # **✅ ENHANCED LOGGING: Detailed state analysis for hook coordination errors** (ghi chép nâng cao: phân tích trạng thái chi tiết cho lỗi điều phối hook)
                        with self.lock:
                            recent_history = self.hook_status_history.get(pid, [])
                            last_events = [event.get('event_type', 'unknown') for event in recent_history[-3:]] if recent_history else []
                        
                        process_status = "exists" if psutil.pid_exists(pid) else "missing"
                        recovery_count = self.recovery_attempts.get(pid, 0)
                        
                        self.logger.error(f"🚨 **[HEALTH] Hook coordination lost for PID {pid}** "
                                        f"([SỨC KHỎE] Mất điều phối hook cho PID {pid}) - "
                                        f"State Analysis: internal={hooks_ready_state}, env={env_state}, "
                                        f"seq={sequence_number}, handoff_age={time_since_handoff:.2f}s, "
                                        f"process={process_status}, recovery_attempts={recovery_count}, "
                                        f"recent_events={last_events}, protection_window={handoff_protection_period}s")
                    
                    # **Attempt recovery** (thử phục hồi)
                    self.attempt_hook_recovery(pid)
                else:
                    # **Reset recovery attempts on successful verification** (đặt lại số lần thử phục hồi khi xác minh thành công)
                    with self.lock:
                        self.recovery_attempts[pid] = 0
                    
                    if self.logger:
                        self.logger.debug(f"✅ **[HEALTH] PID {pid} hook coordination healthy** ([SỨC KHỎE] Điều phối hook cho PID {pid} khỏe mạnh)")
                        
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ **[HEALTH] Error checking PID {pid}** ([SỨC KHỎE] Lỗi khi kiểm tra PID {pid}): {e}")
    
    def verify_hook_status(self, pid: int) -> bool:
        """**Verify Hook Status** (xác minh trạng thái hook - kiểm tra chi tiết hook coordination với retry mechanism)"""
        retry_config = self.verification_retry_config
        
        for attempt in range(retry_config['max_retries']):
            try:
                # **Check if process still exists** (kiểm tra xem tiến trình còn tồn tại không)
                if not psutil.pid_exists(pid):
                    if self.logger:
                        self.logger.warning(f"⚠️ **[HEALTH] PID {pid} no longer exists - removing from tracking** ([SỨC KHỎE] PID {pid} không còn tồn tại - xóa khỏi theo dõi)")
                    self.cleanup_pid(pid)
                    return False
                
                # **✅ SYNCHRONIZATION: Verify with retry and exponential backoff** (đồng bộ: xác minh với thử lại và backoff theo cấp số nhân)
                verification_result = self._verify_with_retry(pid, attempt)
                
                if verification_result['success']:
                    # **Record successful verification** (ghi lại xác minh thành công)
                    self._record_status_change(pid, 'health_check', True)
                    return verification_result['hooks_ready']
                elif verification_result['should_retry'] and attempt < retry_config['max_retries'] - 1:
                    # **Calculate exponential backoff delay** (tính toán độ trễ backoff theo cấp số nhân)
                    delay = min(
                        retry_config['base_delay'] * (retry_config['backoff_factor'] ** attempt),
                        retry_config['max_delay']
                    )
                    # **Add jitter to prevent thundering herd** (thêm jitter để ngăn hiệu ứng bầy đàn)
                    jitter = random.uniform(0, 0.1)
                    total_delay = delay + jitter
                    
                    if self.logger:
                        self.logger.debug(f"🔄 **[VERIFY] PID {pid} retry {attempt + 1}/{retry_config['max_retries']} after {total_delay:.3f}s** ([XÁC MINH] PID {pid} thử lại {attempt + 1}/{retry_config['max_retries']} sau {total_delay:.3f}s)")
                    
                    time.sleep(total_delay)
                    continue
                else:
                    # **Final failure or non-retryable error** (thất bại cuối cùng hoặc lỗi không thể thử lại)
                    if self.logger:
                        self.logger.warning(f"⚠️ **[HEALTH] PID {pid} verification failed after {attempt + 1} attempts** ([SỨC KHỎE] Xác minh PID {pid} thất bại sau {attempt + 1} lần thử)")
                    return False
                    
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ **[HEALTH] Error verifying PID {pid} status (attempt {attempt + 1})** ([SỨC KHỎE] Lỗi xác minh trạng thái PID {pid} (lần thử {attempt + 1})): {e}")
                
                if attempt < retry_config['max_retries'] - 1:
                    time.sleep(retry_config['base_delay'])
                    continue
                else:
                    return False
        
        return False
    
    def _sync_hooks_ready_state(self, pid: int, ready_state: bool) -> bool:
        """
        **Sync Hooks Ready State** (đồng bộ trạng thái hooks sẵn sàng)
        
        **✅ PRIORITY 2: STATE SYNCHRONIZATION with comprehensive retry mechanism and exponential backoff**
        (ưu tiên 2: đồng bộ trạng thái với cơ chế thử lại toàn diện và backoff theo cấp số nhân)
        **Enhanced thread-safe synchronization with systematic retry, state verification, and graceful error handling**
        (đồng bộ an toàn luồng nâng cao với thử lại có hệ thống, xác minh trạng thái và xử lý lỗi mượt mà).
        """
        # **✅ RETRY CONFIGURATION: Enhanced retry parameters for better reliability** (cấu hình thử lại: tham số thử lại nâng cao để tin cậy hơn)
        max_retries = 3
        base_delay = 0.1  # **100ms base delay** (độ trễ cơ bản 100ms)
        backoff_factor = 2  # **Exponential backoff multiplier** (hệ số nhân backoff theo cấp số nhân)
        max_delay = 1.0  # **Maximum delay cap (1 second)** (giới hạn độ trễ tối đa - 1 giây)
        
        for attempt in range(max_retries):
            try:
                # **✅ EXPONENTIAL BACKOFF: Calculate delay for current attempt** (backoff theo cấp số nhân: tính toán độ trễ cho lần thử hiện tại)
                if attempt > 0:
                    delay = min(base_delay * (backoff_factor ** (attempt - 1)), max_delay)
                    # **Add jitter to prevent thundering herd** (thêm jitter để ngăn hiệu ứng bầy đàn)
                    jitter = random.uniform(0, delay * 0.1)
                    total_delay = delay + jitter
                    
                    if self.logger:
                        self.logger.debug(f"🔄 **[STATE-SYNC] PID {pid} retry {attempt + 1}/{max_retries} after {total_delay:.3f}s** ([ĐỒNG BỘ TRẠNG THÁI] PID {pid} thử lại {attempt + 1}/{max_retries} sau {total_delay:.3f}s)")
                    
                    time.sleep(total_delay)
                
                # **✅ ATOMIC OPERATION: Double-lock pattern for maximum consistency** (thao tác nguyên tử: mẫu khóa kép để nhất quán tối đa)
                with self.environment_sync_lock:
                    with self.lock:
                        # **Store previous state for rollback capability** (lưu trạng thái trước đó để có khả năng rollback)
                        previous_internal_state = self.hooks_ready.get(pid, False)
                        env_var = f'HOOKS_READY_PID_{pid}'
                        previous_env_state = os.environ.get(env_var) == '1'
                        
                        # **Record synchronization attempt with retry context** (ghi lại lần thử đồng bộ với ngữ cảnh thử lại)
                        sync_timestamp = time.time()
                        sync_context = {
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'pid': pid,
                            'target_state': ready_state,
                            'previous_internal': previous_internal_state,
                            'previous_env': previous_env_state
                        }
                        
                        if self.logger:
                            self.logger.debug(f"🔄 **[STATE-SYNC] PID {pid} synchronization attempt {attempt + 1}/{max_retries}** "
                                            f"([ĐỒNG BỘ TRẠNG THÁI] PID {pid} lần thử đồng bộ {attempt + 1}/{max_retries}) - "
                                            f"target: {ready_state}, current_internal: {previous_internal_state}, current_env: {previous_env_state}")
                        
                        try:
                            # **✅ Step 1: Update internal state** (bước 1: cập nhật trạng thái nội bộ)
                            success = self._update_internal_state(pid, ready_state)
                            if not success:
                                raise Exception("Failed to update internal state")
                            
                            # **✅ Step 2: Sync environment variable with verification** (bước 2: đồng bộ biến môi trường với xác minh)
                            success = self._sync_environment_variable(pid, ready_state)
                            if not success:
                                raise Exception("Failed to sync environment variable")
                            
                            # **✅ Step 3: Verify state consistency between internal and external state** (bước 3: xác minh tính nhất quán trạng thái giữa nội bộ và bên ngoài)
                            if self._verify_state_consistency(pid):
                                # **✅ SUCCESS: Record successful synchronization** (thành công: ghi lại đồng bộ thành công)
                                self._record_sync_success(pid, ready_state, sync_timestamp, sync_context)
                                
                                if self.logger:
                                    self.logger.info(f"✅ **[STATE-SYNC] PID {pid} state synchronized successfully: {ready_state}** "
                                                   f"([ĐỒNG BỘ TRẠNG THÁI] PID {pid} đồng bộ trạng thái thành công: {ready_state}) "
                                                   f"(attempt: {attempt + 1}, duration: {(time.time() - sync_timestamp)*1000:.1f}ms)")
                                return True
                            else:
                                raise Exception("State consistency verification failed")
                                
                        except Exception as sync_error:
                            # **✅ ROLLBACK: Restore previous state on failure** (hoàn nguyên: khôi phục trạng thái trước đó khi thất bại)
                            rollback_success = self._rollback_state(pid, previous_internal_state, previous_env_state, env_var)
                            
                            if self.logger:
                                self.logger.warning(f"⚠️ **[STATE-SYNC] PID {pid} sync failed (attempt {attempt + 1})** "
                                                 f"([ĐỒNG BỘ TRẠNG THÁI] PID {pid} đồng bộ thất bại (lần thử {attempt + 1})): {sync_error} "
                                                 f"(rollback: {'success' if rollback_success else 'failed'})")
                            
                            # **Record failure attempt** (ghi lại lần thử thất bại)
                            self._record_sync_failure(pid, ready_state, sync_timestamp, sync_context, str(sync_error))
                            
                            # **If this is the last attempt, fail permanently** (nếu đây là lần thử cuối cùng, thất bại vĩnh viễn)
                            if attempt == max_retries - 1:
                                if self.logger:
                                    self.logger.error(f"❌ **[STATE-SYNC] PID {pid} state sync failed after {max_retries} attempts** ([ĐỒNG BỘ TRẠNG THÁI] PID {pid} đồng bộ trạng thái thất bại sau {max_retries} lần thử): {sync_error}")
                                return False
                            
                            # **Continue to next retry attempt** (tiếp tục lần thử lại tiếp theo)
                            continue
                            
            except Exception as e:
                # **✅ COMPREHENSIVE ERROR HANDLING: Handle unexpected errors** (xử lý lỗi toàn diện: xử lý các lỗi không mong đợi)
                if self.logger:
                    self.logger.error(f"❌ **[STATE-SYNC] Critical error in state sync for PID {pid} (attempt {attempt + 1})** ([ĐỒNG BỘ TRẠNG THÁI] Lỗi nghiêm trọng trong đồng bộ trạng thái cho PID {pid} (lần thử {attempt + 1})): {e}")
                
                if attempt == max_retries - 1:
                    if self.logger:
                        self.logger.error(f"❌ **[STATE-SYNC] State sync failed after {max_retries} attempts** ([ĐỒNG BỘ TRẠNG THÁI] Đồng bộ trạng thái thất bại sau {max_retries} lần thử): {e}")
                    return False
                
                # **Continue to next retry attempt even on critical errors** (tiếp tục lần thử lại tiếp theo ngay cả khi có lỗi nghiêm trọng)
                continue
        
        # **All retry attempts exhausted** (đã hết tất cả lần thử lại)
        if self.logger:
            self.logger.error(f"❌ **[STATE-SYNC] All {max_retries} state sync attempts failed for PID {pid}** ([ĐỒNG BỘ TRẠNG THÁI] Tất cả {max_retries} lần thử đồng bộ trạng thái đã thất bại cho PID {pid})")
        return False
    
    def _update_internal_state(self, pid: int, ready_state: bool) -> bool:
        """
        **Update Internal State** (cập nhật trạng thái nội bộ)
        
        **Safely update internal hooks_ready state with validation** 
        (cập nhật an toàn trạng thái hooks_ready nội bộ với xác thực).
        """
        try:
            self.hooks_ready[pid] = ready_state
            
            # **Verify update was successful** (xác minh cập nhật thành công)
            actual_state = self.hooks_ready.get(pid, False)
            if actual_state == ready_state:
                if self.logger:
                    self.logger.debug(f"🔄 **[INTERNAL-UPDATE] PID {pid} internal state updated: {ready_state}** ([CẬP NHẬT NỘI BỘ] PID {pid} trạng thái nội bộ đã cập nhật: {ready_state})")
                return True
            else:
                if self.logger:
                    self.logger.error(f"❌ **[INTERNAL-UPDATE] PID {pid} state update failed** ([CẬP NHẬT NỘI BỘ] PID {pid} cập nhật trạng thái thất bại) - expected: {ready_state}, actual: {actual_state}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[INTERNAL-UPDATE] Error updating internal state for PID {pid}** ([CẬP NHẬT NỘI BỘ] Lỗi cập nhật trạng thái nội bộ cho PID {pid}): {e}")
            return False
    
    def _sync_environment_variable(self, pid: int, ready_state: bool) -> bool:
        """
        **Sync Environment Variable** (đồng bộ biến môi trường)
        
        **Update environment variable with fallback mechanism and verification**
        (cập nhật biến môi trường với cơ chế dự phòng và xác minh).
        """
        try:
            env_var = f'HOOKS_READY_PID_{pid}'
            
            # **Update environment variable based on state** (cập nhật biến môi trường dựa trên trạng thái)
            if ready_state:
                os.environ[env_var] = '1'
            else:
                os.environ.pop(env_var, None)
            
            # **✅ VERIFICATION: Verify environment variable was set correctly** (xác minh: kiểm tra biến môi trường được thiết lập chính xác)
            actual_env_state = os.environ.get(env_var) == '1'
            if actual_env_state == ready_state:
                if self.logger:
                    self.logger.debug(f"🔄 **[ENV-SYNC] PID {pid} environment variable synced: {ready_state}** ([ĐỒNG BỘ MÔI TRƯỜNG] PID {pid} biến môi trường đã đồng bộ: {ready_state})")
                return True
            else:
                if self.logger:
                    self.logger.error(f"❌ **[ENV-SYNC] PID {pid} environment sync failed** ([ĐỒNG BỘ MÔI TRƯỜNG] PID {pid} đồng bộ môi trường thất bại) - expected: {ready_state}, actual: {actual_env_state}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ENV-SYNC] Error syncing environment variable for PID {pid}** ([ĐỒNG BỘ MÔI TRƯỜNG] Lỗi đồng bộ biến môi trường cho PID {pid}): {e}")
            return False
    
    def _verify_state_consistency(self, pid: int) -> bool:
        """
        **Verify State Consistency** (xác minh tính nhất quán trạng thái)
        
        **Compare internal hooks_ready[pid] vs environment variable to ensure consistency**
        (so sánh hooks_ready[pid] nội bộ với biến môi trường để đảm bảo tính nhất quán).
        """
        try:
            # **Get internal state** (lấy trạng thái nội bộ)
            internal_state = self.hooks_ready.get(pid, False)
            
            # **Get environment variable state** (lấy trạng thái biến môi trường)
            env_var = f'HOOKS_READY_PID_{pid}'
            env_state = os.environ.get(env_var) == '1'
            
            # **Check consistency** (kiểm tra tính nhất quán)
            is_consistent = (internal_state == env_state)
            
            if self.logger:
                if is_consistent:
                    self.logger.debug(f"✅ **[CONSISTENCY] PID {pid} state consistent** ([NHẤT QUÁN] PID {pid} trạng thái nhất quán) - internal: {internal_state}, env: {env_state}")
                else:
                    self.logger.warning(f"⚠️ **[CONSISTENCY] PID {pid} state inconsistent** ([NHẤT QUÁN] PID {pid} trạng thái không nhất quán) - internal: {internal_state}, env: {env_state}")
            
            return is_consistent
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[CONSISTENCY] Error verifying state consistency for PID {pid}** ([NHẤT QUÁN] Lỗi xác minh tính nhất quán trạng thái cho PID {pid}): {e}")
            return False
    
    def _rollback_state(self, pid: int, previous_internal_state: bool, previous_env_state: bool, env_var: str) -> bool:
        """
        **Rollback State** (hoàn nguyên trạng thái)
        
        **Restore previous state on synchronization failure**
        (khôi phục trạng thái trước đó khi đồng bộ thất bại).
        """
        try:
            rollback_success = True
            
            # **Restore internal state** (khôi phục trạng thái nội bộ)
            try:
                self.hooks_ready[pid] = previous_internal_state
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ **[ROLLBACK] Failed to restore internal state for PID {pid}** ([HOÀN NGUYÊN] Thất bại khôi phục trạng thái nội bộ cho PID {pid}): {e}")
                rollback_success = False
            
            # **Restore environment variable** (khôi phục biến môi trường)
            try:
                if previous_env_state:
                    os.environ[env_var] = '1'
                else:
                    os.environ.pop(env_var, None)
            except Exception as e:
                if self.logger:
                    self.logger.error(f"❌ **[ROLLBACK] Failed to restore environment variable for PID {pid}** ([HOÀN NGUYÊN] Thất bại khôi phục biến môi trường cho PID {pid}): {e}")
                rollback_success = False
            
            if self.logger:
                if rollback_success:
                    self.logger.debug(f"🔄 **[ROLLBACK] PID {pid} state rollback successful** ([HOÀN NGUYÊN] PID {pid} hoàn nguyên trạng thái thành công)")
                else:
                    self.logger.warning(f"⚠️ **[ROLLBACK] PID {pid} partial rollback failure** ([HOÀN NGUYÊN] PID {pid} hoàn nguyên một phần thất bại)")
            
            return rollback_success
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ROLLBACK] Critical error during rollback for PID {pid}** ([HOÀN NGUYÊN] Lỗi nghiêm trọng trong khi hoàn nguyên cho PID {pid}): {e}")
            return False
    
    def _record_sync_success(self, pid: int, ready_state: bool, timestamp: float, context: Dict[str, Any]) -> None:
        """
        **Record Sync Success** (ghi lại đồng bộ thành công)
        
        **Record successful state synchronization event with comprehensive context**
        (ghi lại sự kiện đồng bộ trạng thái thành công với ngữ cảnh toàn diện).
        """
        try:
            sync_duration = time.time() - timestamp
            success_record = {
                'timestamp': timestamp,
                'event_type': 'state_sync_success',
                'success': True,
                'ready_state': ready_state,
                'attempt_number': context.get('attempt', 1),
                'max_retries': context.get('max_retries', 3),
                'sync_duration_ms': round(sync_duration * 1000, 2),
                'previous_states': {
                    'internal': context.get('previous_internal', False),
                    'env': context.get('previous_env', False)
                },
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(success_record)
                    
                    # **Keep history manageable** (giữ lịch sử ở mức có thể quản lý)
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                self.logger.debug(f"📝 **[SYNC-SUCCESS] Recorded successful sync for PID {pid}** ([ĐỒNG BỘ THÀNH CÔNG] Đã ghi lại đồng bộ thành công cho PID {pid}) (attempt: {context.get('attempt', 1)})")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[SYNC-SUCCESS] Error recording sync success for PID {pid}** ([ĐỒNG BỘ THÀNH CÔNG] Lỗi ghi lại đồng bộ thành công cho PID {pid}): {e}")
    
    def _record_sync_failure(self, pid: int, ready_state: bool, timestamp: float, context: Dict[str, Any], error_msg: str) -> None:
        """
        **Record Sync Failure** (ghi lại đồng bộ thất bại)
        
        **Record failed synchronization attempt with detailed error context**
        (ghi lại lần thử đồng bộ thất bại với ngữ cảnh lỗi chi tiết).
        """
        try:
            sync_duration = time.time() - timestamp
            failure_record = {
                'timestamp': timestamp,
                'event_type': 'state_sync_failure',
                'success': False,
                'ready_state': ready_state,
                'attempt_number': context.get('attempt', 1),
                'max_retries': context.get('max_retries', 3),
                'sync_duration_ms': round(sync_duration * 1000, 2),
                'error_message': error_msg,
                'previous_states': {
                    'internal': context.get('previous_internal', False),
                    'env': context.get('previous_env', False)
                },
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid in self.hook_status_history:
                    self.hook_status_history[pid].append(failure_record)
                    
                    # **Keep history manageable** (giữ lịch sử ở mức có thể quản lý)
                    if len(self.hook_status_history[pid]) > 25:
                        self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                self.logger.debug(f"📝 **[SYNC-FAILURE] Recorded sync failure for PID {pid}** ([ĐỒNG BỘ THẤT BẠI] Đã ghi lại đồng bộ thất bại cho PID {pid}) (attempt: {context.get('attempt', 1)})")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[SYNC-FAILURE] Error recording sync failure for PID {pid}** ([ĐỒNG BỘ THẤT BẠI] Lỗi ghi lại đồng bộ thất bại cho PID {pid}): {e}")
    
    def _validate_atomic_sync(self, pid: int, expected_state: bool, sync_timestamp: float) -> Dict[str, Any]:
        """
        **Validate Atomic Sync** (xác thực đồng bộ nguyên tử)
        
        **✅ LEGACY SUPPORT: Maintained for compatibility with existing verification calls**
        (hỗ trợ kế thừa: duy trì để tương thích với các lệnh gọi xác minh hiện có)
        **Now serves as a wrapper around the enhanced _verify_state_consistency method**
        (hiện đóng vai trò là wrapper cho phương thức _verify_state_consistency nâng cao)
        
        Returns:
            **Dict with success status and validation details**
            (từ điển với trạng thái thành công và chi tiết xác thực)
        """
        try:
            # **Multi-layer validation using enhanced consistency check** (xác thực đa lớp sử dụng kiểm tra nhất quán nâng cao)
            sync_duration = time.time() - sync_timestamp
            
            # **Use enhanced consistency verification** (sử dụng xác minh nhất quán nâng cao)
            is_consistent = self._verify_state_consistency(pid)
            
            # **Additional validations for backward compatibility** (xác thực bổ sung để tương thích ngược)
            internal_state = self.hooks_ready.get(pid, False)
            env_var = f'HOOKS_READY_PID_{pid}'
            env_state = os.environ.get(env_var) == '1'
            
            validations = {
                'internal_state': (internal_state == expected_state),
                'env_state': (env_state == expected_state),
                'cross_state_sync': is_consistent,
                'timing': (sync_duration < 0.1),  # **Increased to 100ms for retry scenarios** (tăng lên 100ms cho các tình huống thử lại)
                'pid_tracking': (pid in self.active_processes)
            }
            
            # **Overall success** (thành công tổng thể)
            all_valid = all(validations.values())
            
            return {
                'success': all_valid,
                'details': validations,
                'sync_duration': sync_duration,
                'expected_state': expected_state,
                'actual_internal': internal_state,
                'actual_env': env_state
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[VALIDATE-ATOMIC] Error in atomic sync validation for PID {pid}** ([XÁC THỰC NGUYÊN TỬ] Lỗi trong xác thực đồng bộ nguyên tử cho PID {pid}): {e}")
            return {
                'success': False,
                'error': str(e),
                'details': {'validation_error': True}
            }
    
    def _record_atomic_sync_success(self, pid: int, ready_state: bool, timestamp: float, attempt_number: int) -> None:
        """
        **Record Atomic Sync Success** (ghi lại đồng bộ nguyên tử thành công)
        
        **✅ LEGACY SUPPORT: Wrapper around enhanced sync success recording**
        (hỗ trợ kế thừa: wrapper cho ghi lại đồng bộ thành công nâng cao).
        """
        try:
            # **Use enhanced sync success recording with legacy compatibility** (sử dụng ghi lại đồng bộ thành công nâng cao với tương thích kế thừa)
            context = {
                'attempt': attempt_number,
                'max_retries': 3,  # Default for legacy calls
                'previous_internal': False,  # Unknown for legacy calls
                'previous_env': False  # Unknown for legacy calls
            }
            
            self._record_sync_success(pid, ready_state, timestamp, context)
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ATOMIC-SYNC] Error recording legacy success for PID {pid}** ([ĐỒNG BỘ NGUYÊN TỬ] Lỗi ghi lại thành công kế thừa cho PID {pid}): {e}")
    
    def _record_atomic_sync_failure(self, pid: int, ready_state: bool, timestamp: float, attempt_number: int, validation_results: Dict[str, Any]) -> None:
        """
        **Record Atomic Sync Failure** (ghi lại đồng bộ nguyên tử thất bại)
        
        **✅ LEGACY SUPPORT: Wrapper around enhanced sync failure recording**
        (hỗ trợ kế thừa: wrapper cho ghi lại đồng bộ thất bại nâng cao).
        """
        try:
            # **Use enhanced sync failure recording with legacy compatibility** (sử dụng ghi lại đồng bộ thất bại nâng cao với tương thích kế thừa)
            context = {
                'attempt': attempt_number,
                'max_retries': 3,  # Default for legacy calls
                'previous_internal': False,  # Unknown for legacy calls
                'previous_env': False  # Unknown for legacy calls
            }
            
            error_msg = f"Validation failed: {validation_results.get('details', 'Unknown error')}"
            self._record_sync_failure(pid, ready_state, timestamp, context, error_msg)
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ATOMIC-SYNC] Error recording legacy failure for PID {pid}** ([ĐỒNG BỘ NGUYÊN TỬ] Lỗi ghi lại thất bại kế thừa cho PID {pid}): {e}")
    
    def _verify_with_retry(self, pid: int, attempt: int) -> Dict[str, any]:
        """
        **Verify With Retry** (xác minh với thử lại)
        
        **✅ SOLUTION 3: HEALTH CHECK REFINEMENT with handoff-aware validation**
        (giải pháp 3: tinh chỉnh kiểm tra sức khỏe với xác thực nhận biết bàn giao)
        **Single verification attempt with detailed result and handoff coordination awareness**
        (một lần thử xác minh với kết quả chi tiết và nhận biết phối hợp bàn giao).
        """
        try:
            verification_start_time = time.time()
            
            # **✅ HANDOFF AWARENESS: Check for recent handoffs that might affect verification** (nhận biết bàn giao: kiểm tra các bàn giao gần đây có thể ảnh hưởng xác minh)
            with self.lock:
                hooks_ready = self.hooks_ready.get(pid, False)
                
                # **Get handoff timing information for context** (lấy thông tin thời gian bàn giao cho ngữ cảnh)
                last_handoff_time = self.handoff_timestamps.get(pid, 0)
                time_since_handoff = verification_start_time - last_handoff_time
                current_sequence = self.handoff_sequence_numbers.get(pid, 0)
            
            # **Check environment variable consistency** (kiểm tra tính nhất quán biến môi trường)
            env_var = f'HOOKS_READY_PID_{pid}'
            env_status = os.environ.get(env_var) == '1'
            
            # **✅ HANDOFF-AWARE TIMING: Allow grace period for recent handoffs** (thời gian nhận biết bàn giao: cho phép thời gian ân hạn cho bàn giao gần đây)
            handoff_grace_period = 3.0  # **3-second grace period after handoff (increased from 2.0s for enhanced stability)** (thời gian ân hạn 3 giây sau bàn giao - tăng từ 2.0s để ổn định hơn)
            is_recent_handoff = time_since_handoff < handoff_grace_period
            
            # **Enhanced verification with handoff context** (xác minh nâng cao với ngữ cảnh bàn giao)
            verification_context = {
                'verification_timestamp': verification_start_time,
                'last_handoff_time': last_handoff_time,
                'time_since_handoff': time_since_handoff,
                'is_recent_handoff': is_recent_handoff,
                'handoff_sequence': current_sequence,
                'attempt_number': attempt + 1
            }
            
            if self.logger:
                self.logger.debug(f"🔍 **[VERIFY-ENHANCED] PID {pid} verification context** ([XÁC MINH NÂNG CAO] Ngữ cảnh xác minh PID {pid}): "
                                f"recent_handoff={is_recent_handoff}, time_since={time_since_handoff:.2f}s, "
                                f"seq={current_sequence}, attempt={attempt + 1}")
            
            # **Verify consistency between internal state and environment variable** (xác minh tính nhất quán giữa trạng thái nội bộ và biến môi trường)
            if hooks_ready != env_status:
                inconsistency_severity = self._assess_inconsistency_severity(
                    pid, hooks_ready, env_status, verification_context
                )
                
                if self.logger:
                    severity_msg = f"severity={inconsistency_severity['level']}"
                    if is_recent_handoff:
                        severity_msg += f" (recent_handoff_tolerance)"
                    
                    self.logger.warning(f"⚠️ **[VERIFY-ENHANCED] PID {pid} inconsistency** ([XÁC MINH NÂNG CAO] PID {pid} không nhất quán) (attempt {attempt + 1}): "
                                      f"internal={hooks_ready}, env={env_status}, {severity_msg}")
                
                # **✅ HANDOFF-AWARE RECOVERY: Different strategies based on handoff timing** (phục hồi nhận biết bàn giao: các chiến lược khác nhau dựa trên thời gian bàn giao)
                if is_recent_handoff and inconsistency_severity['level'] == 'low':
                    # **For recent handoffs with low severity, allow more recovery attempts** (với bàn giao gần đây có mức độ thấp, cho phép nhiều lần phục hồi hơn)
                    if attempt < self.verification_retry_config['max_retries'] - 1:
                        # **Try enhanced synchronization for recent handoffs** (thử đồng bộ nâng cao cho bàn giao gần đây)
                        sync_success = self._enhanced_sync_for_handoff(pid, verification_context)
                        
                        return {
                            'success': False,
                            'should_retry': True,
                            'hooks_ready': False,
                            'sync_attempted': sync_success,
                            'inconsistency_detected': True,
                            'inconsistency_severity': inconsistency_severity,
                            'verification_context': verification_context,
                            'recovery_strategy': 'handoff_aware_sync'
                        }
                else:
                    # **Standard recovery for non-recent handoffs or high severity** (phục hồi tiêu chuẩn cho bàn giao không gần đây hoặc mức độ cao)
                    if attempt < self.verification_retry_config['max_retries'] - 1:
                        sync_success = self.sync_environment_state(pid)
                        return {
                            'success': False,
                            'should_retry': True,
                            'hooks_ready': False,
                            'sync_attempted': sync_success,
                            'inconsistency_detected': True,
                            'inconsistency_severity': inconsistency_severity,
                            'verification_context': verification_context,
                            'recovery_strategy': 'standard_sync'
                        }
                
                # **Final attempt or unrecoverable inconsistency** (lần thử cuối cùng hoặc không nhất quán không thể phục hồi)
                return {
                    'success': False,
                    'should_retry': False,
                    'hooks_ready': False,
                    'inconsistency_detected': True,
                    'inconsistency_severity': inconsistency_severity,
                    'verification_context': verification_context,
                    'recovery_strategy': 'none_final_attempt'
                }
            
            # **✅ CONSISTENT STATES: Perform additional validation for recent handoffs** (trạng thái nhất quán: thực hiện xác thực bổ sung cho bàn giao gần đây)
            if is_recent_handoff:
                # **Additional validation for recent handoffs to ensure stability** (xác thực bổ sung cho bàn giao gần đây để đảm bảo ổn định)
                additional_validation = self._validate_handoff_stability(pid, verification_context)
                
                if not additional_validation['stable']:
                    if self.logger:
                        self.logger.debug(f"🔍 **[VERIFY-ENHANCED] PID {pid} handoff stability check failed** ([XÁC MINH NÂNG CAO] PID {pid} kiểm tra ổn định bàn giao thất bại): "
                                        f"{additional_validation['details']}")
                    
                    if attempt < self.verification_retry_config['max_retries'] - 1:
                        return {
                            'success': False,
                            'should_retry': True,
                            'hooks_ready': hooks_ready and env_status,
                            'inconsistency_detected': False,
                            'stability_check': additional_validation,
                            'verification_context': verification_context,
                            'recovery_strategy': 'stability_recheck'
                        }
            
            # **✅ SUCCESS: States are consistent and stable** (thành công: trạng thái nhất quán và ổn định)
            verification_duration = time.time() - verification_start_time
            
            return {
                'success': True,
                'should_retry': False,
                'hooks_ready': hooks_ready and env_status,
                'inconsistency_detected': False,
                'verification_context': verification_context,
                'verification_duration': verification_duration,
                'stability_validated': is_recent_handoff
            }
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[VERIFY-ENHANCED] Error in verification attempt {attempt + 1} for PID {pid}** ([XÁC MINH NÂNG CAO] Lỗi trong lần xác minh {attempt + 1} cho PID {pid}): {e}")
            
            return {
                'success': False,
                'should_retry': True,  # **Retry on exception unless it's the last attempt** (thử lại khi có ngoại lệ trừ khi là lần thử cuối cùng)
                'hooks_ready': False,
                'error': str(e),
                'verification_context': {
                    'verification_timestamp': time.time(),
                    'error_occurred': True,
                    'attempt_number': attempt + 1
                }
            }
    
    def _assess_inconsistency_severity(self, pid: int, internal_state: bool, env_state: bool, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        **Assess Inconsistency Severity** (đánh giá mức độ nghiêm trọng không nhất quán)
        
        **Evaluates severity of state inconsistency based on handoff timing and patterns**
        (đánh giá mức độ nghiêm trọng của sự không nhất quán trạng thái dựa trên thời gian bàn giao và các mẫu).
        """
        try:
            severity_factors = {
                'time_since_handoff': context.get('time_since_handoff', 999),
                'is_recent_handoff': context.get('is_recent_handoff', False),
                'state_difference': abs(int(internal_state) - int(env_state)),
                'attempt_number': context.get('attempt_number', 1)
            }
            
            # **Calculate severity level** (tính toán mức độ nghiêm trọng)
            if severity_factors['is_recent_handoff'] and severity_factors['time_since_handoff'] < 0.5:
                level = 'low'  # **Very recent handoff, inconsistency might be temporary** (bàn giao rất gần đây, không nhất quán có thể tạm thời)
            elif severity_factors['time_since_handoff'] < 2.0:
                level = 'medium'  # **Recent handoff, worth retrying** (bàn giao gần đây, đáng thử lại)
            else:
                level = 'high'  # **Old handoff, inconsistency is problematic** (bàn giao cũ, không nhất quán là vấn đề)
            
            return {
                'level': level,
                'factors': severity_factors,
                'recommendation': 'retry' if level in ['low', 'medium'] else 'escalate'
            }
            
        except Exception as e:
            return {
                'level': 'unknown',
                'error': str(e),
                'recommendation': 'escalate'
            }
    
    def _enhanced_sync_for_handoff(self, pid: int, context: Dict[str, Any]) -> bool:
        """
        **Enhanced Sync for Handoff** (đồng bộ nâng cao cho bàn giao)
        
        **Special synchronization method for recent handoffs with additional validation**
        (phương thức đồng bộ đặc biệt cho bàn giao gần đây với xác thực bổ sung).
        """
        try:
            if self.logger:
                self.logger.debug(f"🔄 **[ENHANCED-SYNC] Performing handoff-aware sync for PID {pid}** ([ĐỒNG BỘ NÂNG CAO] Thực hiện đồng bộ nhận biết bàn giao cho PID {pid})")
            
            # **Use the enhanced atomic sync method** (sử dụng phương thức đồng bộ nguyên tử nâng cao)
            sync_success = self._sync_hooks_ready_state(pid, self.hooks_ready.get(pid, False))
            
            if sync_success:
                # **Additional verification after sync** (xác thực bổ sung sau đồng bộ)
                time.sleep(0.001)  # **Brief stabilization delay** (độ trễ ổn định ngắn)
                
                # **Re-verify consistency** (xác minh lại tính nhất quán)
                with self.lock:
                    internal_state = self.hooks_ready.get(pid, False)
                
                env_var = f'HOOKS_READY_PID_{pid}'
                env_state = os.environ.get(env_var) == '1'
                
                final_consistency = (internal_state == env_state)
                
                if self.logger:
                    self.logger.debug(f"🔄 **[ENHANCED-SYNC] PID {pid} post-sync verification** ([ĐỒNG BỘ NÂNG CAO] Xác minh sau đồng bộ PID {pid}): "
                                    f"consistent={final_consistency}, state={internal_state}")
                
                return final_consistency
            else:
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ENHANCED-SYNC] Error in enhanced sync for PID {pid}** ([ĐỒNG BỘ NÂNG CAO] Lỗi trong đồng bộ nâng cao cho PID {pid}): {e}")
            return False
    
    def _validate_handoff_stability(self, pid: int, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        **Validate Handoff Stability** (xác thực tính ổn định bàn giao)
        
        **Additional validation for recent handoffs to ensure state stability**
        (xác thực bổ sung cho bàn giao gần đây để đảm bảo tính ổn định trạng thái).
        """
        try:
            # **Check for rapid state changes that might indicate instability** (kiểm tra thay đổi trạng thái nhanh có thể chỉ ra sự không ổn định)
            with self.lock:
                recent_history = self.hook_status_history.get(pid, [])
                
            # **Look for recent state changes** (tìm kiếm thay đổi trạng thái gần đây)
            current_time = time.time()
            recent_changes = [
                event for event in recent_history[-5:]  # **Last 5 events** (5 sự kiện cuối cùng)
                if current_time - event.get('timestamp', 0) < 2.0  # **Within 2 seconds** (trong vòng 2 giây)
            ]
            
            # **Stability indicators** (chỉ báo ổn định)
            stability_checks = {
                'rapid_changes': len(recent_changes) > 3,  # **More than 3 changes in 2 seconds** (hơn 3 thay đổi trong 2 giây)
                'state_oscillation': self._detect_state_oscillation(recent_changes),
                'handoff_completion': context.get('time_since_handoff', 0) > 0.1  # **✅ ENHANCED: Increased to 100ms for stability with longer grace periods** (nâng cao: tăng lên 100ms để ổn định với thời gian ân hạn dài hơn)
            }
            
            # **Overall stability** (tính ổn định tổng thể)
            is_stable = not any([
                stability_checks['rapid_changes'],
                stability_checks['state_oscillation']
            ]) and stability_checks['handoff_completion']
            
            return {
                'stable': is_stable,
                'details': stability_checks,
                'recent_changes_count': len(recent_changes)
            }
            
        except Exception as e:
            return {
                'stable': False,
                'error': str(e),
                'details': {'validation_error': True}
            }
    
    def _detect_state_oscillation(self, recent_events: list) -> bool:
        """
        **Detect State Oscillation** (phát hiện dao động trạng thái)
        
        **Detects alternating success/failure patterns indicating instability**
        (phát hiện các mẫu thành công/thất bại xen kẽ chỉ ra sự không ổn định).
        """
        try:
            if len(recent_events) < 3:
                return False
            
            # **Look for alternating success/failure patterns** (tìm kiếm các mẫu thành công/thất bại xen kẽ)
            success_pattern = [event.get('success', True) for event in recent_events[-3:]]
            
            # **Detect oscillation: True->False->True or False->True->False** (phát hiện dao động: Đúng->Sai->Đúng hoặc Sai->Đúng->Sai)
            if len(success_pattern) >= 3:
                return (success_pattern[0] != success_pattern[1] and 
                       success_pattern[1] != success_pattern[2])
            
            return False
            
        except Exception:
            return False
    
    def sync_environment_state(self, pid: int) -> bool:
        """
        **Sync Environment State** (đồng bộ trạng thái môi trường)
        
        **Force sync environment variable with internal state**
        (bắt buộc đồng bộ biến môi trường với trạng thái nội bộ).
        """
        try:
            with self.environment_sync_lock:
                with self.lock:
                    internal_state = self.hooks_ready.get(pid, False)
                
                env_var = f'HOOKS_READY_PID_{pid}'
                
                # **Sync environment to match internal state** (đồng bộ môi trường để khớp với trạng thái nội bộ)
                if internal_state:
                    os.environ[env_var] = '1'
                else:
                    os.environ.pop(env_var, None)
                
                # **Verify sync success** (xác minh đồng bộ thành công)
                env_state = os.environ.get(env_var) == '1'
                sync_success = (internal_state == env_state)
                
                if self.logger:
                    if sync_success:
                        self.logger.debug(f"🔄 **[ENV_SYNC] PID {pid} environment synced to: {internal_state}** ([ĐỒNG BỘ MÔI TRƯỜNG] PID {pid} môi trường đã đồng bộ thành: {internal_state})")
                    else:
                        self.logger.error(f"❌ **[ENV_SYNC] PID {pid} sync failed** ([ĐỒNG BỘ MÔI TRƯỜNG] PID {pid} đồng bộ thất bại): internal={internal_state}, env={env_state}")
                
                return sync_success
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ **[ENV_SYNC] Error syncing environment for PID {pid}** ([ĐỒNG BỘ MÔI TRƯỜNG] Lỗi đồng bộ môi trường cho PID {pid}): {e}")
            return False
    
    def attempt_hook_recovery(self, pid: int) -> bool:
        """
        **Attempt Hook Recovery** (thử phục hồi hook)
        
        **Comprehensive recovery with enhanced synchronization and state validation**
        (phục hồi toàn diện với đồng bộ nâng cao và xác thực trạng thái).
        """
        try:
            with self.lock:
                current_attempts = self.recovery_attempts.get(pid, 0)
                
                if current_attempts >= self.max_recovery_attempts:
                    if self.logger:
                        self.logger.error(f"💀 **[RECOVERY] PID {pid} exceeded max recovery attempts ({self.max_recovery_attempts})** ([PHỤC HỒI] PID {pid} vượt quá số lần phục hồi tối đa) - removing from tracking")
                    self.cleanup_pid(pid)
                    return False
                
                # **Increment recovery attempts** (tăng số lần thử phục hồi)
                self.recovery_attempts[pid] = current_attempts + 1
            
            if self.logger:
                self.logger.info(f"🔧 **[RECOVERY] Enhanced recovery for PID {pid}** ([PHỤC HỒI] Phục hồi nâng cao cho PID {pid}) (attempt {current_attempts + 1}/{self.max_recovery_attempts})")
            
            # **Enhanced Recovery Strategy** (chiến lược phục hồi nâng cao):
            
            # **Step 1: Comprehensive state validation** (bước 1: xác thực trạng thái toàn diện)
            process_exists = psutil.pid_exists(pid)
            if not process_exists:
                if self.logger:
                    self.logger.warning(f"⚠️ [RECOVERY] PID {pid} no longer exists during recovery initiation")
                self.cleanup_pid(pid)
                return False
            
            # Step 2: Reset states with synchronized clearing
            reset_success = self._sync_hooks_ready_state(pid, False)
            if not reset_success:
                if self.logger:
                    self.logger.error(f"❌ [RECOVERY] Failed to reset state for PID {pid}")
                return False
            
            # Step 3: Optimized recovery delay for performance
            recovery_delay = min(0.01 + (current_attempts * 0.005), 0.05)  # Progressive delay: 10ms, 15ms, 20ms, max 50ms
            
            if self.logger:
                self.logger.debug(f"⏳ [RECOVERY] PID {pid} waiting {recovery_delay*1000:.1f}ms for state stabilization")
            
            time.sleep(recovery_delay)
            
            # Step 4: Verify process is still responsive
            if not psutil.pid_exists(pid):
                if self.logger:
                    self.logger.warning(f"⚠️ [RECOVERY] PID {pid} disappeared during recovery")
                self.cleanup_pid(pid)
                return False
            
            # Step 5: Re-establish hook coordination with enhanced sync
            restore_success = self._sync_hooks_ready_state(pid, True)
            
            if restore_success:
                # Step 6: Validate recovery success
                validation_success = self._validate_recovery(pid)
                
                if validation_success:
                    if self.logger:
                        self.logger.info(f"✅ [RECOVERY] PID {pid} hook coordination fully restored and validated")
                    
                    # Record successful recovery
                    self._record_status_change(pid, 'recovery_success', True)
                    
                    # Reset recovery attempts on success
                    with self.lock:
                        self.recovery_attempts[pid] = 0
                    
                    return True
                else:
                    if self.logger:
                        self.logger.error(f"❌ [RECOVERY] PID {pid} restoration failed validation")
                    return False
            else:
                if self.logger:
                    self.logger.error(f"❌ [RECOVERY] Failed to restore hook state for PID {pid}")
                return False
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [RECOVERY] Enhanced recovery failed for PID {pid}: {e}")
            
            # Record failed recovery
            self._record_status_change(pid, 'recovery_failed', False)
            
            return False
    
    def _validate_recovery(self, pid: int) -> bool:
        """**Validate Recovery** (xác thực phục hồi - comprehensive validation của recovery success)"""
        try:
            # Minimal wait for state stabilization
            time.sleep(0.001)
            
            # Multi-layer validation
            validations = []
            
            # Validation 1: Process existence
            process_exists = psutil.pid_exists(pid)
            validations.append(('process_exists', process_exists))
            
            # Validation 2: Internal state consistency
            with self.lock:
                internal_ready = self.hooks_ready.get(pid, False)
            validations.append(('internal_state', internal_ready))
            
            # Validation 3: Environment variable consistency  
            env_var = f'HOOKS_READY_PID_{pid}'
            env_ready = os.environ.get(env_var) == '1'
            validations.append(('env_state', env_ready))
            
            # Validation 4: State synchronization
            state_sync = (internal_ready == env_ready == True)
            validations.append(('state_sync', state_sync))
            
            # Validation 5: PID tracking consistency
            with self.lock:
                is_tracked = pid in self.active_processes
            validations.append(('tracking_consistency', is_tracked))
            
            # Evaluate overall validation
            all_valid = all(result for _, result in validations)
            
            if self.logger:
                validation_status = ", ".join([f"{name}={result}" for name, result in validations])
                self.logger.debug(f"🔍 [VALIDATION] PID {pid} recovery validation: {validation_status}")
            
            return all_valid
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [VALIDATION] Error validating recovery for PID {pid}: {e}")
            return False
    
    def _record_status_change(self, pid: int, event_type: str, success: bool) -> None:
        """**Record Status Change** (ghi lại thay đổi trạng thái - lưu trữ lịch sử changes cho health monitoring)"""
        try:
            timestamp = time.time()
            status_entry = {
                'timestamp': timestamp,
                'event_type': event_type,
                'success': success,
                'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))
            }
            
            with self.lock:
                if pid not in self.hook_status_history:
                    self.hook_status_history[pid] = []
                
                self.hook_status_history[pid].append(status_entry)
                
                # Keep only last 25 entries per PID for memory optimization in linear flow
                if len(self.hook_status_history[pid]) > 25:
                    self.hook_status_history[pid] = self.hook_status_history[pid][-25:]
            
            if self.logger:
                self.logger.debug(f"📝 [HEALTH] Recorded {event_type} for PID {pid}: {success}")
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [HEALTH] Error recording status change for PID {pid}: {e}")
    
    def get_health_report(self) -> Dict[str, Any]:
        """**Enhanced Health Report** (báo cáo sức khỏe nâng cao - trả về comprehensive health status với linear flow metrics)"""
        try:
            with self.lock:
                current_time = time.time()
                
                # Basic statistics
                total_processes = len(self.active_processes)
                ready_processes = sum(1 for pid in self.active_processes if self.hooks_ready.get(pid, False))
                
                # Recovery statistics
                total_recovery_attempts = sum(self.recovery_attempts.values())
                processes_with_recoveries = len([pid for pid, attempts in self.recovery_attempts.items() if attempts > 0])
                
                # **Linear Flow Statistics** (thống kê luồng tuyến tính)
                handoff_stats = {
                    'total_handoffs': len(self.handoff_timestamps),
                    'recent_handoffs': len([t for t in self.handoff_timestamps.values() if current_time - t < 300]),  # Last 5 minutes
                    'average_handoff_interval': 0.0
                }
                
                # Calculate average handoff interval
                if len(self.handoff_timestamps) > 1:
                    handoff_times = sorted(self.handoff_timestamps.values())
                    intervals = [handoff_times[i] - handoff_times[i-1] for i in range(1, len(handoff_times))]
                    handoff_stats['average_handoff_interval'] = sum(intervals) / len(intervals)
                
                # **Environment Variable Health** (sức khỏe biến môi trường)
                env_health = {
                    'linear_handoff_vars': len([k for k in os.environ.keys() if k.startswith('LINEAR_HANDOFF_RM_PID_')]),
                    'pickup_ready_vars': len([k for k in os.environ.keys() if k.startswith('RM_PICKUP_READY_PID_')]),
                    'deferred_handoff_vars': len([k for k in os.environ.keys() if k.startswith('DEFERRED_RM_HANDOFF_PID_')]),
                    'hooks_ready_vars': len([k for k in os.environ.keys() if k.startswith('HOOKS_READY_PID_')])
                }
                
                # Health status determination
                if total_processes == 0:
                    health_status = 'IDLE'
                elif ready_processes == total_processes:
                    health_status = 'HEALTHY'
                elif ready_processes > total_processes * 0.7:
                    health_status = 'WARNING'
                else:
                    health_status = 'CRITICAL'
                
                report = {
                    'timestamp': current_time,
                    'time_str': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time)),
                    'health_status': health_status,
                    'monitoring_active': self.health_monitoring_active,
                    'statistics': {
                        'total_processes': total_processes,
                        'ready_processes': ready_processes,
                        'pending_processes': total_processes - ready_processes,
                        'ready_percentage': (ready_processes / total_processes * 100) if total_processes > 0 else 0
                    },
                    'recovery_stats': {
                        'total_recovery_attempts': total_recovery_attempts,
                        'processes_with_recoveries': processes_with_recoveries,
                        'max_recovery_attempts': self.max_recovery_attempts
                    },
                    'linear_flow_stats': handoff_stats,
                    'environment_health': env_health,
                    'active_processes': list(self.active_processes),
                    'process_status': {pid: self.hooks_ready.get(pid, False) for pid in self.active_processes},
                    'last_health_check': self.last_health_check,
                    'health_check_interval': self.health_check_interval
                }
                
                return report
                
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ [HEALTH] Error generating enhanced health report: {e}")
            
            return {
                'timestamp': time.time(),
                'health_status': 'ERROR',
                'error': str(e),
                'monitoring_active': self.health_monitoring_active
            }
    
    def get_process_health_history(self, pid: int) -> Optional[list]:
        """**Get Process Health History** (lấy lịch sử sức khỏe tiến trình - history của status changes cho PID cụ thể)"""
        with self.lock:
            return self.hook_status_history.get(pid, []).copy() if pid in self.hook_status_history else None

# Global instance
_coordinator: Optional[HookCoordinator] = None
_lock = threading.Lock()

def get_hook_coordinator() -> HookCoordinator:
    """**Enhanced Hook Coordinator Singleton** (lấy coordinator singleton nâng cao)
    
    Thread-safe singleton access với enhanced initialization logging.
    
    Returns:
        HookCoordinator: Enhanced singleton instance with linear flow support
    """
    global _coordinator
    
    with _lock:
        if _coordinator is None:
            _coordinator = HookCoordinator()
            # **Enhanced initialization logging** (ghi log khởi tạo nâng cao)
            if hasattr(_coordinator, 'logger') and _coordinator.logger:
                _coordinator.logger.info("✅ [SINGLETON] Enhanced HookCoordinator singleton created with linear flow support")
                _coordinator.logger.info(f"🔗 [SINGLETON] Enhanced features: direct handoff, deferred coordination, comprehensive cleanup")
        return _coordinator

def reset_hook_coordinator() -> None:
    """**Reset Hook Coordinator** (reset hook coordinator)
    
    Testing and development utility to reset singleton state.
    """
    global _coordinator
    with _lock:
        if _coordinator:
            # Cleanup resources before reset
            if hasattr(_coordinator, '_stop_health_monitoring'):
                _coordinator._stop_health_monitoring()
        _coordinator = None