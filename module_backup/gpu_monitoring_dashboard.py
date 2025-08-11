"""
GPU Monitoring Dashboard
Web-based dashboard để theo dõi GPUResourceManager và system health
"""

import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Flask, render_template_string, jsonify, request
from concurrent.futures import ThreadPoolExecutor

# ✅ MIGRATED LOGGING: Use new module-specific logging system  
from .module_loggers import get_dashboard_logger
from .gpu_resource_monitor import get_gpu_monitor

class GPUMonitoringDashboard:
    """
    **GPU Monitoring Dashboard** (bảng điều khiển giám sát GPU)
    
    Chức năng:
    - **Web interface** (giao diện web) để hiển thị GPU metrics
    - **Real-time updates** (cập nhật thời gian thực) qua WebSocket/AJAX
    - **Historical data** (dữ liệu lịch sử) visualization
    - **Alert system** (hệ thống cảnh báo) cho critical issues
    """
    
    def __init__(self, host: str = "127.0.0.1", port: int = 8888):
        """
        Khởi tạo GPU Monitoring Dashboard
        
        Args:
            host: Dashboard host address
            port: Dashboard port number
        """
        self.logger = get_dashboard_logger()
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        self.gpu_monitor = get_gpu_monitor()
        
        # ✅ DASHBOARD STATE: Trạng thái dashboard
        self.is_running = False
        self.dashboard_thread: Optional[threading.Thread] = None
        self.last_update = time.time()
        
        # ✅ SETUP ROUTES: Thiết lập routes
        self._setup_routes()
        
        self.logger.info(f"🌐 [DASHBOARD] GPU Monitoring Dashboard initialized on {host}:{port}")
    
    def _setup_routes(self) -> None:
        """**Setup Flask Routes** (thiết lập các routes Flask)"""
        
        @self.app.route('/')
        def dashboard_home():
            """**Main Dashboard Page** (trang dashboard chính)"""
            return render_template_string(self._get_dashboard_template())
        
        @self.app.route('/api/gpu/status')
        def api_gpu_status():
            """**GPU Status API Endpoint** (endpoint API trạng thái GPU)"""
            try:
                dashboard_data = self.gpu_monitor.get_dashboard_data()
                return jsonify({
                    'success': True,
                    'data': dashboard_data,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"❌ [DASHBOARD API] Error getting GPU status: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/api/gpu/health')
        def api_gpu_health():
            """**GPU Health API Endpoint** (endpoint API sức khỏe GPU)"""
            try:
                health_summary = self.gpu_monitor.get_health_summary()
                return jsonify({
                    'success': True,
                    'health': health_summary,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"❌ [DASHBOARD API] Error getting GPU health: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        @self.app.route('/api/gpu/metrics')
        def api_gpu_metrics():
            """**GPU Metrics API Endpoint** (endpoint API chỉ số GPU)"""
            try:
                dashboard_data = self.gpu_monitor.get_dashboard_data()
                
                # ✅ EXTRACT METRICS: Trích xuất metrics để charting
                metrics = {
                    'gpu_utilization': dashboard_data.get('hardware_metrics', {}).get('utilization_percent', 0),
                    'memory_usage': dashboard_data.get('hardware_metrics', {}).get('memory_usage_mb', 0),
                    'temperature': dashboard_data.get('hardware_metrics', {}).get('temperature_celsius', 0),
                    'power_usage': dashboard_data.get('hardware_metrics', {}).get('power_usage_watts', 0),
                    'processes_cloaked': dashboard_data.get('performance_metrics', {}).get('processes_cloaked', 0),
                    'success_rate': dashboard_data.get('performance_metrics', {}).get('cloaking_success_rate', 0),
                    'response_time': dashboard_data.get('performance_metrics', {}).get('average_response_time_ms', 0)
                }

                return jsonify({
                    'success': True,
                    'metrics': metrics,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"❌ [DASHBOARD API] Error getting GPU metrics: {e}")
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
