#!/usr/bin/env python3
"""
Test script for GPU Optimization Strategies
Kiểm tra các modules chiến lược tối ưu GPU
"""

import sys
import logging
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test importing all modules"""
    print("\n=== Testing Imports ===")
    
    try:
        # Add current directory to path for imports
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        import base
        from base import BaseStrategy, StrategyContext, StrategyResult, StrategyType, Priority
        print("✓ base.py imported successfully")
        
        import selector
        from selector import StrategySelector, SelectionMode
        print("✓ selector.py imported successfully")
        
        import balanced
        from balanced import BalancedStrategy, BalancedConfig
        print("✓ balanced.py imported successfully")
        
        import aggressive
        from aggressive import AggressiveStrategy, AggressiveConfig
        print("✓ aggressive.py imported successfully")
        
        import cloak
        from cloak import CloakStrategy, CloakConfig, CloakMode
        print("✓ cloak.py imported successfully")
        
        import parallel_executor
        from parallel_executor import ParallelExecutor, ParallelConfig, ExecutionMode
        print("✓ parallel_executor.py imported successfully")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_base_classes():
    """Test base classes instantiation"""
    print("\n=== Testing Base Classes ===")
    
    try:
        from base import StrategyContext, StrategyResult, Priority
        
        # Create test context
        context = StrategyContext(
            pid=1234,
            gpu_id=0,
            gpu_metrics={
                'utilization': 75.0,
                'memory_percent': 60.0,
                'temperature': 70.0,
                'power_draw': 200.0
            }
        )
        print(f"✓ Created StrategyContext: pid={context.pid}, gpu={context.gpu_id}")
        
        # Create test result
        result = StrategyResult(
            success=True,
            message="Test successful",
            metrics_before={'utilization': 70.0},
            metrics_after={'utilization': 75.0},
            duration=1.5
        )
        print(f"✓ Created StrategyResult: success={result.success}")
        
        return True
        
    except Exception as e:
        print(f"✗ Base class test failed: {e}")
        return False

def test_strategies():
    """Test strategy instantiation"""
    print("\n=== Testing Strategies ===")
    
    try:
        from base import StrategyContext
        from balanced import BalancedStrategy, BalancedConfig
        from aggressive import AggressiveStrategy, AggressiveConfig
        from cloak import CloakStrategy, CloakConfig, CloakMode
        
        # Test Balanced Strategy
        balanced_config = BalancedConfig(
            target_utilization=70.0,
            target_temperature=65.0
        )
        balanced = BalancedStrategy(balanced_config)
        print(f"✓ Created BalancedStrategy: {balanced}")
        
        # Test Aggressive Strategy
        aggressive_config = AggressiveConfig(
            max_gpu_utilization=95.0,
            risk_tolerance=0.8
        )
        aggressive = AggressiveStrategy(aggressive_config)
        print(f"✓ Created AggressiveStrategy: {aggressive}")
        
        # Test Cloak Strategy
        cloak_config = CloakConfig(
            mode=CloakMode.ACTIVE,
            target_utilization=30.0
        )
        cloak = CloakStrategy(cloak_config)
        print(f"✓ Created CloakStrategy: {cloak}")
        
        return True
        
    except Exception as e:
        print(f"✗ Strategy test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_selector():
    """Test strategy selector"""
    print("\n=== Testing Strategy Selector ===")
    
    try:
        from selector import StrategySelector, SelectionMode
        from balanced import BalancedStrategy
        from aggressive import AggressiveStrategy
        from base import StrategyContext, StrategyType
        
        # Create selector
        selector = StrategySelector(mode=SelectionMode.AUTOMATIC)
        print(f"✓ Created StrategySelector in {selector.mode.value} mode")
        
        # Register strategies (pass class not instance)
        selector.register_strategy(StrategyType.BALANCED, BalancedStrategy)
        selector.register_strategy(StrategyType.AGGRESSIVE, AggressiveStrategy)
        print(f"✓ Registered {len(selector.available_strategies)} strategies")
        
        # Test selection
        context = StrategyContext(
            pid=1234,
            gpu_id=0,
            gpu_metrics={
                'utilization': 75.0,
                'memory_percent': 60.0,
                'temperature': 70.0,
                'power_draw': 200.0
            }
        )
        
        selected = selector.select_strategy(context)
        if selected:
            print(f"✓ Selected strategy: {selected.name}")
        else:
            print("✗ No strategy selected")
        
        # Get recommendation
        recommendation = selector.get_recommendation(context)
        if recommendation['recommended']:
            print(f"✓ Got recommendation: {recommendation['recommended']} (confidence: {recommendation.get('confidence', 'N/A')})")
        else:
            print("✓ Got recommendation (no strategy available)")
        
        return True
        
    except Exception as e:
        print(f"✗ Selector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_parallel_executor():
    """Test parallel executor"""
    print("\n=== Testing Parallel Executor ===")
    
    try:
        from parallel_executor import ParallelExecutor, ParallelConfig, ExecutionMode
        from balanced import BalancedStrategy
        from base import StrategyContext, Priority
        
        # Create executor
        config = ParallelConfig(
            mode=ExecutionMode.THREAD,
            max_workers=2
        )
        executor = ParallelExecutor(config)
        print(f"✓ Created ParallelExecutor: {executor}")
        
        # Submit test task
        strategy = BalancedStrategy()
        context = StrategyContext(
            pid=1234,
            gpu_id=0,
            gpu_metrics={
                'utilization': 75.0,
                'memory_percent': 60.0,
                'temperature': 70.0,
                'power_draw': 200.0
            }
        )
        
        task_id = executor.submit_task(strategy, context, Priority.MEDIUM)
        print(f"✓ Submitted task: {task_id}")
        
        # Get statistics
        stats = executor.get_statistics()
        print(f"✓ Executor stats: {stats}")
        
        # Clean up
        executor.stop()
        print("✓ Executor stopped cleanly")
        
        return True
        
    except Exception as e:
        print(f"✗ Parallel executor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("GPU Optimization Strategies Test Suite")
    print("=" * 60)
    
    results = {
        'imports': test_imports(),
        'base_classes': test_base_classes(),
        'strategies': test_strategies(),
        'selector': test_selector(),
        'parallel_executor': test_parallel_executor()
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:20s}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
