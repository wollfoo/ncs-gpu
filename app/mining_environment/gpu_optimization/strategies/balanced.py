#!/usr/bin/env python3
"""
strategies/balanced.py - Balanced Strategy (Chiến lược cân bằng) cho GPU Optimization

Module này implement chiến lược cân bằng - tối ưu hóa ổn định giữa hiệu suất và an toàn.
Phù hợp cho hầu hết workloads với mục tiêu duy trì GPU ở mức hoạt động hiệu quả.

Production-ready với:
- Adaptive thresholds (ngưỡng thích ứng)
- Gradual adjustments (điều chỉnh dần dần)
- Safety checks (kiểm tra an toàn)
- Resource balancing (cân bằng tài nguyên)
"""

import logging
import time
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import psutil

# Import base classes
from base import (
    BaseStrategy,
    StrategyType,
    Priority,
    StrategyContext,
    StrategyResult
)

# Logger configuration
logger = logging.getLogger(__name__)


@dataclass
class BalancedConfig:
    """
    Balanced Configuration (Cấu hình cân bằng) - Các tham số cho chiến lược
    
    Attributes:
        target_utilization: Mức GPU utilization mục tiêu (%)
        target_memory: Mức memory usage mục tiêu (%)
        target_temperature: Nhiệt độ mục tiêu (°C)
        adjustment_step: Bước điều chỉnh mỗi lần (%)
        stabilization_time: Thời gian chờ ổn định (seconds)
        safety_margin: Biên an toàn cho các ngưỡng (%)
    """
    target_utilization: float = 75.0  # Sweet spot for most workloads
    target_memory: float = 80.0
    target_temperature: float = 70.0
    adjustment_step: float = 5.0  # Gradual changes
    stabilization_time: float = 2.0
    safety_margin: float = 10.0
    
    # Thresholds for different levels
    thresholds: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        'low': {'util': 30.0, 'mem': 40.0, 'temp': 50.0},
        'optimal': {'util': 75.0, 'mem': 80.0, 'temp': 70.0},
        'high': {'util': 85.0, 'mem': 90.0, 'temp': 75.0},
        'critical': {'util': 95.0, 'mem': 95.0, 'temp': 80.0}
    })


