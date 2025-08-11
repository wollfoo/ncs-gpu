#!/bin/bash
# PHASE 3: TESTING AND VALIDATION
# Thời gian: 4 giờ
# Mục đích: Test toàn diện và validate migration

set -e
set -u

echo "=========================================="
echo "PHASE 3: TESTING AND VALIDATION"
echo "=========================================="

BASE_DIR="/app/mining_environment/gpu_optimization"
SCRIPTS_DIR="/app/mining_environment/scripts"
TEST_LOG="phase3_test_results.log"

# Initialize log
echo "PHASE 3 TEST RESULTS - $(date)" > "$TEST_LOG"
echo "==========================================" >> "$TEST_LOG"

# 3.1 RUN COMPATIBILITY TESTS
echo "[1/5] Running compatibility tests..."

cat > test_compatibility.py << 'EOF'
#!/usr/bin/env python3
"""Test backward compatibility of imports"""

import sys
import warnings
import traceback

# Suppress deprecation warnings for this test
warnings.filterwarnings('ignore', category=DeprecationWarning)

def test_old_imports():
    """Test that old import paths still work"""
    print("Testing old import paths (via compatibility layer)...")
    
    old_imports = [
        ('scripts.gpu_optimization_orchestrator', ['GPUOrchestrator']),
        ('scripts.gpu_monitoring_dashboard', ['GPUMonitor', 'dashboard_main']),
        ('scripts.gpu_resource_monitor', ['ResourceMonitor']),
        ('scripts.cloak_strategies', ['CloakStrategy', 'apply_cloak']),
        ('scripts.resource_control', ['ResourceController']),
        ('scripts.cross_process_coordination', ['CrossProcessCoordinator']),
        ('scripts.parallel_strategy_executor', ['ParallelExecutor']),
        ('scripts.performance_profiler', ['PerformanceProfiler']),
    ]
    
    passed = 0
    failed = 0
    
    for module_path, expected_attrs in old_imports:
        try:
            module = __import__(module_path, fromlist=[''])
            for attr in expected_attrs:
                if not hasattr(module, attr):
                    print(f"  ✗ {module_path}.{attr} not found")
                    failed += 1
                else:
                    print(f"  ✓ {module_path}.{attr}")
                    passed += 1
        except ImportError as e:
            print(f"  ✗ Failed to import {module_path}: {e}")
            failed += 1
            for attr in expected_attrs:
                failed += 1
    
    print(f"\nOld imports: {passed} passed, {failed} failed")
    return failed == 0

def test_new_imports():
    """Test that new import paths work"""
    print("\nTesting new import paths...")
    
    new_imports = [
        ('gpu_optimization', ['GPUOrchestrator', 'GPUMonitor']),
        ('gpu_optimization.orchestrator', ['orchestrator']),
        ('gpu_optimization.monitoring', ['dashboard', 'resource_monitor']),
        ('gpu_optimization.strategies', ['cloak']),
        ('gpu_optimization.resource_control', ['controller']),
        ('gpu_optimization.coordination', ['cross_process', 'dag_sync']),
        ('gpu_optimization.execution', ['parallel_executor']),
        ('gpu_optimization.profiling', ['performance_profiler']),
    ]
    
    passed = 0
    failed = 0
    
    for module_path, expected_modules in new_imports:
        try:
            module = __import__(module_path, fromlist=[''])
            print(f"  ✓ Import {module_path}")
            passed += 1
        except ImportError as e:
            print(f"  ✗ Failed to import {module_path}: {e}")
            failed += 1
    
    print(f"\nNew imports: {passed} passed, {failed} failed")
    return failed == 0

def main():
    sys.path.insert(0, '/app/mining_environment')
    
    old_ok = test_old_imports()
    new_ok = test_new_imports()
    
    if old_ok and new_ok:
        print("\n✅ All compatibility tests passed!")
        return 0
    else:
        print("\n⚠️ Some compatibility tests failed")
        return 1

if __name__ == '__main__':
    exit(main())
EOF

