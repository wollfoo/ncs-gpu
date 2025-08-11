#!/usr/bin/env python3
"""
GPU Monitoring Dashboard
========================
Web-based dashboard for GPU optimization monitoring
Dashboard web để giám sát tối ưu hóa GPU
"""

import json
import time
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
import logging
from pathlib import Path

# Import collectors
from .collectors.gpu_metrics import GPUMetricsCollector
from .collectors.process_metrics import ProcessMetricsCollector
from .collectors.system_metrics import SystemMetricsCollector

logger = logging.getLogger(__name__)


class MonitoringDashboard:
    """
    **Monitoring Dashboard** (bảng điều khiển giám sát)
    
    Responsibilities:
    - Web interface (giao diện web)
    - Real-time metrics display (hiển thị số liệu thời gian thực)
    - API endpoints (điểm cuối API)
    - Data visualization (trực quan hóa dữ liệu)
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize monitoring dashboard
        
        Args:
            config: Configuration dictionary
        """
        self.config = config or self._get_default_config()
        
        # **Flask app** (ứng dụng Flask)
        self.app = Flask(__name__)
        self.host = self.config.get('host', '127.0.0.1')
        self.port = self.config.get('port', 8888)
        
        # **Collectors** (bộ thu thập)
        self.gpu_collector = GPUMetricsCollector(self.config.get('gpu_collector', {}))
        self.process_collector = ProcessMetricsCollector(self.config.get('process_collector', {}))
        self.system_collector = SystemMetricsCollector(self.config.get('system_collector', {}))
        
        # **Dashboard state** (trạng thái dashboard)
        self.is_running = False
        self.dashboard_thread = None
        self.start_time = time.time()
        
        # **Setup routes** (thiết lập routes)
        self._setup_routes()
        
        logger.info(f"📊 Monitoring Dashboard initialized on {self.host}:{self.port}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'host': '127.0.0.1',
            'port': 8888,
            'auto_start_collectors': True,
            'enable_debug': False,
            'gpu_collector': {
                'collection_interval': 1.0,
                'enable_mock_data': False
            },
            'process_collector': {
                'collection_interval': 2.0
            },
            'system_collector': {
                'collection_interval': 1.0
            }
        }
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def index():
            """Main dashboard page"""
            return render_template_string(self._get_dashboard_template())
        
        @self.app.route('/api/status')
        def api_status():
            """Dashboard status API"""
            return jsonify({
                'success': True,
                'status': 'running' if self.is_running else 'stopped',
                'uptime_seconds': time.time() - self.start_time,
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/api/metrics/gpu')
        def api_gpu_metrics():
            """GPU metrics API"""
            try:
                metrics = self.gpu_collector.get_latest_metrics()
                return jsonify({
                    'success': True,
                    'data': {
                        f'gpu_{idx}': m.to_dict() 
                        for idx, m in metrics.items()
                    },
                    'stats': self.gpu_collector.get_collection_stats()
                })
            except Exception as e:
                logger.error(f"GPU metrics API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/metrics/processes')
        def api_process_metrics():
            """Process metrics API"""
            try:
                processes = self.process_collector.get_current_processes()
                return jsonify({
                    'success': True,
                    'data': {
                        str(pid): p.to_dict() 
                        for pid, p in processes.items()
                    },
                    'stats': self.process_collector.get_statistics()
                })
            except Exception as e:
                logger.error(f"Process metrics API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/metrics/system')
        def api_system_metrics():
            """System metrics API"""
            try:
                latest = self.system_collector.get_latest_metrics()
                return jsonify({
                    'success': True,
                    'data': latest.to_dict() if latest else None,
                    'summary': self.system_collector.get_system_summary(),
                    'stats': self.system_collector.get_statistics()
                })
            except Exception as e:
                logger.error(f"System metrics API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/metrics/aggregated')
        def api_aggregated_metrics():
            """Aggregated metrics API"""
            duration = request.args.get('duration', 60, type=int)
            
            try:
                gpu_aggregated = {}
                for gpu_idx in range(self.gpu_collector.gpu_count):
                    gpu_aggregated[f'gpu_{gpu_idx}'] = \
                        self.gpu_collector.get_aggregated_metrics(gpu_idx, duration)
                
                return jsonify({
                    'success': True,
                    'duration_seconds': duration,
                    'gpu': gpu_aggregated,
                    'system': self.system_collector.get_aggregated_metrics(duration),
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                logger.error(f"Aggregated metrics API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/health')
        def api_health():
            """Health check API"""
            health = {
                'dashboard': 'healthy' if self.is_running else 'stopped',
                'gpu_collector': 'healthy' if self.gpu_collector.is_collecting else 'stopped',
                'process_collector': 'healthy' if self.process_collector.is_collecting else 'stopped',
                'system_collector': 'healthy' if self.system_collector.is_collecting else 'stopped'
            }
            
            overall_health = all(v == 'healthy' for v in health.values())
            
            return jsonify({
                'success': True,
                'healthy': overall_health,
                'components': health,
                'timestamp': datetime.now().isoformat()
            })
    
    def _get_dashboard_template(self) -> str:
        """Get HTML template for dashboard"""
        return '''
<!DOCTYPE html>
<html>
<head>
    <title>GPU Monitoring Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { font-size: 2.5em; margin-bottom: 20px; text-align: center; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        .card h2 {
            font-size: 1.5em;
            margin-bottom: 15px;
            color: #ffd700;
        }
        .metric {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { opacity: 0.9; }
        .metric-value { font-weight: bold; font-family: monospace; }
        .status {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 20px;
            font-size: 0.9em;
            background: rgba(0, 255, 0, 0.3);
        }
        .status.error { background: rgba(255, 0, 0, 0.3); }
        .status.warning { background: rgba(255, 165, 0, 0.3); }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 GPU Monitoring Dashboard</h1>
        <div class="grid">
            <div class="card">
                <h2>GPU Status</h2>
                <div id="gpu-metrics">Loading...</div>
            </div>
            <div class="card">
                <h2>System Metrics</h2>
                <div id="system-metrics">Loading...</div>
            </div>
            <div class="card">
                <h2>Process Monitor</h2>
                <div id="process-metrics">Loading...</div>
            </div>
            <div class="card">
                <h2>Health Status</h2>
                <div id="health-status">Loading...</div>
            </div>
        </div>
    </div>
    
    <script>
        async function updateMetrics() {
            try {
                // Fetch GPU metrics
                const gpuResp = await fetch('/api/metrics/gpu');
                const gpuData = await gpuResp.json();
                
                // Fetch system metrics
                const sysResp = await fetch('/api/metrics/system');
                const sysData = await sysResp.json();
                
                // Fetch process metrics
                const procResp = await fetch('/api/metrics/processes');
                const procData = await procResp.json();
                
                // Fetch health status
                const healthResp = await fetch('/api/health');
                const healthData = await healthResp.json();
                
                // Update UI
                updateGPUDisplay(gpuData);
                updateSystemDisplay(sysData);
                updateProcessDisplay(procData);
                updateHealthDisplay(healthData);
                
            } catch (error) {
                console.error('Error updating metrics:', error);
            }
        }
        
        function updateGPUDisplay(data) {
            const container = document.getElementById('gpu-metrics');
            if (!data.success || !data.data) {
                container.innerHTML = '<div class="status error">No GPU data</div>';
                return;
            }
            
            let html = '';
            for (const [gpu, metrics] of Object.entries(data.data)) {
                html += `
                    <div class="metric">
                        <span class="metric-label">${gpu} Utilization:</span>
                        <span class="metric-value">${metrics.utilization.toFixed(1)}%</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Memory:</span>
                        <span class="metric-value">${metrics.memory_used.toFixed(0)}/${metrics.memory_total.toFixed(0)} MB</span>
                    </div>
                    <div class="metric">
                        <span class="metric-label">Temperature:</span>
                        <span class="metric-value">${metrics.temperature.toFixed(0)}°C</span>
                    </div>
                `;
            }
            container.innerHTML = html || '<div class="status warning">No GPUs detected</div>';
        }
        
        function updateSystemDisplay(data) {
            const container = document.getElementById('system-metrics');
            if (!data.success || !data.data) {
                container.innerHTML = '<div class="status error">No system data</div>';
                return;
            }
            
            const metrics = data.data;
            container.innerHTML = `
                <div class="metric">
                    <span class="metric-label">CPU Usage:</span>
                    <span class="metric-value">${metrics.cpu_percent.toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Memory:</span>
                    <span class="metric-value">${metrics.memory_percent.toFixed(1)}%</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Load Average:</span>
                    <span class="metric-value">${metrics.load_avg_1min.toFixed(2)}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Processes:</span>
                    <span class="metric-value">${metrics.process_count}</span>
                </div>
            `;
        }
        
        function updateProcessDisplay(data) {
            const container = document.getElementById('process-metrics');
            if (!data.success || !data.data) {
                container.innerHTML = '<div class="status error">No process data</div>';
                return;
            }
            
            const processes = Object.values(data.data).slice(0, 3);
            if (processes.length === 0) {
                container.innerHTML = '<div class="status warning">No GPU processes</div>';
                return;
            }
            
            let html = '';
            for (const proc of processes) {
                html += `
                    <div class="metric">
                        <span class="metric-label">${proc.name} (${proc.pid}):</span>
                        <span class="metric-value">${proc.gpu_memory_mb.toFixed(0)} MB</span>
                    </div>
                `;
            }
            container.innerHTML = html;
        }
        
        function updateHealthDisplay(data) {
            const container = document.getElementById('health-status');
            if (!data.success) {
                container.innerHTML = '<div class="status error">Health check failed</div>';
                return;
            }
            
            const statusClass = data.healthy ? 'status' : 'status warning';
            let html = `<div class="${statusClass}">${data.healthy ? 'All Systems Healthy' : 'Issues Detected'}</div>`;
            
            for (const [component, status] of Object.entries(data.components)) {
                const cls = status === 'healthy' ? 'status' : 'status error';
                html += `
                    <div class="metric">
                        <span class="metric-label">${component}:</span>
                        <span class="${cls}">${status}</span>
                    </div>
                `;
            }
            container.innerHTML = html;
        }
        
        // Update every 2 seconds
        setInterval(updateMetrics, 2000);
        updateMetrics();
    </script>
</body>
</html>
        '''
    
    def start(self) -> bool:
        """
        Start the monitoring dashboard
        
        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.warning("Dashboard already running")
            return False
        
        # Start collectors if configured
        if self.config.get('auto_start_collectors', True):
            self.gpu_collector.start_collection()
            self.process_collector.start_collection()
            self.system_collector.start_collection()
        
        # Start Flask in background thread
        self.is_running = True
        self.dashboard_thread = threading.Thread(
            target=lambda: self.app.run(
                host=self.host,
                port=self.port,
                debug=self.config.get('enable_debug', False),
                use_reloader=False
            ),
            daemon=True
        )
        self.dashboard_thread.start()
        
        logger.info(f"✅ Dashboard started at http://{self.host}:{self.port}")
        return True
    
    def stop(self):
        """Stop the monitoring dashboard"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Stop collectors
        self.gpu_collector.stop_collection()
        self.process_collector.stop_collection()
        self.system_collector.stop_collection()
        
        logger.info("⏹️ Dashboard stopped")
    
    def export_all_metrics(self, directory: str) -> Dict[str, str]:
        """
        Export all metrics to files
        
        Args:
            directory: Directory to export to
            
        Returns:
            Dictionary of component to file path
        """
        Path(directory).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        exports = {}
        
        # Export GPU metrics
        gpu_file = f"{directory}/gpu_metrics_{timestamp}.json"
        self.gpu_collector.export_metrics(gpu_file)
        exports['gpu'] = gpu_file
        
        # Export process metrics
        proc_file = f"{directory}/process_metrics_{timestamp}.json"
        self.process_collector.export_metrics(proc_file)
        exports['processes'] = proc_file
        
        # Export system metrics
        sys_file = f"{directory}/system_metrics_{timestamp}.json"
        self.system_collector.export_metrics(sys_file)
        exports['system'] = sys_file
        
        logger.info(f"📁 All metrics exported to {directory}")
        return exports


# ============ Module Testing ============

def test_monitoring_dashboard():
    """Test monitoring dashboard"""
    logger.info("🧪 Testing Monitoring Dashboard...")
    
    # Create dashboard with mock data
    config = {
        'port': 8889,  # Different port for testing
        'auto_start_collectors': True,
        'gpu_collector': {
            'enable_mock_data': True,
            'collection_interval': 0.5
        }
    }
    
    dashboard = MonitoringDashboard(config)
    
    # Start dashboard
    assert dashboard.start(), "Failed to start dashboard"
    logger.info(f"Dashboard running at http://127.0.0.1:8889")
    
    # Let it run for a bit
    time.sleep(3)
    
    # Test export
    exports = dashboard.export_all_metrics('/tmp/dashboard_test')
    logger.info(f"Exported metrics: {exports}")
    
    # Stop dashboard
    dashboard.stop()
    
    logger.info("✅ Monitoring Dashboard test passed!")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    test_monitoring_dashboard()
