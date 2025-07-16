#!/usr/bin/env python3
"""
Test GPU Logging System - Kiểm tra hệ thống logging cho GPU functions
"""
import os
import sys
import time
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_gpu_optimization_logger():
    """Test GPU optimization logger"""
    print("🧪 Testing GPU Optimization Logger...")
    
    try:
        from gpu_optimization_logger import gpu_opt_logger, log_gpu_optimization
        
        # Test basic function call logging
        @log_gpu_optimization()
        def test_gpu_function():
            time.sleep(0.1)  # Simulate some work
            return "success"
        
        # Test function with failure
        @log_gpu_optimization()
        def test_gpu_function_fail():
            raise Exception("Test error")
        
        # Test successful function
        print("  ✓ Testing successful function...")
        result = test_gpu_function()
        print(f"    Result: {result}")
        
        # Test failed function
        print("  ✓ Testing failed function...")
        try:
            test_gpu_function_fail()
        except Exception as e:
            print(f"    Expected error: {e}")
        
        # Test plugin lifecycle logging
        print("  ✓ Testing plugin lifecycle logging...")
        gpu_opt_logger.log_plugin_lifecycle(
            "test_plugin",
            "LOAD",
            "SUCCESS",
            {"config": {"enabled": True}}
        )
        
        # Test performance metrics
        print("  ✓ Testing performance metrics...")
        gpu_opt_logger.log_performance_metrics(
            "test_function",
            {
                "execution_time": 0.123,
                "memory_usage": 45.6,
                "cpu_usage": 12.3
            }
        )
        
        # Generate performance report
        print("  ✓ Generating performance report...")
        report_path = gpu_opt_logger.export_performance_report()
        print(f"    Report saved to: {report_path}")
        
        print("✅ GPU Optimization Logger test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ GPU Optimization Logger test failed: {e}")
        return False

def test_gpu_cloaking_logger():
    """Test GPU cloaking logger"""
    print("\n🧪 Testing GPU Cloaking Logger...")
    
    try:
        from gpu_cloaking_logger import gpu_cloak_logger, log_gpu_cloaking
        
        # Test cloaking strategy logging
        @log_gpu_cloaking(strategy_name="test_strategy", action="EXECUTE")
        def test_cloaking_function():
            time.sleep(0.05)  # Simulate some work
            return "cloaked"
        
        print("  ✓ Testing cloaking function...")
        result = test_cloaking_function()
        print(f"    Result: {result}")
        
        # Test NVML interception logging
        print("  ✓ Testing NVML interception logging...")
        gpu_cloak_logger.log_nvml_interception(
            action="START",
            status="SUCCESS",
            fake_utilization=5,
            fake_memory=100,
            lib_path="/opt/hooks/libgpuhook.so"
        )
        
        # Test thermal spoofing logging
        print("  ✓ Testing thermal spoofing logging...")
        gpu_cloak_logger.log_thermal_spoofing(
            action="START",
            status="SUCCESS",
            fake_temperature=50.0,
            add_noise=True,
            lib_path="/opt/hooks/libtempspoof.so"
        )
        
        # Test time-based evasion logging
        print("  ✓ Testing time-based evasion logging...")
        gpu_cloak_logger.log_time_based_evasion(
            action="START",
            status="SUCCESS",
            work_ms=800,
            sleep_ms=200,
            target_pid=12345
        )
        
        # Test eBPF filter logging
        print("  ✓ Testing eBPF filter logging...")
        gpu_cloak_logger.log_ebpf_filter(
            action="START",
            status="SUCCESS",
            filter_mode="auto",
            mock_mode=False
        )
        
        # Test effectiveness logging
        print("  ✓ Testing effectiveness logging...")
        gpu_cloak_logger.log_cloaking_effectiveness(
            strategy_name="test_strategy",
            detection_attempts=10,
            successful_evasions=9,
            detection_sources=["nvidia-smi", "htop"]
        )
        
        # Get active strategies
        print("  ✓ Getting active strategies...")
        active_strategies = gpu_cloak_logger.get_active_strategies()
        print(f"    Active strategies: {len(active_strategies)}")
        
        # Generate cloaking report
        print("  ✓ Generating cloaking report...")
        report_path = gpu_cloak_logger.export_cloaking_report()
        print(f"    Report saved to: {report_path}")
        
        print("✅ GPU Cloaking Logger test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ GPU Cloaking Logger test failed: {e}")
        return False

def test_log_files():
    """Test log files creation and content"""
    print("\n🧪 Testing Log Files...")
    
    try:
        # Check logs directory
        logs_dir = Path("/home/azureuser/grok4/app/mining_environment/logs")
        if not logs_dir.exists():
            print(f"❌ Logs directory not found: {logs_dir}")
            return False
        
        print(f"  ✓ Logs directory exists: {logs_dir}")
        
        # List log files
        log_files = list(logs_dir.glob("*.log"))
        print(f"  ✓ Found {len(log_files)} log files:")
        
        for log_file in log_files:
            print(f"    - {log_file.name}")
            
            # Check file content
            with open(log_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if content:
                    print(f"      Size: {len(content)} characters")
                    
                    # Try to parse JSON lines
                    lines = content.strip().split('\n')
                    json_lines = 0
                    for line in lines:
                        if line.strip() and ' - ' in line:
                            try:
                                # Extract JSON part after the log format
                                json_part = line.split(' - ')[-1]
                                if json_part.startswith('{') and json_part.endswith('}'):
                                    json.loads(json_part)
                                    json_lines += 1
                            except:
                                pass
                    
                    print(f"      JSON entries: {json_lines}")
                else:
                    print(f"      Empty file")
        
        # Check report files (now .log format)
        report_files = list(logs_dir.glob("*_report_*.log"))
        print(f"  ✓ Found {len(report_files)} report files:")
        
        for report_file in report_files:
            print(f"    - {report_file.name}")
            
            # Validate log structure
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.strip().split('\n')
                print(f"      Lines: {len(lines)}")
        
        print("✅ Log files test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Log files test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Starting GPU Logging System Tests...")
    print("=" * 50)
    
    # Create logs directory if it doesn't exist
    logs_dir = Path("/home/azureuser/grok4/app/mining_environment/logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Run tests
    tests = [
        test_gpu_optimization_logger,
        test_gpu_cloaking_logger,
        test_log_files
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed! GPU Logging System is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())