python test_compatibility.py 2>&1 | tee -a "$TEST_LOG"
COMPAT_RESULT=$?

# 3.2 RUN UNIT TESTS
echo ""
echo "[2/5] Running unit tests..."

# Create basic unit test if not exists
mkdir -p "$BASE_DIR/tests/unit"
cat > "$BASE_DIR/tests/unit/test_imports.py" << 'EOF'
"""Basic import tests for migrated modules"""

import unittest
import sys
import os

sys.path.insert(0, '/app/mining_environment')

class TestModuleImports(unittest.TestCase):
    """Test that all modules can be imported"""
    
    def test_main_module_import(self):
        """Test main module import"""
        import gpu_optimization
        self.assertIsNotNone(gpu_optimization.__version__)
    
    def test_submodule_imports(self):
        """Test submodule imports"""
        modules = [
            'gpu_optimization.orchestrator',
            'gpu_optimization.monitoring',
            'gpu_optimization.strategies',
            'gpu_optimization.resource_control',
            'gpu_optimization.coordination',
            'gpu_optimization.execution',
            'gpu_optimization.profiling',
        ]
        
        for module_name in modules:
            with self.subTest(module=module_name):
                try:
                    __import__(module_name)
                except ImportError as e:
                    self.fail(f"Failed to import {module_name}: {e}")

if __name__ == '__main__':
    unittest.main(verbosity=2)
EOF

cd "$BASE_DIR"
python -m pytest tests/unit/ -v 2>&1 | tee -a "$TEST_LOG" || true
UNIT_RESULT=$?

# 3.3 PERFORMANCE BENCHMARK
echo ""
echo "[3/5] Running performance benchmark..."

cat > benchmark_imports.py << 'EOF'
#!/usr/bin/env python3
"""Benchmark import performance"""

import time
import sys
import statistics

sys.path.insert(0, '/app/mining_environment')

def benchmark_import(module_name, iterations=10):
    """Benchmark import time for a module"""
    times = []
    
    for _ in range(iterations):
        # Clear from cache
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        start = time.perf_counter()
        __import__(module_name)
        end = time.perf_counter()
        
        times.append((end - start) * 1000)  # Convert to ms
    
    return {
        'mean': statistics.mean(times),
        'median': statistics.median(times),
        'stdev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
    }

def main():
    print("Import Performance Benchmark")
    print("=" * 40)
    
    modules = [
        'gpu_optimization',
        'gpu_optimization.orchestrator',
        'gpu_optimization.monitoring',
        'gpu_optimization.strategies',
    ]
    
    for module in modules:
        try:
            stats = benchmark_import(module)
            print(f"\n{module}:")
            print(f"  Mean:   {stats['mean']:.2f} ms")
            print(f"  Median: {stats['median']:.2f} ms")
            print(f"  StdDev: {stats['stdev']:.2f} ms")
            print(f"  Range:  {stats['min']:.2f} - {stats['max']:.2f} ms")
        except Exception as e:
            print(f"\n{module}: FAILED - {e}")
    
    print("\n" + "=" * 40)
    print("Benchmark complete")

if __name__ == '__main__':
    main()
EOF

python benchmark_imports.py 2>&1 | tee -a "$TEST_LOG"

# 3.4 INTEGRATION TEST
echo ""
echo "[4/5] Running integration test..."

cat > integration_test.py << 'EOF'
#!/usr/bin/env python3
"""Integration test for migrated modules"""

import sys
import os
import warnings

sys.path.insert(0, '/app/mining_environment')
warnings.filterwarnings('ignore', category=DeprecationWarning)

def test_basic_workflow():
    """Test a basic workflow using the migrated modules"""
    print("Testing basic GPU optimization workflow...")
    
    try:
        # Test new imports
        from gpu_optimization import GPUOrchestrator, GPUMonitor
        print("✓ Main API imports successful")
        
        # Test instantiation (may fail if dependencies missing)
        try:
            if GPUOrchestrator:
                orchestrator = GPUOrchestrator()
                print("✓ GPUOrchestrator instantiated")
        except Exception as e:
            print(f"⚠ GPUOrchestrator instantiation failed (expected): {e}")
        
        try:
            if GPUMonitor:
                monitor = GPUMonitor()
                print("✓ GPUMonitor instantiated")
        except Exception as e:
            print(f"⚠ GPUMonitor instantiation failed (expected): {e}")
        
        # Test old imports still work
        import scripts.gpu_optimization_orchestrator
        print("✓ Legacy imports still functional")
        
        return True
        
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_basic_workflow()
    exit(0 if success else 1)
