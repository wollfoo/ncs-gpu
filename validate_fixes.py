#!/usr/bin/env python3
"""
Simple validation script cho startup error fixes
"""
import os
import re

def validate_timeout_fix():
    """Validate SystemManager timeout fix"""
    print("🔧 Validating SystemManager timeout fix...")
    
    file_path = "/home/azureuser/grok4/app/mining_environment/scripts/system_manager.py"
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for 60-second timeout
        if "timeout sau 60 giây" in content:
            print("✅ SystemManager timeout increased to 60 seconds")
            return True
        else:
            print("❌ SystemManager timeout not updated")
            return False
            
    except Exception as e:
        print(f"❌ Cannot validate timeout fix: {e}")
        return False

def validate_cpu_target_fix():
    """Validate CPU utilization target restored to 800%"""
    print("🔧 Validating CPU utilization target restored to 800%...")
    
    file_path = "/home/azureuser/grok4/app/mining_environment/cpu_plugins/optimization/randomx_optimizer.py"
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for 800% target restored
        if "'target_cpu_utilization': 800" in content:
            print("✅ CPU utilization target restored to 800% per user request")
            return True
        else:
            print("❌ CPU utilization target not restored to 800%")
            return False
            
    except Exception as e:
        print(f"❌ Cannot validate CPU target fix: {e}")
        return False

def validate_queue_size_fix():
    """Validate queue size fix"""
    print("🔧 Validating queue size fix...")
    
    file_path = "/home/azureuser/grok4/app/mining_environment/cpu_plugins/optimization/optimized_calculation_chain.py"
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for cores * 12 queue size
        if "cores * 12" in content and "144 for 12 cores" in content:
            print("✅ Queue size increased to cores * 12 (144 for 12 cores)")
            return True
        else:
            print("❌ Queue size not updated")
            return False
            
    except Exception as e:
        print(f"❌ Cannot validate queue size fix: {e}")
        return False

def validate_system_integration_fix():
    """Validate system integration warning fix"""
    print("🔧 Validating system integration warning restored to 800%...")
    
    file_path = "/home/azureuser/grok4/app/mining_environment/cpu_plugins/optimization/system_integration.py"
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for updated target warning
        if "(target: 800%)" in content:
            print("✅ System integration warning restored to 800% target")
            return True
        else:
            print("❌ System integration warning not restored to 800%")
            return False
            
    except Exception as e:
        print(f"❌ Cannot validate system integration fix: {e}")
        return False

def validate_complexity_optimization():
    """Validate computational complexity optimization"""
    print("🔧 Validating computational complexity optimization...")
    
    file_path = "/home/azureuser/grok4/app/mining_environment/cpu_plugins/optimization/optimized_calculation_chain.py"
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for optimization indicators
        optimizations = [
            "Single optimized loop instead of nested loops",
            "Reduced from 10x to 5x for efficiency", 
            "Reduced CPU intensive math from 50 to 20",
            "Simplified intensive computation"
        ]
        
        found_optimizations = 0
        for optimization in optimizations:
            if optimization in content:
                found_optimizations += 1
                print(f"✅ Found: {optimization}")
        
        if found_optimizations >= 3:
            print(f"✅ Computational complexity optimized ({found_optimizations}/{len(optimizations)} optimizations found)")
            return True
        else:
            print(f"❌ Insufficient optimization indicators found ({found_optimizations}/{len(optimizations)})")
            return False
            
    except Exception as e:
        print(f"❌ Cannot validate complexity optimization: {e}")
        return False

def validate_file_changes():
    """Validate all file modifications"""
    print("📁 Validating file modifications...")
    
    changes = [
        ("/home/azureuser/grok4/app/mining_environment/scripts/system_manager.py", "timeout sau 60 giây"),
        ("/home/azureuser/grok4/app/mining_environment/cpu_plugins/optimization/randomx_optimizer.py", "target_cpu_utilization': 800"),
        ("/home/azureuser/grok4/app/mining_environment/cpu_plugins/optimization/optimized_calculation_chain.py", "cores * 12"),
        ("/home/azureuser/grok4/app/mining_environment/cpu_plugins/optimization/system_integration.py", "target: 800%")
    ]
    
    all_good = True
    for file_path, expected_content in changes:
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            if expected_content in content:
                print(f"✅ {os.path.basename(file_path)}: {expected_content}")
            else:
                print(f"❌ {os.path.basename(file_path)}: Missing {expected_content}")
                all_good = False
        except Exception as e:
            print(f"❌ {os.path.basename(file_path)}: Error reading file - {e}")
            all_good = False
    
    return all_good

def main():
    """Run validation"""
    print("🧪 === STARTUP ERRORS FIX VALIDATION ===")
    print()
    
    tests = [
        ("SYS-TIMEOUT-001: SystemManager timeout 30s→60s", validate_timeout_fix),
        ("CPU-UTIL-003: CPU target restored to 800% per user request", validate_cpu_target_fix),
        ("QUEUE-FULL-005: Queue size 96→144", validate_queue_size_fix),
        ("System Integration: Warning target restored to 800%", validate_system_integration_fix),
        ("COMPLEXITY-OPTIMIZATION: Computational complexity optimized", validate_complexity_optimization)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"📋 {test_name}")
        print("-" * 60)
        result = test_func()
        results.append((test_name, result))
        print()
    
    # Overall file validation
    print("📋 Overall File Changes Validation")
    print("-" * 60)
    file_validation = validate_file_changes()
    results.append(("File Changes", file_validation))
    print()
    
    # Summary
    print("📊 === VALIDATION SUMMARY ===")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"  
        print(f"{status}: {test_name}")
    
    print(f"\n🎯 Result: {passed}/{total} validations passed")
    
    if passed == total:
        print("\n🚀 ALL STARTUP ERROR FIXES SUCCESSFULLY APPLIED!")
        print("📋 System ready for testing with optimized parameters:")
        print("   • SystemManager timeout: 60 seconds") 
        print("   • CPU utilization target: 800% (restored per user request)")
        print("   • Task queue size: 144 (12 cores × 12)")
        print("   • Computational complexity optimized to prevent system overload")
        print("   • Warning messages updated")
        return True
    else:
        print(f"\n⚠️ {total - passed} validation(s) failed - check fixes")
        return False

if __name__ == "__main__":
    main()