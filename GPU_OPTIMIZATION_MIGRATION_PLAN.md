# 📋 **KẾ HOẠCH MIGRATION GPU OPTIMIZATION - PHIÊN BẢN TỐI ƯU**

## 📌 **Tổng Quan Dự Án**

**Project Name**: GPU Optimization Module Rebuild  
**Version**: 2.0.0 (Breaking Changes - không tương thích ngược)  
**Status**: Planning Phase  
**Created**: 2025-08-11  
**Author**: AI Engineering Team  

---

## 🎯 **MỤC TIÊU RÕ RÀNG**

### **Mục Tiêu Chính**
1. **Xây dựng lại hoàn toàn** module GPU Optimization với **architecture** (kiến trúc) tối ưu
2. **Tái sử dụng** các **algorithms** (thuật toán) và **logic** (luận lý) từ codebase cũ
3. **Loại bỏ** toàn bộ **legacy code** (mã nguồn cũ) sau khi migration
4. **Tối giản hóa** structure với chỉ **core functionality** (chức năng cốt lõi)

### **Mục Tiêu Cụ Thể**
- ✅ Giảm **code complexity** (độ phức tạp mã) xuống 50%
- ✅ Tăng **performance** (hiệu năng) lên 30%
- ✅ Giảm **memory footprint** (dấu vết bộ nhớ) xuống < 100MB
- ✅ **Response time** (thời gian phản hồi) < 10ms cho mỗi optimization call
- ✅ **Test coverage** (độ bao phủ kiểm thử) > 90%

---

## 📝 **CÁC BƯỚC THỰC THI CHI TIẾT**

### **PHASE 1: ANALYSIS & EXTRACTION** (Phân tích & Trích xuất - 2 ngày)

#### **Day 1: Code Analysis**
```bash
# 1.1 Phân tích các module hiện tại
cd /app/mining_environment/scripts

# Tạo báo cáo phân tích
python3 << 'EOF'
import ast
import os

modules_to_analyze = [
    'gpu_monitoring_dashboard.py',
    'gpu_optimization_orchestrator.py', 
    'gpu_resource_monitor.py',
    'parallel_strategy_executor.py',
    'performance_profiler.py',
    'dag_synchronization.py',
    'cross_process_coordination.py',
    'cloak_strategies.py',
    'resource_control.py'
]

analysis_report = {}
for module in modules_to_analyze:
    if os.path.exists(module):
        with open(module, 'r') as f:
            tree = ast.parse(f.read())
            analysis_report[module] = {
                'classes': [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)],
                'functions': [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)],
                'imports': [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
            }

# Save report
import json
with open('/app/code_analysis_report.json', 'w') as f:
    json.dump(analysis_report, f, indent=2)
EOF
```

#### **Day 2: Logic Extraction**
```python
# 1.2 Trích xuất core algorithms
EXTRACTION_TARGETS = {
    'cloak_strategies.py': [
        'apply_stealth_mode',
        'calculate_optimal_clocks', 
        'dynamic_power_adjustment'
    ],
    'resource_control.py': [
        'OptimizedHardwareController.__init__',
        'apply_gpu_controls',
        'monitor_and_adjust'
    ],
    'cross_process_coordination.py': [
        'allocate_resources',
        'semaphore_management',
        'deadlock_prevention'
    ]
}
```

### **PHASE 2: STRUCTURE CREATION** (Tạo cấu trúc - 1 ngày)

