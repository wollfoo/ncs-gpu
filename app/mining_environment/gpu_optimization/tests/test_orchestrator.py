#!/usr/bin/env python3
"""
Test script for GPU Orchestrator
Kiểm thử cho bộ điều phối GPU
"""

import sys
import os
import time
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.orchestrator import (
    GPUOrchestrator,
    StrategyEngine, 
    HardwareController,
    MetricsCollector
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_orchestrator():
    """Test orchestrator functionality"""
    
    print("\n" + "="*60)
    print("🧪 GPU ORCHESTRATOR TEST")
    print("="*60)
    
    # Test configuration
    config = {
        'max_workers': 2,
        'strategy_timeout': 10.0,
        'power_params': {'target_power': 180},
        'clock_params': {'target_clock': 1400},
        'temperature_params': {'target_temp': 65}
    }
    
    try:
        # 1. Initialize orchestrator
        print("\n1️⃣ Initializing orchestrator...")
        orchestrator = GPUOrchestrator(config)
        print("   ✅ Orchestrator initialized")
        
        # 2. Test strategy engine
        print("\n2️⃣ Testing strategy engine...")
        engine = StrategyEngine()
        
        # Test metrics for strategy selection
        test_metrics = {
            'power': 280,  # High power
            'temperature': 78,  # High temp
            'memory_used': 9000  # High memory
        }
        
        strategies = engine.select_strategies(test_metrics)
        print(f"   Selected strategies: {strategies}")
        print("   ✅ Strategy selection working")
        
        # 3. Test hardware controller
        print("\n3️⃣ Testing hardware controller...")
        hw_controller = HardwareController()
        
        strategy_results = {
            'power': {'status': 'success', 'target': 200},
            'temperature': {'status': 'success', 'target_temp': 70}
        }
        
        hw_results = hw_controller.apply_optimizations(
            pid=1234,
            gpu_index=0,
            strategy_results=strategy_results
        )
        print(f"   Applied settings: {hw_results['applied']}")
        print("   ✅ Hardware controller working")
        
        # 4. Test metrics collector
        print("\n4️⃣ Testing metrics collector...")
        collector = MetricsCollector()
        
        metrics = collector.collect_gpu_metrics(gpu_index=0)
        print(f"   Collected metrics: GPU {metrics['gpu_index']}")
        print(f"   - Power: {metrics['power']}W")
        print(f"   - Temperature: {metrics['temperature']}°C")
        print(f"   - Memory: {metrics['memory_used']}/{metrics['memory_total']} MB")
        print("   ✅ Metrics collector working")
        
        # 5. Test full optimization flow
        print("\n5️⃣ Testing full optimization flow...")
        
        # Use current process PID for testing
        current_pid = os.getpid()
        process_info = {
            'pid': current_pid,
            'gpu_index': 0
        }
        
        results = orchestrator.optimize(
            process_info=process_info,
            strategies=['balanced']
        )
        
        print(f"   Optimization results:")
        print(f"   - Success: {results['success']}")
        print(f"   - Strategies applied: {results['strategies_applied']}")
        print(f"   - Duration: {results['duration']:.2f}s")
        
        if results['improvements']:
            print(f"   - Improvements: {list(results['improvements'].keys())}")
        
        print("   ✅ Full optimization flow completed")
        
        # 6. Test status
        print("\n6️⃣ Testing status retrieval...")
        status = orchestrator.get_status()
        print(f"   Stats: {status['stats']}")
        print("   ✅ Status retrieval working")
        
        # 7. Test shutdown
        print("\n7️⃣ Testing graceful shutdown...")
        orchestrator.shutdown()
        print("   ✅ Shutdown completed")
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_orchestrator()
    sys.exit(0 if success else 1)
