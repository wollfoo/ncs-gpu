import sys
import types
import time
import unittest

# --- Prepare stub pynvml module BEFORE importing resource_control ---

def make_pynvml_stub(count=2):
    mod = types.ModuleType('pynvml')
    # State and counters for verification
    mod._inited = False
    mod._count = int(count)
    mod._temps = [60.0 + i for i in range(count)]  # Celsius
    mod._powers_mw = [50000 + i * 1000 for i in range(count)]  # mW
    mod._utils_pct = [10 + i * 20 for i in range(count)]  # percent values e.g. 10, 30
    mod._mem_used = [int((i + 1) * 256 * 1024 * 1024) for i in range(count)]  # bytes
    mod._mem_total = [int((i + 4) * 1024 * 1024 * 1024) for i in range(count)]  # bytes

    mod.call_counts = {
        'nvmlInit': 0,
        'DeviceGetCount': 0,
        'DeviceGetHandleByIndex': 0,
        'DeviceGetTemperature': 0,
        'DeviceGetPowerUsage': 0,
        'DeviceGetUtilizationRates': 0,
        'DeviceGetMemoryInfo': 0,
    }

    class NVMLError(Exception):
        pass

    class _Util:
        def __init__(self, gpu):
            self.gpu = gpu

    class _Mem:
        def __init__(self, used, total):
            self.used = used
            self.total = total

    # Constants used by resource_control
    mod.NVML_TEMPERATURE_GPU = 0
    mod.NVML_CLOCK_SM = 0
    mod.NVML_CLOCK_MEM = 1
    mod.NVMLError = NVMLError

    def nvmlInit():
        mod.call_counts['nvmlInit'] += 1
        mod._inited = True

    def nvmlDeviceGetCount():
        mod.call_counts['DeviceGetCount'] += 1
        return mod._count

    def nvmlDeviceGetHandleByIndex(i):
        mod.call_counts['DeviceGetHandleByIndex'] += 1
        # simple handle is just the index
        return int(i)

    def nvmlDeviceGetTemperature(handle, which):
        mod.call_counts['DeviceGetTemperature'] += 1
        return int(mod._temps[int(handle)])

    def nvmlDeviceGetPowerUsage(handle):
        mod.call_counts['DeviceGetPowerUsage'] += 1
        return int(mod._powers_mw[int(handle)])

    def nvmlDeviceGetUtilizationRates(handle):
        mod.call_counts['DeviceGetUtilizationRates'] += 1
        return _Util(int(mod._utils_pct[int(handle)]))

    def nvmlDeviceGetMemoryInfo(handle):
        mod.call_counts['DeviceGetMemoryInfo'] += 1
        idx = int(handle)
        return _Mem(int(mod._mem_used[idx]), int(mod._mem_total[idx]))

    # Expose functions
    mod.nvmlInit = nvmlInit
    mod.nvmlDeviceGetCount = nvmlDeviceGetCount
    mod.nvmlDeviceGetHandleByIndex = nvmlDeviceGetHandleByIndex
    mod.nvmlDeviceGetTemperature = nvmlDeviceGetTemperature
    mod.nvmlDeviceGetPowerUsage = nvmlDeviceGetPowerUsage
    mod.nvmlDeviceGetUtilizationRates = nvmlDeviceGetUtilizationRates
    mod.nvmlDeviceGetMemoryInfo = nvmlDeviceGetMemoryInfo

    return mod


class TestGpuResourceManagerSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Inject stub before importing GPUResourceManager
        sys.modules['pynvml'] = make_pynvml_stub(count=2)
        # Import after stub is ready
        from app.mining_environment.scripts.resource_control import GPUResourceManager, GpuMetricsSnapshot
        cls.GPUResourceManager = GPUResourceManager
        cls.GpuMetricsSnapshot = GpuMetricsSnapshot

    @classmethod
    def tearDownClass(cls):
        # Clean up stub
        try:
            del sys.modules['pynvml']
        except KeyError:
            pass

    def setUp(self):
        # fresh stub per test
        sys.modules['pynvml'] = make_pynvml_stub(count=2)
        self.grm = self.GPUResourceManager(config={}, logger=None)

    def test_snapshot_mapping_ratio_and_bytes(self):
        snap = self.grm.get_metrics_snapshot(ttl_sec=1.0)
        self.assertIsInstance(snap, self.GpuMetricsSnapshot)
        # indices
        self.assertEqual(snap.gpu_indices, [0, 1])
        # utilization ratio mapping
        self.assertAlmostEqual(snap.utilization[0], 0.10, places=5)
        self.assertAlmostEqual(snap.utilization[1], 0.30, places=5)
        # memory bytes
        self.assertIsInstance(snap.mem_used_bytes[0], int)
        self.assertGreater(snap.mem_total_bytes[1], snap.mem_used_bytes[1])
        # temperature/power types
        self.assertIsInstance(snap.temperature_c[0], float)
        self.assertIsInstance(snap.power_watts[1], float)

    def test_ttl_caching_returns_same_object_and_avoids_nvml_calls(self):
        stub = sys.modules['pynvml']
        # First call
        snap1 = self.grm.get_metrics_snapshot(ttl_sec=2.0)
        # Capture counts after first call
        c1 = dict(stub.call_counts)
        # Immediate second call within TTL
        snap2 = self.grm.get_metrics_snapshot(ttl_sec=2.0)
        c2 = dict(stub.call_counts)
        # Same object due to cache
        self.assertIs(snap1, snap2)
        # NVML functions should not be called again
        self.assertEqual(c1, c2)

    def test_ttl_expiry_triggers_refresh(self):
        # Very short TTL
        snap1 = self.grm.get_metrics_snapshot(ttl_sec=0.01)
        time.sleep(0.02)
        snap2 = self.grm.get_metrics_snapshot(ttl_sec=0.01)
        self.assertIsInstance(snap1, self.GpuMetricsSnapshot)
        self.assertIsInstance(snap2, self.GpuMetricsSnapshot)
        # New snapshot (allow either different object or updated timestamp)
        self.assertNotEqual(snap1.timestamp, snap2.timestamp)

    def test_fallback_nvidia_smi_path_is_used_when_nvml_not_initialized(self):
        # Override fallback collector to avoid system dependency
        # Force NVML uninitialized
        self.grm.gpu_initialized = False

        def fake_smi(indices=None):
            # indices, temps, powers, utils(ratio), mem_used_bytes, mem_total_bytes
            return [0], {0: 70.0}, {0: 55.0}, {0: 0.5}, {0: 500 * 1024 * 1024}, {0: 8000 * 1024 * 1024}

        # Monkeypatch instance method
        self.grm._collect_metrics_with_nvidia_smi = fake_smi  # type: ignore

        snap = self.grm.get_metrics_snapshot(ttl_sec=1.0)
        self.assertEqual(snap.gpu_indices, [0])
        self.assertAlmostEqual(snap.temperature_c[0], 70.0)
        self.assertAlmostEqual(snap.power_watts[0], 55.0)
        self.assertAlmostEqual(snap.utilization[0], 0.5)
        self.assertEqual(snap.mem_total_bytes[0], 8000 * 1024 * 1024)


if __name__ == '__main__':
    unittest.main(verbosity=2)