```
/app/mining_environment/
            ├── gpu_optimization/
                │
                ├── __init__.py                        # Khởi tạo gói **Central manager - quản lý trung tâm**  ( Đã xây dựng )  
                │
                ├── orchestrator/                      # Điều phối tổng quát ( Đã xây dựng )
                │   ├── __init__.py
                │   ├── orchestrator.py
                │   └── lifecycle_manager.py
                │
                ├── monitoring/                        # Thu thập & dashboard ( Đã xây dựng )
                │   ├── __init__.py
                │   ├── collectors/
                │   │   ├── gpu_metrics.py
                │   │   ├── process_metrics.py
                │   │   └── system_metrics.py
                │   ├── dashboard.py                   
                │   └── exporters/
                │       ├── prometheus.py
                │       └── json_exporter.py
                │
                ├── strategies/                        # Chiến lược tối ưu ( Tiếp tục xây dựng )
                │   ├── __init__.py
                │   ├── base.py
                │   ├── cloak.py                       # cloak_strategies.py
                │   ├── aggressive.py
                │   ├── balanced.py
                │   └── selector.py
                │
                ├── resource_control/                  # Quản lý tài nguyên GPU & tiến trình ( Xây dựng sau )
                │   ├── __init__.py
                │   ├── gpu_controller.py
                │   ├── power_manager.py
                │   ├── thermal_control.py
                │   └── pid_mapper.py
                │
                ├── coordination/                      # Liên tiến trình / DAG ( Xây dựng sau )
                │   ├── __init__.py
                │   ├── dag_synchronization.py
                │   ├── cross_process_coordination.py
                │   └── semaphore_pool.py
                │
                ├── profiling/                         # Hiệu năng & báo cáo ( Xây dựng sau )
                │   ├── __init__.py
                │   ├── performance_profiler.py
                |        
                ├── parallel_execution/                # Thực thi song song ( Xây dựng sau )
                │   ├── __init__.py
                │   └── parallel_strategy_executor.py
                │
                ├── config/                             # Cấu hình ( xây dựng sau )
                │   ├── __init__.py
                │   ├── default.yaml
                │   └── loader.py
                │
                ├── utils/                             # Công cụ hỗ trợ ( Xây dựng sau )
                │   ├── __init__.py
                │   ├── logger.py
                │   ├── validators.py
                │   └── exceptions.py
                │
                └── tests/ (unit, integration, fixtures)

```

#### **Day 3: Directory Setup**
```bash
# 2.1 Tạo cấu trúc thư mục mới
mkdir -p /app/mining_environment/gpu_optimization/{orchestrator,monitoring/{collectors,exporters},strategies,resource_control,coordination,profiling,parallel_execution,config,utils,tests/{unit,integration,fixtures}}

# 2.2 Tạo các file __init__.py
find /app/mining_environment/gpu_optimization -type d -exec touch {}/__init__.py \;

# 2.3 Tạo file cấu hình mặc định
cat > /app/mining_environment/gpu_optimization/config/default.yaml << 'EOF'
# GPU Optimization Configuration
version: 2.0.0
enabled: true

orchestrator:
  max_workers: 4
  scheduling_interval: 100  # ms
  priority_weights:
    performance: 0.4
    efficiency: 0.3
    temperature: 0.3

monitoring:
  sampling_rate: 1000  # Hz
  buffer_size: 1024
  retention_period: 3600  # seconds

strategies:
  default: balanced
  available:
    - aggressive
    - balanced
    - stealth
    - adaptive

resource_control:
  power_cap_range: [100, 300]  # Watts
  clock_frequencies:
    min: 300  # MHz
    max: 1980  # MHz
  memory_bandwidth:
    min: 100  # GB/s
    max: 900  # GB/s

coordination:
  semaphore_timeout: 5  # seconds
  max_concurrent_processes: 8
  deadlock_detection: true

profiling:
  enabled: false  # Enable only in debug mode
  trace_depth: 3
  sampling_mode: statistical
EOF
```


### **PHASE 3: CORE IMPLEMENTATION** (Triển khai lõi - 5 ngày)

#### **Day 4-5: Orchestrator Module**
```python
# 3.1 orchestrator/orchestrator.py
"""
GPU Optimization Orchestrator - Điều phối tối ưu GPU
Main entry point for all optimization operations
"""
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
import yaml

@dataclass
class OptimizationRequest:
    pid: int
    gpu_index: int = 0
    priority: str = 'normal'
    strategy: Optional[str] = None

class GPUOrchestrator:
    """Central orchestrator - Bộ điều phối trung tâm"""
    
    def __init__(self, config_path: str = 'config/default.yaml'):
        self.config = self._load_config(config_path)
        self.monitor = None  # Lazy init
        self.strategy_engine = None
        self.controller = None
        self.coordinator = None
        self.profiler = None
        
    async def initialize(self):
        """Async initialization - Khởi tạo bất đồng bộ"""
        from ..monitoring.collectors.gpu_metrics import GPUMetricsCollector
        from ..strategies.selector import StrategySelector
        from ..resource_control.gpu_controller import GPUController
        from ..coordination.cross_process_coordination import ProcessCoordinator
        
        self.monitor = GPUMetricsCollector()
        self.strategy_engine = StrategySelector(self.config['strategies'])
        self.controller = GPUController(self.config['resource_control'])
        self.coordinator = ProcessCoordinator(self.config['coordination'])
        
        # Start background tasks
        await self.monitor.start()
        
    async def optimize(self, request: OptimizationRequest) -> Dict[str, Any]:
        """Main optimization pipeline - Quy trình tối ưu chính"""
        # Step 1: Collect metrics
        metrics = await self.monitor.collect(request.pid)
        
        # Step 2: Select strategy
        strategy = self.strategy_engine.select(
            metrics, 
            override=request.strategy
        )
        
        # Step 3: Coordinate resources
        async with self.coordinator.allocate(request.pid):
            # Step 4: Apply optimizations
            result = await self.controller.apply(
                strategy,
                request.gpu_index,
                metrics
            )
            
        return result
```

