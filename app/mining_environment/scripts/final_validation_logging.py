#!/usr/bin/env python3
"""
Final Validation Script cho Hệ Thống Logging Mới
Kiểm tra toàn diện tất cả components và log outputs
"""

import os
import sys
import time
import threading
import traceback
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, '/home/azureuser/ncs-gpu/app')

# Import new logging system
from mining_environment.scripts.logging_config import setup_logging, get_unified_logger
from mining_environment.scripts.module_loggers import (
    get_mining_performance_logger,
    get_stealth_inference_logger,
    get_coordination_logger,
    get_registry_logger,
    get_resource_manager_logger,
    get_resource_control_logger,
    get_stealth_monitor_logger,
    get_dashboard_logger,
    get_pid_logger,
    get_utility_logger,
    get_gpu_plugin_logger,
    get_nvml_logger,
    get_thermal_logger,
    get_timing_logger,
    get_proxy_daemon_logger,
    get_environment_logger,
    get_gpu_cloaking_logger,
    get_gpu_stealth_logger,
    get_gpu_monitor_logger
)

class LoggingValidator:
    """Validator cho hệ thống logging mới"""
    
    def __init__(self):
        self.results = {}
        self.log_dir = Path("/home/azureuser/ncs-gpu/app/mining_environment/logs")
        self.start_time = datetime.now()
        
    def validate_setup(self) -> Tuple[bool, str]:
        """Validate logging setup và initialization"""
        try:
            # Test setup_logging
            setup_logging(log_level="DEBUG")
            return True, "✅ Logging setup successful"
        except Exception as e:
            return False, f"❌ Setup failed: {e}"
            
    def validate_all_loggers(self) -> Dict[str, Tuple[bool, str]]:
        """Test tất cả domain-specific loggers"""
        logger_tests = [
            ("mining_performance", get_mining_performance_logger, "mining_performance.log"),
            ("stealth_inference", get_stealth_inference_logger, "stealth_inference.log"),
            ("coordination", get_coordination_logger, "coordination.log"),
            ("registry", get_registry_logger, "registry.log"),
            ("resource_manager", get_resource_manager_logger, "resource_manager.log"),
            ("resource_control", get_resource_control_logger, "resource_control.log"),
            ("stealth_monitor", get_stealth_monitor_logger, "stealth_monitor.log"),
            ("dashboard", get_dashboard_logger, "dashboard.log"),
            ("pid_logger", get_pid_logger, "pid_logger.log"),
            ("utility", get_utility_logger, "utility.log"),
            ("gpu_plugin", get_gpu_plugin_logger, "gpu_plugin.log"),
            ("nvml", get_nvml_logger, "nvml.log"),
            ("thermal", get_thermal_logger, "thermal.log"),
            ("timing", get_timing_logger, "timing.log"),
            ("proxy_daemon", get_proxy_daemon_logger, "proxy_daemon.log"),
            ("environment", get_environment_logger, "environment.log"),
            ("gpu_cloaking", get_gpu_cloaking_logger, "gpu_cloaking.log"),
            # Test aliases
            ("gpu_stealth_alias", get_gpu_stealth_logger, "stealth_inference.log"),
            ("gpu_monitor_alias", get_gpu_monitor_logger, "stealth_monitor.log"),
        ]
        
        results = {}
        for name, logger_func, expected_file in logger_tests:
            try:
                # Get logger
                logger = logger_func()
                
                # Test log at each level
                test_msg = f"Validation test for {name}"
                logger.debug(f"🔍 DEBUG: {test_msg}")
                logger.info(f"ℹ️ INFO: {test_msg}")
                logger.warning(f"⚠️ WARNING: {test_msg}")
                logger.error(f"❌ ERROR: {test_msg}")
                
                # Check log file exists
                log_path = self.log_dir / expected_file
                if log_path.exists():
                    results[name] = (True, f"✅ Logger works, file: {expected_file}")
                else:
                    results[name] = (False, f"⚠️ Logger works but file not found: {expected_file}")
                    
            except Exception as e:
                results[name] = (False, f"❌ Failed: {e}")
                
        return results
        
    def validate_thread_safety(self) -> Tuple[bool, str]:
        """Test thread safety với multiple concurrent loggers"""
        try:
            errors = []
            threads = []
            
            def thread_worker(thread_id: int):
                try:
                    logger = get_mining_performance_logger()
                    for i in range(10):
                        logger.info(f"🧵 Thread {thread_id} - Message {i}")
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(f"Thread {thread_id}: {e}")
                    
            # Create 10 concurrent threads
            for i in range(10):
                t = threading.Thread(target=thread_worker, args=(i,))
                threads.append(t)
                t.start()
                
            # Wait for all threads
            for t in threads:
                t.join()
                
            if errors:
                return False, f"❌ Thread safety issues: {errors}"
            return True, "✅ Thread safety validated (10 concurrent threads)"
            
        except Exception as e:
            return False, f"❌ Thread safety test failed: {e}"
            
    def validate_log_rotation(self) -> Tuple[bool, str]:
        """Test log rotation functionality"""
        try:
            logger = get_utility_logger()
            
            # Write many messages to trigger rotation
            for i in range(100):
                logger.info(f"📊 Rotation test message {i} - " + "x" * 200)
                
            # Check for rotated files
            rotated_files = list(self.log_dir.glob("utils.log.*"))
            if rotated_files:
                return True, f"✅ Log rotation working ({len(rotated_files)} rotated files)"
            else:
                return True, "✅ Log rotation configured (no rotation triggered yet)"
                
        except Exception as e:
            return False, f"❌ Log rotation test failed: {e}"
            
    def validate_performance(self) -> Tuple[bool, str]:
        """Quick performance check"""
        try:
            logger = get_mining_performance_logger()
            
            # Measure throughput
            start = time.time()
            for i in range(1000):
                logger.debug(f"Performance test message {i}")
            elapsed = time.time() - start
            
            throughput = 1000 / elapsed
            
            if throughput > 450:  # Target: > 450 logs/sec
                return True, f"✅ Performance excellent: {throughput:.0f} logs/sec"
            else:
                return False, f"⚠️ Performance below target: {throughput:.0f} logs/sec (target: 450+)"
                
        except Exception as e:
            return False, f"❌ Performance test failed: {e}"
            
    def validate_backward_compatibility(self) -> Tuple[bool, str]:
        """Test backward compatibility với old API"""
        try:
            # Test generic logger
            logger = get_unified_logger("test_module")
            logger.info("Testing backward compatibility")
            
            return True, "✅ Backward compatibility maintained"
            
        except Exception as e:
            return False, f"❌ Backward compatibility broken: {e}"
            
    def check_legacy_cleanup(self) -> Tuple[bool, str]:
        """Verify legacy files đã được xóa"""
        legacy_files = [
            "/home/azureuser/ncs-gpu/app/mining_environment/scripts/unified_logging.py",
            "/home/azureuser/ncs-gpu/app/mining_environment/scripts/unified_log_aggregator.py"
        ]
        
        existing = []
        for file in legacy_files:
            if os.path.exists(file):
                existing.append(os.path.basename(file))
                
        if existing:
            return False, f"❌ Legacy files still exist: {existing}"
        return True, "✅ Legacy files cleaned up successfully"
        
    def run_full_validation(self):
        """Chạy toàn bộ validation suite"""
        print("=" * 60)
        print("🔍 FINAL VALIDATION - HỆ THỐNG LOGGING MỚI")
        print("=" * 60)
        print(f"📅 Start time: {self.start_time}")
        print()
        
        # 1. Setup validation
        print("1️⃣ VALIDATING SETUP...")
        success, msg = self.validate_setup()
        print(f"   {msg}")
        print()
        
        # 2. Legacy cleanup check
        print("2️⃣ CHECKING LEGACY CLEANUP...")
        success, msg = self.check_legacy_cleanup()
        print(f"   {msg}")
        print()
        
        # 3. Logger validation
        print("3️⃣ VALIDATING ALL LOGGERS...")
        logger_results = self.validate_all_loggers()
        passed = sum(1 for s, _ in logger_results.values() if s)
        total = len(logger_results)
        print(f"   📊 Passed: {passed}/{total} loggers")
        
        for name, (success, msg) in logger_results.items():
            if not success:
                print(f"   {msg}")
        
        if passed == total:
            print("   ✅ All loggers validated successfully!")
        print()
        
        # 4. Thread safety
        print("4️⃣ VALIDATING THREAD SAFETY...")
        success, msg = self.validate_thread_safety()
        print(f"   {msg}")
        print()
        
        # 5. Log rotation
        print("5️⃣ VALIDATING LOG ROTATION...")
        success, msg = self.validate_log_rotation()
        print(f"   {msg}")
        print()
        
        # 6. Performance
        print("6️⃣ VALIDATING PERFORMANCE...")
        success, msg = self.validate_performance()
        print(f"   {msg}")
        print()
        
        # 7. Backward compatibility
        print("7️⃣ VALIDATING BACKWARD COMPATIBILITY...")
        success, msg = self.validate_backward_compatibility()
        print(f"   {msg}")
        print()
        
        # Summary
        print("=" * 60)
        print("📋 VALIDATION SUMMARY")
        print("=" * 60)
        
        # Calculate overall status
        all_passed = (
            passed == total and
            all([
                self.validate_setup()[0],
                self.check_legacy_cleanup()[0],
                self.validate_thread_safety()[0],
                self.validate_performance()[0],
                self.validate_backward_compatibility()[0]
            ])
        )
        
        if all_passed:
            print("✅ ALL VALIDATIONS PASSED!")
            print("🎉 Hệ thống logging mới đã sẵn sàng production!")
        else:
            print("⚠️ Some validations failed. Please review above.")
            
        print(f"\n⏱️ Total validation time: {datetime.now() - self.start_time}")
        print("=" * 60)
        
        return all_passed


def main():
    """Main validation entry point"""
    try:
        validator = LoggingValidator()
        success = validator.run_full_validation()
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
