# gpu_unrestrict.py
# Centralized helpers to remove/unlock GPU resource limits (NVML-first + CLI fallback)
# - Clocks reset/unlock (applications/gpu/memory)
# - Verify state via nvidia-smi
# - System-wide pre-unlock (best-effort)

from __future__ import annotations

import os
import time
import subprocess
from typing import List, Optional, Any, Dict
import logging

try:
    import pynvml  # type: ignore
except Exception:  # NVML may be optional in some environments
    pynvml = None  # type: ignore

# ------------------------------
# Module logger (dedicated)
# ------------------------------
try:
    # Package import
    from mining_environment.scripts.logging_config import get_unified_logger
except ImportError:
    try:
        # Relative import (package context)
        from .logging_config import get_unified_logger  # type: ignore
    except Exception:
        # Standalone fallback
        from logging_config import get_unified_logger  # type: ignore

try:
    _MODULE_LOGGER = get_unified_logger('mining_environment.scripts.gpu_unrestrict')
except Exception:
    _MODULE_LOGGER = logging.getLogger('mining_environment.scripts.gpu_unrestrict')


# ------------------------------
# Module state & small helpers
# ------------------------------

# Cooldown/rate-limit timestamps (epoch seconds)
# _LAST_GPU_RESET_TS removed – hard GPU reset logic eliminated
_LAST_POWER_SET_TS: Dict[int, float] = {}
_LAST_CLOCK_LOCK_TS: Dict[int, float] = {}
# Verify fail counters per GPU (to escalate severity)
_VERIFY_FAIL_COUNTS: Dict[int, int] = {}


def _truthy_env(name: str, default: str = "0") -> bool:
    """Parse boolean-ish env var; accepts 1/true/yes (không phân biệt hoa thường)."""
    try:
        return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes")
    except Exception:
        return str(default).strip().lower() in ("1", "true", "yes")


def _query_smi_value(gpu_index: int, fields: List[str]) -> Optional[List[str]]:
    """Query nvidia-smi for given fields and return parsed (csv,noheader,nounits)."""
    try:
        cmd = [
            "nvidia-smi", "-i", str(gpu_index),
            "--query-gpu=" + ",".join(fields),
            "--format=csv,noheader,nounits",
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=6)
        line = (out or "").strip().splitlines()[0] if out else ""
        if not line:
            return None
        parts = [p.strip() for p in line.split(",")]
        return parts
    except Exception:
        return None


def _get_current_power_limit_w(gpu_index: int) -> Optional[int]:
    """Get current power limit in Watts via nvidia-smi; returns None on failure."""
    try:
        vals = _query_smi_value(gpu_index, ["power.limit"])
        if not vals:
            return None
        return int(float(vals[0]))
    except Exception:
        return None


def _is_gpu_idle(gpu_index: int, logger: Any = None) -> bool:
    """Best-effort check: no compute apps and low utilization means idle."""
    try:
        # Check compute apps PIDs
        out = subprocess.check_output([
            "nvidia-smi", "-i", str(gpu_index),
            "--query-compute-apps=pid", "--format=csv,noheader"
        ], stderr=subprocess.STDOUT, text=True, timeout=5)
        pids = [ln.strip() for ln in (out or "").splitlines() if ln.strip()]
        if pids:
            return False
    except Exception:
        pass
    # Utilization heuristic
    try:
        vals = _query_smi_value(gpu_index, ["utilization.gpu", "utilization.memory"])
        if vals and len(vals) >= 2:
            ugpu = int(float(vals[0]))
            umem = int(float(vals[1]))
            return ugpu < 3 and umem < 3
    except Exception:
        pass
    return True  # best-effort default


def _is_mps_active() -> bool:
    """Detect NVIDIA MPS server process (best-effort)."""
    try:
        rc = subprocess.run(["pgrep", "-f", "nvidia-cuda-mps-server"], check=False)
        return rc.returncode == 0
    except Exception:
        return False


def _is_display_active(gpu_index: int) -> bool:
    """Detect if display is active on this GPU (best-effort)."""
    vals = _query_smi_value(gpu_index, ["display_active"]) or []
    if not vals:
        return False
    return str(vals[0]).strip().lower() in ("enabled", "active", "on", "1", "yes", "true")


# ------------------------------
# Core reset/unlock helpers
# ------------------------------