#### **Day 6: Monitoring Module**
```python
# 3.2 monitoring/collectors/gpu_metrics.py
"""
GPU Metrics Collector - Thu thập metrics GPU
Collects real-time GPU performance metrics
"""
import asyncio
import pynvml
from typing import Dict, Any
from collections import deque
import time

class GPUMetricsCollector:
    """Async GPU metrics collection - Thu thập metrics GPU bất đồng bộ"""
    
    def __init__(self, buffer_size: int = 1024):
        self.buffer = deque(maxlen=buffer_size)
        self.running = False
        pynvml.nvmlInit()
        
    async def start(self):
        """Start background collection - Bắt đầu thu thập nền"""
        self.running = True
        asyncio.create_task(self._collect_loop())
        
    async def _collect_loop(self):
        """Background collection loop - Vòng lặp thu thập nền"""
        while self.running:
            try:
                metrics = self._get_gpu_metrics()
                self.buffer.append({
                    'timestamp': time.time(),
                    'metrics': metrics
                })
                await asyncio.sleep(0.1)  # 10Hz sampling
            except Exception as e:
                print(f"Collection error: {e}")
                
    def _get_gpu_metrics(self) -> Dict[str, Any]:
        """Get current GPU metrics - Lấy metrics GPU hiện tại"""
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        return {
            'utilization': pynvml.nvmlDeviceGetUtilizationRates(handle).gpu,
            'memory_used': pynvml.nvmlDeviceGetMemoryInfo(handle).used,
            'temperature': pynvml.nvmlDeviceGetTemperature(handle, 0),
            'power': pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0,
            'clocks': {
                'sm': pynvml.nvmlDeviceGetClockInfo(handle, 1),
                'mem': pynvml.nvmlDeviceGetClockInfo(handle, 2)
            }
        }
```

#### **Day 7: Strategy Module**
```python
# 3.3 strategies/selector.py
"""
Strategy Selector - Bộ chọn chiến lược
ML-based strategy selection engine
"""
from typing import Dict, Any, Optional
import numpy as np

class StrategySelector:
    """Intelligent strategy selection - Lựa chọn chiến lược thông minh"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strategies = self._load_strategies()
        
    def select(self, metrics: Dict[str, Any], override: Optional[str] = None) -> str:
        """Select optimal strategy - Chọn chiến lược tối ưu"""
        if override and override in self.strategies:
            return override
            
        # ML-based scoring
        scores = {}
        for name, strategy in self.strategies.items():
            scores[name] = self._calculate_score(strategy, metrics)
            
        return max(scores, key=scores.get)
        
    def _calculate_score(self, strategy: Dict, metrics: Dict) -> float:
        """Calculate strategy fitness score - Tính điểm phù hợp chiến lược"""
        score = 0.0
        
        # Temperature factor
        if metrics['temperature'] > 80:
            if strategy['name'] == 'stealth':
                score += 10
                
        # Utilization factor  
        if metrics['utilization'] > 90:
            if strategy['name'] == 'aggressive':
                score += 8
                
        # Power efficiency
        power_efficiency = metrics['utilization'] / metrics['power']
        score += power_efficiency * strategy.get('efficiency_weight', 1.0)
        
        return score
```