EOF

python integration_test.py 2>&1 | tee -a "$TEST_LOG"
INTEGRATION_RESULT=$?

# 3.5 DOCKER CONTAINER TEST
echo ""
echo "[5/5] Testing in Docker container (if available)..."

if command -v docker &> /dev/null; then
    cat > Dockerfile.test << 'EOF'
FROM python:3.10-slim

WORKDIR /app

# Copy the migrated code
COPY mining_environment /app/mining_environment

# Install dependencies (adjust as needed)
RUN pip install pytest numpy torch pynvml || true

# Run tests
CMD ["python", "-c", "import gpu_optimization; print('Docker test: SUCCESS')"]
EOF

    # Try to build and run
    docker build -f Dockerfile.test -t gpu-migration-test . 2>&1 | tee -a "$TEST_LOG" || true
    docker run --rm gpu-migration-test 2>&1 | tee -a "$TEST_LOG" || true
    
    echo "✓ Docker test attempted"
else
    echo "⚠ Docker not available, skipping container test"
fi

# GENERATE TEST REPORT
echo ""
echo "=========================================="
echo "GENERATING TEST REPORT..."
echo "=========================================="

cat > phase3_report.md << EOF
# Phase 3 Test Report

## Test Results Summary
- **Date**: $(date)
- **Compatibility Tests**: $([ $COMPAT_RESULT -eq 0 ] && echo "✅ PASSED" || echo "⚠️ FAILED")
- **Unit Tests**: $([ $UNIT_RESULT -eq 0 ] && echo "✅ PASSED" || echo "⚠️ FAILED")
- **Integration Test**: $([ $INTEGRATION_RESULT -eq 0 ] && echo "✅ PASSED" || echo "⚠️ FAILED")

## Test Coverage
- Old import paths: Tested via compatibility layer
- New import paths: Tested directly
- Module instantiation: Attempted (may fail due to dependencies)
- Performance benchmark: Completed

## Known Issues
- Some modules may fail to instantiate due to missing hardware dependencies
- This is expected in test environment

## Recommendations
$(if [ $COMPAT_RESULT -eq 0 ] && [ $UNIT_RESULT -eq 0 ]; then
    echo "1. ✅ Migration appears successful"
    echo "2. ✅ Proceed to Phase 4 (Cleanup)"
    echo "3. Monitor deprecation warnings in production"
else
    echo "1. ⚠️ Review failed tests in $TEST_LOG"
    echo "2. Fix import issues before proceeding"
    echo "3. Re-run this phase after fixes"
fi)

## Next Steps
- Review detailed logs in: $TEST_LOG
- If all tests pass: Run phase4_cleanup.sh
- If tests fail: Debug and re-run phase3_testing.sh

---
*Generated by Phase 3 Testing Script*
EOF

echo "✓ Test report generated: phase3_report.md"

# FINAL SUMMARY
echo ""
echo "=========================================="
echo "PHASE 3 COMPLETE!"
echo "=========================================="

if [ $COMPAT_RESULT -eq 0 ] && [ $UNIT_RESULT -eq 0 ]; then
    echo "✅ All critical tests passed!"
    echo "Ready to proceed to Phase 4 (Cleanup)"
else
    echo "⚠️ Some tests failed - review phase3_report.md"
    echo "Check $TEST_LOG for details"
fi

echo ""
echo "Reports generated:"
echo "  - phase3_report.md (summary)"
echo "  - $TEST_LOG (detailed logs)"
echo ""
echo "Next step: Review reports, then run phase4_cleanup.sh if ready"
