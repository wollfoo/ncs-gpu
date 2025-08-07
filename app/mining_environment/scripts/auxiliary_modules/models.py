class ConfigModel:
    def __init__(self, **kwargs):
        # **GPU-Only Configuration** (cấu hình GPU duy nhất)
        self.processes = {'GPU': 'inference-cuda'}
        self.network_interface = 'eth0'
        self.process_priority_map = {'inference-cuda': 3}
        # **GPU-Only Cloaking Strategies** (chiến lược cloaking GPU duy nhất)
        self.cloaking_strategies = {
            'gpu_cloaking': {'enabled': True},
            'network': {'enabled': True},
            'memory': {'enabled': True},
            'disk': {'enabled': True},
        }
        # **GPU Plugins Configuration** (cấu hình plugin GPU)
        self.enable_gpu_plugins = True  # Auto-enable GPU plugins (tự động kích hoạt các plugin GPU)
        for key, value in kwargs.items():
            setattr(self, key, value)
    def get(self, key, default=None):
        return getattr(self, key, default)
