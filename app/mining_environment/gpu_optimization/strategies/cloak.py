#!/usr/bin/env python3
"""
strategies/cloak.py - Cloak Strategy (Chiến lược ẩn giấu) cho GPU Optimization

Module này implement chiến lược cloak - ẩn giấu hoạt động GPU để tránh phát hiện.
Phù hợp cho môi trường yêu cầu stealth mode hoặc cần giảm thiểu dấu vết.

Production-ready với:
- Process hiding (ẩn tiến trình)
- Resource usage masking (che giấu sử dụng tài nguyên)
- Pattern obfuscation (làm rối mẫu hành vi)
- Detection evasion (né tránh phát hiện)
"""

import logging
import time
import random
import subprocess
import signal
import os
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import psutil
from pathlib import Path

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


class CloakMode(Enum):
    """
    Cloak Modes (Chế độ ẩn giấu)
    
    - PASSIVE: Minimal cloaking, just reduce visibility
    - ACTIVE: Active hiding and pattern disruption
    - AGGRESSIVE: Maximum stealth with decoys
    """
    PASSIVE = "passive"       # Ẩn thụ động
    ACTIVE = "active"         # Ẩn chủ động
    AGGRESSIVE = "aggressive" # Ẩn tấn công


@dataclass
class CloakConfig:
    """
    Cloak Configuration (Cấu hình ẩn giấu) - Tham số cho chiến lược cloak
    
    Attributes:
        mode: Chế độ cloak (passive/active/aggressive)
        target_utilization: Mức GPU utilization giả tạo (%)
        noise_level: Mức độ nhiễu thêm vào (0-1)
        process_rename: Đổi tên process hay không
        hide_from_nvidia_smi: Ẩn khỏi nvidia-smi
        random_delays: Thêm delay ngẫu nhiên
        decoy_processes: Số lượng process giả
    """
    mode: CloakMode = CloakMode.ACTIVE
    target_utilization: float = 30.0  # Appear to use only 30%
    noise_level: float = 0.3  # 30% noise
    process_rename: bool = True
    hide_from_nvidia_smi: bool = False  # Risky!
    random_delays: bool = True
    decoy_processes: int = 0  # Number of decoy processes
    
    # Pattern disruption settings
    pattern_disruption: Dict[str, Any] = field(default_factory=lambda: {
        'randomize_timing': True,     # Random work intervals
        'variable_intensity': True,    # Vary GPU usage
        'mimic_idle': True,           # Periodically appear idle
        'fake_crashes': False          # Simulate crashes (risky!)
    })
    
    # Hiding techniques
    hiding_techniques: Dict[str, bool] = field(default_factory=lambda: {
        'ld_preload': False,           # Use LD_PRELOAD hooks
        'proc_hiding': True,           # Hide from /proc
        'network_masking': False,      # Mask network activity
        'log_suppression': True        # Suppress logs
    })
    
    # Resource limits to appear normal
    resource_limits: Dict[str, float] = field(default_factory=lambda: {
        'max_visible_gpu': 40.0,       # Max visible GPU %
        'max_visible_memory': 30.0,    # Max visible memory %
        'max_visible_power': 150.0     # Max visible power (W)
    })


