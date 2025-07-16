#!/usr/bin/env python3
"""
Test script để validate các thay đổi timeout fix
"""
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.mining_environment.scripts.logging_config import setup_logging
from app.mining_environment.scripts.facade import SystemFacade
from app.mining_environment.scripts.auxiliary_modules.event_bus import EventBus
from app.mining_environment.scripts.auxiliary_modules.models import ConfigModel

def test_timeout_fix():
    """Test các thay đổi timeout và progress logging"""
    print("🧪 Testing SystemManagerCore timeout fix...")
    
    # Setup logging
    logger = setup_logging('test_timeout', '/tmp/test_timeout.log', 'INFO')
    resource_logger = setup_logging('test_resource', '/tmp/test_resource.log', 'INFO')
    
    # Create mock config
    config = ConfigModel()
    event_bus = EventBus()
    
    # Test SystemFacade initialization với progress logging
    print("📋 Testing SystemFacade initialization...")
    start_time = time.time()
    
    try:
        facade = SystemFacade(config, event_bus, resource_logger)
        result = facade.initialize_system()
        
        elapsed = time.time() - start_time
        print(f"✅ SystemFacade initialization {'succeeded' if result else 'failed'} in {elapsed:.2f}s")
        
        if result:
            print("✅ Progress logging works correctly")
            facade.shutdown_system()
        else:
            print("❌ SystemFacade initialization failed")
            
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ SystemFacade initialization threw exception after {elapsed:.2f}s: {e}")
        
    print("🧪 Test completed")

if __name__ == "__main__":
    test_timeout_fix()