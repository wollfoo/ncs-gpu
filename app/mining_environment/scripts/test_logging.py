#!/usr/bin/env python3
"""
Test script to verify detailed logging for GPU optimization classes
"""

import os
import sys
import logging
from datetime import datetime

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'test_logging_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)

def test_metrics_collection_hub():
    """Test MetricsCollectionHub logging"""
    print("\n" + "="*60)
    print("🧪 Testing MetricsCollectionHub logging...")
    print("="*60)
    
    try:
        from cloak_strategies import MetricsCollectionHub
        
        # Create instance
        hub = MetricsCollectionHub()
        
        # Test collecting metrics
        test_metrics = {
            'gpu_temp': 65.5,
            'gpu_power': 150.0,
            'gpu_utilization': 85.0,
            'vram_used': 4096,
            'vram_total': 8192
        }
        
        hub.collect(12345, test_metrics)
        
        # Test getting aggregated data
        aggregated = hub.get_aggregated_data()
        print(f"✅ Aggregated data: {aggregated}")
        
        # Test exporting metrics
        export_path = '/tmp/test_metrics_export.json'
        if hub.export_metrics(export_path):
            print(f"✅ Metrics exported to {export_path}")
        
        print("✅ MetricsCollectionHub logging test PASSED")
        
    except Exception as e:
        print(f"❌ MetricsCollectionHub test failed: {e}")
        import traceback
        traceback.print_exc()

def test_adaptive_pattern_generator():
    """Test AdaptivePatternGenerator logging"""
    print("\n" + "="*60)
    print("🧪 Testing AdaptivePatternGenerator logging...")
    print("="*60)
    
    try:
        from cloak_strategies import AdaptivePatternGenerator
        
        # Create instance
        generator = AdaptivePatternGenerator()
        
        # Test generating pattern
        pattern = generator.generate_pattern(
            current_temp=70.0,
            target_temp=65.0,
            current_power=180.0,
            target_power=150.0
        )
        
        print(f"✅ Generated pattern: {pattern}")
        
        # Test updating history
        generator.update_history(pattern, success=True, temp_achieved=64.5)
        
        print("✅ AdaptivePatternGenerator logging test PASSED")
        
    except Exception as e:
        print(f"❌ AdaptivePatternGenerator test failed: {e}")
        import traceback
        traceback.print_exc()

def test_optimized_hardware_controller():
    """Test OptimizedHardwareController logging"""
    print("\n" + "="*60)
    print("🧪 Testing OptimizedHardwareController logging...")
    print("="*60)
    
    try:
        # Mock the imports to avoid dependency issues
        import unittest.mock as mock
        
        # Mock the GPU manager
        with mock.patch('resource_control.GPUManager'):
            # Import after mocking
            from resource_control import OptimizedHardwareController
            
            # Create instance
            controller = OptimizedHardwareController()
            
            # Test optimization
            print("📊 Testing optimize_for_workload...")
            result = controller.optimize_for_workload(
                pid=12345,
                target_temp=65,
                target_power=150,
                vram_usage_gb=4.0
            )
            
            print(f"✅ Optimization result: {result}")
            
            # Test baseline verification
            print("📊 Testing baseline verification...")
            should_verify = controller._should_verify_baseline()
            print(f"✅ Should verify baseline: {should_verify}")
            
            # Test cleanup
            print("📊 Testing cleanup...")
            controller.cleanup()
            
            print("✅ OptimizedHardwareController logging test PASSED")
        
    except Exception as e:
        print(f"❌ OptimizedHardwareController test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Run all logging tests"""
    print("\n" + "🚀"*30)
    print("Starting GPU Optimization Logging Tests")
    print("🚀"*30)
    
    # Test each component
    test_metrics_collection_hub()
    test_adaptive_pattern_generator()
    test_optimized_hardware_controller()
    
    print("\n" + "✨"*30)
    print("All logging tests completed!")
    print("✨"*30)
    print("\n📝 Check the log file for detailed logging output")

if __name__ == "__main__":
    main()
