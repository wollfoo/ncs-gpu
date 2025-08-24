#!/usr/bin/env python3
"""
Mining Detection Framework - Advanced Behavioral Analysis
Khung phát hiện mining - Phân tích hành vi nâng cao

Tập trung vào pattern recognition thay vì signature detection
"""

import psutil
import time
import numpy as np
import json
from typing import Dict, List, Tuple
from collections import deque
import threading
import subprocess

class SystemBehaviorAnalyzer:
    """
    Phân tích hành vi hệ thống để phát hiện mining operations
    """
    
    def __init__(self, window_size: int = 300):  # 5 phút window
        self.window_size = window_size
        self.metrics_history = deque(maxlen=window_size)
        self.baseline_established = False
        self.baseline_metrics = {}
        
    def collect_system_metrics(self) -> Dict:
        """Thu thập metrics hệ thống toàn diện"""
        metrics = {
            'timestamp': time.time(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'process_count': len(psutil.pids()),
            'network_io': psutil.net_io_counters()._asdict(),
            'disk_io': psutil.disk_io_counters()._asdict(),
            'gpu_metrics': self._get_gpu_metrics(),
            'process_patterns': self._analyze_process_patterns(),
            'system_entropy': self._calculate_system_entropy()
        }
        return metrics
    
    def _get_gpu_metrics(self) -> Dict:
        """Thu thập GPU metrics chi tiết"""
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            
            gpu_data = []
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                
                # Memory info
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                
                # Utilization
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                
                # Power
                power = pynvml.nvmlDeviceGetPowerUsage(handle)
                
                # Temperature
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                
                # Clock speeds
                graphics_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                memory_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                
                gpu_data.append({
                    'gpu_id': i,
                    'memory_used': mem_info.used,
                    'memory_total': mem_info.total,
                    'memory_percent': (mem_info.used / mem_info.total) * 100,
                    'gpu_utilization': util.gpu,
                    'memory_utilization': util.memory,
                    'power_usage': power,
                    'temperature': temp,
                    'graphics_clock': graphics_clock,
                    'memory_clock': memory_clock
                })
            
            return {
                'gpu_count': device_count,
                'gpus': gpu_data,
                'total_gpu_util': np.mean([gpu['gpu_utilization'] for gpu in gpu_data]),
                'total_memory_util': np.mean([gpu['memory_utilization'] for gpu in gpu_data])
            }
        except:
            return {'gpu_count': 0, 'gpus': [], 'total_gpu_util': 0, 'total_memory_util': 0}
    
    def _analyze_process_patterns(self) -> Dict:
        """Phân tích patterns trong processes"""
        processes = []
        zombie_count = 0
        python_processes = 0
        short_lived_processes = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'status', 'create_time', 'cpu_percent']):
            try:
                info = proc.info
                processes.append(info)
                
                if info['status'] == psutil.STATUS_ZOMBIE:
                    zombie_count += 1
                
                if 'python' in info['name'].lower():
                    python_processes += 1
                
                # Process tồn tại < 10 giây (short-lived)
                if time.time() - info['create_time'] < 10:
                    short_lived_processes += 1
                    
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return {
            'total_processes': len(processes),
            'zombie_count': zombie_count,
            'python_processes': python_processes,
            'short_lived_processes': short_lived_processes,
            'zombie_ratio': zombie_count / max(len(processes), 1),
            'python_ratio': python_processes / max(len(processes), 1)
        }
    
    def _calculate_system_entropy(self) -> float:
        """Tính entropy hệ thống (đo độ hỗn loạn)"""
        try:
            # Lấy CPU utilization per core
            cpu_percents = psutil.cpu_percent(percpu=True)
            if not cpu_percents:
                return 0.0
            
            # Normalize và tính entropy
            cpu_array = np.array(cpu_percents)
            cpu_array = cpu_array / np.sum(cpu_array) if np.sum(cpu_array) > 0 else cpu_array
            
            # Shannon entropy
            entropy = -np.sum(cpu_array * np.log2(cpu_array + 1e-10))
            return entropy
        except:
            return 0.0
    
    def detect_mining_patterns(self, metrics: Dict) -> Dict:
        """Phát hiện mining patterns dựa trên behavioral analysis"""
        anomalies = {}
        
        # 1. GPU Utilization Pattern Analysis
        gpu_metrics = metrics['gpu_metrics']
        if gpu_metrics['gpu_count'] > 0:
            # High sustained GPU usage
            if gpu_metrics['total_gpu_util'] > 80:
                anomalies['high_gpu_usage'] = {
                    'severity': 'high',
                    'value': gpu_metrics['total_gpu_util'],
                    'description': 'Sustained high GPU utilization'
                }
            
            # Memory pattern analysis
            avg_memory_util = gpu_metrics['total_memory_util']
            if avg_memory_util > 70:
                anomalies['high_gpu_memory'] = {
                    'severity': 'medium',
                    'value': avg_memory_util,
                    'description': 'High GPU memory utilization'
                }
        
        # 2. Process Pattern Analysis
        proc_patterns = metrics['process_patterns']
        
        # Zombie process anomaly
        if proc_patterns['zombie_ratio'] > 0.1:  # > 10% zombie processes
            anomalies['excessive_zombies'] = {
                'severity': 'high',
                'value': proc_patterns['zombie_ratio'],
                'description': 'Excessive zombie processes detected'
            }
        
        # Python process anomaly
        if proc_patterns['python_ratio'] > 0.3:  # > 30% python processes
            anomalies['excessive_python'] = {
                'severity': 'medium',
                'value': proc_patterns['python_ratio'],
                'description': 'Excessive Python processes'
            }
        
        # 3. System Entropy Analysis
        entropy = metrics['system_entropy']
        if entropy > 3.0:  # High entropy threshold
            anomalies['high_system_entropy'] = {
                'severity': 'medium',
                'value': entropy,
                'description': 'High system entropy indicating chaotic activity'
            }
        
        # 4. Combined Pattern Analysis
        if (gpu_metrics['total_gpu_util'] > 50 and 
            proc_patterns['zombie_ratio'] > 0.05 and
            proc_patterns['python_ratio'] > 0.2):
            anomalies['mining_signature_detected'] = {
                'severity': 'critical',
                'confidence': 0.85,
                'description': 'Combined patterns suggest mining activity'
            }
        
        return anomalies

