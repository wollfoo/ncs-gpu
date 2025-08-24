#!/usr/bin/env python3
"""
Simple Fingerprinting Demo - Lightweight version
Demo đơn giản cho Mining Detection và Anti-Fingerprinting
"""

import psutil
import time
import json
import random
import os
from pathlib import Path

class SimpleDetector:
    """Simple mining detector"""
    
    def collect_system_metrics(self):
        """Thu thập metrics cơ bản"""
        try:
            # System metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Process analysis
            processes = list(psutil.process_iter(['pid', 'name', 'status']))
            total_processes = len(processes)
            
            zombie_count = 0
            python_processes = 0
            
            for proc in processes:
                try:
                    if proc.info['status'] == psutil.STATUS_ZOMBIE:
                        zombie_count += 1
                    if 'python' in proc.info['name'].lower():
                        python_processes += 1
                except:
                    continue
            
            # Network connections
            connections = psutil.net_connections(kind='inet')
            
            metrics = {
                'timestamp': time.time(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'total_processes': total_processes,
                'zombie_count': zombie_count,
                'zombie_ratio': zombie_count / max(total_processes, 1),
                'python_processes': python_processes,
                'python_ratio': python_processes / max(total_processes, 1),
                'network_connections': len(connections)
            }
            
            return metrics
        except Exception as e:
            print(f"❌ Error collecting metrics: {e}")
            return {}
    
    def detect_mining_patterns(self, metrics):
        """Detect basic mining patterns"""
        anomalies = {}
        
        # High CPU usage
        if metrics.get('cpu_percent', 0) > 80:
            anomalies['high_cpu'] = {
                'value': metrics['cpu_percent'],
                'severity': 'high',
                'description': 'High CPU utilization detected'
            }
        
        # Excessive zombie processes
        zombie_ratio = metrics.get('zombie_ratio', 0)
        if zombie_ratio > 0.1:  # >10% zombie processes
            anomalies['excessive_zombies'] = {
                'value': zombie_ratio,
                'severity': 'high',
                'description': f'Excessive zombie processes: {zombie_ratio:.1%}'
            }
        
        # High Python process ratio
        python_ratio = metrics.get('python_ratio', 0)
        if python_ratio > 0.3:  # >30% python processes
            anomalies['excessive_python'] = {
                'value': python_ratio,
                'severity': 'medium',
                'description': f'High Python process ratio: {python_ratio:.1%}'
            }
        
        # Combined pattern (likely mining)
        cpu_high = metrics.get('cpu_percent', 0) > 50
        zombies_high = zombie_ratio > 0.05
        python_high = python_ratio > 0.2
        
        if cpu_high and zombies_high and python_high:
            anomalies['mining_signature'] = {
                'confidence': 0.85,
                'severity': 'critical',
                'description': 'Combined patterns suggest mining activity'
            }
        
        return anomalies

class SimpleAntiFingerprinting:
    """Simple anti-fingerprinting techniques"""
    
    def __init__(self):
        self.active_techniques = []
    
    def enable_process_mimicry(self):
        """Simulate process mimicry"""
        print("  ✅ Process Mimicry: Would disguise process names")
        print("      - Rename mining processes to system-like names")
        print("      - Create decoy processes")
        self.active_techniques.append("Process Mimicry")
    
    def enable_resource_masking(self):
        """Simulate resource masking"""
        print("  ✅ Resource Masking: Would throttle and mask usage")
        print("      - Adaptive throttling based on detection risk")
        print("      - Inject artificial pauses")
        self.active_techniques.append("Resource Masking")
    
    def enable_log_obfuscation(self):
        """Simulate log obfuscation"""
        print("  ✅ Log Obfuscation: Would obfuscate mining logs")
        print("      - Replace mining terms with neutral ones")
        print("      - Create decoy log entries")
        self.active_techniques.append("Log Obfuscation")
    
    def enable_network_stealth(self):
        """Simulate network stealthing"""
        print("  ✅ Network Stealth: Would obfuscate network traffic")
        print("      - Domain fronting to hide destinations")
        print("      - Traffic mixing with legitimate requests")
        self.active_techniques.append("Network Stealth")
    
    def enable_all_techniques(self):
        """Enable all anti-fingerprinting techniques"""
        print("\n🥷 Enabling Anti-Fingerprinting Techniques:")
        
        self.enable_process_mimicry()
        self.enable_resource_masking()
        self.enable_log_obfuscation()
        self.enable_network_stealth()
        
        stealth_level = len(self.active_techniques) / 4.0
        print(f"\n🛡️ Stealth Level: {stealth_level:.1%}")
        
        return {
            'techniques': self.active_techniques,
            'stealth_level': stealth_level
        }

def generate_sample_mining_scenario():
    """Generate sample metrics that simulate mining activity"""
    print("\n🔬 Generating Sample Mining Scenario...")
    
    # Simulate mining detection
    fake_metrics = {
        'timestamp': time.time(),
        'cpu_percent': 85.0,  # High CPU usage
        'memory_percent': 60.0,
        'total_processes': 250,
        'zombie_count': 45,  # Many zombie processes
        'zombie_ratio': 0.18,  # 18% zombie ratio
        'python_processes': 75,  # Many Python processes
        'python_ratio': 0.30,  # 30% Python ratio
        'network_connections': 15
    }
    
    return fake_metrics

def run_comprehensive_demo():
    """Run comprehensive demo"""
    print("🚀 COMPREHENSIVE FINGERPRINTING DEMO")
    print("=" * 60)
    
    detector = SimpleDetector()
    anti_fp = SimpleAntiFingerprinting()
    
    # === PART 1: DETECTION DEMO ===
    print("\n🔍 PART 1: MINING DETECTION")
    print("-" * 40)
    
    # Real system metrics
    print("📊 Collecting real system metrics...")
    real_metrics = detector.collect_system_metrics()
    
    if real_metrics:
        print(f"Current System Status:")
        print(f"  • CPU Usage: {real_metrics['cpu_percent']:.1f}%")
        print(f"  • Memory Usage: {real_metrics['memory_percent']:.1f}%")
        print(f"  • Total Processes: {real_metrics['total_processes']}")
        print(f"  • Zombie Processes: {real_metrics['zombie_count']} ({real_metrics['zombie_ratio']:.1%})")
        print(f"  • Python Processes: {real_metrics['python_processes']} ({real_metrics['python_ratio']:.1%})")
        
        # Analyze real metrics
        real_anomalies = detector.detect_mining_patterns(real_metrics)
        
        if real_anomalies:
            print(f"\n🚨 Real System Anomalies Detected:")
            for anomaly_type, details in real_anomalies.items():
                print(f"  • {anomaly_type}: {details['description']}")
        else:
            print("\n✅ No anomalies detected in real system")
    
    # Simulated mining scenario
    print("\n" + "="*50)
    fake_metrics = generate_sample_mining_scenario()
    
    print("📈 Simulated Mining Scenario Metrics:")
    print(f"  • CPU Usage: {fake_metrics['cpu_percent']:.1f}%")
    print(f"  • Zombie Ratio: {fake_metrics['zombie_ratio']:.1%}")
    print(f"  • Python Ratio: {fake_metrics['python_ratio']:.1%}")
    
    # Analyze simulated metrics
    fake_anomalies = detector.detect_mining_patterns(fake_metrics)
    
    print(f"\n🚨 Simulated Mining Detection Results:")
    for anomaly_type, details in fake_anomalies.items():
        severity = details['severity'].upper()
        print(f"  • {anomaly_type} [{severity}]: {details['description']}")
    
    # === PART 2: ANTI-FINGERPRINTING DEMO ===
    print("\n\n🥷 PART 2: ANTI-FINGERPRINTING")
    print("-" * 40)
    
    stealth_results = anti_fp.enable_all_techniques()
    
    # === PART 3: ADVANCED TECHNIQUES ===
    print("\n\n🧠 PART 3: ADVANCED TECHNIQUES")
    print("-" * 40)
    
    print("🔬 Advanced Detection Methods:")
    print("  • Machine Learning Anomaly Detection")
    print("    → Isolation Forest for behavioral analysis")
    print("    → LSTM networks for temporal pattern detection")
    print("  • Hardware Signature Analysis")
    print("    → GPU power consumption patterns")
    print("    → Thermal fingerprinting")
    print("  • Network Traffic Analysis")
    print("    → Mining pool connection detection")
    print("    → Protocol analysis")
    
    print("\n🛡️ Advanced Anti-Fingerprinting:")
    print("  • Adaptive Behavior Mimicking")
    print("    → Learn normal system patterns")
    print("    → Dynamically adjust mining intensity")
    print("  • Multi-Layer Obfuscation")
    print("    → Process name spoofing")
    print("    → Traffic tunneling through legitimate protocols")
    print("  • AI-Driven Evasion")
    print("    → Reinforcement learning for detection avoidance")
    print("    → Adversarial pattern generation")
    
    # === SUMMARY ===
    print("\n\n📋 DEMO SUMMARY")
    print("=" * 40)
    
    print("✅ Detection Capabilities Demonstrated:")
    print(f"  • Real system anomalies: {len(real_anomalies) if real_metrics else 0}")
    print(f"  • Simulated mining detection: {len(fake_anomalies)}")
    
    print(f"\n✅ Anti-Fingerprinting Techniques: {len(stealth_results['techniques'])}")
    print(f"  • Stealth Level: {stealth_results['stealth_level']:.1%}")
    
    # Save results
    results = {
        'real_metrics': real_metrics,
        'real_anomalies': real_anomalies,
        'simulated_metrics': fake_metrics,
        'simulated_anomalies': fake_anomalies,
        'stealth_techniques': stealth_results
    }
    
    # Write results to file
    results_file = Path('demo_results.json')
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📁 Results saved to: {results_file}")
    
    return results

if __name__ == "__main__":
    try:
        results = run_comprehensive_demo()
        print("\n🎉 Demo completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
