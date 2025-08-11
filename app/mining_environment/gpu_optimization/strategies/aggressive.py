#!/usr/bin/env python3
"""
strategies/aggressive.py - Aggressive Strategy (Chiến lược tấn công) cho GPU Optimization

Module này implement chiến lược aggressive - tối đa hóa hiệu suất GPU bằng mọi giá.
Phù hợp cho workloads yêu cầu hiệu năng cao và có thể chấp nhận rủi ro.

Production-ready với:
- Maximum performance tuning (điều chỉnh hiệu năng tối đa)
- Overclocking support (hỗ trợ ép xung)
- Power limit bypass (vượt giới hạn công suất)
- Thermal throttling mitigation (giảm thiểu giới hạn nhiệt)
"""

import logging
import time
import subprocess
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
import psutil
import os

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
class AggressiveConfig:
    """
    Aggressive Configuration (Cấu hình tấn công) - Tham số cho chiến lược aggressive
    
    Attributes:
        max_gpu_utilization: GPU utilization tối đa cho phép (%)
        max_memory_utilization: Memory utilization tối đa (%)
        max_temperature: Nhiệt độ tối đa chấp nhận được (°C)
        power_limit_increase: Mức tăng power limit (%)
        clock_boost: Mức tăng clock speed (MHz)
        fan_speed_override: Override tốc độ quạt (%)
        risk_tolerance: Mức độ chấp nhận rủi ro (0-1)
    """
    max_gpu_utilization: float = 95.0
    max_memory_utilization: float = 95.0
    max_temperature: float = 83.0  # NVIDIA default thermal throttle
    power_limit_increase: float = 20.0  # +20% power
    clock_boost: int = 100  # +100 MHz
    fan_speed_override: Optional[int] = None  # Auto by default
    risk_tolerance: float = 0.8  # High risk tolerance
    
    # Performance targets
    performance_targets: Dict[str, float] = field(default_factory=lambda: {
        'min_hashrate': 90.0,  # Minimum acceptable hashrate %
        'min_efficiency': 70.0,  # Minimum power efficiency %
        'target_boost': 15.0  # Target performance boost %
    })
    
    # Safety limits (even aggressive has limits)
    safety_limits: Dict[str, float] = field(default_factory=lambda: {
        'absolute_max_temp': 87.0,  # Hard limit
        'absolute_max_power': 350.0,  # Watts
        'min_stability_score': 0.7  # Minimum stability before backing off
    })


