# gpu_unrestrict.py
# Centralized helpers to remove/unlock GPU resource limits (NVML-first + CLI fallback)
# - Clocks reset/unlock (applications/gpu/memory)
# - Verify state via nvidia-smi
# - System-wide pre-unlock (best-effort)

from __future__ import annotations

import os
import time
import subprocess
from typing import List, Optional, Any

try:
    import pynvml  # type: ignore
except Exception:  # NVML may be optional in some environments
    pynvml = None  # type: ignore


# ------------------------------
# Core reset/unlock helpers
# ------------------------------

def reset_app_clocks_nvml(gpu_manager: Any, gpu_index: int) -> bool:
    """
    Reset ứng dụng clocks (Applications Clocks) theo NVML-first.

    - Ưu tiên NVML: nvmlDeviceResetApplicationsClocks(handle)
    - Trả về True nếu NVML báo thành công, False nếu lỗi/không hỗ trợ
    """
    logger = getattr(gpu_manager, 'logger', None)
    try:
        if getattr(gpu_manager, 'gpu_initialized', False) is False:
            if logger:
                logger.error("[RC.reset] NVML chưa khởi tạo – không thể reset applications clocks.")
            return False
        get_handle = getattr(gpu_manager, 'get_handle', None)
        handle = get_handle(gpu_index) if callable(get_handle) else None
        if handle is None:
            if logger:
                logger.error(f"[RC.reset] Không lấy được handle cho GPU={gpu_index}.")
            return False
        if pynvml is None:
            if logger:
                logger.warning(f"[RC.reset] NVML module not available – cannot reset applications clocks | GPU={gpu_index}")
            return False
        pynvml.nvmlDeviceResetApplicationsClocks(handle)
        if logger:
            logger.info(f"[RC.reset] ✅ NVML nvmlDeviceResetApplicationsClocks thành công | GPU={gpu_index}")
        return True
    except Exception as e:
        if logger:
            logger.error(f"[RC.reset] Exception khi NVML reset applications clocks | GPU={gpu_index} | err={e}")
        return False


def reset_gpu_clocks_cli(logger: Any, gpu_index: int) -> bool:
    """
    Reset clocks bằng nvidia-smi (CLI fallback – phương án dự phòng):
    - Thứ tự cố gắng: -rac (reset applications clocks) → -rgc (reset gpu clocks) → --reset-memory-clocks/-rmc
    - Thành công nếu ít nhất một lệnh chạy ok.
    """
    attempts: List[List[str]] = [
        ['nvidia-smi', '-i', str(gpu_index), '-rac'],
        ['nvidia-smi', '-i', str(gpu_index), '-rgc'],
        ['nvidia-smi', '-i', str(gpu_index), '--reset-memory-clocks'],
        ['nvidia-smi', '-i', str(gpu_index), '-rmc'],  # alias nếu bản CLI hỗ trợ
    ]
    success_any = False
    for cmd in attempts:
        try:
            subprocess.run(cmd, check=True, timeout=10)
            success_any = True
            if logger:
                logger.info(f"[RC.reset] ✅ CLI success: {' '.join(cmd)}")
        except subprocess.TimeoutExpired as e:
            if logger:
                logger.warning(f"[RC.reset] ⏱️ CLI timeout: {' '.join(cmd)} | err={e}")
        except subprocess.CalledProcessError as e:
            if logger:
                logger.warning(f"[RC.reset] CLI failed: {' '.join(cmd)} | err={e}")
        except FileNotFoundError as e:
            if logger:
                logger.error(f"[RC.reset] nvidia-smi không tồn tại trong PATH | err={e}")
            break
        except Exception as e:
            if logger:
                logger.error(f"[RC.reset] CLI exception: {' '.join(cmd)} | err={e}")
    if not success_any and logger:
        logger.warning(f"[RC.reset] ❌ Không reset được clocks bằng CLI cho GPU={gpu_index}")
    return success_any