#### **Day 8: Resource Control Module**
```python
# 3.4 resource_control/gpu_controller.py
"""
GPU Controller - Bộ điều khiển GPU
Hardware-level GPU control operations
"""
import subprocess
import asyncio
from typing import Dict, Any

class GPUController:
    """Direct GPU hardware control - Điều khiển phần cứng GPU trực tiếp"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.power_limits = config['power_cap_range']
        self.clock_limits = config['clock_frequencies']
        
    async def apply(self, strategy: str, gpu_index: int, metrics: Dict) -> Dict:
        """Apply optimization strategy - Áp dụng chiến lược tối ưu"""
        commands = self._generate_commands(strategy, gpu_index, metrics)
        
        results = []
        for cmd in commands:
            result = await self._execute_command(cmd)
            results.append(result)
            
        return {
            'strategy': strategy,
            'gpu_index': gpu_index,
            'commands_executed': len(commands),
            'success': all(r['success'] for r in results)
        }
        
    def _generate_commands(self, strategy: str, gpu_index: int, metrics: Dict) -> list:
        """Generate nvidia-smi commands - Tạo lệnh nvidia-smi"""
        commands = []
        
        if strategy == 'aggressive':
            # Max performance
            commands.append(f"nvidia-smi -i {gpu_index} -pl {self.power_limits[1]}")
            commands.append(f"nvidia-smi -i {gpu_index} -lgc {self.clock_limits['max']}")
            
        elif strategy == 'stealth':
            # Low profile
            commands.append(f"nvidia-smi -i {gpu_index} -pl {self.power_limits[0]}")
            commands.append(f"nvidia-smi -i {gpu_index} -lgc {self.clock_limits['min']}")
            
        elif strategy == 'balanced':
            # Adaptive middle ground
            target_power = (self.power_limits[0] + self.power_limits[1]) / 2
            target_clock = (self.clock_limits['min'] + self.clock_limits['max']) / 2
            commands.append(f"nvidia-smi -i {gpu_index} -pl {int(target_power)}")
            commands.append(f"nvidia-smi -i {gpu_index} -lgc {int(target_clock)}")
            
        return commands
        
    async def _execute_command(self, cmd: str) -> Dict:
        """Execute system command - Thực thi lệnh hệ thống"""
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return {
                'command': cmd,
                'success': proc.returncode == 0,
                'output': stdout.decode() if stdout else None,
                'error': stderr.decode() if stderr else None
            }
        except Exception as e:
            return {
                'command': cmd,
                'success': False,
                'error': str(e)
            }
```

### **PHASE 4: INTEGRATION & TESTING** (Tích hợp & Kiểm thử - 3 ngày)

#### **Day 9: Integration Layer**
```python
# 4.1 __init__.py - Main entry point
"""
GPU Optimization Module v2.0
Complete GPU optimization solution
"""
from .orchestrator.orchestrator import GPUOrchestrator, OptimizationRequest

__version__ = '2.0.0'
__all__ = ['GPUOptimizer', 'optimize_gpu']

class GPUOptimizer:
    """Public API wrapper - API công khai"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.orchestrator = None
        return cls._instance
        
    async def initialize(self, config_path: str = None):
        """Initialize optimizer - Khởi tạo bộ tối ưu"""
        if self.orchestrator is None:
            self.orchestrator = GPUOrchestrator(config_path)
            await self.orchestrator.initialize()
            
    async def optimize(self, pid: int, **kwargs) -> Dict:
        """Optimize GPU for process - Tối ưu GPU cho tiến trình"""
        if self.orchestrator is None:
            await self.initialize()
            
        request = OptimizationRequest(pid=pid, **kwargs)
        return await self.orchestrator.optimize(request)

# Convenience function
async def optimize_gpu(pid: int, **kwargs):
    """Quick optimization - Tối ưu nhanh"""
    optimizer = GPUOptimizer()
    return await optimizer.optimize(pid, **kwargs)
```

#### **Day 10: Unit Tests**
```python
# 4.2 tests/unit/test_orchestrator.py
import pytest
import asyncio
from gpu_optimization import GPUOptimizer

@pytest.mark.asyncio
async def test_optimizer_initialization():
    """Test optimizer initialization"""
    optimizer = GPUOptimizer()
    await optimizer.initialize()
    assert optimizer.orchestrator is not None

@pytest.mark.asyncio
async def test_optimization_request():
    """Test optimization request processing"""
    optimizer = GPUOptimizer()
    result = await optimizer.optimize(pid=1234)
    assert 'strategy' in result
    assert result['success'] == True
```

