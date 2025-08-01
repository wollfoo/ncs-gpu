#!/usr/bin/env python3
"""
Test Script cho GPU Monitoring Enhancements
Validate tất cả các cải tiến mới được triển khai
"""

import sys
import time
import logging
import importlib
from pathlib import Path

# ✅ ADD PROJECT PATH: Thêm đường dẫn project
sys.path.insert(0, str(Path(__file__).parent))

def test_enhanced_logging():
    """**Test Enhanced Logging in ResourceControlFactory** (test logging nâng cao)"""
    print("🔧 Testing Enhanced Logging in ResourceControlFactory...")
    
    try:
        # ✅ IMPORT TEST: Test import resource_control
        from mining_environment.scripts.resource_control import ResourceControlFactory
        print("✅ ResourceControlFactory import successful")
        
        # ✅ CONFIG TEST: Test với config đơn giản
        test_config = {
            'resource_allocation': {
                'gpu': {'max_usage_percent': [80, 80]}
            }
        }
        
        # ✅ CREATE LOGGER: Tạo test logger
        test_logger = logging.getLogger('test_gpu_monitoring')
        test_logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        test_logger.addHandler(handler)
        
        print("🎮 Testing GPU manager creation...")
        
        # ✅ FACTORY TEST: Test factory creation (sẽ có enhanced GPU logging)
        try:
            resource_managers = ResourceControlFactory.create_resource_managers(test_config, test_logger)
            
            if 'gpu' in resource_managers:
                gpu_manager = resource_managers['gpu']
                print(f"✅ GPU Manager created: GPU count = {gpu_manager.get_gpu_count()}")
                print(f"✅ NVML initialized: {gpu_manager.is_nvml_initialized()}")
            else:
                print("⚠️ GPU Manager not found in resource_managers")
                
        except Exception as e:
            print(f"❌ Factory creation failed: {e}")
            return False
            
        print("✅ Enhanced logging test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced logging test failed: {e}")
        return False

def test_gpu_resource_monitor():
    """**Test GPUResourceManagerMonitor Class** (test lớp giám sát)"""
    print("\\n🎮 Testing GPUResourceManagerMonitor...")
    
    try:
        # ✅ IMPORT TEST: Test import monitor
        from mining_environment.scripts.gpu_resource_monitor import GPUResourceManagerMonitor, get_gpu_monitor
        print("✅ GPUResourceManagerMonitor import successful")
        
        # ✅ INSTANCE TEST: Test tạo instance
        monitor = GPUResourceManagerMonitor()
        print("✅ GPUResourceManagerMonitor instance created")
        
        # ✅ GLOBAL INSTANCE TEST: Test global instance
        global_monitor = get_gpu_monitor()
        print("✅ Global GPU monitor instance obtained")
        
        # ✅ HEALTH CHECK TEST: Test health check (without GPU manager)
        print("🔍 Testing health check without GPU manager...")
        health_metrics = monitor.perform_health_check()
        print(f"✅ Health check completed: Manager active = {health_metrics.manager_active}")
        
        # ✅ DASHBOARD DATA TEST: Test dashboard data
        print("📊 Testing dashboard data generation...")
        dashboard_data = monitor.get_dashboard_data()
        print(f"✅ Dashboard data generated: Status = {dashboard_data.get('status', 'unknown')}")
        
        # ✅ HEALTH SUMMARY TEST: Test health summary
        print("📋 Testing health summary...")
        health_summary = monitor.get_health_summary()
        print(f"✅ Health summary generated: Status = {health_summary['status']}")
        
        print("✅ GPUResourceManagerMonitor test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ GPUResourceManagerMonitor test failed: {e}")
        return False