def verify_gpu_clock_state(logger: Any, gpu_index: int) -> bool:
    """
    Verify trạng thái sau reset bằng nvidia-smi:
    - Kỳ vọng: clocks.applications.graphics/memory ở trạng thái không khoá (N/A)
    - Ghi nhận: clocks.current.*, pstate, power.draw để quan sát
    Trả về True nếu nhìn thấy trạng thái "unlocked"; False nếu còn giá trị khoá rõ ràng.
    """
    try:
        cmd = [
            'nvidia-smi', '-i', str(gpu_index),
            '--query-gpu=clocks.applications.graphics,clocks.applications.memory,clocks.current.graphics,clocks.current.memory,pstate,power.draw',
            '--format=csv,noheader,nounits'
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=8)
        line = out.strip().splitlines()[0] if out else ''
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 6:
            if logger:
                logger.warning(f"[RC.verify] Output bất thường từ nvidia-smi: '{line}'")
            return True  # best-effort

        apps_g, apps_m, cur_g, cur_m, pstate, power = parts[:6]

        def _is_numeric(v: str) -> bool:
            try:
                t = str(v).strip().lower()
                if t in ('', 'n/a', 'na', 'nan'):
                    return False
                float(t)
                return True
            except Exception:
                return False

        locked_g = _is_numeric(apps_g)
        locked_m = _is_numeric(apps_m)
        unlocked = not (locked_g or locked_m)
        try:
            if logger:
                logger.info(
                    f"[RC.verify] GPU={gpu_index} | apps(g,m)=({apps_g},{apps_m}) | current(g,m)=({cur_g},{cur_m}) | pstate={pstate} | power={power}W | unlocked={unlocked}"
                )
        except Exception:
            pass
        return unlocked
    except subprocess.TimeoutExpired as e:
        if logger:
            logger.warning(f"[RC.verify] ⏱️ Timeout khi gọi nvidia-smi verify | GPU={gpu_index} | err={e}")
        return True  # best-effort
    except Exception as e:
        if logger:
            logger.warning(f"[RC.verify] Không thể verify bằng nvidia-smi | GPU={gpu_index} | err={e}")
        return True  # best-effort


def reset_gpu_clocks_and_verify(
    gpu_manager: Any,
    logger: Any,
    gpu_index: int,
    post_sleep_sec: Optional[float] = None,
) -> bool:
    """
    Orchestrator: NVML-first reset → CLI fallback → Verify.

    - post_sleep_sec: ngủ rất ngắn sau reset để phần cứng cập nhật trạng thái (mặc định 0.2s, tối đa 2s)
    - Trả về True nếu reset (NVML hoặc CLI) và verify thành công.
    """
    try:
        ok = reset_app_clocks_nvml(gpu_manager, gpu_index)
        if not ok:
            ok = reset_gpu_clocks_cli(logger, gpu_index)

        # Ngủ ngắn để phần cứng/phần mềm cập nhật trạng thái
        try:
            if post_sleep_sec is None:
                post_sleep_sec = float(os.getenv('POST_RESET_SLEEP_SEC', '0.2'))
        except Exception:
            post_sleep_sec = 0.2
        post_sleep_sec = max(0.0, min(2.0, float(post_sleep_sec)))
        if post_sleep_sec > 0:
            time.sleep(post_sleep_sec)

        verified = verify_gpu_clock_state(logger, gpu_index)
        if not verified and logger:
            logger.warning(f"[RC.reset] Reset ok nhưng verify không đạt | GPU={gpu_index}")
        return bool(ok and verified)
    except Exception as e:
        if logger:
            logger.error(f"[RC.reset] Lỗi trong reset_gpu_clocks_and_verify | GPU={gpu_index} | err={e}")
        return False
 
def unrestrict_gpu(
    gpu_manager: Any,
    logger: Any,
    gpu_index: int,
    power_preference: str = "default",
    post_sleep_sec: Optional[float] = None,
    enforce_baseline: bool = False,
) -> bool:
    """
    Standard unrestrict flow (luồng gỡ giới hạn chuẩn):
    1) Reset/unlock clocks (NVML-first → CLI fallback) và verify.
    2) Khôi phục power limit về default/max (NVML-first → CLI fallback).
    3) Optional: enforce baseline (có thể khoá lại clocks nếu ALLOW_CLOCK_LOCK cho phép).
    """
    try:
        ok_reset = reset_gpu_clocks_and_verify(
            gpu_manager=gpu_manager,
            logger=logger,
            gpu_index=gpu_index,
            post_sleep_sec=post_sleep_sec,
        )
        ok_power = restore_power_limit(
            logger=logger,
            gpu_manager=gpu_manager,
            gpu_index=gpu_index,
            preference=power_preference,
        )
        ok = bool(ok_reset and ok_power)
        if enforce_baseline:
            try:
                enforce_gpu_baselines(logger)
            except Exception as e:
                if logger:
                    logger.debug(f"[RC.unrestrict] enforce_gpu_baselines skipped/failed: {e}")
        return ok
    except Exception as e:
        if logger:
            logger.error(f"[RC.unrestrict] Error in unrestrict_gpu | GPU={gpu_index} | err={e}")
        return False
 
 
# ------------------------------
# System-wide pre-unlock helper
# ------------------------------

