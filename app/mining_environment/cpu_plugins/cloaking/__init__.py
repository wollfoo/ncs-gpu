"""cpu_plugins.cloaking

Module che giấu CPU, cung cấp các kỹ thuật ẩn danh và tránh phát hiện.
"""

# Stealth components moved to standalone stealth module
from .adaptive_cloak_plugin import AdaptiveCloakPlugin
from .signature_randomizer import SignatureRandomizer

__all__ = [
    # Stealth exports removed - use mining_environment.stealth directly
    'AdaptiveCloakPlugin',
    'SignatureRandomizer',
] 