def test_periodic_health_checks():
    """**Test Periodic Health Checks Integration** (test tích hợp health checks)"""
    print("\\n⏰ Testing Periodic Health Checks Integration...")
    
    try:
        # ✅ IMPORT TEST: Test import resource_manager
        from mining_environment.scripts.resource_manager import ResourceManager
        print("✅ ResourceManager import successful")
        
        # ✅ CHECK METHODS: Kiểm tra các methods mới
        methods_to_check = [
            '_initialize_gpu_monitoring',
            '_periodic_gpu_health_check', 
            'register_process_for_monitoring',
            'unregister_process_from_monitoring'
        ]
        
        for method_name in methods_to_check:
            if hasattr(ResourceManager, method_name):
                print(f"✅ Method {method_name} exists in ResourceManager")
            else:
                print(f"❌ Method {method_name} missing in ResourceManager")
                return False
        
        print("✅ Periodic health checks integration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Periodic health checks test failed: {e}")
        return False

def test_monitoring_dashboard():
    """**Test Monitoring Dashboard** (test dashboard giám sát)"""
    print("\\n🌐 Testing Monitoring Dashboard...")
    
    try:
        # ✅ IMPORT TEST: Test import dashboard
        from mining_environment.scripts.gpu_monitoring_dashboard import (
            GPUMonitoringDashboard, 
            get_gpu_dashboard,
            ConsoleDashboard,
            display_console_dashboard
        )
        print("✅ Dashboard imports successful")
        
        # ✅ DASHBOARD INSTANCE TEST: Test tạo dashboard instance
        dashboard = GPUMonitoringDashboard(host="127.0.0.1", port=8889)  # Use different port
        print("✅ GPUMonitoringDashboard instance created")
        
        # ✅ GLOBAL DASHBOARD TEST: Test global dashboard
        global_dashboard = get_gpu_dashboard(host="127.0.0.1", port=8890)
        print("✅ Global dashboard instance obtained")
        
        # ✅ CONSOLE DASHBOARD TEST: Test console dashboard
        print("📺 Testing console dashboard...")
        console_dashboard = ConsoleDashboard()
        
        # Test compact status (should work even without GPU manager)
        print("Testing compact status display:")
        console_dashboard.display_compact_status()
        print("✅ Console dashboard test completed")
        
        # ✅ FLASK APP TEST: Test Flask app creation
        if hasattr(dashboard, 'app'):
            print("✅ Flask app created successfully")
            
            # Test routes exist
            routes = [rule.rule for rule in dashboard.app.url_map.iter_rules()]
            expected_routes = ['/', '/api/gpu/status', '/api/gpu/health', '/api/gpu/metrics', '/api/gpu/export']
            
            for route in expected_routes:
                if route in routes:
                    print(f"✅ Route {route} exists")
                else:
                    print(f"❌ Route {route} missing")
                    return False
        
        print("✅ Monitoring dashboard test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Monitoring dashboard test failed: {e}")
        return False

def test_integration():
    """**Test Full Integration** (test tích hợp đầy đủ)"""
    print("\\n🔗 Testing Full Integration...")
    
    try:
        # ✅ INTEGRATION TEST: Test tích hợp các components
        print("🎯 Testing ResourceManager + GPU Monitor integration...")
        
        # ✅ IMPORT ALL: Import tất cả components
        from mining_environment.scripts.resource_control import ResourceControlFactory
        from mining_environment.scripts.gpu_resource_monitor import initialize_gpu_monitoring
        from mining_environment.scripts.gpu_monitoring_dashboard import start_gpu_dashboard
        
        print("✅ All integration imports successful")
        
        # ✅ CREATE CONFIG: Tạo config test
        integration_config = {
            'resource_allocation': {
                'gpu': {'max_usage_percent': [80, 80]}
            },
            'monitoring': {
                'auto_start_monitoring': False,  # Don't auto-start for test
                'health_check_interval_seconds': 5
            }
        }
        
        # ✅ CREATE LOGGER: Tạo integration logger
        integration_logger = logging.getLogger('integration_test')
        integration_logger.setLevel(logging.INFO)
        
        print("🔧 Creating resource managers...")
        resource_managers = ResourceControlFactory.create_resource_managers(integration_config, integration_logger)
        
        if 'gpu' in resource_managers:
            gpu_manager = resource_managers['gpu']
            print("✅ GPU Manager available for integration")
            
            # ✅ INITIALIZE MONITORING: Khởi tạo monitoring
            print("🎮 Initializing GPU monitoring...")
            monitor = initialize_gpu_monitoring(gpu_manager, integration_config.get('monitoring', {}))
            print("✅ GPU monitoring initialized")
            
            # ✅ PERFORM HEALTH CHECK: Thực hiện health check
            print("🔍 Performing integration health check...")
            health_metrics = monitor.perform_health_check()
            print(f"✅ Integration health check completed: GPU count = {health_metrics.gpu_count}")
            
        else:
            print("⚠️ GPU Manager not available - integration test limited")
        
        print("✅ Full integration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Full integration test failed: {e}")
        return False

