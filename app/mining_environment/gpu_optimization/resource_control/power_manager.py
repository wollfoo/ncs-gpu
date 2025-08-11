"""
Power Manager Module
====================
GPU power management and optimization
Quản lý và tối ưu điện năng GPU

Chức năng chính:
- Dynamic power budget allocation (Phân bổ ngân sách điện năng động)
- Per-PID power tracking (Theo dõi điện năng theo PID)
- Power efficiency optimization (Tối ưu hiệu suất điện)
- Emergency power control (Điều khiển điện năng khẩn cấp)
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from threading import RLock
from typing import Dict, List, Optional, Tuple, Any


class PowerState(Enum):
    """Trạng thái điện năng GPU"""
    IDLE = "idle"  # Rảnh rỗi, tiêu thụ thấp
    LOW = "low"  # Công suất thấp
    NORMAL = "normal"  # Công suất bình thường
    HIGH = "high"  # Công suất cao
    BOOST = "boost"  # Tăng cường hiệu năng
    EMERGENCY = "emergency"  # Khẩn cấp - giảm công suất


@dataclass
class PowerAllocation:
    """
    Phân bổ điện năng cho một PID
    Power allocation for a PID
    """
    pid: int
    gpu_index: int
    allocated_watts: float
    min_watts: float = 50.0
    max_watts: float = 300.0
    priority: int = 5  # 1-10, higher is more important
    timestamp: float = field(default_factory=time.time)
    efficiency_score: float = 0.0  # Performance per watt
    
    def calculate_efficiency(self, utilization: float):
        """Tính điểm hiệu suất điện năng"""
        if self.allocated_watts > 0:
            self.efficiency_score = utilization / self.allocated_watts
        return self.efficiency_score


@dataclass 
class PowerBudget:
    """
    Ngân sách điện năng tổng
    Total power budget
    """
    total_budget_watts: float
    reserved_watts: float = 0.0  # Reserved for critical processes
    allocated_watts: float = 0.0
    emergency_reserve: float = 50.0  # Emergency headroom
    
    @property
    def available_watts(self) -> float:
        """Điện năng khả dụng để phân bổ"""
        return self.total_budget_watts - self.allocated_watts - self.reserved_watts
    
    @property
    def utilization_percent(self) -> float:
        """Phần trăm sử dụng ngân sách"""
        if self.total_budget_watts > 0:
            return (self.allocated_watts / self.total_budget_watts) * 100
        return 0.0


class PowerManager:
    """
    GPU Power Manager
    Quản lý điện năng GPU
    
    Features:
    - Dynamic power allocation (Phân bổ điện năng động)
    - Efficiency optimization (Tối ưu hiệu suất)
    - Emergency response (Phản ứng khẩn cấp)
    - Hysteresis control (Điều khiển trễ)
    """
    
    # Power state thresholds
    STATE_THRESHOLDS = {
        PowerState.IDLE: (0, 30),
        PowerState.LOW: (30, 50),
        PowerState.NORMAL: (50, 70),
        PowerState.HIGH: (70, 85),
        PowerState.BOOST: (85, 95),
        PowerState.EMERGENCY: (95, 100)
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None, gpu_controller=None):
        """
        Khởi tạo Power Manager
        
        Args:
            config: Configuration dictionary
            gpu_controller: GPUController instance for hardware control
        """
        self.config = config or {}
        self.gpu_controller = gpu_controller
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Power tracking
        self.power_allocations: Dict[int, PowerAllocation] = {}  # PID -> allocation
        self.gpu_power_states: Dict[int, PowerState] = {}  # GPU -> power state
        self.power_budgets: Dict[int, PowerBudget] = {}  # GPU -> budget
        self.power_history: Dict[int, deque] = defaultdict(lambda: deque(maxlen=100))
        
        # Configuration
        self.total_system_budget = self.config.get("total_budget_watts", 1000.0)
        self.per_gpu_budget = self.config.get("per_gpu_budget_watts", 300.0)
        self.hysteresis_threshold = self.config.get("hysteresis_threshold", 5.0)  # Watts
        self.rebalance_interval = self.config.get("rebalance_interval", 30)  # seconds
        self.monitoring_interval = self.config.get("monitoring_interval", 5)  # seconds
        
        # Thread safety
        self.allocation_lock = RLock()
        
        # Background tasks
        self._monitoring_task = None
        self._rebalance_task = None
        self._running = False
        
    async def initialize(self) -> bool:
        """
        Khởi tạo Power Manager
        Initialize Power Manager
        
        Returns:
            bool: True nếu khởi tạo thành công
        """
        try:
            # Initialize power budgets for each GPU
            if self.gpu_controller:
                num_gpus = self.gpu_controller.num_gpus
                for gpu_index in range(num_gpus):
                    self.power_budgets[gpu_index] = PowerBudget(
                        total_budget_watts=self.per_gpu_budget
                    )
                    self.gpu_power_states[gpu_index] = PowerState.NORMAL
            
            # Start background tasks
            self._running = True
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            self._rebalance_task = asyncio.create_task(self._rebalance_loop())
            
            self.logger.info("✅ Power Manager initialized")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Lỗi khởi tạo Power Manager: {e}")
            return False
    
    async def allocate_power(
        self,
        gpu_index: int,
        pid: int,
        requirements: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Phân bổ điện năng cho một process
        Allocate power for a process
        
        Args:
            gpu_index: GPU index
            pid: Process ID
            requirements: Power requirements (optional)
            
        Returns:
            Dict chứa thông tin phân bổ
        """
        with self.allocation_lock:
            try:
                # Parse requirements
                min_watts = requirements.get("min_watts", 50.0) if requirements else 50.0
                max_watts = requirements.get("max_watts", 200.0) if requirements else 200.0
                priority = requirements.get("priority", 5) if requirements else 5
                
                # Check budget availability
                budget = self.power_budgets.get(gpu_index)
                if not budget:
                    raise Exception(f"No budget for GPU {gpu_index}")
                
                # Calculate allocation based on available budget
                available = budget.available_watts
                allocated = min(max_watts, max(min_watts, available * 0.8))  # Use 80% of available
                
                # Create allocation
                allocation = PowerAllocation(
                    pid=pid,
                    gpu_index=gpu_index,
                    allocated_watts=allocated,
                    min_watts=min_watts,
                    max_watts=max_watts,
                    priority=priority
                )
                
                # Store allocation
                self.power_allocations[pid] = allocation
                budget.allocated_watts += allocated
                
                # Apply to hardware if controller available
                if self.gpu_controller:
                    result = await self.gpu_controller.set_power_limit(
                        gpu_index,
                        budget.allocated_watts,
                        smooth_transition=True
                    )
                    
                    if not result.success:
                        # Rollback allocation on failure
                        del self.power_allocations[pid]
                        budget.allocated_watts -= allocated
                        raise Exception(result.error)
                
                self.logger.info(
                    f"✅ Allocated {allocated:.1f}W to PID {pid} on GPU {gpu_index}"
                )
                
                return {
                    "success": True,
                    "pid": pid,
                    "gpu_index": gpu_index,
                    "allocated_watts": allocated,
                    "budget_utilization": budget.utilization_percent
                }
                
            except Exception as e:
                self.logger.error(f"❌ Lỗi phân bổ điện năng cho PID {pid}: {e}")
                return {
                    "success": False,
                    "pid": pid,
                    "error": str(e)
                }
    
    async def release_power_allocation(self, pid: int) -> bool:
        """
        Giải phóng phân bổ điện năng của một process
        Release power allocation for a process
        
        Args:
            pid: Process ID
            
        Returns:
            bool: True nếu giải phóng thành công
        """
        with self.allocation_lock:
            try:
                if pid not in self.power_allocations:
                    return True  # Already released
                
                allocation = self.power_allocations[pid]
                gpu_index = allocation.gpu_index
                
                # Update budget
                if gpu_index in self.power_budgets:
                    budget = self.power_budgets[gpu_index]
                    budget.allocated_watts -= allocation.allocated_watts
                
                # Remove allocation
                del self.power_allocations[pid]
                
                self.logger.info(f"✅ Released power allocation for PID {pid}")
                return True
                
            except Exception as e:
                self.logger.error(f"❌ Lỗi giải phóng điện năng PID {pid}: {e}")
                return False
    
    async def optimize_power_efficiency(self):
        """
        Tối ưu hiệu suất điện năng
        Optimize power efficiency
        """
        try:
            if not self.gpu_controller:
                return
            
            # Calculate efficiency for all allocations
            efficiency_scores = []
            
            for pid, allocation in self.power_allocations.items():
                # Get GPU metrics
                metrics = await self.gpu_controller.get_gpu_metrics(allocation.gpu_index)
                if metrics:
                    allocation.calculate_efficiency(metrics.utilization_percent)
                    efficiency_scores.append((pid, allocation.efficiency_score))
            
            # Sort by efficiency (lower is worse)
            efficiency_scores.sort(key=lambda x: x[1])
            
            # Reallocate power from inefficient to efficient processes
            if len(efficiency_scores) > 1:
                worst_pid = efficiency_scores[0][0]
                best_pid = efficiency_scores[-1][0]
                
                worst_alloc = self.power_allocations[worst_pid]
                best_alloc = self.power_allocations[best_pid]
                
                # Transfer 10% power from worst to best
                transfer_amount = worst_alloc.allocated_watts * 0.1
                
                if transfer_amount > self.hysteresis_threshold:
                    worst_alloc.allocated_watts -= transfer_amount
                    best_alloc.allocated_watts += transfer_amount
                    
                    self.logger.info(
                        f"⚡ Transferred {transfer_amount:.1f}W from PID {worst_pid} to {best_pid}"
                    )
            
        except Exception as e:
            self.logger.error(f"Error optimizing power efficiency: {e}")
    
    async def apply_emergency_power_reduction(self, gpu_index: int, reduction_percent: float = 30):
        """
        Áp dụng giảm điện năng khẩn cấp
        Apply emergency power reduction
        
        Args:
            gpu_index: GPU index
            reduction_percent: Percentage to reduce power
        """
        try:
            if gpu_index in self.power_budgets:
                budget = self.power_budgets[gpu_index]
                
                # Reduce all allocations on this GPU
                for pid, allocation in self.power_allocations.items():
                    if allocation.gpu_index == gpu_index:
                        reduction = allocation.allocated_watts * (reduction_percent / 100)
                        allocation.allocated_watts -= reduction
                        budget.allocated_watts -= reduction
                
                # Apply to hardware
                if self.gpu_controller:
                    new_limit = budget.allocated_watts
                    await self.gpu_controller.set_power_limit(
                        gpu_index,
                        new_limit,
                        smooth_transition=False  # Immediate for emergency
                    )
                
                # Update state
                self.gpu_power_states[gpu_index] = PowerState.EMERGENCY
                
                self.logger.warning(
                    f"🚨 Emergency power reduction {reduction_percent}% on GPU {gpu_index}"
                )
                
        except Exception as e:
            self.logger.error(f"Error applying emergency power reduction: {e}")
    
    def _determine_power_state(self, utilization_percent: float) -> PowerState:
        """Xác định power state dựa trên utilization"""
        for state, (min_util, max_util) in self.STATE_THRESHOLDS.items():
            if min_util <= utilization_percent < max_util:
                return state
        return PowerState.NORMAL
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while self._running:
            try:
                await asyncio.sleep(self.monitoring_interval)
                
                if self.gpu_controller:
                    for gpu_index in range(self.gpu_controller.num_gpus):
                        metrics = await self.gpu_controller.get_gpu_metrics(gpu_index)
                        if metrics:
                            # Store history
                            self.power_history[gpu_index].append({
                                "timestamp": time.time(),
                                "power_watts": metrics.power_watts,
                                "utilization": metrics.utilization_percent
                            })
                            
                            # Update power state
                            new_state = self._determine_power_state(metrics.utilization_percent)
                            
                            # Apply hysteresis
                            current_state = self.gpu_power_states.get(gpu_index, PowerState.NORMAL)
                            if new_state != current_state:
                                self.gpu_power_states[gpu_index] = new_state
                                self.logger.info(
                                    f"🔄 GPU {gpu_index} power state: {current_state.value} → {new_state.value}"
                                )
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
    
    async def _rebalance_loop(self):
        """Background rebalancing loop"""
        while self._running:
            try:
                await asyncio.sleep(self.rebalance_interval)
                await self.optimize_power_efficiency()
            except Exception as e:
                self.logger.error(f"Rebalance loop error: {e}")
    
    async def get_power_status(self) -> Dict[str, Any]:
        """
        Lấy trạng thái điện năng hiện tại
        Get current power status
        """
        status = {
            "total_system_budget": self.total_system_budget,
            "allocations": {},
            "gpu_states": {},
            "budgets": {}
        }
        
        # Add allocation details
        for pid, allocation in self.power_allocations.items():
            status["allocations"][pid] = {
                "gpu_index": allocation.gpu_index,
                "allocated_watts": allocation.allocated_watts,
                "priority": allocation.priority,
                "efficiency_score": allocation.efficiency_score
            }
        
        # Add GPU states
        for gpu_index, state in self.gpu_power_states.items():
            status["gpu_states"][gpu_index] = state.value
        
        # Add budget info
        for gpu_index, budget in self.power_budgets.items():
            status["budgets"][gpu_index] = {
                "total": budget.total_budget_watts,
                "allocated": budget.allocated_watts,
                "available": budget.available_watts,
                "utilization_percent": budget.utilization_percent
            }
        
        return status
    
    async def shutdown(self):
        """Shutdown Power Manager gracefully"""
        self.logger.info("🔄 Shutting down Power Manager...")
        self._running = False
        
        # Cancel background tasks
        if self._monitoring_task:
            self._monitoring_task.cancel()
        if self._rebalance_task:
            self._rebalance_task.cancel()
        
        await asyncio.gather(
            self._monitoring_task,
            self._rebalance_task,
            return_exceptions=True
        )
        
        self.logger.info("✅ Power Manager shutdown complete")