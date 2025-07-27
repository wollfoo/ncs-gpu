"""mining_environment.stealth

🔒 **[GPU-Only Stealth System]** (Hệ thống ẩn danh chỉ GPU)

Module tập trung các chức năng **[Process Name Spoofing]** (giả mạo tên tiến trình) 
và **[Stealth Execution]** (thực thi ẩn danh) cho GPU mining environment.

⚠️ ORGANIZATION:
- **core/**: Self-stealth engine và logging utilities
- **wrappers/**: GPU stealth wrappers (CPU wrapper removed)
- **plugins/**: External stealth plugins và execution modules

✅ FEATURES:
- GPU process protection
- Self-managed process name rotation
- External disguise capabilities  
- Comprehensive logging & monitoring
"""

# Export main components for easy import - CPU component removed
from .core.self_stealth import SelfStealthManager, start_self_stealth
# CPU stealth import removed for GPU-only mining
from .wrappers.stealth_inference_cuda import main as gpu_stealth_main

__version__ = "1.0.0"
__author__ = "Stealth GPU-Only System"

# Module metadata - CPU component removed
__all__ = [
    'SelfStealthManager',
    'start_self_stealth', 
    'gpu_stealth_main'
]