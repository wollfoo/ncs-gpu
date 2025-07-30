#!/usr/bin/env python3
"""
🧪 EventBus Removal Validation Script
Kiểm tra tính toàn vẹn của hệ thống sau khi loại bỏ EventBus dependencies.
"""

import sys
import os
import importlib
from pathlib import Path

def validate_imports():
    """Kiểm tra các imports quan trọng hoạt động sau khi loại bỏ EventBus"""
    print("🔍 Validating critical imports after EventBus removal...")
    
    # Add project root to path
    sys.path.insert(0, '/home/azureuser/ncs-gpu/app')
    
    validation_results = {}
    
    # Test critical modules
    critical_modules = [
        'mining_environment.scripts.unified_logging',
        'mining_environment.scripts.error_management', 
        'mining_environment.scripts.resource_manager',
        'mining_environment.stealth.core.stealth_activation_manager',
        'pid_logger.direct_registry'
    ]
    
    for module_name in critical_modules:
        try:
            module = importlib.import_module(module_name)
            validation_results[module_name] = "✅ PASS"
            print(f"✅ {module_name} - Import successful")
        except ImportError as e:
            validation_results[module_name] = f"❌ FAIL: {e}"
            print(f"❌ {module_name} - Import failed: {e}")
        except Exception as e:
            validation_results[module_name] = f"⚠️ WARNING: {e}"
            print(f"⚠️ {module_name} - Import warning: {e}")
    
    return validation_results

def validate_directpid_registry():
    """Kiểm tra DirectPIDRegistry hoạt động"""
    print("\n🧠 Validating DirectPIDRegistry functionality...")
    
    try:
        from pid_logger.direct_registry import get_direct_registry
        
        registry = get_direct_registry()
        print("✅ DirectPIDRegistry instance created successfully")
        
        # Test basic functionality
        initial_count = len(registry.get_all_processes())
        print(f"📊 DirectPIDRegistry contains {initial_count} processes")
        
        return True
        
    except Exception as e:
        print(f"❌ DirectPIDRegistry validation failed: {e}")
        return False

def validate_stealth_activation():
    """Kiểm tra Stealth Activation Manager"""
    print("\n🔄 Validating Stealth Activation Manager...")
    
    try:
        from mining_environment.stealth.core.stealth_activation_manager import get_stealth_activation_manager
        
        manager = get_stealth_activation_manager()
        print("✅ Stealth Activation Manager instance created successfully")
        
        # Test initialization
        success = manager.initialize()
        if success:
            print("✅ Stealth Activation Manager initialized successfully")
            
            # Get status
            status = manager.get_stealth_status()
            print(f"📊 Stealth Status: {status}")
            
            return True
        else:
            print("❌ Stealth Activation Manager initialization failed")
            return False
            
    except Exception as e:
        print(f"❌ Stealth Activation Manager validation failed: {e}")
        return False

def validate_error_management():
    """Kiểm tra Error Management System"""
    print("\n🚨 Validating Error Management System...")
    
    try:
        from mining_environment.scripts.error_management import get_error_reporter, ErrorCode, ErrorSeverity
        
        reporter = get_error_reporter()
        print("✅ Error Reporter instance created successfully")
        
        # Test error reporting
        test_error = reporter.report_error(
            error_code=ErrorCode.SYSTEM_CONFIGURATION_INVALID,
            message="Test error for validation",
            severity=ErrorSeverity.LOW
        )
        
        print(f"✅ Test error reported successfully: ID={test_error.error_id}")
        
        # Get metrics
        metrics = reporter.get_error_metrics()
        print(f"📊 Error Metrics: {metrics['total_errors']} total errors")
        
        return True
        
    except Exception as e:
        print(f"❌ Error Management validation failed: {e}")
        return False

def validate_unified_logging():
    """Kiểm tra Unified Logging System"""
    print("\n📋 Validating Unified Logging System...")
    
    try:
        from mining_environment.scripts.unified_logging import get_unified_logger, get_logging_status
        
        logger = get_unified_logger('validation_test')
        print("✅ Unified Logger instance created successfully")
        
        # Test logging
        logger.info("🧪 Test log message from validation script")
        print("✅ Test log message sent successfully")
        
        # Get status
        status = get_logging_status()
        print(f"📊 Logging Status: {status['total_loggers']} loggers, {status['total_handlers']} handlers")
        
        return True
        
    except Exception as e:
        print(f"❌ Unified Logging validation failed: {e}")
        return False

def check_eventbus_references():
    """Kiểm tra còn EventBus references nào không"""
    print("\n🗑️ Checking for remaining EventBus references...")
    
    app_path = Path('/home/azureuser/ncs-gpu/app')
    eventbus_files = []
    
    # Scan for EventBus references in Python files
    for py_file in app_path.rglob('*.py'):
        try:
            content = py_file.read_text(encoding='utf-8')
            if 'EventBus' in content or 'event_bus' in content:
                # Count references
                eventbus_count = content.count('EventBus') + content.count('event_bus')
                # Filter out comments
                lines_with_eventbus = []
                for i, line in enumerate(content.split('\n'), 1):
                    if ('EventBus' in line or 'event_bus' in line) and not line.strip().startswith('#'):
                        lines_with_eventbus.append(f"  Line {i}: {line.strip()}")
                
                if lines_with_eventbus:
                    eventbus_files.append({
                        'file': str(py_file.relative_to(app_path)),
                        'count': eventbus_count,
                        'lines': lines_with_eventbus
                    })
        except Exception:
            continue
    
    if eventbus_files:
        print("⚠️ Found EventBus references in the following files:")
        for file_info in eventbus_files:
            print(f"  📄 {file_info['file']} ({file_info['count']} references)")
            for line in file_info['lines'][:3]:  # Show first 3 lines
                print(f"    {line}")
            if len(file_info['lines']) > 3:
                print(f"    ... and {len(file_info['lines']) - 3} more")
    else:
        print("✅ No active EventBus references found (comments excluded)")
    
    return len(eventbus_files) == 0

def main():
    """Main validation function"""
    print("🚀 Starting EventBus Removal Validation")
    print("=" * 50)
    
    validation_results = []
    
    # Run all validations
    validation_results.append(("Import Validation", validate_imports()))
    validation_results.append(("DirectPIDRegistry", validate_directpid_registry()))
    validation_results.append(("Stealth Activation", validate_stealth_activation()))
    validation_results.append(("Error Management", validate_error_management()))
    validation_results.append(("Unified Logging", validate_unified_logging()))
    validation_results.append(("EventBus References", check_eventbus_references()))
    
    # Summary
    print("\n" + "=" * 50)
    print("🏁 VALIDATION SUMMARY")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in validation_results:
        if isinstance(result, dict):
            # Import validation results
            all_passed = all("PASS" in str(v) for v in result.values())
            status = "✅ PASS" if all_passed else "❌ FAIL"
            print(f"{status} {test_name}")
            if all_passed:
                passed += 1
            else:
                failed += 1
        elif result:
            print(f"✅ PASS {test_name}")
            passed += 1
        else:
            print(f"❌ FAIL {test_name}")
            failed += 1
    
    print(f"\n📊 FINAL RESULT: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 ALL VALIDATIONS PASSED - EventBus removal successful!")
        return 0
    else:
        print("⚠️ Some validations failed - please review the issues above")
        return 1

if __name__ == "__main__":
    sys.exit(main())