def reset_gpu_state(logger: Any) -> None:
    """
    Reset GPU state to normal (đặt lại trạng thái GPU về bình thường – mở khóa xung nếu có)
    - Gọi nvidia-smi để bỏ lock graphics/memory clocks (không dùng NVML trực tiếp)
    - Thực thi best-effort, bỏ qua lỗi nếu không hỗ trợ.
    """
    try:
        # Phát hiện số GPU qua nvidia-smi; nếu không có, vẫn thử GPU 0 để best-effort
        try:
            count = _detect_gpu_count(logger)
        except Exception:
            count = 0
        total = max(1, int(count) if isinstance(count, int) else 0)
        for idx in range(total):
            try:
                _run_smi(['nvidia-smi','-i',str(idx),'-rgc'], logger, f"Unlock graphics clocks for GPU {idx}")
                _run_smi(['nvidia-smi','-i',str(idx),'--reset-memory-clocks'], logger, f"Reset memory clocks for GPU {idx}")
            except Exception as smi_e:
                if logger:
                    logger.debug(f"[GPU-RESET] nvidia-smi unlock exception for GPU {idx}: {smi_e}")
    except Exception as e:
        if logger:
            logger.debug(f"[GPU-RESET] Skipped due to unexpected error: {e}")


def _run_smi(cmd: List[str], logger: Any, desc: str) -> int:
    """Run nvidia-smi command with rc capture and detailed logging."""
    try:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            if logger:
                logger.info(f"[NVSMI] ✅ {desc} | rc=0 | cmd={' '.join(cmd)}")
        else:
            stderr = (result.stderr or '').strip()
            if logger:
                logger.warning(f"[NVSMI] ❌ {desc} | rc={result.returncode} | cmd={' '.join(cmd)} | stderr={stderr}")
        return result.returncode
    except Exception as e:
        try:
            if logger:
                logger.warning(f"[NVSMI] ❌ {desc} | exception={e} | cmd={' '.join(cmd)}")
        except Exception:
            if logger:
                logger.warning(f"[NVSMI] ❌ {desc} | exception={e}")
        return -1
 