#### **Day 11: Integration Tests**
```python
# 4.3 tests/integration/test_full_pipeline.py
import pytest
import asyncio
import subprocess

@pytest.mark.asyncio
async def test_full_optimization_pipeline():
    """Test complete optimization pipeline"""
    # Start a dummy GPU process
    proc = subprocess.Popen(['python', '-c', 'import time; time.sleep(10)'])
    
    try:
        from gpu_optimization import optimize_gpu
        result = await optimize_gpu(proc.pid, strategy='balanced')
        
        assert result['success']
        assert result['strategy'] == 'balanced'
        
    finally:
        proc.terminate()
```

### **PHASE 5: MIGRATION & CLEANUP** (Di chuyển & Dọn dẹp - 2 ngày)

#### **Day 12: Migration Execution**
```bash
# 5.1 Backup old modules
tar -czf /app/gpu_opt_backup_$(date +%Y%m%d).tar.gz \
    /app/mining_environment/scripts/{gpu_*,cloak_*,resource_*,cross_*,parallel_*,performance_*,dag_*}.py

# 5.2 Update imports in main flow
sed -i 's/from scripts\.cloak_strategies/from gpu_optimization/g' \
    /app/mining_environment/scripts/resource_manager.py

# 5.3 Test new integration
python3 -c "
import asyncio
from gpu_optimization import optimize_gpu
asyncio.run(optimize_gpu(1234))
"
```

#### **Day 13: Cleanup & Documentation**
```bash
# 5.4 Remove old modules (after validation)
rm -f /app/mining_environment/scripts/{gpu_monitoring_dashboard,gpu_optimization_orchestrator,gpu_resource_monitor}.py
rm -f /app/mining_environment/scripts/{parallel_strategy_executor,performance_profiler,dag_synchronization}.py
rm -f /app/mining_environment/scripts/{cross_process_coordination,cloak_strategies,resource_control}.py

# 5.5 Generate documentation
python3 -m pydoc -w gpu_optimization > /app/docs/gpu_optimization.html
```

---

## 📊 **CHỈ SỐ ĐO LƯỜNG THÀNH CÔNG**

### **Performance KPIs** (Chỉ số hiệu năng)

| **Metric** | **Target** | **Measurement Method** | **Frequency** |
|------------|------------|------------------------|---------------|
| **Module Load Time** | < 100ms | `time python -c "import gpu_optimization"` | Daily |
| **Optimization Latency** | < 10ms | Profiler measurement | Per request |
| **Memory Usage** | < 100MB | `tracemalloc` profiling | Hourly |
| **GPU Utilization Gain** | +15% | NVML metrics comparison | Per session |
| **Power Efficiency** | +20% | Power/Performance ratio | Daily |
| **Error Rate** | < 0.1% | Log analysis | Continuous |

### **Code Quality Metrics** (Chỉ số chất lượng code)

| **Metric** | **Target** | **Tool** |
|------------|------------|----------|
| **Test Coverage** | > 90% | `pytest --cov` |
| **Code Complexity** | < 10 | `radon cc` |
| **Maintainability Index** | > 80 | `radon mi` |
| **Technical Debt** | < 2 days | SonarQube |
| **Documentation Coverage** | 100% | `pydocstyle` |

---

## ⚠️ **RỦI RO TIỀM ẨN & BIỆN PHÁP GIẢM THIỂU**

### **Technical Risks** (Rủi ro kỹ thuật)

| **Risk** | **Probability** | **Impact** | **Mitigation Strategy** |
|----------|-----------------|------------|-------------------------|
| **CUDA Compatibility Issues** | Medium | High | • Test on multiple CUDA versions<br>• Implement version detection<br>• Fallback mechanisms |
| **Memory Leaks** | Medium | High | • Use context managers<br>• Regular profiling<br>• Automated leak detection |
| **Performance Regression** | Low | High | • Continuous benchmarking<br>• A/B testing<br>• Rollback plan |
| **Integration Failures** | Medium | Medium | • Phased rollout<br>• Feature flags<br>• Parallel run period |

### **Operational Risks** (Rủi ro vận hành)

| **Risk** | **Probability** | **Impact** | **Mitigation Strategy** |
|----------|-----------------|------------|-------------------------|
| **Service Downtime** | Low | High | • Blue-green deployment<br>• Health checks<br>• Auto-recovery |
| **Data Loss** | Low | Medium | • Backup before migration<br>• Version control<br>• Rollback scripts |
| **User Disruption** | Medium | Low | • Clear communication<br>• Migration guide<br>• Support channels |

