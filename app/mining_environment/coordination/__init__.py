# Hook Coordination Module
# Auto-apply Resource Manager patch when module is imported

try:
    from .resource_manager_patch import apply_resource_manager_patch
    apply_resource_manager_patch()
except Exception as e:
    print(f"⚠️ [COORDINATION] Auto-patch failed: {e}")