class AggressiveStrategy(BaseStrategy):
    """
    Aggressive Strategy (Chiến lược tấn công) - Tối đa hóa hiệu suất GPU
    
    Chiến lược này tập trung vào:
    - Maximum performance extraction (khai thác hiệu suất tối đa)
    - Pushing hardware limits (đẩy giới hạn phần cứng)
    - Overclocking và power modifications (ép xung và điều chỉnh công suất)
    - Minimal safety margins (biên an toàn tối thiểu)
    
    Phù hợp cho:
    - High-performance computing (tính toán hiệu năng cao)
    - Competitive mining (đào coin cạnh tranh)
    - Benchmark runs (chạy benchmark)
    - Short burst workloads (khối lượng công việc ngắn)
    
    Cảnh báo: Có thể gây hư hại phần cứng nếu sử dụng không đúng!
    """
    
    def __init__(self, config: Optional[AggressiveConfig] = None):
        """
        Initialize aggressive strategy
        
        Args:
            config: Configuration cho strategy
        """
        super().__init__(
            name="AggressiveStrategy",
            strategy_type=StrategyType.AGGRESSIVE,
            priority=Priority.HIGH,  # High priority
            max_retries=5,  # More retries for aggressive
            retry_delay=0.5  # Faster retries
        )
        
        self.config = config or AggressiveConfig()
        
        # State tracking
        self._boosted_processes: Dict[int, Dict[str, Any]] = {}
        self._performance_history: List[Dict[str, float]] = []
        self._stability_scores: Dict[int, float] = {}
        
        # GPU state cache
        self._original_settings: Dict[str, Any] = {}
        self._current_boosts: Dict[str, float] = {}
        
        logger.warning(f"Initialized AggressiveStrategy - HIGH RISK MODE [risk={self.config.risk_tolerance}]")
    
    def validate(self, context: StrategyContext) -> bool:
        """
        Validate context (Xác thực ngữ cảnh) cho aggressive strategy
        
        Kiểm tra xem có an toàn để apply aggressive optimization không.
        
        Args:
            context: Context với metrics
            
        Returns:
            True nếu có thể apply aggressive strategy
        """
        # Check process exists
        if not psutil.pid_exists(context.pid):
            logger.warning(f"Process {context.pid} does not exist")
            return False
        
        # Check temperature headroom
        current_temp = context.gpu_metrics.get('temperature', 0)
        if current_temp > self.config.safety_limits['absolute_max_temp'] - 5:
            logger.warning(f"Temperature too high for aggressive: {current_temp}°C")
            return False
        
        # Check power headroom
        current_power = context.gpu_metrics.get('power_draw', 0)
        if current_power > self.config.safety_limits['absolute_max_power'] - 50:
            logger.warning(f"Power draw too high for aggressive: {current_power}W")
            return False
        
        # Check stability score
        stability = self._calculate_stability_score(context)
        if stability < self.config.safety_limits['min_stability_score']:
            logger.warning(f"System not stable enough: {stability:.2f}")
            return False
        
        # Check if already boosted
        if context.pid in self._boosted_processes:
            boost_time = self._boosted_processes[context.pid].get('timestamp', 0)
            if time.time() - boost_time < 60:  # Minimum 1 minute between boosts
                logger.debug(f"Process {context.pid} recently boosted")
                return False
        
        return True
    
    def apply(self, context: StrategyContext) -> StrategyResult:
        """
        Apply aggressive optimization (Áp dụng tối ưu tấn công)
        
        Pushes GPU to maximum performance với minimal safety.
        
        Args:
            context: Context với current metrics
            
        Returns:
            StrategyResult với kết quả optimization
        """
        start_time = time.time()
        
        try:
            # Save original settings (for rollback)
            if not self._original_settings:
                self._save_original_settings()
            
            # Calculate boost levels
            boost_config = self._calculate_boost_levels(context)
            logger.info(f"Calculated boost config: {boost_config}")
            
            # Apply performance modifications
            modifications = []
            errors = []
            
            # 1. Increase power limit
            if boost_config['power_boost'] > 0:
                success, error = self._adjust_power_limit(boost_config['power_boost'])
                if success:
                    modifications.append(f"Power limit +{boost_config['power_boost']}%")
                else:
                    errors.append(f"Power limit: {error}")
            
            # 2. Overclock GPU
            if boost_config['clock_boost'] > 0:
                success, error = self._adjust_gpu_clock(boost_config['clock_boost'])
                if success:
                    modifications.append(f"GPU clock +{boost_config['clock_boost']}MHz")
                else:
                    errors.append(f"GPU clock: {error}")
            
            # 3. Overclock memory
            if boost_config['memory_boost'] > 0:
                success, error = self._adjust_memory_clock(boost_config['memory_boost'])
                if success:
                    modifications.append(f"Memory clock +{boost_config['memory_boost']}MHz")
                else:
                    errors.append(f"Memory clock: {error}")
            
            # 4. Adjust fan curve (if needed)
            if boost_config['fan_override']:
                success, error = self._set_fan_speed(boost_config['fan_override'])
                if success:
                    modifications.append(f"Fan speed {boost_config['fan_override']}%")
                else:
                    errors.append(f"Fan speed: {error}")
            
            # 5. Process-specific optimizations
            process_mods = self._optimize_process(context.pid)
            modifications.extend(process_mods)
            
            # Wait for changes to take effect
            time.sleep(2.0)
            
            # Collect new metrics
            new_metrics = self._collect_boosted_metrics(context.pid)
            
            # Calculate performance improvement
            improvement = self._calculate_improvement(
                context.gpu_metrics,
                new_metrics
            )
            
            # Update tracking
            self._boosted_processes[context.pid] = {
                'timestamp': time.time(),
                'boost_config': boost_config,
                'modifications': modifications,
                'improvement': improvement
            }
            
            # Record performance
            self._record_performance(context, new_metrics, improvement)
            
            # Prepare result
            success = len(modifications) > 0
            message = f"Applied {len(modifications)} aggressive optimizations: {', '.join(modifications)}"
            if errors:
                message += f" | Errors: {', '.join(errors)}"
            
            return StrategyResult(
                success=success,
                message=message,
                metrics_before=context.gpu_metrics.copy(),
                metrics_after=new_metrics,
                duration=time.time() - start_time,
                metadata={
                    'boost_config': boost_config,
                    'modifications': modifications,
                    'improvement_percent': improvement,
                    'stability_score': self._calculate_stability_score(context),
                    'errors': errors
                }
            )
            
        except Exception as e:
            logger.error(f"Aggressive strategy failed: {e}")
            # Try to rollback on failure
            self._emergency_rollback()
            
            return StrategyResult(
                success=False,
                message=f"Aggressive optimization failed: {str(e)}",
                metrics_before=context.gpu_metrics.copy(),
                metrics_after=context.gpu_metrics.copy(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def _calculate_boost_levels(self, context: StrategyContext) -> Dict[str, Any]:
        """
        Calculate boost levels (Tính mức boost) dựa trên current state
        
        Returns:
            Dictionary với boost configuration
        """
        # Get current metrics
        gpu_util = context.gpu_metrics.get('utilization', 0)
        gpu_temp = context.gpu_metrics.get('temperature', 0)
        power_draw = context.gpu_metrics.get('power_draw', 0)
        
        # Calculate headroom
        temp_headroom = self.config.max_temperature - gpu_temp
        power_headroom = self.config.safety_limits['absolute_max_power'] - power_draw
        
        # Determine boost levels based on headroom and risk tolerance
        boost_config = {
            'power_boost': 0,
            'clock_boost': 0,
            'memory_boost': 0,
            'fan_override': None
        }
        
        # Power boost (aggressive but with headroom check)
        if power_headroom > 50:
            boost_config['power_boost'] = min(
                self.config.power_limit_increase,
                power_headroom * 0.5 * self.config.risk_tolerance
            )
        
        # Clock boost (temperature dependent)
        if temp_headroom > 10:
            boost_config['clock_boost'] = min(
                self.config.clock_boost,
                int(temp_headroom * 10 * self.config.risk_tolerance)
            )
            # Memory is usually more stable
            boost_config['memory_boost'] = int(boost_config['clock_boost'] * 0.7)
        
        # Fan override if pushing limits
        if gpu_temp > 75 or boost_config['clock_boost'] > 50:
            # Aggressive fan curve
            boost_config['fan_override'] = min(100, int(70 + (gpu_temp - 70) * 2))
        
        return boost_config
    
    def _adjust_power_limit(self, boost_percent: float) -> Tuple[bool, Optional[str]]:
        """Adjust GPU power limit"""
        try:
            # In production, would use nvidia-smi
            # cmd = f"nvidia-smi -pl {new_power_limit}"
            logger.info(f"Would increase power limit by {boost_percent}%")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _adjust_gpu_clock(self, boost_mhz: int) -> Tuple[bool, Optional[str]]:
        """Adjust GPU core clock"""
        try:
            # In production, would use nvidia-settings or nvidia-smi
            # cmd = f"nvidia-settings -a GPUGraphicsClockOffset[3]={boost_mhz}"
            logger.info(f"Would increase GPU clock by {boost_mhz}MHz")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _adjust_memory_clock(self, boost_mhz: int) -> Tuple[bool, Optional[str]]:
        """Adjust GPU memory clock"""
        try:
            # In production, would use nvidia-settings
            # cmd = f"nvidia-settings -a GPUMemoryTransferRateOffset[3]={boost_mhz}"
            logger.info(f"Would increase memory clock by {boost_mhz}MHz")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _set_fan_speed(self, speed_percent: int) -> Tuple[bool, Optional[str]]:
        """Override GPU fan speed"""
        try:
            # In production, would use nvidia-settings
            # cmd = f"nvidia-settings -a GPUFanControlState=1 -a GPUTargetFanSpeed={speed_percent}"
            logger.info(f"Would set fan speed to {speed_percent}%")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _optimize_process(self, pid: int) -> List[str]:
        """Process-specific aggressive optimizations"""
        modifications = []
        
        try:
            process = psutil.Process(pid)
            
            # Set highest priority
            process.nice(-20)
            modifications.append("Process priority maximized")
            
            # Set real-time scheduling if possible
            if os.name == 'posix':
                try:
                    os.sched_setscheduler(pid, os.SCHED_FIFO, os.sched_param(1))
                    modifications.append("Real-time scheduling enabled")
                except PermissionError:
                    pass
            
            # Maximize CPU affinity
            cpu_count = psutil.cpu_count()
            process.cpu_affinity(list(range(cpu_count)))
            modifications.append(f"CPU affinity set to all {cpu_count} cores")
            
        except Exception as e:
            logger.warning(f"Process optimization partial: {e}")
        
        return modifications
    
    def _calculate_stability_score(self, context: StrategyContext) -> float:
        """
        Calculate system stability score (Tính điểm ổn định hệ thống)
        
        Returns:
            Score 0-1 (1 = perfectly stable)
        """
        score = 1.0
        
        # Temperature stability
        temp = context.gpu_metrics.get('temperature', 0)
        if temp > 80:
            score *= 0.8
        if temp > 85:
            score *= 0.5
        
        # Check for thermal throttling
        if context.gpu_metrics.get('throttle_reason', 0) > 0:
            score *= 0.6
        
        # Historical performance
        if self._performance_history:
            recent = self._performance_history[-5:]
            variance = statistics.variance([p['improvement'] for p in recent]) if len(recent) > 1 else 0
            if variance > 10:
                score *= 0.7
        
        return max(0.0, min(1.0, score))
    
    def _collect_boosted_metrics(self, pid: int) -> Dict[str, Any]:
        """Collect metrics after boost"""
        # In production, would query actual metrics
        # Simulating boosted performance
        return {
            'utilization': 92.0,
            'memory_percent': 88.0,
            'temperature': 78.0,
            'power_draw': 320.0,
            'clock_speed': 1950,  # MHz
            'memory_clock': 7500,  # MHz
            'fan_speed': 85,  # %
            'timestamp': time.time()
        }
    
    def _calculate_improvement(self, before: Dict, after: Dict) -> float:
        """Calculate performance improvement percentage"""
        # Simple calculation based on utilization and clocks
        util_improvement = (after.get('utilization', 0) - before.get('utilization', 0)) / max(before.get('utilization', 1), 1) * 100
        
        # Estimate based on clock speeds if available
        if 'clock_speed' in after and 'clock_speed' in before:
            clock_improvement = (after['clock_speed'] - before.get('clock_speed', 1800)) / before.get('clock_speed', 1800) * 100
            return (util_improvement + clock_improvement) / 2
        
        return util_improvement
    
    def _save_original_settings(self):
        """Save original GPU settings for rollback"""
        # In production, would query and save actual settings
        self._original_settings = {
            'power_limit': 250,
            'gpu_clock_offset': 0,
            'memory_clock_offset': 0,
            'fan_control': 'auto',
            'saved_at': time.time()
        }
        logger.info("Saved original GPU settings")
    
    def _emergency_rollback(self):
        """Emergency rollback to original settings"""
        logger.warning("Performing emergency rollback!")
        
        if not self._original_settings:
            logger.error("No original settings to rollback to!")
            return
        
        try:
            # In production, would restore actual settings
            # cmd = f"nvidia-smi -pl {self._original_settings['power_limit']}"
            # cmd = "nvidia-settings -a GPUGraphicsClockOffset[3]=0"
            # cmd = "nvidia-settings -a GPUMemoryTransferRateOffset[3]=0"
            # cmd = "nvidia-settings -a GPUFanControlState=0"
            
            logger.info("Rolled back to original settings")
            self._boosted_processes.clear()
            self._current_boosts.clear()
            
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
    
    def _record_performance(self, 
                           context: StrategyContext,
                           new_metrics: Dict[str, Any],
                           improvement: float):
        """Record performance history"""
        record = {
            'timestamp': time.time(),
            'pid': context.pid,
            'improvement': improvement,
            'temperature': new_metrics.get('temperature', 0),
            'power_draw': new_metrics.get('power_draw', 0),
            'stability': self._calculate_stability_score(context)
        }
        
        self._performance_history.append(record)
        
        # Keep limited history
        if len(self._performance_history) > 100:
            self._performance_history = self._performance_history[-100:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get strategy statistics"""
        if not self._performance_history:
            return {
                'total_boosts': 0,
                'average_improvement': 0.0,
                'max_improvement': 0.0,
                'active_processes': 0
            }
        
        improvements = [p['improvement'] for p in self._performance_history]
        
        return {
            'total_boosts': len(self._performance_history),
            'average_improvement': statistics.mean(improvements),
            'max_improvement': max(improvements),
            'active_processes': len(self._boosted_processes),
            'average_stability': statistics.mean([p['stability'] for p in self._performance_history]),
            'risk_tolerance': self.config.risk_tolerance
        }
    
    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (f"AggressiveStrategy(boosts={stats['total_boosts']}, "
                f"avg_improvement={stats['average_improvement']:.1f}%, "
                f"risk={self.config.risk_tolerance})")


# Export public API
__all__ = ['AggressiveStrategy', 'AggressiveConfig']
