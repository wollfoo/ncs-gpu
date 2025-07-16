"""
System Facade - Unified system management interface
Provides simplified interface for system operations and resource management
"""

import logging
import time
from typing import Dict, Any, Optional
from .auxiliary_modules.event_bus import EventBus
from .auxiliary_modules.models import ConfigModel


class SystemFacade:
    """
    Unified system management facade
    Provides simplified interface for system operations and resource management
    """
    
    def __init__(self, config: ConfigModel, event_bus: EventBus, resource_logger: logging.Logger):
        """
        Initialize SystemFacade with configuration and event bus
        
        Args:
            config: System configuration model
            event_bus: Event bus for system-wide communication
            resource_logger: Logger for resource management
        """
        self.config = config
        self.event_bus = event_bus
        self.resource_logger = resource_logger
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # System state tracking
        self.system_state = {
            'initialized': False,
            'status': 'starting',
            'resources': {},
            'performance': {}
        }
        
        self.logger.info("SystemFacade initialized")
    
    def initialize_system(self) -> bool:
        """
        Initialize system components
        
        Returns:
            bool: True if initialization successful
        """
        try:
            self.logger.info("Initializing system components...")
            
            # Initialize system state
            self.system_state['initialized'] = True
            self.system_state['status'] = 'ready'
            
            # Publish initialization event
            self.event_bus.publish('system.initialized', {
                'timestamp': time.time(),
                'status': 'ready'
            })
            
            self.logger.info("System initialization completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"System initialization failed: {e}")
            self.system_state['status'] = 'error'
            return False
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        Get current system status
        
        Returns:
            Dict containing system status information
        """
        return {
            'state': self.system_state,
            'config': self.config.to_dict() if hasattr(self.config, 'to_dict') else str(self.config),
            'timestamp': time.time()
        }
    
    def shutdown_system(self) -> bool:
        """
        Shutdown system components gracefully
        
        Returns:
            bool: True if shutdown successful
        """
        try:
            self.logger.info("Shutting down system components...")
            
            # Update system state
            self.system_state['status'] = 'shutting_down'
            
            # Publish shutdown event
            self.event_bus.publish('system.shutdown', {
                'timestamp': time.time(),
                'status': 'shutting_down'
            })
            
            # Clean up resources
            self.system_state['initialized'] = False
            self.system_state['status'] = 'stopped'
            
            self.logger.info("System shutdown completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"System shutdown failed: {e}")
            return False
    
    def get_resource_status(self) -> Dict[str, Any]:
        """
        Get current resource utilization status
        
        Returns:
            Dict containing resource status information
        """
        return {
            'resources': self.system_state.get('resources', {}),
            'performance': self.system_state.get('performance', {}),
            'timestamp': time.time()
        }
    
    def update_resource_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Update resource metrics
        
        Args:
            metrics: Resource metrics to update
        """
        if 'resources' not in self.system_state:
            self.system_state['resources'] = {}
        
        self.system_state['resources'].update(metrics)
        
        # Log resource update
        self.resource_logger.info(f"Resource metrics updated: {metrics}")
        
        # Publish resource update event
        self.event_bus.publish('system.resource_update', {
            'metrics': metrics,
            'timestamp': time.time()
        })
    
    def start(self) -> bool:
        """
        Khởi động SystemFacade và các components
        
        Returns:
            bool: True nếu khởi động thành công
        """
        try:
            # Log to both console and file
            start_msg = "🚀 Starting SystemFacade..."
            self.logger.info(start_msg)
            print(f"[INFO] {start_msg}")
            
            # Initialize system components
            if not self.initialize_system():
                error_msg = "❌ Failed to initialize system components"
                self.logger.error(error_msg)
                print(f"[ERROR] {error_msg}")
                return False
            
            # Update system state
            self.system_state['status'] = 'running'
            
            # Publish start event
            self.event_bus.publish('system.started', {
                'timestamp': time.time(),
                'status': 'running'
            })
            
            success_msg = "✅ SystemFacade started successfully"
            self.logger.info(success_msg)
            print(f"[INFO] {success_msg}")
            return True
            
        except Exception as e:
            error_msg = f"❌ SystemFacade start failed: {e}"
            self.logger.error(error_msg)
            print(f"[ERROR] {error_msg}")
            self.system_state['status'] = 'error'
            return False

    def stop(self) -> bool:
        """
        Dừng SystemFacade
        
        Returns:
            bool: True nếu dừng thành công
        """
        try:
            stop_msg = "🛑 Stopping SystemFacade..."
            self.logger.info(stop_msg)
            print(f"[INFO] {stop_msg}")
            
            result = self.shutdown_system()
            
            if result:
                success_msg = "✅ SystemFacade stopped successfully"
                self.logger.info(success_msg)
                print(f"[INFO] {success_msg}")
            else:
                error_msg = "❌ SystemFacade stop failed"
                self.logger.error(error_msg)
                print(f"[ERROR] {error_msg}")
            
            return result
            
        except Exception as e:
            error_msg = f"❌ SystemFacade stop error: {e}"
            self.logger.error(error_msg)
            print(f"[ERROR] {error_msg}")
            return False