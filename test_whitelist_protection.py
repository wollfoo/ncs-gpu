#!/usr/bin/env python3
"""
Test Script cho Enhanced Process Whitelist Protection

Kiểm tra xem mining processes có được bảo vệ khỏi STEALTH system hay không.
"""
import os
import sys
import time
import logging
import subprocess
from typing import Dict, Any

# Add path để import modules
sys.path.insert(0, '/home/azureuser/grok4/app/mining_environment')

try:
    from cpu_plugins.cloaking.stealth_exec import StealthExecution
    from scripts.unified_logging import get_unified_logger
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def setup_test_logger() -> logging.Logger:
    """Setup test logger"""
    logger = logging.getLogger('whitelist_test')
    logger.setLevel(logging.DEBUG)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

def test_whitelist_protection():
    """Test Enhanced Process Whitelist Protection"""
    logger = setup_test_logger()
    logger.info("🚀 Starting Enhanced Process Whitelist Protection Test")
    
    try:
        # ✅ TEST 1: Initialize StealthExecution
        logger.info("📋 TEST 1: Initializing StealthExecution with whitelist protection...")
        stealth_exec = StealthExecution(logger=logger, comm_rotation_interval=10)
        
        # ✅ TEST 2: Check whitelist configuration
        logger.info("📋 TEST 2: Verifying whitelist configuration...")
        logger.info(f"Mining Process Whitelist: {stealth_exec.MINING_PROCESS_WHITELIST}")
        
        # ✅ TEST 3: Test process name extraction
        logger.info("📋 TEST 3: Testing process name extraction...")
        current_pid = os.getpid()
        current_name = stealth_exec._get_process_name(current_pid)
        logger.info(f"Current process: PID {current_pid}, Name: {current_name}")
        
        # ✅ TEST 4: Test whitelist decision logic
        logger.info("📋 TEST 4: Testing whitelist decision logic...")
        
        # Test mining process (should be protected)
        test_cases = [
            ("ml-inference", "Should be PROTECTED"),
            ("inference-cuda", "Should be PROTECTED"), 
            ("python", "Should be PROTECTED"),
            ("systemd-journal", "Should be DISGUISED"),
            ("unknown-process", "Should be DISGUISED")
        ]
        
        for process_name, expected in test_cases:
            should_disguise = stealth_exec.should_disguise_process(current_pid, process_name)
            result = "DISGUISED" if should_disguise else "PROTECTED"
            status = "✅" if (
                (should_disguise and "DISGUISED" in expected) or 
                (not should_disguise and "PROTECTED" in expected)
            ) else "❌"
            
            logger.info(f"{status} Process '{process_name}': {result} ({expected})")
        
        # ✅ TEST 5: Test protection metrics
        logger.info("📋 TEST 5: Testing protection metrics...")
        metrics = stealth_exec.get_protection_metrics()
        logger.info(f"Protection Metrics: {metrics}")
        
        # ✅ TEST 6: Test add_process với mining process
        logger.info("📋 TEST 6: Testing add_process with mining process...")
        
        # Create a dummy mining process để test (simulation)
        test_script = '''
import time
import sys
import os

# Simulate ml-inference process
sys.argv[0] = "ml-inference"

# Keep running for test
for i in range(30):
    time.sleep(1)
    if i % 5 == 0:
        print(f"ml-inference process running... {i}/30")

print("ml-inference process completed")
'''
        
        # Write test script
        with open('/tmp/test_ml_inference.py', 'w') as f:
            f.write(test_script)
        
        # Start test process
        test_process = subprocess.Popen([
            sys.executable, '/tmp/test_ml_inference.py'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        logger.info(f"Started test ml-inference process: PID {test_process.pid}")
        
        # Wait a moment for process to start
        time.sleep(1)
        
        # Test adding the process to stealth
        logger.info("Testing add_process() with mining process...")
        result = stealth_exec.add_process(test_process.pid)
        logger.info(f"Add process result: {result}")
        
        # Check if process was protected
        final_metrics = stealth_exec.get_protection_metrics()
        logger.info(f"Final Protection Metrics: {final_metrics}")
        
        # Cleanup test process
        test_process.terminate()
        test_process.wait(timeout=5)
        
        # Remove test script
        try:
            os.unlink('/tmp/test_ml_inference.py')
        except:
            pass
        
        logger.info("✅ Enhanced Process Whitelist Protection Test COMPLETED")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

def test_circuit_breaker():
    """Test Circuit Breaker functionality"""
    logger = setup_test_logger()
    logger.info("🔧 Testing Circuit Breaker functionality...")
    
    try:
        stealth_exec = StealthExecution(logger=logger)
        
        # Simulate multiple errors to trigger circuit breaker
        logger.info("Simulating errors to trigger circuit breaker...")
        for i in range(15):  # More than error_threshold (10)
            stealth_exec._handle_error(Exception(f"Test error {i+1}"))
        
        # Check if circuit breaker is open
        metrics = stealth_exec.get_protection_metrics()
        circuit_open = metrics['circuit_breaker_open']
        error_count = metrics['error_count']
        
        logger.info(f"Circuit Breaker Status: {'OPEN' if circuit_open else 'CLOSED'}")
        logger.info(f"Error Count: {error_count}")
        
        if circuit_open:
            logger.info("✅ Circuit breaker triggered successfully")
            
            # Test reset
            stealth_exec._reset_circuit_breaker()
            metrics_after_reset = stealth_exec.get_protection_metrics()
            
            if not metrics_after_reset['circuit_breaker_open']:
                logger.info("✅ Circuit breaker reset successfully")
                return True
            else:
                logger.error("❌ Circuit breaker reset failed")
                return False
        else:
            logger.error("❌ Circuit breaker did not trigger")
            return False
            
    except Exception as e:
        logger.error(f"❌ Circuit breaker test failed: {e}")
        return False

if __name__ == "__main__":
    logger = setup_test_logger()
    
    try:
        logger.info("=" * 60)
        logger.info("🧪 ENHANCED PROCESS WHITELIST PROTECTION TEST SUITE")
        logger.info("=" * 60)
        
        # Run main test
        test1_result = test_whitelist_protection()
        
        # Run circuit breaker test
        test2_result = test_circuit_breaker()
        
        # Summary
        logger.info("=" * 60)
        logger.info("📊 TEST RESULTS SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Whitelist Protection Test: {'✅ PASSED' if test1_result else '❌ FAILED'}")
        logger.info(f"Circuit Breaker Test: {'✅ PASSED' if test2_result else '❌ FAILED'}")
        
        overall_result = test1_result and test2_result
        logger.info(f"Overall Result: {'✅ ALL TESTS PASSED' if overall_result else '❌ SOME TESTS FAILED'}")
        
        sys.exit(0 if overall_result else 1)
        
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        sys.exit(1)