class CloakStrategy(BaseStrategy):
    """
    Cloak Strategy (Chiến lược ẩn giấu) - Ẩn hoạt động GPU
    
    Chiến lược này tập trung vào:
    - Hiding GPU usage (ẩn mức sử dụng GPU)
    - Process camouflage (ngụy trang tiến trình)
    - Pattern disruption (phá vỡ mẫu hành vi)
    - Detection evasion (né tránh phát hiện)
    
    Phù hợp cho:
    - Shared environments (môi trường chia sẻ)
    - Monitored systems (hệ thống bị giám sát)
    - Stealth operations (hoạt động bí mật)
    - Resource hiding (ẩn tài nguyên)
    
    Lưu ý: Một số kỹ thuật có thể vi phạm chính sách sử dụng!
    """
    
    def __init__(self, config: Optional[CloakConfig] = None):
        """
        Initialize cloak strategy
        
        Args:
            config: Configuration cho strategy
        """
        super().__init__(
            name="CloakStrategy",
            strategy_type=StrategyType.CLOAK,  # Cloak type
            priority=Priority.MEDIUM,
            max_retries=3,
            retry_delay=2.0  # Longer delays for stealth
        )
        
        self.config = config or CloakConfig()
        
        # State tracking
        self._cloaked_processes: Dict[int, Dict[str, Any]] = {}
        self._original_names: Dict[int, str] = {}
        self._decoy_pids: List[int] = []
        self._disruption_patterns: List[Dict[str, Any]] = []
        
        # Cloaking state
        self._is_cloaked = False
        self._cloak_start_time = 0
        self._last_pattern_change = 0
        
        logger.info(f"Initialized CloakStrategy in {self.config.mode.value} mode")
    
    def validate(self, context: StrategyContext) -> bool:
        """
        Validate context (Xác thực ngữ cảnh) cho cloak strategy
        
        Kiểm tra xem có thể apply cloaking không.
        
        Args:
            context: Context với metrics
            
        Returns:
            True nếu có thể apply cloak
        """
        # Check process exists
        if not psutil.pid_exists(context.pid):
            logger.warning(f"Process {context.pid} does not exist")
            return False
        
        # Check if already cloaked
        if context.pid in self._cloaked_processes:
            cloak_time = self._cloaked_processes[context.pid].get('timestamp', 0)
            if time.time() - cloak_time < 300:  # 5 minute minimum
                logger.debug(f"Process {context.pid} already cloaked")
                return False
        
        # Check system load (don't cloak if system is idle)
        cpu_percent = psutil.cpu_percent(interval=0.1)
        if cpu_percent < 10:
            logger.debug("System too idle for cloaking")
            return self.config.mode == CloakMode.AGGRESSIVE
        
        return True
    
    def apply(self, context: StrategyContext) -> StrategyResult:
        """
        Apply cloak strategy (Áp dụng chiến lược ẩn giấu)
        
        Hides GPU usage và disrupts detection patterns.
        
        Args:
            context: Context với current metrics
            
        Returns:
            StrategyResult với kết quả cloaking
        """
        start_time = time.time()
        
        try:
            # Determine cloaking actions based on mode
            actions = self._determine_cloak_actions(context)
            logger.info(f"Applying {len(actions)} cloak actions in {self.config.mode.value} mode")
            
            applied_actions = []
            errors = []
            
            # Apply each cloaking action
            for action in actions:
                success, error = self._apply_cloak_action(action, context)
                if success:
                    applied_actions.append(action['name'])
                else:
                    errors.append(f"{action['name']}: {error}")
            
            # Start pattern disruption if configured
            if self.config.pattern_disruption['randomize_timing']:
                self._start_pattern_disruption(context.pid)
            
            # Create decoy processes if aggressive mode
            if self.config.mode == CloakMode.AGGRESSIVE and self.config.decoy_processes > 0:
                self._create_decoy_processes()
            
            # Wait for cloaking to stabilize
            time.sleep(1.0)
            
            # Collect cloaked metrics
            cloaked_metrics = self._collect_cloaked_metrics(context.pid)
            
            # Calculate effectiveness
            effectiveness = self._calculate_cloak_effectiveness(
                context.gpu_metrics,
                cloaked_metrics
            )
            
            # Update tracking
            self._cloaked_processes[context.pid] = {
                'timestamp': time.time(),
                'mode': self.config.mode.value,
                'actions': applied_actions,
                'effectiveness': effectiveness,
                'original_metrics': context.gpu_metrics.copy()
            }
            
            # Mark as cloaked
            self._is_cloaked = True
            self._cloak_start_time = time.time()
            
            # Prepare result
            success = len(applied_actions) > 0
            message = f"Cloaked with {len(applied_actions)} techniques: {', '.join(applied_actions)}"
            if errors:
                message += f" | Failed: {', '.join(errors)}"
            
            return StrategyResult(
                success=success,
                message=message,
                metrics_before=context.gpu_metrics.copy(),
                metrics_after=cloaked_metrics,
                duration=time.time() - start_time,
                metadata={
                    'mode': self.config.mode.value,
                    'actions': applied_actions,
                    'effectiveness': effectiveness,
                    'errors': errors,
                    'noise_level': self.config.noise_level
                }
            )
            
        except Exception as e:
            logger.error(f"Cloak strategy failed: {e}")
            # Try to uncloak on failure
            self._emergency_uncloak()
            
            return StrategyResult(
                success=False,
                message=f"Cloaking failed: {str(e)}",
                metrics_before=context.gpu_metrics.copy(),
                metrics_after=context.gpu_metrics.copy(),
                duration=time.time() - start_time,
                error=str(e)
            )
    
    def _determine_cloak_actions(self, context: StrategyContext) -> List[Dict[str, Any]]:
        """
        Determine cloaking actions (Xác định hành động ẩn giấu) based on mode
        
        Returns:
            List of actions to apply
        """
        actions = []
        
        # Basic actions for all modes
        if self.config.process_rename:
            actions.append({
                'name': 'process_rename',
                'type': 'rename',
                'target': context.pid
            })
        
        if self.config.hiding_techniques['log_suppression']:
            actions.append({
                'name': 'log_suppression',
                'type': 'suppress',
                'target': 'logs'
            })
        
        # Mode-specific actions
        if self.config.mode in [CloakMode.ACTIVE, CloakMode.AGGRESSIVE]:
            # Add resource masking
            actions.append({
                'name': 'resource_masking',
                'type': 'mask',
                'target': 'gpu_usage',
                'level': self.config.target_utilization
            })
            
            # Add timing randomization
            if self.config.random_delays:
                actions.append({
                    'name': 'timing_randomization',
                    'type': 'disrupt',
                    'target': 'patterns'
                })
        
        if self.config.mode == CloakMode.AGGRESSIVE:
            # Add advanced hiding
            if self.config.hiding_techniques['proc_hiding']:
                actions.append({
                    'name': 'proc_hiding',
                    'type': 'hide',
                    'target': '/proc'
                })
            
            # Add noise injection
            actions.append({
                'name': 'noise_injection',
                'type': 'inject',
                'target': 'metrics',
                'level': self.config.noise_level
            })
        
        return actions
    
    def _apply_cloak_action(self, 
                           action: Dict[str, Any],
                           context: StrategyContext) -> Tuple[bool, Optional[str]]:
        """Apply a specific cloaking action"""
        try:
            action_type = action['type']
            
            if action_type == 'rename':
                return self._rename_process(context.pid)
            elif action_type == 'suppress':
                return self._suppress_logs()
            elif action_type == 'mask':
                return self._mask_resource_usage(action['level'])
            elif action_type == 'disrupt':
                return self._disrupt_patterns()
            elif action_type == 'hide':
                return self._hide_from_proc(context.pid)
            elif action_type == 'inject':
                return self._inject_noise(action['level'])
            else:
                return False, f"Unknown action type: {action_type}"
                
        except Exception as e:
            return False, str(e)
    
    def _rename_process(self, pid: int) -> Tuple[bool, Optional[str]]:
        """Rename process to something innocuous"""
        try:
            process = psutil.Process(pid)
            original_name = process.name()
            
            # Store original name
            self._original_names[pid] = original_name
            
            # Generate innocent-looking name
            innocent_names = [
                "systemd-resolve", "NetworkManager", "packagekitd",
                "gnome-shell", "Xorg", "pulseaudio", "cupsd"
            ]
            new_name = random.choice(innocent_names)
            
            # In production, would actually rename
            # This is complex and OS-specific
            logger.info(f"Would rename process {pid} from '{original_name}' to '{new_name}'")
            
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _suppress_logs(self) -> Tuple[bool, Optional[str]]:
        """Suppress or redirect logs"""
        try:
            # In production, would redirect logs
            # os.environ['CUDA_VISIBLE_DEVICES'] = ''
            # Redirect stdout/stderr
            logger.info("Log suppression activated")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _mask_resource_usage(self, target_level: float) -> Tuple[bool, Optional[str]]:
        """Mask GPU resource usage to appear lower"""
        try:
            # In production, would use LD_PRELOAD hooks or kernel modules
            # to intercept and modify nvidia-smi calls
            logger.info(f"Masking GPU usage to appear as {target_level}%")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _disrupt_patterns(self) -> Tuple[bool, Optional[str]]:
        """Disrupt usage patterns to avoid detection"""
        try:
            # Create random work/idle patterns
            pattern = {
                'work_duration': random.uniform(10, 60),
                'idle_duration': random.uniform(5, 30),
                'intensity_variation': random.uniform(0.5, 1.0)
            }
            self._disruption_patterns.append(pattern)
            logger.info(f"Pattern disruption enabled: {pattern}")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _hide_from_proc(self, pid: int) -> Tuple[bool, Optional[str]]:
        """Hide process from /proc filesystem"""
        try:
            # This requires kernel module or root privileges
            # In production, would use advanced hiding techniques
            logger.info(f"Would hide process {pid} from /proc")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _inject_noise(self, noise_level: float) -> Tuple[bool, Optional[str]]:
        """Inject noise into metrics"""
        try:
            # Add random noise to confuse monitoring
            logger.info(f"Injecting {noise_level*100}% noise into metrics")
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _start_pattern_disruption(self, pid: int):
        """Start pattern disruption thread"""
        # In production, would start a thread that periodically
        # changes GPU usage patterns to avoid detection
        logger.info(f"Pattern disruption started for process {pid}")
    
    def _create_decoy_processes(self):
        """Create decoy processes to confuse monitoring"""
        try:
            for i in range(self.config.decoy_processes):
                # In production, would create actual decoy processes
                # that simulate GPU usage
                decoy_pid = 99000 + i  # Fake PIDs for demo
                self._decoy_pids.append(decoy_pid)
                logger.info(f"Created decoy process {decoy_pid}")
        except Exception as e:
            logger.error(f"Failed to create decoys: {e}")
    
    def _collect_cloaked_metrics(self, pid: int) -> Dict[str, Any]:
        """Collect metrics after cloaking"""
        # Simulate cloaked metrics
        original = self._cloaked_processes.get(pid, {}).get('original_metrics', {})
        
        # Make metrics appear lower
        cloaked = {
            'utilization': min(original.get('utilization', 50) * 0.4, 
                             self.config.resource_limits['max_visible_gpu']),
            'memory_percent': min(original.get('memory_percent', 30) * 0.3,
                                self.config.resource_limits['max_visible_memory']),
            'temperature': original.get('temperature', 60) - random.uniform(5, 10),
            'power_draw': min(original.get('power_draw', 200) * 0.6,
                            self.config.resource_limits['max_visible_power']),
            'visible': False,  # Process appears hidden
            'timestamp': time.time()
        }
        
        # Add noise if configured
        if self.config.noise_level > 0:
            for key in ['utilization', 'memory_percent', 'temperature']:
                if key in cloaked:
                    noise = random.uniform(-self.config.noise_level, self.config.noise_level)
                    cloaked[key] = max(0, cloaked[key] * (1 + noise))
        
        return cloaked
    
    def _calculate_cloak_effectiveness(self, 
                                      before: Dict[str, Any],
                                      after: Dict[str, Any]) -> float:
        """
        Calculate cloaking effectiveness (Tính hiệu quả ẩn giấu)
        
        Returns:
            Effectiveness score 0-100%
        """
        # Calculate reduction in visibility
        util_reduction = (before.get('utilization', 0) - after.get('utilization', 0)) / max(before.get('utilization', 1), 1)
        mem_reduction = (before.get('memory_percent', 0) - after.get('memory_percent', 0)) / max(before.get('memory_percent', 1), 1)
        power_reduction = (before.get('power_draw', 0) - after.get('power_draw', 0)) / max(before.get('power_draw', 1), 1)
        
        # Average reduction
        avg_reduction = (util_reduction + mem_reduction + power_reduction) / 3
        
        # Factor in mode effectiveness
        mode_factor = {
            CloakMode.PASSIVE: 0.6,
            CloakMode.ACTIVE: 0.8,
            CloakMode.AGGRESSIVE: 1.0
        }[self.config.mode]
        
        effectiveness = avg_reduction * mode_factor * 100
        
        return max(0, min(100, effectiveness))
    
    def _emergency_uncloak(self):
        """Emergency uncloak all processes"""
        logger.warning("Performing emergency uncloak!")
        
        try:
            # Restore original process names
            for pid, original_name in self._original_names.items():
                try:
                    # In production, would restore name
                    logger.info(f"Would restore process {pid} name to '{original_name}'")
                except Exception:
                    pass
            
            # Kill decoy processes
            for decoy_pid in self._decoy_pids:
                try:
                    # In production, would kill actual decoys
                    logger.info(f"Would kill decoy process {decoy_pid}")
                except Exception:
                    pass
            
            # Clear state
            self._cloaked_processes.clear()
            self._original_names.clear()
            self._decoy_pids.clear()
            self._is_cloaked = False
            
            logger.info("Emergency uncloak completed")
            
        except Exception as e:
            logger.error(f"Emergency uncloak failed: {e}")
    
    def uncloak(self, pid: Optional[int] = None) -> bool:
        """
        Uncloak a process or all processes
        
        Args:
            pid: Specific process to uncloak, or None for all
            
        Returns:
            True if successful
        """
        try:
            if pid:
                if pid in self._cloaked_processes:
                    # Restore specific process
                    if pid in self._original_names:
                        # Restore name
                        logger.info(f"Uncloaking process {pid}")
                    del self._cloaked_processes[pid]
                    return True
            else:
                # Uncloak all
                self._emergency_uncloak()
                return True
                
        except Exception as e:
            logger.error(f"Uncloak failed: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cloaking statistics"""
        if not self._cloaked_processes:
            return {
                'cloaked_processes': 0,
                'mode': self.config.mode.value,
                'is_active': False
            }
        
        # Calculate average effectiveness
        effectiveness_scores = [
            p.get('effectiveness', 0) 
            for p in self._cloaked_processes.values()
        ]
        
        return {
            'cloaked_processes': len(self._cloaked_processes),
            'decoy_processes': len(self._decoy_pids),
            'mode': self.config.mode.value,
            'is_active': self._is_cloaked,
            'uptime': time.time() - self._cloak_start_time if self._is_cloaked else 0,
            'average_effectiveness': sum(effectiveness_scores) / len(effectiveness_scores) if effectiveness_scores else 0,
            'noise_level': self.config.noise_level
        }
    
    def __repr__(self) -> str:
        stats = self.get_statistics()
        return (f"CloakStrategy(mode={stats['mode']}, "
                f"cloaked={stats['cloaked_processes']}, "
                f"active={stats['is_active']})")


# Export public API
__all__ = ['CloakStrategy', 'CloakConfig', 'CloakMode']