def test_file_validation():
    """**Test File Validation** (test validation file)"""
    print("\\n📁 Testing File Validation...")
    
    try:
        # ✅ CHECK FILES: Kiểm tra các files đã tạo
        files_to_check = [
            "mining_environment/scripts/gpu_resource_monitor.py",
            "mining_environment/scripts/gpu_monitoring_dashboard.py"
        ]
        
        base_path = Path(__file__).parent
        
        for file_path in files_to_check:
            full_path = base_path / file_path
            if full_path.exists():
                print(f"✅ File exists: {file_path}")
                
                # ✅ CHECK FILE SIZE: Kiểm tra kích thước file
                file_size = full_path.stat().st_size
                if file_size > 1000:  # At least 1KB
                    print(f"✅ File size OK: {file_size} bytes")
                else:
                    print(f"⚠️ File size small: {file_size} bytes")
            else:
                print(f"❌ File missing: {file_path}")
                return False
        
        # ✅ CHECK MODIFIED RESOURCE_CONTROL: Kiểm tra file đã modify
        resource_control_path = base_path / "mining_environment/scripts/resource_control.py"
        if resource_control_path.exists():
            print("✅ resource_control.py exists")
            
            # ✅ CHECK ENHANCED LOGGING: Kiểm tra enhanced logging code
            content = resource_control_path.read_text()
            if "GPU MANAGER] ✅ ACTIVE" in content:
                print("✅ Enhanced GPU logging found in resource_control.py")
            else:
                print("❌ Enhanced GPU logging not found in resource_control.py")
                return False
        
        # ✅ CHECK MODIFIED RESOURCE_MANAGER: Kiểm tra resource_manager đã modify
        resource_manager_path = base_path / "mining_environment/scripts/resource_manager.py"
        if resource_manager_path.exists():
            print("✅ resource_manager.py exists")
            
            # ✅ CHECK GPU MONITORING: Kiểm tra GPU monitoring code
            content = resource_manager_path.read_text()
            if "_initialize_gpu_monitoring" in content:
                print("✅ GPU monitoring integration found in resource_manager.py")
            else:
                print("❌ GPU monitoring integration not found in resource_manager.py")
                return False
        
        print("✅ File validation test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ File validation test failed: {e}")
        return False

def main():
    """**Main Test Function** (hàm test chính)"""
    print("🚀 Starting GPU Monitoring Enhancements Test Suite")
    print("=" * 80)
    
    # ✅ TEST RESULTS: Kết quả test
    test_results = {
        "Enhanced Logging": test_enhanced_logging(),
        "GPU Resource Monitor": test_gpu_resource_monitor(), 
        "Periodic Health Checks": test_periodic_health_checks(),
        "Monitoring Dashboard": test_monitoring_dashboard(),
        "Full Integration": test_integration(),
        "File Validation": test_file_validation()
    }
    
    # ✅ SUMMARY: Tóm tắt kết quả
    print("\\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30} | {status}")
        if result:
            passed_tests += 1
    
    print("-" * 80)
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if passed_tests == total_tests:
        print("\\n🎉 ALL TESTS PASSED! GPU Monitoring Enhancements are working correctly.")
        return True
    else:
        print(f"\\n⚠️ {total_tests - passed_tests} TEST(S) FAILED. Please check the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)