def restore_power_limit(logger: Any, gpu_manager: Any, gpu_index: int, preference: str = "default") -> bool:
    """
    Khôi phục power limit về mặc định/tối đa theo chiến lược NVML-first, CLI fallback.
    
    - preference: "default" để dùng default limit từ NVML; "max" để dùng max limit (constraints).
    - NVML-first: đọc target_mw và gọi nvmlDeviceSetPowerManagementLimit(handle, target_mw).
    - Fallback: nvidia-smi -pl <watts>, cố gắng truy vấn giá trị qua --query-gpu.
    """
    try:
        pref = str(preference or "default").strip().lower()
        if pref not in ("default", "max"):
            pref = "default"
        # NVML-first
        if pynvml is not None and getattr(gpu_manager, "gpu_initialized", False):
            get_handle = getattr(gpu_manager, "get_handle", None)
            handle = get_handle(gpu_index) if callable(get_handle) else None
            if handle is not None:
                try:
                    if pref == "default":
                        target_mw = int(pynvml.nvmlDeviceGetPowerManagementDefaultLimit(handle))
                    else:
                        _min_mw, max_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
                        target_mw = int(max_mw)
                    pynvml.nvmlDeviceSetPowerManagementLimit(handle, int(target_mw))
                    if logger:
                        target_w = int(target_mw // 1000)
                        logger.info(f"[RC.power] ✅ NVML restore power limit ({pref}) = {target_w}W | GPU={gpu_index}")
                    return True
                except Exception as e:
                    if logger:
                        logger.warning(f"[RC.power] NVML restore power limit ({pref}) failed | GPU={gpu_index} | err={e}")
        # CLI fallback
        # Query desired watts
        target_w: Optional[int] = None
        try:
            if pref == "default":
                # Thử truy vấn default; nếu không hỗ trợ, sẽ fallback max
                out = subprocess.check_output([
                    "nvidia-smi", "-i", str(gpu_index),
                    "--query-gpu=power.default_limit", "--format=csv,noheader,nounits"
                ], stderr=subprocess.STDOUT, text=True, timeout=5)
                line = (out or "").strip().splitlines()[0] if out else ""
                target_w = int(float(line))
        except Exception:
            target_w = None
        if target_w is None:
            try:
                out = subprocess.check_output([
                    "nvidia-smi", "-i", str(gpu_index),
                    "--query-gpu=power.max_limit", "--format=csv,noheader,nounits"
                ], stderr=subprocess.STDOUT, text=True, timeout=5)
                line = (out or "").strip().splitlines()[0] if out else ""
                target_w = int(float(line))
            except Exception as e:
                if logger:
                    logger.error(f"[RC.power] CLI query target watts failed | GPU={gpu_index} | err={e}")
                target_w = None
        if target_w is not None:
            rc = _run_smi(
                ["nvidia-smi", "-i", str(gpu_index), "-pl", str(int(target_w))],
                logger, f"Restore power limit ({pref}) to {int(target_w)}W for GPU {gpu_index}"
            )
            return rc == 0
        else:
            if logger:
                logger.warning(f"[RC.power] Unable to determine target watts for restore ({pref}) | GPU={gpu_index}")
            return False
    except Exception as e:
        if logger:
            logger.error(f"[RC.power] Unexpected error in restore_power_limit | GPU={gpu_index} | err={e}")
        return False

def enforce_gpu_baselines(logger: Any) -> None:
    """
    Enforce baseline GPU power limit và clocks ngay sau reset (best-effort).

    - Power limit: đặt tối thiểu MIN_POWER_LIMIT nếu có
    - SM/MEM clocks: lock theo LOCK_TARGET_* nếu có, nếu không dùng MIN_* làm baseline
    - Tuân thủ ALLOW_CLOCK_LOCK; bỏ qua nếu tắt
    - Bật persistence mode nếu ENABLE_PERSISTENCE_MODE_ON_SETUP = 1/true/yes
    """
    try:
        try:
            allow_clock_lock = str(os.getenv('ALLOW_CLOCK_LOCK', '1')).lower() in ('1','true','yes')
        except Exception:
            allow_clock_lock = False

        min_pl = os.getenv('MIN_POWER_LIMIT', '120')
        min_sm = os.getenv('MIN_SM_CLOCK', '1200')
        min_mem = os.getenv('MIN_MEM_CLOCK', '877')
        tgt_sm = os.getenv('LOCK_TARGET_SM_CLOCK', '') or min_sm
        tgt_mem = os.getenv('LOCK_TARGET_MEM_CLOCK', '') or min_mem

        # Detect GPU count (fallback to 1 if unknown)
        try:
            count = _detect_gpu_count(logger)
        except Exception:
            count = 0
        total = max(1, int(count) if isinstance(count, int) else 0)

        # Optional: enable persistence mode (best-effort)
        try:
            if str(os.getenv('ENABLE_PERSISTENCE_MODE_ON_SETUP', '1')).lower() in ('1','true','yes'):
                _run_smi(['nvidia-smi','-pm','1'], logger, "Enable persistence mode")
        except Exception:
            pass

        for idx in range(total):
            # Enforce minimum power limit (best-effort)
            try:
                if str(min_pl).strip():
                    _run_smi(['nvidia-smi','-i',str(idx),'-pl',str(int(float(min_pl)))], logger, f"Set MIN_POWER_LIMIT≥{min_pl}W for GPU {idx}")
            except Exception as e:
                if logger:
                    logger.debug(f"[GPU-BASELINE] Skip power limit set for GPU {idx}: {e}")

            # Enforce baseline clocks only if allowed
            if not allow_clock_lock:
                if logger:
                    logger.info(f"[GPU-BASELINE] Skipping clock lock (ALLOW_CLOCK_LOCK disabled) | gpu={idx}")
                continue

            # Lock SM clock (graphics clock)
            try:
                if str(tgt_sm).strip():
                    _run_smi(['nvidia-smi','-i',str(idx),'--lock-gpu-clocks='+str(int(float(tgt_sm)))], logger, f"Lock SM clock to ≥{tgt_sm}MHz for GPU {idx}")
            except Exception as e:
                if logger:
                    logger.debug(f"[GPU-BASELINE] Skip SM clock lock for GPU {idx}: {e}")

            # Lock MEM clock (may be unsupported on some GPUs)
            try:
                if str(tgt_mem).strip():
                    _run_smi(['nvidia-smi','-i',str(idx),'--lock-memory-clocks='+str(int(float(tgt_mem)))], logger, f"Lock MEM clock to ≥{tgt_mem}MHz for GPU {idx}")
            except Exception as e:
                if logger:
                    logger.info(f"ℹ️ [CAPABILITY] Skipped MEM clock lock for GPU {idx}: {e}")
    except Exception as e:
        if logger:
            logger.debug(f"[GPU-BASELINE] Enforcement skipped due to unexpected error: {e}")


def _detect_gpu_count(logger: Any) -> int:
    """
    Detect number of NVIDIA GPUs via nvidia-smi; returns 0 on failure.
    """
    try:
        out = subprocess.check_output(['nvidia-smi', '--list-gpus'], stderr=subprocess.DEVNULL, text=True, timeout=5)
        return len([ln for ln in (out or '').splitlines() if ln.strip()])
    except Exception as e:
        try:
            if logger:
                logger.debug(f"[NVSMI] GPU count detection failed: {e}")
        except Exception:
            pass
        return 0