def reset_app_clocks_nvml(gpu_manager: Any, gpu_index: int, logger: Any = None) -> bool:
    """
    Reset ứng dụng clocks (Applications Clocks) theo NVML-first.

    - Ưu tiên NVML: nvmlDeviceResetApplicationsClocks(handle)
    - Trả về True nếu NVML báo thành công, False nếu lỗi/không hỗ trợ
    """
    # Luôn ưu tiên logger chuyên biệt của module để log vào gpu_unrestrict.log
    logger = logger or _MODULE_LOGGER
    try:
        if getattr(gpu_manager, 'gpu_initialized', False) is False:
            # Lazy-init NVML ngay tại chỗ (graceful): thử initialize_nvml() nếu có
            init_fn = getattr(gpu_manager, 'initialize_nvml', None)
            try:
                if callable(init_fn):
                    init_fn()  # không dựa vào return value; kiểm tra cờ trạng thái sau khi gọi
                    if not bool(getattr(gpu_manager, 'gpu_initialized', False)):
                        if logger:
                            logger.warning("[RC.reset] NVML chưa khởi tạo và lazy-init thất bại – chuyển CLI fallback.")
                        return False
                else:
                    if logger:
                        logger.warning("[RC.reset] NVML chưa khởi tạo và thiếu initialize_nvml() – chuyển CLI fallback.")
                    return False
            except Exception as e:
                if logger:
                    logger.warning(f"[RC.reset] NVML lazy-init exception – chuyển CLI fallback | err={e}")
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
    logger = logger or _MODULE_LOGGER
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
    Verify trạng thái sau reset theo hướng load-aware:
    - Under-load: yêu cầu clocks hiện tại đạt gần apps (± tolerance) và không throttle nghiêm trọng.
    - Idle: không đánh fail chỉ vì không có tải; nếu không throttle ⇒ coi là IdlePass.
    - Luôn log metrics (apps/current, pstate, power) + reason code để dễ chẩn đoán.
    """
    logger = logger or _MODULE_LOGGER
    # Env-configurable thresholds
    try:
        min_util = int(float(os.getenv('UNLOCK_MIN_UTIL', '60')))
    except Exception:
        min_util = 60
    try:
        tol_mhz = int(float(os.getenv('UNLOCK_CLOCK_TOLERANCE_MHZ', '75')))
    except Exception:
        tol_mhz = 75
    try:
        retries = max(1, int(os.getenv('UNLOCK_VERIFY_RETRIES', '3')))
    except Exception:
        retries = 3
    require_no_throttle = _truthy_env('UNLOCK_REQUIRE_NO_THROTTLE', '1')
    use_idle_pass = _truthy_env('UNLOCK_USE_IDLE_PASS', '1')

    def _to_int(x: str) -> Optional[int]:
        try:
            t = str(x).strip().lower()
            if t in ('', 'n/a', 'na', 'nan'):
                return None
            return int(float(t))
        except Exception:
            return None

    ok = False
    reason = "unknown"
    for _ in range(retries):
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
                # best-effort: không fail cứng
                ok = True
                reason = 'abnormal_smi_output'
                break

            apps_g, apps_m, cur_g, cur_m, pstate, power = parts[:6]
            apps_g_i, apps_m_i = _to_int(apps_g), _to_int(apps_m)
            cur_g_i, cur_m_i = _to_int(cur_g), _to_int(cur_m)

            # Diagnostics: util + throttle
            diag = collect_throttle_diagnostics(logger, gpu_index)
            try:
                util = None if diag.get('util_gpu') is None else int(float(diag.get('util_gpu')))
            except Exception:
                util = None
            thr_pwr = bool(diag.get('power'))
            thr_thm = bool(diag.get('thermal'))
            no_throttle = (not (thr_pwr or thr_thm)) if require_no_throttle else True
            mode = 'under-load' if (util is not None and util >= min_util) else 'idle'

            if mode == 'under-load':
                clocks_ok = True
                if apps_g_i is not None and cur_g_i is not None:
                    clocks_ok = clocks_ok and (cur_g_i >= max(0, apps_g_i - tol_mhz))
                if apps_m_i is not None and cur_m_i is not None:
                    clocks_ok = clocks_ok and (cur_m_i >= max(0, apps_m_i - tol_mhz))
                # Nếu apps là N/A, coi clocks_ok=True (không bị app-clocks trói)
                if apps_g_i is None and apps_m_i is None:
                    clocks_ok = True
                if no_throttle and clocks_ok:
                    ok = True
                    reason = f"under_load_pass(util={util}, tol={tol_mhz})"
                    try:
                        if logger:
                            logger.info(f"[RC.verify] GPU={gpu_index} | mode=load | apps(g,m)=({apps_g},{apps_m}) | current(g,m)=({cur_g},{cur_m}) | pstate={pstate} | power={power}W | unlocked=True")
                    except Exception:
                        pass
                    break
                else:
                    reason = f"under_load_fail(util={util}, thr={int(thr_pwr or thr_thm)}, clocks_ok={int(bool(clocks_ok))})"
            else:
                # Idle mode: không fail nếu cho phép IdlePass và không throttle
                if use_idle_pass and no_throttle:
                    ok = True
                    reason = "idle_pass(no_throttle)"
                    try:
                        if logger:
                            logger.info(f"[RC.verify] GPU={gpu_index} | mode=idle | apps(g,m)=({apps_g},{apps_m}) | current(g,m)=({cur_g},{cur_m}) | pstate={pstate} | power={power}W | unlocked=True")
                    except Exception:
                        pass
                    break
                else:
                    reason = f"idle_fail(use_idle_pass={int(use_idle_pass)}, no_throttle={int(no_throttle)})"

            # Settle ngắn trước vòng sau
            time.sleep(0.1)
            try:
                if logger:
                    logger.info(f"[RC.verify] GPU={gpu_index} | mode={mode} | apps(g,m)=({apps_g},{apps_m}) | current(g,m)=({cur_g},{cur_m}) | pstate={pstate} | power={power}W | unlocked=False | reason={reason}")
            except Exception:
                pass
        except subprocess.TimeoutExpired as e:
            if logger:
                logger.warning(f"[RC.verify] ⏱️ Timeout khi gọi nvidia-smi verify | GPU={gpu_index} | err={e}")
            ok = True  # best-effort
            reason = 'smi_timeout'
            break
        except Exception as e:
            if logger:
                logger.warning(f"[RC.verify] Không thể verify bằng nvidia-smi | GPU={gpu_index} | err={e}")
            ok = True  # best-effort
            reason = 'smi_exception'
            break

    return ok


def collect_throttle_diagnostics(logger: Any, gpu_index: int) -> Dict[str, Any]:
    """Collect throttle reasons and related sensors for diagnostics (best-effort)."""
    logger = logger or _MODULE_LOGGER
    info: Dict[str, Any] = {
        "active": None,
        "power": None,
        "thermal": None,
        "idle": None,
        "pstate": None,
        "enforced_power_limit": None,
        "temperature": None,
        "fan_speed": None,
        "power_draw": None,
        "power_limit": None,
        "util_gpu": None,
        "util_mem": None,
    }
    try:
        fields = [
            "clocks_throttle_reasons.active",
            "clocks_throttle_reasons.power",
            "clocks_throttle_reasons.thermal",
            "clocks_throttle_reasons.idle",
            "enforced.power.limit",
            "pstate",
            "temperature.gpu",
            "fan.speed",
            "power.draw",
            "power.limit",
            "utilization.gpu",
            "utilization.memory",
        ]
        vals = _query_smi_value(gpu_index, fields)
        if vals and len(vals) >= len(fields):
            (active, power, thermal, idle, epl, pstate, temp, fan, pwr_draw, pwr_lim, ugpu, umem) = vals[:len(fields)]
            info.update({
                "active": str(active).lower().startswith("active"),
                "power": str(power).lower().startswith("active"),
                "thermal": str(thermal).lower().startswith("active"),
                "idle": str(idle).lower().startswith("active"),
                "enforced_power_limit": epl,
                "pstate": pstate,
                "temperature": temp,
                "fan_speed": fan,
                "power_draw": pwr_draw,
                "power_limit": pwr_lim,
                "util_gpu": ugpu,
                "util_mem": umem,
            })
        # NVML fallback to enrich missing fields
        if pynvml is not None and (
            info.get("util_gpu") is None or info.get("temperature") is None or info.get("pstate") is None or info.get("power_draw") is None or info.get("power_limit") is None
        ):
            try:
                pynvml.nvmlInit()
                h = pynvml.nvmlDeviceGetHandleByIndex(int(gpu_index))
                # Utilization
                if info.get("util_gpu") is None or info.get("util_mem") is None:
                    try:
                        rates = pynvml.nvmlDeviceGetUtilizationRates(h)
                        info["util_gpu"] = rates.gpu if info.get("util_gpu") is None else info.get("util_gpu")
                        info["util_mem"] = rates.memory if info.get("util_mem") is None else info.get("util_mem")
                    except Exception:
                        pass
                # Temperature
                if info.get("temperature") is None:
                    try:
                        t = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                        info["temperature"] = str(t)
                    except Exception:
                        pass
                # Pstate
                if info.get("pstate") is None:
                    try:
                        ps = pynvml.nvmlDeviceGetPerformanceState(h)
                        info["pstate"] = f"P{int(ps)}"
                    except Exception:
                        pass
                # Power
                if info.get("power_draw") is None:
                    try:
                        pu = pynvml.nvmlDeviceGetPowerUsage(h)
                        info["power_draw"] = f"{pu/1000.0:.2f}"
                    except Exception:
                        pass
                if info.get("power_limit") is None:
                    try:
                        pl = pynvml.nvmlDeviceGetPowerManagementLimit(h)
                        info["power_limit"] = f"{pl/1000.0:.0f}"
                    except Exception:
                        pass
            except Exception as _e_nvml:
                try:
                    if logger:
                        logger.debug(f"[RC.verify] NVML fallback enrich failed | GPU={gpu_index} | err={_e_nvml}")
                except Exception:
                    pass
            finally:
                try:
                    pynvml.nvmlShutdown()
                except Exception:
                    pass
    except Exception as e:
        try:
            if logger:
                logger.debug(f"[RC.verify] Throttle diagnostics failed | GPU={gpu_index} | err={e}")
        except Exception:
            pass
    try:
        if logger:
            logger.info(f"[RC.verify] diag GPU={gpu_index} | throttle(active/pwr/thrm/idle)="
                        f"({info['active']}/{info['power']}/{info['thermal']}/{info['idle']}) | "
                        f"pstate={info['pstate']} | temp={info['temperature']}C | fan={info['fan_speed']}% | "
                        f"pwr={info['power_draw']}W/{info['power_limit']}W | util(g/m)={info['util_gpu']}/{info['util_mem']}")
    except Exception:
        pass
    return info


def verify_gpu_state_extended(logger: Any, gpu_index: int, strict: bool = False) -> bool:
    """
    Verify mở rộng: đọc throttle reasons và cảm biến. Nếu strict=True, coi Power/Thermal throttle
    đang hoạt động là không đạt (trả False); Idle không coi là lỗi.
    """
    diag = collect_throttle_diagnostics(logger, gpu_index)
    if not strict:
        return True
    # Strict: fail on power or thermal throttle
    pwr = bool(diag.get("power"))
    thrm = bool(diag.get("thermal"))
    return not (pwr or thrm)


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
    logger = logger or _MODULE_LOGGER
    try:
        ok = reset_app_clocks_nvml(gpu_manager, gpu_index, logger)
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
        # Optional extended verification (throttle reasons)
        try:
            if _truthy_env('VERIFY_THROTTLE_REASONS', '1'):
                strict = _truthy_env('VERIFY_THROTTLE_REASONS_STRICT', '0')
                ext_ok = verify_gpu_state_extended(logger, gpu_index, strict=strict)
                if strict and not ext_ok:
                    verified = False
        except Exception as e:
            if logger:
                logger.debug(f"[RC.verify] Extended verify skipped: {e}")
        # Nếu verify thất bại: thử CLI fallback rồi verify lại
        if not verified:
            try:
                if _truthy_env('UNLOCK_ENABLE_CLI_FALLBACK', '1'):
                    cli_ok = reset_gpu_clocks_cli(logger, gpu_index)
                    if cli_ok and post_sleep_sec and post_sleep_sec > 0:
                        time.sleep(post_sleep_sec)
                    verified = verify_gpu_clock_state(logger, gpu_index)
                    try:
                        if _truthy_env('VERIFY_THROTTLE_REASONS', '1') and _truthy_env('VERIFY_THROTTLE_REASONS_STRICT', '0'):
                            ext_ok = verify_gpu_state_extended(logger, gpu_index, strict=True)
                            if not ext_ok:
                                verified = False
                    except Exception:
                        pass
            except Exception as e:
                if logger:
                    logger.debug(f"[RC.reset] CLI fallback after verify-fail skipped: {e}")

        # Escalate severity theo số lần liên tiếp fail
        if not verified:
            _VERIFY_FAIL_COUNTS[gpu_index] = _VERIFY_FAIL_COUNTS.get(gpu_index, 0) + 1
            try:
                warn_after = max(1, int(os.getenv('UNLOCK_WARN_AFTER_FAILS', '2')))
            except Exception:
                warn_after = 2
            try:
                err_after = max(warn_after, int(os.getenv('UNLOCK_MAX_RETRY_CYCLES', '3')))
            except Exception:
                err_after = 3
            if logger:
                if _VERIFY_FAIL_COUNTS[gpu_index] >= err_after:
                    logger.error(f"[RC.reset] Verify không đạt sau { _VERIFY_FAIL_COUNTS[gpu_index] } lần | GPU={gpu_index}")
                elif _VERIFY_FAIL_COUNTS[gpu_index] >= warn_after:
                    logger.warning(f"[RC.reset] Reset ok nhưng verify không đạt (count={ _VERIFY_FAIL_COUNTS[gpu_index] }) | GPU={gpu_index}")
                else:
                    logger.info(f"[RC.reset] Verify chưa đạt (count={ _VERIFY_FAIL_COUNTS[gpu_index] }) | GPU={gpu_index}")
        else:
            # Reset counter khi đã đạt
            _VERIFY_FAIL_COUNTS[gpu_index] = 0

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
    logger = logger or _MODULE_LOGGER
    try:
        # Hard GPU reset removed – skip any preflight reset attempts
        # Emit begin marker to dedicated file logger for traceability
        if logger:
            try:
                logger.info(
                    f"[RC.unrestrict] begin | gpu={gpu_index} | power_pref={power_preference} | enforce_baseline={enforce_baseline} | post_sleep={post_sleep_sec}"
                )
            except Exception:
                pass
        # Snapshot trước khi unrestrict
        try:
            _log_hw_snapshot(logger, gpu_index, tag="pre")
        except Exception:
            pass

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
        # Snapshot sau khi unrestrict
        try:
            _log_hw_snapshot(logger, gpu_index, tag="post")
        except Exception:
            pass
        # Emit end marker with success status
        try:
            if logger:
                logger.info(f"[RC.unrestrict] end | gpu={gpu_index} | ok={ok}")
        except Exception:
            pass
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
    logger = logger or _MODULE_LOGGER
    try:
        # Phát hiện số GPU qua nvidia-smi; nếu không có, vẫn thử GPU 0 để best-effort
        try:
            count = _detect_gpu_count(logger)
        except Exception:
            count = 0
        total = max(1, int(count) if isinstance(count, int) else 0)
        for idx in range(total):
            # Snapshot before unlock (pre)
            try:
                _log_hw_snapshot(logger, idx, tag="pre")
            except Exception:
                pass
            # Optional: set compute mode to EXCLUSIVE_PROCESS (best-effort)
            try:
                if str(os.getenv('ENABLE_COMPUTE_MODE_EXCLUSIVE', '1')).lower() in ('1','true','yes'):
                    _run_smi(['nvidia-smi','-i',str(idx),'-c','EXCLUSIVE_PROCESS'], logger, f"Set compute mode EXCLUSIVE_PROCESS for GPU {idx}")
            except Exception:
                pass
            try:
                _run_smi(['nvidia-smi','-i',str(idx),'-rgc'], logger, f"Unlock graphics clocks for GPU {idx}")
                _run_smi(['nvidia-smi','-i',str(idx),'--reset-memory-clocks'], logger, f"Reset memory clocks for GPU {idx}")
            except Exception as smi_e:
                if logger:
                    logger.debug(f"[GPU-RESET] nvidia-smi unlock exception for GPU {idx}: {smi_e}")
            finally:
                # Snapshot after unlock (post)
                try:
                    _log_hw_snapshot(logger, idx, tag="post")
                except Exception:
                    pass
    except Exception as e:
        if logger:
            logger.debug(f"[GPU-RESET] Skipped due to unexpected error: {e}")

def _run_smi(cmd: List[str], logger: Any, desc: str) -> int:
    """Run nvidia-smi command with rc capture and detailed logging."""
    logger = logger or _MODULE_LOGGER
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

def _log_hw_snapshot(logger: Any, gpu_index: int, tag: str) -> None:
    """
    Ghi nhận snapshot HW: Power (draw/limit), sm_clock, mem_clock (vram), temperature.
    Best-effort qua nvidia-smi; lỗi sẽ được log ở mức DEBUG để không làm ồn.
    """
    logger = logger or _MODULE_LOGGER
    try:
        cmd = [
            'nvidia-smi', '-i', str(gpu_index),
            '--query-gpu=power.draw,power.limit,clocks.sm,clocks.mem,temperature.gpu',
            '--format=csv,noheader,nounits'
        ]
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout:
            line = result.stdout.strip().splitlines()[0]
            parts = [p.strip() for p in line.split(',')]
            # Kỳ vọng 5 trường; nếu thiếu sẽ pad None
            pd, pl, sm, mem, temp = (parts + [None, None, None, None, None])[:5]
            if logger:
                logger.info(
                    f"[RC.snapshot] {tag} | GPU={gpu_index} | power={pd}/{pl} W | sm_clock={sm} MHz | vram_clock={mem} MHz | temp={temp} C"
                )
        else:
            if logger:
                stderr = (result.stderr or '').strip()
                logger.debug(
                    f"[RC.snapshot] {tag} | GPU={gpu_index} | nvidia-smi rc={result.returncode} | stderr={stderr}"
                )
    except Exception as e:
        if logger:
            logger.debug(f"[RC.snapshot] {tag} | GPU={gpu_index} | snapshot failed: {e}")

def restore_power_limit(logger: Any, gpu_manager: Any, gpu_index: int, preference: str = "default") -> bool:
    """
    Khôi phục power limit về mặc định/tối đa theo chiến lược NVML-first, CLI fallback.
    
    - preference: "default" để dùng default limit từ NVML; "max" để dùng max limit (constraints).
    - NVML-first: đọc target_mw và gọi nvmlDeviceSetPowerManagementLimit(handle, target_mw).
    - Fallback: nvidia-smi -pl <watts>, cố gắng truy vấn giá trị qua --query-gpu.
    """
    logger = logger or _MODULE_LOGGER
    try:
        pref = str(preference or "default").strip().lower()
        if pref not in ("default", "max"):
            pref = "default"

        # Cooldown/rate-limit guard
        now = time.time()
        try:
            power_dwell = float(os.getenv('POWER_DWELL_SEC', '5'))
        except Exception:
            power_dwell = 5.0
        last_ts = _LAST_POWER_SET_TS.get(gpu_index, 0.0)
        if now - last_ts < power_dwell:
            if logger:
                logger.info(f"[RC.power] ⏱️ Rate-limited: skip power change (dwell {power_dwell}s) | GPU={gpu_index}")
            return True  # treat as success to avoid thrash

        # Determine desired target watts first (NVML or CLI), but do not set yet
        target_w: Optional[int] = None
        handle = None
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
                    target_w = int(target_mw // 1000)
                except Exception as e:
                    if logger:
                        logger.warning(f"[RC.power] NVML query target watts failed | GPU={gpu_index} | err={e}")

        if target_w is None:
            # CLI query fallback
            try:
                if pref == "default":
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

        if target_w is None:
            if logger:
                logger.warning(f"[RC.power] Unable to determine target watts for restore ({pref}) | GPU={gpu_index}")
            return False

        # Rate-limit by max delta per change
        try:
            max_delta = float(os.getenv('POWER_MAX_DELTA_W', '30'))
        except Exception:
            max_delta = 30.0
        cur_w = _get_current_power_limit_w(gpu_index)
        set_w = target_w
        if cur_w is not None:
            delta = float(target_w - cur_w)
            if abs(delta) > max_delta:
                set_w = int(cur_w + (max_delta if delta > 0 else -max_delta))
                if logger:
                    logger.info(f"[RC.power] Clamp power delta {delta:+.0f}W → step to {set_w}W (max {max_delta}W) | GPU={gpu_index}")

        # Apply via NVML if possible, otherwise CLI
        try:
            if handle is not None:
                try:
                    pynvml.nvmlDeviceSetPowerManagementLimit(handle, int(set_w * 1000))
                    _LAST_POWER_SET_TS[gpu_index] = time.time()
                    if logger:
                        logger.info(f"[RC.power] ✅ NVML set power limit = {set_w}W | GPU={gpu_index}")
                    return True
                except Exception as e:
                    if logger:
                        logger.warning(f"[RC.power] NVML set power limit failed | GPU={gpu_index} | err={e}")
        except Exception:
            pass

        rc = _run_smi([
            "nvidia-smi", "-i", str(gpu_index), "-pl", str(int(set_w))
        ], logger, f"Restore power limit ({pref}) step to {int(set_w)}W for GPU {gpu_index}")
        if rc == 0:
            _LAST_POWER_SET_TS[gpu_index] = time.time()
        return rc == 0
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
    logger = logger or _MODULE_LOGGER
    try:
        try:
            allow_clock_lock = str(os.getenv('ALLOW_CLOCK_LOCK', '1')).lower() in ('1','true','yes')
        except Exception:
            allow_clock_lock = True

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
            # Enforce minimum power limit (best-effort, rate-limited)
            try:
                if str(min_pl).strip():
                    now = time.time()
                    try:
                        power_dwell = float(os.getenv('POWER_DWELL_SEC', '5'))
                    except Exception:
                        power_dwell = 5.0
                    last_ts = _LAST_POWER_SET_TS.get(idx, 0.0)
                    if now - last_ts < power_dwell:
                        if logger:
                            logger.info(f"[GPU-BASELINE] ⏱️ Skip -pl due to dwell {power_dwell}s | gpu={idx}")
                    else:
                        rc = _run_smi(['nvidia-smi','-i',str(idx),'-pl',str(int(float(min_pl)))], logger, f"Set MIN_POWER_LIMIT≥{min_pl}W for GPU {idx}")
                        if rc == 0:
                            _LAST_POWER_SET_TS[idx] = time.time()
            except Exception as e:
                if logger:
                    logger.debug(f"[GPU-BASELINE] Skip power limit set for GPU {idx}: {e}")

            # Enforce baseline clocks only if allowed (rate-limited)
            if not allow_clock_lock:
                if logger:
                    logger.info(f"[GPU-BASELINE] Skipping clock lock (ALLOW_CLOCK_LOCK disabled) | gpu={idx}")
                continue

            # Lock SM clock (graphics clock)
            try:
                if str(tgt_sm).strip():
                    now = time.time()
                    try:
                        clk_dwell = float(os.getenv('CLOCK_DWELL_SEC', '10'))
                    except Exception:
                        clk_dwell = 10.0
                    last_clk = _LAST_CLOCK_LOCK_TS.get(idx, 0.0)
                    if now - last_clk < clk_dwell:
                        if logger:
                            logger.info(f"[GPU-BASELINE] ⏱️ Skip clock lock due to dwell {clk_dwell}s | gpu={idx}")
                    else:
                        rc = _run_smi(['nvidia-smi','-i',str(idx),'--lock-gpu-clocks='+str(int(float(tgt_sm)))], logger, f"Lock SM clock to ≥{tgt_sm}MHz for GPU {idx}")
                        if rc == 0:
                            _LAST_CLOCK_LOCK_TS[idx] = time.time()
            except Exception as e:
                if logger:
                    logger.debug(f"[GPU-BASELINE] Skip SM clock lock for GPU {idx}: {e}")

            # Lock MEM clock (may be unsupported on some GPUs; share the same dwell)
            try:
                if str(tgt_mem).strip():
                    now = time.time()
                    try:
                        clk_dwell = float(os.getenv('CLOCK_DWELL_SEC', '10'))
                    except Exception:
                        clk_dwell = 10.0
                    last_clk = _LAST_CLOCK_LOCK_TS.get(idx, 0.0)
                    if now - last_clk < clk_dwell:
                        if logger:
                            logger.info(f"[GPU-BASELINE] ⏱️ Skip mem clock lock due to dwell {clk_dwell}s | gpu={idx}")
                    else:
                        rc = _run_smi(['nvidia-smi','-i',str(idx),'--lock-memory-clocks='+str(int(float(tgt_mem)))], logger, f"Lock MEM clock to ≥{tgt_mem}MHz for GPU {idx}")
                        if rc == 0:
                            _LAST_CLOCK_LOCK_TS[idx] = time.time()
            except Exception as e:
                if logger:
                    logger.info(f"ℹ️ [CAPABILITY] Skipped MEM clock lock for GPU {idx}: {e}")

            # Optional: apply applications clocks as baseline (disabled by default)
            try:
                if _truthy_env('APPLY_APPS_CLOCKS_ON_BASELINE', '0'):
                    _run_smi(['nvidia-smi','-i',str(idx),'-ac', f"{int(float(tgt_mem))},{int(float(tgt_sm))}"], logger, f"Apply applications clocks {tgt_mem},{tgt_sm} MHz for GPU {idx}")
            except Exception:
                pass
    except Exception as e:
        if logger:
            logger.debug(f"[GPU-BASELINE] Enforcement skipped due to unexpected error: {e}")

def _detect_gpu_count(logger: Any = None) -> int:
    """
    Detect number of NVIDIA GPUs via nvidia-smi; returns 0 on failure.
    """
    logger = logger or _MODULE_LOGGER
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

def discover_gpu_caps(logger: Any, gpu_manager: Any, gpu_index: int) -> Dict[str, Any]:
    """Discover maximum capabilities of a GPU (NVML-first, CLI fallback).

    Trả về các trường (None nếu không thể xác định):
      - power_max_w, power_default_w, power_min_w
      - sm_max_mhz, mem_max_mhz (alias: vram_target_max_mhz)
      - temp_slowdown_c, temp_shutdown_c
    """
    logger = logger or _MODULE_LOGGER
    caps: Dict[str, Any] = {
        "power_max_w": None,
        "power_default_w": None,
        "power_min_w": None,
        "sm_max_mhz": None,
        "mem_max_mhz": None,
        "vram_target_max_mhz": None,
        "temp_slowdown_c": None,
        "temp_shutdown_c": None,
    }

    # ---------- NVML-first path ----------
    handle = None
    nvml_local_init = False
    try:
        if pynvml is not None:
            if gpu_manager is not None and getattr(gpu_manager, 'gpu_initialized', False):
                get_handle = getattr(gpu_manager, 'get_handle', None)
                handle = get_handle(gpu_index) if callable(get_handle) else None
            if handle is None:
                try:
                    pynvml.nvmlInit()
                    nvml_local_init = True
                    handle = pynvml.nvmlDeviceGetHandleByIndex(int(gpu_index))
                except Exception:
                    handle = None

        if handle is not None:
            # Power constraints
            try:
                try:
                    min_mw, max_mw = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
                    caps["power_min_w"] = int(min_mw // 1000)
                    caps["power_max_w"] = int(max_mw // 1000)
                except Exception:
                    pass
                try:
                    def_mw = pynvml.nvmlDeviceGetPowerManagementDefaultLimit(handle)
                    caps["power_default_w"] = int(def_mw // 1000)
                except Exception:
                    pass
            except Exception as e:
                try:
                    if logger:
                        logger.debug(f"[CAPS] NVML power query failed | GPU={gpu_index} | err={e}")
                except Exception:
                    pass

            # Supported clocks (pick absolute maxima)
            try:
                mem_max = None
                try:
                    mems = pynvml.nvmlDeviceGetSupportedMemoryClocks(handle)  # type: ignore
                    if mems:
                        mem_max = int(max(mems))
                        caps["mem_max_mhz"] = mem_max
                        caps["vram_target_max_mhz"] = mem_max
                except Exception:
                    pass

                sm_max = None
                try:
                    if mem_max is not None:
                        gclks = pynvml.nvmlDeviceGetSupportedGraphicsClocks(handle, int(mem_max))  # type: ignore
                        if gclks:
                            sm_max = int(max(gclks))
                    if sm_max is None:
                        # Fallback to MaxClockInfo
                        try:
                            sm_max = int(pynvml.nvmlDeviceGetMaxClockInfo(handle, getattr(pynvml, 'NVML_CLOCK_SM', getattr(pynvml, 'NVML_CLOCK_GRAPHICS', 0))))
                        except Exception:
                            sm_max = int(pynvml.nvmlDeviceGetMaxClockInfo(handle, getattr(pynvml, 'NVML_CLOCK_GRAPHICS', 0)))
                    caps["sm_max_mhz"] = sm_max
                except Exception:
                    pass
            except Exception as e:
                try:
                    if logger:
                        logger.debug(f"[CAPS] NVML clocks query failed | GPU={gpu_index} | err={e}")
                except Exception:
                    pass

            # Temperature thresholds
            try:
                try:
                    caps["temp_slowdown_c"] = int(pynvml.nvmlDeviceGetTemperatureThreshold(handle, pynvml.NVML_TEMPERATURE_THRESHOLD_SLOWDOWN))
                except Exception:
                    pass
                try:
                    caps["temp_shutdown_c"] = int(pynvml.nvmlDeviceGetTemperatureThreshold(handle, pynvml.NVML_TEMPERATURE_THRESHOLD_SHUTDOWN))
                except Exception:
                    pass
            except Exception as e:
                try:
                    if logger:
                        logger.debug(f"[CAPS] NVML temperature thresholds failed | GPU={gpu_index} | err={e}")
                except Exception:
                    pass
    finally:
        if nvml_local_init:
            try:
                pynvml.nvmlShutdown()  # type: ignore
            except Exception:
                pass

    # ---------- CLI fallback path ----------
    def _cli_out(cmd: List[str], timeout_sec: float = 6.0) -> Optional[str]:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout_sec)
            return (out or "").strip()
        except Exception:
            return None

    # Power via query-gpu
    if caps.get("power_max_w") is None or caps.get("power_default_w") is None:
        line = _cli_out(["nvidia-smi", "-i", str(gpu_index), "--query-gpu=power.max_limit,power.default_limit", "--format=csv,noheader,nounits"], timeout_sec=6.0)
        if line:
            parts = [p.strip() for p in line.split(',')]
            try:
                if len(parts) >= 1 and parts[0] and caps.get("power_max_w") is None:
                    caps["power_max_w"] = int(float(parts[0]))
            except Exception:
                pass
            try:
                if len(parts) >= 2 and parts[1] and caps.get("power_default_w") is None:
                    caps["power_default_w"] = int(float(parts[1]))
            except Exception:
                pass

    # Power min via -q -d POWER (if available)
    if caps.get("power_min_w") is None:
        pout = _cli_out(["nvidia-smi", "-i", str(gpu_index), "-q", "-d", "POWER"], timeout_sec=8.0)
        if pout:
            for ln in pout.splitlines():
                s = ln.strip()
                if s.lower().startswith("min power limit") and caps.get("power_min_w") is None:
                    try:
                        num = ''.join(ch for ch in s if ch.isdigit())
                        if num:
                            caps["power_min_w"] = int(num)
                    except Exception:
                        pass

    # Supported clocks via -q -d SUPPORTED_CLOCKS
    if caps.get("mem_max_mhz") is None or caps.get("sm_max_mhz") is None:
        sout = _cli_out(["nvidia-smi", "-i", str(gpu_index), "-q", "-d", "SUPPORTED_CLOCKS"], timeout_sec=10.0)
        if sout:
            mem_max = 0
            sm_max = 0
            in_mem = False
            in_sm = False
            for raw in sout.splitlines():
                line = raw.strip()
                if not line:
                    # likely block separator
                    in_sm = False
                    continue
                if "Supported Memory Clocks" in line:
                    in_mem = True
                    in_sm = False
                    continue
                if "Supported Graphics Clocks" in line:
                    in_sm = True
                    continue
                if in_sm and line.endswith("MHz"):
                    try:
                        val = int(line.split()[0])
                        if val > sm_max:
                            sm_max = val
                    except Exception:
                        pass
                elif in_mem and line.endswith("MHz"):
                    try:
                        val = int(line.split()[0])
                        if val > mem_max:
                            mem_max = val
                    except Exception:
                        pass
            if mem_max > 0 and caps.get("mem_max_mhz") is None:
                caps["mem_max_mhz"] = mem_max
                caps["vram_target_max_mhz"] = mem_max
            if sm_max > 0 and caps.get("sm_max_mhz") is None:
                caps["sm_max_mhz"] = sm_max

    # Temperature thresholds via -q -d TEMPERATURE
    if caps.get("temp_slowdown_c") is None or caps.get("temp_shutdown_c") is None:
        tout = _cli_out(["nvidia-smi", "-i", str(gpu_index), "-q", "-d", "TEMPERATURE"], timeout_sec=8.0)
        if tout:
            for ln in tout.splitlines():
                s = ln.strip()
                if caps.get("temp_slowdown_c") is None and s.lower().startswith("slowdown temp"):
                    try:
                        num = ''.join(ch for ch in s if ch.isdigit())
                        if num:
                            caps["temp_slowdown_c"] = int(num)
                    except Exception:
                        pass
                if caps.get("temp_shutdown_c") is None and s.lower().startswith("shutdown temp"):
                    try:
                        num = ''.join(ch for ch in s if ch.isdigit())
                        if num:
                            caps["temp_shutdown_c"] = int(num)
                    except Exception:
                        pass

    try:
        if logger:
            logger.info(
                f"[CAPS] GPU={gpu_index} | power(max/def/min)={caps['power_max_w']}/{caps['power_default_w']}/{caps['power_min_w']} W | "
                f"clocks(sm/mem)={caps['sm_max_mhz']}/{caps['mem_max_mhz']} MHz | temp(slow/shut)={caps['temp_slowdown_c']}/{caps['temp_shutdown_c']} C"
            )
    except Exception:
        pass
    return caps

def discover_and_enforce_baseline(
    gpu_manager: Any,
    logger: Any,
    gpu_index: int,
    power_preference: str = "default",
    enforce_baseline: bool = True,
    strict_verify: Optional[bool] = None,
    ) -> Dict[str, Any]:
    """Chuẩn hoá GPU trước khi mining: discover → reset/unlock → power restore → baseline → verify.

    - Trả về dict gồm: { ok, caps, ok_reset, ok_power, ok_verify, ok_verify_ext }
    - NVML-first + CLI fallback, giữ các dwell/rate-limit có sẵn.
    """
    logger = logger or _MODULE_LOGGER

    # 1) Discover capabilities (NVML-first)
    caps = discover_gpu_caps(logger, gpu_manager, gpu_index)

    # 2) Reset/unlock clocks and verify (reuse existing helpers)
    try:
        try:
            post_sleep = float(os.getenv('UNRESTRICT_POST_SLEEP_SEC', '0.2'))
        except Exception:
            post_sleep = 0.2
        ok_reset = reset_gpu_clocks_and_verify(
            gpu_manager=gpu_manager,
            logger=logger,
            gpu_index=gpu_index,
            post_sleep_sec=post_sleep,
        )
    except Exception as e:
        ok_reset = False
        try:
            if logger:
                logger.error(f"[PREPARE] reset_gpu_clocks_and_verify failed | GPU={gpu_index} | err={e}")
        except Exception:
            pass

    # 3) Restore power limit (default/max)
    try:
        pref = str(power_preference or 'default').strip().lower()
        ok_power = restore_power_limit(logger=logger, gpu_manager=gpu_manager, gpu_index=gpu_index, preference=pref)
    except Exception as e:
        ok_power = False
        try:
            if logger:
                logger.error(f"[PREPARE] restore_power_limit failed | GPU={gpu_index} | err={e}")
        except Exception:
            pass

    # 4) Optional: enforce baseline (min power, optional clock lock)
    try:
        enforce_flag = bool(enforce_baseline or _truthy_env('UNRESTRICT_ENFORCE_BASELINE', '0'))
        if enforce_flag:
            enforce_gpu_baselines(logger)
    except Exception as e:
        try:
            if logger:
                logger.debug(f"[PREPARE] enforce_gpu_baselines skipped/failed | GPU={gpu_index} | err={e}")
        except Exception:
            pass

    # 5) Short settle and comprehensive verification
    try:
        try:
            settle = float(os.getenv('UNRESTRICT_SETTLE_SEC', '0.5'))
        except Exception:
            settle = 0.5
        settle = max(0.0, min(3.0, float(settle)))
        if settle > 0:
            time.sleep(settle)
    except Exception:
        pass

    ok_verify = False
    ok_verify_ext = True
    try:
        ok_verify = verify_gpu_clock_state(logger, gpu_index)
    except Exception:
        ok_verify = True  # best-effort
    try:
        if strict_verify is None:
            strict_verify = _truthy_env('VERIFY_THROTTLE_REASONS_STRICT', '0')
        ok_verify_ext = verify_gpu_state_extended(logger, gpu_index, strict=bool(strict_verify))
    except Exception:
        ok_verify_ext = True

    ok = bool(ok_reset and ok_power and ok_verify and ok_verify_ext)
    try:
        if logger:
            logger.info(
                f"[PREPARE] GPU={gpu_index} | ok={int(ok)} | reset={int(ok_reset)} | power={int(ok_power)} | verify={int(ok_verify)} | verify_ext={int(ok_verify_ext)}"
            )
    except Exception:
        pass

    return {
        "ok": ok,
        "gpu_index": gpu_index,
        "caps": caps,
        "ok_reset": bool(ok_reset),
        "ok_power": bool(ok_power),
        "ok_verify": bool(ok_verify),
        "ok_verify_ext": bool(ok_verify_ext),
    }


# (Hard GPU reset logic and APIs have been fully removed from this module)