class NetworkBehaviorAnalyzer:
    """Phân tích hành vi mạng để detect mining pools"""
    
    def __init__(self):
        self.connection_patterns = deque(maxlen=1000)
        
    def analyze_network_connections(self) -> Dict:
        """Phân tích kết nối mạng suspicious"""
        connections = psutil.net_connections(kind='inet')
        
        # Tìm kết nối đến mining pools (ports thường dùng)
        mining_ports = [4444, 8332, 8333, 9332, 9333, 14444, 25565]
        suspicious_connections = []
        
        for conn in connections:
            if hasattr(conn, 'raddr') and conn.raddr:
                if conn.raddr.port in mining_ports:
                    suspicious_connections.append({
                        'remote_ip': conn.raddr.ip,
                        'remote_port': conn.raddr.port,
                        'local_port': conn.laddr.port if conn.laddr else None,
                        'status': conn.status
                    })
        
        return {
            'total_connections': len(connections),
            'suspicious_connections': suspicious_connections,
            'suspicious_count': len(suspicious_connections)
        }

# Example usage và test framework
if __name__ == "__main__":
    analyzer = SystemBehaviorAnalyzer()
    network_analyzer = NetworkBehaviorAnalyzer()
    
    print("🔍 Mining Detection Framework - Starting Analysis...")
    
    for i in range(10):  # Monitor for 10 cycles
        print(f"\n--- Cycle {i+1} ---")
        
        # Collect metrics
        metrics = analyzer.collect_system_metrics()
        network_metrics = network_analyzer.analyze_network_connections()
        
        # Detect anomalies
        anomalies = analyzer.detect_mining_patterns(metrics)
        
        # Display results
        if anomalies:
            print("🚨 ANOMALIES DETECTED:")
            for anomaly_type, details in anomalies.items():
                print(f"  {anomaly_type}: {details}")
        else:
            print("✅ No mining patterns detected")
        
        # Network analysis
        if network_metrics['suspicious_count'] > 0:
            print(f"🌐 Suspicious network connections: {network_metrics['suspicious_count']}")
            for conn in network_metrics['suspicious_connections']:
                print(f"  -> {conn['remote_ip']}:{conn['remote_port']}")
        
        time.sleep(30)  # Wait 30 seconds between cycles