---

## 🕓 **LỘ TRÌNH THỜI GIAN CỤ THỂ**

### **Timeline Gantt Chart**

```
Week 1 (Days 1-7):
│ Mon │ Tue │ Wed │ Thu │ Fri │ Sat │ Sun │
├─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│ Ana │ Ext │ Str │ Orc │ Orc │ Mon │ Str │
│ lys │ rac │ uct │ hes │ hes │ ito │ ate │
│ is  │ t   │ ure │ tr1 │ tr2 │ r   │ gy  │

Week 2 (Days 8-14):
│ Mon │ Tue │ Wed │ Thu │ Fri │ Sat │ Sun │
├─────┼─────┼─────┼─────┼─────┼─────┼─────┤
│ Res │ Int │ Uni │ Int │ Mig │ Cle │ Doc │
│ Ctrl│ egr │ t   │ Test│ rate│ an  │ s   │
│     │ ate │Test │     │     │ up  │     │
```

### **Milestones** (Cột mốc)

| **Date** | **Milestone** | **Deliverable** |
|----------|---------------|-----------------|
| Day 3 | Structure Complete | Directory tree created |
| Day 8 | Core Modules Done | All main modules implemented |
| Day 11 | Testing Complete | 90% test coverage achieved |
| Day 13 | Migration Done | Old modules removed |
| Day 14 | Documentation | Full documentation published |

---

## 📝 **CHECKLIST TRIỂN KHAI**

### **Pre-Migration Checklist**
- [ ] Backup existing modules
- [ ] Document current dependencies
- [ ] Identify integration points
- [ ] Prepare rollback plan
- [ ] Notify stakeholders

### **Migration Checklist**
- [ ] Create new directory structure
- [ ] Extract and port core logic
- [ ] Implement new modules
- [ ] Write comprehensive tests
- [ ] Update integration points
- [ ] Run parallel validation

### **Post-Migration Checklist**
- [ ] Verify all functionality
- [ ] Performance benchmarking
- [ ] Remove old modules
- [ ] Update documentation
- [ ] Monitor for issues
- [ ] Collect feedback

---

## 🚀 **QUICK START COMMANDS**

```bash
# 1. Initialize new module
cd /app/mining_environment
python3 -m gpu_optimization.setup

# 2. Run tests
pytest gpu_optimization/tests/ -v --cov

# 3. Start optimization
python3 << 'EOF'
import asyncio
from gpu_optimization import optimize_gpu

async def main():
    result = await optimize_gpu(
        pid=1234,
        strategy='balanced',
        gpu_index=0
    )
    print(f"Optimization result: {result}")

asyncio.run(main())
EOF

# 4. Monitor performance
python3 -m gpu_optimization.monitor --dashboard

# 5. Generate reports
python3 -m gpu_optimization.profiler --report
```

---

## 📚 **APPENDIX**

### **A. Configuration Examples**

```yaml
# Custom strategy configuration
strategies:
  custom_ml:
    type: adaptive
    model: xgboost
    features:
      - temperature
      - utilization
      - memory_usage
    thresholds:
      aggressive: 0.8
      conservative: 0.3
```

### **B. API Reference**

```python
# Async API usage
from gpu_optimization import GPUOptimizer

optimizer = GPUOptimizer()
await optimizer.initialize('/path/to/config.yaml')

# Simple optimization
result = await optimizer.optimize(pid=1234)

# Advanced optimization
result = await optimizer.optimize(
    pid=1234,
    gpu_index=1,
    strategy='custom_ml',
    priority='high'
)
```

### **C. Troubleshooting Guide**

| **Issue** | **Symptom** | **Solution** |
|-----------|-------------|--------------|
| Import Error | `ModuleNotFoundError` | Check PYTHONPATH, reinstall |
| NVML Error | `NVML not initialized` | Install nvidia-ml-py, check drivers |
| Permission Error | `Access denied` | Run with appropriate privileges |
| Config Error | `Config not found` | Verify path, check YAML syntax |

---

## ✅ **SIGN-OFF**

**Project Manager**: ___________________ Date: ___________

**Technical Lead**: ___________________ Date: ___________

**QA Lead**: _______________________ Date: ___________

---

*End of Migration Plan Document*