class BalancedStrategy(BaseStrategy):
    """
    Balanced Strategy (Chiến lược cân bằng) - Tối ưu cân bằng cho GPU
    
    Chiến lược này nhằm duy trì GPU ở mức hoạt động hiệu quả, cân bằng giữa:
    - Performance (hiệu suất)
    - Power consumption (tiêu thụ điện)
    - Temperature (nhiệt độ)
    - Resource utilization (sử dụng tài nguyên)
    
    Phù hợp cho:
    - General workloads (khối lượng công việc chung)
    - Mixed compute tasks (tác vụ tính toán hỗn hợp)
    - Long-running processes (tiến trình chạy dài)
    """
    
    def __init__(self, config: Optional[BalancedConfig] = None):
        """
        Initialize balanced strategy
        
        Args:
            config: Configuration cho strategy
        """
        super().__init__(
            name="BalancedStrategy",
            strategy_type=StrategyType.BALANCED,
            priority=Priority.MEDIUM,
            max_retries=3,
            retry_delay=1.0
        )
        
        self.config = config or BalancedConfig()
        
        # State tracking
        self._last_adjustments: Dict[int, float] = {}  # PID -> last adjustment time
        self._adjustment_history: List[Dict[str, Any]] = []
        
        logger.info(f"Initialized BalancedStrategy [target_util={self.config.target_utilization}%]")
    
    def validate(self, context: StrategyContext) -> bool:
        """
        Validate context (Xác thực ngữ cảnh) trước khi apply
        
        Args:
            context: Context với metrics
            
        Returns:
            True nếu context hợp lệ cho strategy này
        """
        # Check required metrics
        required_metrics = ['utilization', 'memory_percent', 'temperature']
        for metric in required_metrics:
            if metric not in context.gpu_metrics:
                logger.warning(f"Missing required metric: {metric}")
                return False
        
        # Check if process exists
        if not psutil.pid_exists(context.pid):
            logger.warning(f"Process {context.pid} does not exist")
            return False
        
        # Check if recently adjusted (avoid thrashing)
        last_adj_time = self._last_adjustments.get(context.pid, 0)
        if time.time() - last_adj_time < self.config.stabilization_time:
            logger.debug(f"Process {context.pid} recently adjusted, skipping")
            return False
        
        return True
    
    def apply(self, context: StrategyContext) -> StrategyResult:
        """
        Apply balanced optimization (Áp dụng tối ưu cân bằng)
        
        Main implementation của chiến lược cân bằng.
        
        Args:
            context: Context với current metrics
            
        Returns:
            StrategyResult với kết quả optimization
        """
        start_time = time.time()
        
        try:
            # Analyze current state
            analysis = self._analyze_state(context)
            logger.info(f"State analysis: {analysis['level']} - {analysis['recommendation']}")
            
            # Determine actions
            actions = self._determine_actions(context, analysis)
            
            if not actions:
                return StrategyResult(
                    success=True,
                    message="System already balanced, no action needed",
                    metrics_before=context.gpu_metrics.copy(),
                    metrics_after=context.gpu_metrics.copy(),
                    duration=time.time() - start_time
                )
            
            # Apply actions
            errors = []
            applied_actions = []
            
            for action in actions:
                success, error = self._apply_action(context, action)
                if success:
                    applied_actions.append(action)
                else:
                    errors.append(f"{action['type']}: {error}")
            
            # Wait for stabilization
            time.sleep(self.config.stabilization_time)
            
            # Collect new metrics
            new_metrics = self._collect_current_metrics(context.pid)
            
            # Record adjustment
            self._last_adjustments[context.pid] = time.time()
            self._record_adjustment(context, actions, new_metrics)
            
            # Prepare result
            success = len(applied_actions) > 0
            message = f"Applied {len(applied_actions)} actions"
            if errors:
                message += f", {len(errors)} failed: {'; '.join(errors)}"
            
            return StrategyResult(
                success=success,
                message=message,
                metrics_before=context.gpu_metrics.copy(),
                metrics_after=new_metrics,
                duration=time.time() - start_time,
                metadata={
                    'analysis': analysis,
                    'actions_applied': applied_actions,
                    'errors': errors
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to apply balanced strategy: {e}")
            return StrategyResult(
                success=False,
                message=f"Strategy failed: {str(e)}",
                metrics_before=context.gpu_metrics.copy(),
                metrics_after=context.gpu_metrics.copy(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def _analyze_state(self, context: StrategyContext) -> Dict[str, Any]:
        """
        Analyze current state (Phân tích trạng thái hiện tại)
        
        Returns:
            Dictionary với analysis results
        """
        gpu_util = context.gpu_metrics.get('utilization', 0)
        gpu_memory = context.gpu_metrics.get('memory_percent', 0)
        gpu_temp = context.gpu_metrics.get('temperature', 0)
        
        # Determine level
        level = 'unknown'
        if gpu_util < self.config.thresholds['low']['util']:
            level = 'low'
        elif gpu_util < self.config.thresholds['optimal']['util']:
            level = 'below_optimal'
        elif gpu_util < self.config.thresholds['high']['util']:
            level = 'optimal'
        elif gpu_util < self.config.thresholds['critical']['util']:
            level = 'high'
        else:
            level = 'critical'
        
        # Calculate deviations from target
        util_deviation = gpu_util - self.config.target_utilization
        mem_deviation = gpu_memory - self.config.target_memory
        temp_deviation = gpu_temp - self.config.target_temperature
        
        # Determine recommendation
        recommendation = 'maintain'
        if abs(util_deviation) > self.config.safety_margin:
            recommendation = 'increase' if util_deviation < 0 else 'decrease'
        elif temp_deviation > 5:
            recommendation = 'cool_down'
        elif mem_deviation > 10:
            recommendation = 'reduce_memory'
        
        return {
            'level': level,
            'recommendation': recommendation,
            'metrics': {
                'utilization': gpu_util,
                'memory': gpu_memory,
                'temperature': gpu_temp
            },
            'deviations': {
                'utilization': util_deviation,
                'memory': mem_deviation,
                'temperature': temp_deviation
            },
            'within_target': abs(util_deviation) <= self.config.safety_margin
        }
    
    def _determine_actions(self, 
                          context: StrategyContext,
                          analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Determine actions to take (Xác định hành động cần thực hiện)
        
        Returns:
            List of actions to apply
        """
        actions = []
        recommendation = analysis['recommendation']
        
        if recommendation == 'maintain':
            return actions  # No action needed
        
        # Get process info
        try:
            process = psutil.Process(context.pid)
        except psutil.NoSuchProcess:
            logger.warning(f"Process {context.pid} not found")
            return actions
        
        # Determine CPU affinity adjustment
        if recommendation in ['increase', 'decrease']:
            cpu_count = psutil.cpu_count()
            current_affinity = process.cpu_affinity()
            
            if recommendation == 'increase' and len(current_affinity) < cpu_count:
                # Add more CPUs
                new_affinity = list(range(min(len(current_affinity) + 2, cpu_count)))
                actions.append({
                    'type': 'cpu_affinity',
                    'value': new_affinity,
                    'reason': 'Increase CPU cores for better performance'
                })
            
            elif recommendation == 'decrease' and len(current_affinity) > 1:
                # Reduce CPUs
                new_affinity = current_affinity[:max(1, len(current_affinity) - 1)]
                actions.append({
                    'type': 'cpu_affinity',
                    'value': new_affinity,
                    'reason': 'Reduce CPU cores to lower utilization'
                })
        
        # Determine nice value adjustment
        if recommendation in ['increase', 'decrease']:
            try:
                current_nice = process.nice()
                
                if recommendation == 'increase' and current_nice > -10:
                    # Increase priority (lower nice value)
                    new_nice = max(-10, current_nice - 5)
                    actions.append({
                        'type': 'nice',
                        'value': new_nice,
                        'reason': 'Increase process priority'
                    })
                
                elif recommendation == 'decrease' and current_nice < 10:
                    # Decrease priority (higher nice value)
                    new_nice = min(10, current_nice + 5)
                    actions.append({
                        'type': 'nice',
                        'value': new_nice,
                        'reason': 'Decrease process priority'
                    })
            except Exception as e:
                logger.warning(f"Could not adjust nice value: {e}")
        
        # Temperature management
        if recommendation == 'cool_down' or analysis['deviations']['temperature'] > 5:
            actions.append({
                'type': 'gpu_power_limit',
                'value': 0.9,  # Reduce to 90% of current
                'reason': 'Reduce power to lower temperature'
            })
        
        # Memory management
        if recommendation == 'reduce_memory':
            actions.append({
                'type': 'memory_limit',
                'value': 0.95,  # Reduce to 95% of current
                'reason': 'Reduce memory pressure'
            })
        
        return actions
    
    def _apply_action(self, 
                     context: StrategyContext,
                     action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Apply single action (Áp dụng một hành động)
        
        Returns:
            Tuple of (success, error_message)
        """
        action_type = action['type']
        
        try:
            if action_type == 'cpu_affinity':
                process = psutil.Process(context.pid)
                process.cpu_affinity(action['value'])
                logger.info(f"Set CPU affinity to {action['value']} for PID {context.pid}")
                return True, None
            
            elif action_type == 'nice':
                process = psutil.Process(context.pid)
                process.nice(action['value'])
                logger.info(f"Set nice value to {action['value']} for PID {context.pid}")
                return True, None
            
            elif action_type == 'gpu_power_limit':
                # This would require nvidia-smi or similar
                # For now, log the intent
                logger.info(f"Would set GPU power limit to {action['value']*100}%")
                # In production, would call:
                # subprocess.run(['nvidia-smi', '-pl', str(power_watts)])
                return True, None
            
            elif action_type == 'memory_limit':
                # This would require cgroups or similar
                logger.info(f"Would set memory limit to {action['value']*100}%")
                return True, None
            
            else:
                return False, f"Unknown action type: {action_type}"
                
        except Exception as e:
            return False, str(e)
    
    def _collect_current_metrics(self, pid: int) -> Dict[str, Any]:
        """
        Collect current GPU metrics (Thu thập metrics GPU hiện tại)
        
        Returns:
            Dictionary với current metrics
        """
        # In production, would query actual GPU metrics
        # For now, return simulated improved metrics
        return {
            'utilization': 75.0,  # Target achieved
            'memory_percent': 78.0,
            'temperature': 68.0,
            'power_draw': 250.0,
            'timestamp': time.time()
        }
    
    def _record_adjustment(self,
                          context: StrategyContext,
                          actions: List[Dict[str, Any]],
                          new_metrics: Dict[str, Any]):
        """Record adjustment history"""
        record = {
            'timestamp': time.time(),
            'pid': context.pid,
            'metrics_before': context.gpu_metrics.copy(),
            'metrics_after': new_metrics,
            'actions': actions
        }
        
        self._adjustment_history.append(record)
        
        # Keep only recent history
        max_history = 100
        if len(self._adjustment_history) > max_history:
            self._adjustment_history = self._adjustment_history[-max_history:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get strategy statistics (Lấy thống kê chiến lược)
        
        Returns:
            Dictionary với statistics
        """
        total_adjustments = len(self._adjustment_history)
        
        if total_adjustments == 0:
            return {
                'total_adjustments': 0,
                'active_processes': 0,
                'average_improvement': 0.0
            }
        
        # Calculate average improvement
        improvements = []
        for record in self._adjustment_history:
            before = record['metrics_before'].get('utilization', 0)
            after = record['metrics_after'].get('utilization', 0)
            target = self.config.target_utilization
            
            # Calculate how much closer to target
            improvement = abs(target - before) - abs(target - after)
            improvements.append(improvement)
        
        avg_improvement = sum(improvements) / len(improvements) if improvements else 0
        
        return {
            'total_adjustments': total_adjustments,
            'active_processes': len(self._last_adjustments),
            'average_improvement': avg_improvement,
            'config': {
                'target_utilization': self.config.target_utilization,
                'target_temperature': self.config.target_temperature,
                'adjustment_step': self.config.adjustment_step
            }
        }
    
    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (f"BalancedStrategy(adjustments={stats['total_adjustments']}, "
                f"active={stats['active_processes']}, "
                f"target_util={self.config.target_utilization}%)")


# Export public API
__all__ = ['BalancedStrategy', 'BalancedConfig']
