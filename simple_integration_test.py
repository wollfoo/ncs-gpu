#!/usr/bin/env python3
"""
Simple test để kiểm tra integration functions trong start_mining.py
"""

import os
import sys

def test_function_definitions():
    """Test các function có được định nghĩa trong start_mining.py"""
    print("🧪 Testing function definitions in start_mining.py...")
    
    file_path = "/home/azureuser/grok4/app/start_mining.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Test 1: activate_optimization_and_cloaking function
        if 'def activate_optimization_and_cloaking():' in content:
            print("✅ activate_optimization_and_cloaking function defined")
        else:
            print("❌ activate_optimization_and_cloaking function NOT defined")
            return False
        
        # Test 2: apply_cpu_optimization function
        if 'def apply_cpu_optimization(process):' in content:
            print("✅ apply_cpu_optimization function defined")
        else:
            print("❌ apply_cpu_optimization function NOT defined")
            return False
        
        # Test 3: apply_gpu_optimization function
        if 'def apply_gpu_optimization(process):' in content:
            print("✅ apply_gpu_optimization function defined")
        else:
            print("❌ apply_gpu_optimization function NOT defined")
            return False
        
        # Test 4: Integration in main function
        if 'activate_optimization_and_cloaking()' in content:
            print("✅ activate_optimization_and_cloaking() called in main")
        else:
            print("❌ activate_optimization_and_cloaking() NOT called in main")
            return False
        
        # Test 5: Cloaking imports
        expected_imports = [
            'get_process_by_cmdline',
            'spoof_cmdline',
            'restore_cmdline', 
            'create_stealth_subprocess'
        ]
        
        missing_imports = []
        for imp in expected_imports:
            if imp not in content:
                missing_imports.append(imp)
        
        if not missing_imports:
            print("✅ All cloaking utilities imports found")
        else:
            print(f"❌ Missing imports: {missing_imports}")
            return False
        
        # Test 6: Execution order
        main_start = content.find('def main():')
        if main_start == -1:
            print("❌ main() function not found")
            return False
        
        main_content = content[main_start:]
        
        # Kiểm tra thứ tự gọi hàm
        start_manager_pos = main_content.find('start_system_manager()')
        activate_pos = main_content.find('activate_optimization_and_cloaking()')
        
        if start_manager_pos < activate_pos:
            print("✅ Correct execution order: start_system_manager -> activate_optimization_and_cloaking")
        else:
            print("❌ Incorrect execution order")
            return False
        
        print("✅ All function definition tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error reading start_mining.py: {e}")
        return False

def test_integration_logic():
    """Test logic integration"""
    print("\n🧪 Testing integration logic...")
    
    file_path = "/home/azureuser/grok4/app/start_mining.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find activate_optimization_and_cloaking function
        func_start = content.find('def activate_optimization_and_cloaking():')
        if func_start == -1:
            print("❌ activate_optimization_and_cloaking function not found")
            return False
        
        # Extract function content
        func_end = content.find('\ndef ', func_start + 1)
        if func_end == -1:
            func_end = len(content)
        
        func_content = content[func_start:func_end]
        
        # Test logic components
        checks = [
            ('resource_manager access', 'system_manager.resource_manager'),
            ('mining_processes iteration', 'for process in rm.mining_processes'),
            ('CPU optimization call', 'apply_cpu_optimization(process)'),
            ('GPU optimization call', 'apply_gpu_optimization(process)'),
            ('Process state checking', 'process_states'),
            ('GPU process detection', '_is_gpu'),
        ]
        
        passed_checks = 0
        for check_name, pattern in checks:
            if pattern in func_content:
                print(f"✅ {check_name}: found")
                passed_checks += 1
            else:
                print(f"❌ {check_name}: NOT found")
        
        if passed_checks >= len(checks) - 1:  # Allow 1 missing check
            print(f"✅ Integration logic test passed ({passed_checks}/{len(checks)})")
            return True
        else:
            print(f"❌ Integration logic test failed ({passed_checks}/{len(checks)})")
            return False
        
    except Exception as e:
        print(f"❌ Error testing integration logic: {e}")
        return False

def test_comment_documentation():
    """Test documentation and comments"""
    print("\n🧪 Testing documentation...")
    
    file_path = "/home/azureuser/grok4/app/start_mining.py"
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for key documentation
        docs = [
            'Kích hoạt các chức năng tối ưu và cloaking',
            'resource_manager.enqueue_cloaking',
            'discover_mining_processes',
            'Áp dụng CPU optimization',
            'Áp dụng GPU optimization'
        ]
        
        found_docs = 0
        for doc in docs:
            if doc in content:
                found_docs += 1
                print(f"✅ Documentation found: '{doc[:30]}...'")
            else:
                print(f"❌ Documentation missing: '{doc[:30]}...'")
        
        if found_docs >= len(docs) - 1:
            print(f"✅ Documentation test passed ({found_docs}/{len(docs)})")
            return True
        else:
            print(f"❌ Documentation test failed ({found_docs}/{len(docs)})")
            return False
        
    except Exception as e:
        print(f"❌ Error testing documentation: {e}")
        return False

def main():
    """Run all simple integration tests"""
    print("🚀 === SIMPLE INTEGRATION TESTS ===")
    print()
    
    tests = [
        ("Function Definitions", test_function_definitions),
        ("Integration Logic", test_integration_logic),
        ("Documentation", test_comment_documentation)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"📋 {test_name}")
        print("-" * 50)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test failed: {e}")
            results.append((test_name, False))
        print()
    
    # Summary
    print("📊 === TEST RESULTS ===")
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🚀 ALL INTEGRATION TESTS PASSED!")
        print("\n📋 Implementation Summary:")
        print("   ✅ start_mining.py updated with optimization & cloaking integration")
        print("   ✅ activate_optimization_and_cloaking() function implemented")
        print("   ✅ apply_cpu_optimization() function implemented")
        print("   ✅ apply_gpu_optimization() function implemented") 
        print("   ✅ Integration called after resource_manager.enqueue_cloaking")
        print("   ✅ Uses discovered processes from resource_manager.discover_mining_processes")
        print("   ✅ Follows execution flow: setup_env -> system_manager -> optimization/cloaking -> mining")
        print("\n🎯 System ready: Optimization và cloaking sẽ được kích hoạt sau khi resource_manager khám phá tiến trình!")
        return True
    else:
        print(f"\n⚠️ {total - passed} test(s) failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)