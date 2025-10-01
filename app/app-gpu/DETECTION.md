# 🔍 DETECTION GUIDE - Blue Team Handbook

## **MỤC ĐÍCH TÀI LIỆU** (Document Purpose)

Tài liệu này hướng dẫn **Blue Team** (đội phòng thủ - nhóm bảo mật) cách phát hiện và ngăn chặn **GPU cryptomining malware** (phần mềm độc hại khai thác GPU) trong môi trường cloud/datacenter.

**Research Context**: Tài liệu này được tạo từ red team research để giúp blue team hiểu attack vectors và develop detection capabilities.

---

## 📋 **MỤC LỤC** (Table of Contents)

1. [Tổng quan Attack Surface](#attack-surface)
2. [Detection Methods theo Priority](#detection-methods)
3. [SIEM Rules & Queries](#siem-rules)
4. [Incident Response Playbook](#incident-response)
5. [Prevention Strategies](#prevention)
6. [Tool Recommendations](#tools)

---

## 🎯 **ATTACK SURFACE OVERVIEW** {#attack-surface}

### **Threat Model**

```
Attacker Goal: Stealth GPU cryptomining trong cloud environment
Target: NVIDIA GPU instances (AWS p3/p4, Azure NC-series, GCP A100)
Impact:
  - Resource theft ($500-2000/month per GPU)
  - Performance degradation cho legitimate workloads
  - Increased cloud costs
  - Compliance violations
```

### **Attack Chain**

```
1. INITIAL ACCESS
   ├─ Compromised credentials
   ├─ Vulnerable container escape
   └─ Supply chain attack (malicious Docker image)

2. EXECUTION
   ├─ Deploy mining binary
   ├─ Process masquerading (tensorflow_gpu, pytorch_train)
   └─ Fork dummy workers to mimic AI framework

3. PERSISTENCE
   ├─ Systemd service / cron job
   ├─ Container restart policies
   └─ Kubernetes DaemonSet abuse

4. EVASION
   ├─ Process name spoofing
   ├─ NVML metric manipulation
   ├─ Mixed workload (mining + fake AI)
   ├─ In-memory DAG (no disk artifacts)
   └─ TLS-wrapped pool protocol

5. IMPACT
   └─ Sustained GPU resource consumption
```

---

## 🔴 **DETECTION METHODS** (By Priority) {#detection-methods}

### **🥇 TIER 1: HIGH-CONFIDENCE DETECTION** (>95% accuracy)

#### **Method 1: eBPF GPU Kernel Tracing**

**Principle**: GPU mining kernels có function signatures đặc trưng không thể hide.

**Implementation**:
```bash
# Sử dụng bpftrace để trace CUDA kernel launches
sudo bpftrace -e '
uprobe:/usr/lib/x86_64-linux-gnu/libcuda.so:cuLaunchKernel {
  printf("Kernel: %s, Blocks: %d, Threads: %d\n",
         str(arg0), arg1, arg2);
}'
```

**Detection Signatures**:
- Kernel names: `kawpow`, `ethash`, `keccak`, `dag_gen`
- Launch patterns: Sustained high block count (>1000 blocks)
- Grid dimensions: Unusual for AI (e.g., 1D grid với millions of threads)

**Evasion Resistance**: ⭐⭐⭐⭐⭐ (Kernel names có thể obfuscate nhưng pattern khó giấu)

---

#### **Method 2: GPU Memory Access Pattern Analysis**

**Principle**: DAG lookup có stride pattern đặc trưng khác biệt với AI workloads.

**Implementation**:
```python
# Sử dụng NVIDIA Nsight Systems để profile memory access
import pynvml

pynvml.nvmlInit()
handle = pynvml.nvmlDeviceGetHandleByIndex(0)

# Monitor memory bandwidth patterns
while True:
    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)

    # Mining signature: High memory BW + random access pattern
    if util.memory > 80 and util.gpu > 90:
        print("⚠️ Potential mining detected")

        # Check running processes
        procs = pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
        for proc in procs:
            print(f"  PID: {proc.pid}, VRAM: {proc.usedGpuMemory / 1e9:.2f} GB")
```

**Detection Signatures**:
- VRAM allocation: 4-5GB single block (DAG size)
- Memory bandwidth: Sustained >80% (random DAG accesses)
- Access pattern: Random, not sequential (unlike CNN inference)

**Evasion Resistance**: ⭐⭐⭐⭐ (Progressive allocation giảm signal, nhưng pattern vẫn khác AI)

---

#### **Method 3: Network Traffic Analysis (Stratum Protocol)**

**Principle**: Mining pool protocol có fingerprint rõ ràng, dù có TLS wrapper.

**Implementation**:
```bash
# Sniff outbound connections từ GPU processes
sudo tcpdump -i any -A 'tcp and (dst port 3333 or dst port 6060 or dst port 14444)' | \
  grep -E 'mining.subscribe|mining.authorize|mining.submit'
```

**Detection Signatures**:
```json
// Stratum JSON-RPC có format cố định
{
  "id": 1,
  "method": "mining.subscribe",
  "params": ["RedTeamMiner/2.0.0", "EthereumStratum/1.0.0"]
}

// Submit shares có pattern đặc trưng
{
  "method": "mining.submit",
  "params": ["worker", "job_id", "0x1234abcd", "0xdeadbeef", "0xcafebabe"]
}
```

**Detection via TLS Fingerprinting**:
```python
# Phân tích TLS handshake (SNI, cipher suites)
# Mining pools thường dùng specific certificate patterns
import pyshark

capture = pyshark.LiveCapture(interface='eth0', bpf_filter='tcp port 443')

for packet in capture:
    if hasattr(packet, 'tls'):
        sni = packet.tls.handshake_extensions_server_name
        # Check against known mining pool domains
        if any(pool in sni for pool in ['2miners', 'ethermine', 'nanopool']):
            print(f"⚠️ Mining pool connection detected: {sni}")
```

**Evasion Resistance**: ⭐⭐⭐⭐⭐ (Protocol structure khó thay đổi, pool cần standard format)

---

### **🥈 TIER 2: MEDIUM-CONFIDENCE DETECTION** (70-90% accuracy)

#### **Method 4: GPU Utilization Time-Series Analysis**

**Principle**: Mining có sustained utilization pattern, AI training có periodic bursts.

**Detection Algorithm**:
```python
import numpy as np
from scipy import stats

def detect_mining_pattern(gpu_util_history, window_size=60):
    """
    gpu_util_history: List of GPU util % sampled every 1s
    Returns: (is_mining, confidence_score)
    """
    # Calculate statistics
    mean_util = np.mean(gpu_util_history)
    std_util = np.std(gpu_util_history)

    # Mining signature:
    # - High mean utilization (>85%)
    # - Low standard deviation (<10%) - sustained usage
    # - No periodic dips (AI training có cooldown phases)

    if mean_util > 85 and std_util < 10:
        # Check for periodic patterns (AI training có epoch boundaries)
        fft = np.fft.fft(gpu_util_history)
        power_spectrum = np.abs(fft)**2

        # If no dominant frequency, likely mining (random noise only)
        max_power = np.max(power_spectrum[1:len(power_spectrum)//2])
        if max_power < np.mean(power_spectrum) * 3:
            return True, 0.85  # High confidence mining

    return False, 0.0
```

**Evasion Resistance**: ⭐⭐⭐ (Duty cycle modulation có thể giảm signal)

---

#### **Method 5: Process Tree Analysis**

**Principle**: AI frameworks có characteristic process structure.

**Validation Checks**:
```bash
#!/bin/bash
# Check if process tree matches expected AI framework

PID=$1  # Suspicious process PID
PROCESS_NAME=$(ps -p $PID -o comm=)

# Check 1: Process name
if [[ "$PROCESS_NAME" =~ (tensorflow|pytorch|python3) ]]; then
    echo "✓ Process name looks legitimate: $PROCESS_NAME"
else
    echo "⚠️ Unusual process name: $PROCESS_NAME"
fi

# Check 2: Child processes (AI frameworks thường có workers)
CHILDREN=$(pgrep -P $PID | wc -l)
if [ $CHILDREN -ge 4 ] && [ $CHILDREN -le 12 ]; then
    echo "✓ Child count reasonable: $CHILDREN"
else
    echo "⚠️ Suspicious child count: $CHILDREN"
fi

# Check 3: Shared memory segments (PyTorch DataLoader dùng /dev/shm)
SHM_COUNT=$(lsof -p $PID 2>/dev/null | grep '/dev/shm' | wc -l)
if [ $SHM_COUNT -gt 0 ]; then
    echo "✓ Shared memory usage detected: $SHM_COUNT segments"
else
    echo "⚠️ No shared memory usage (unusual for multi-worker AI)"
fi

# Check 4: Command line validation
CMDLINE=$(cat /proc/$PID/cmdline | tr '\0' ' ')
if [[ "$CMDLINE" =~ (train|model|dataset|epoch|batch) ]]; then
    echo "✓ Command line has AI-related keywords"
else
    echo "⚠️ Command line lacks AI keywords: $CMDLINE"
fi
```

**Evasion Resistance**: ⭐⭐ (Dễ spoof, nhưng cross-validation với metrics tăng confidence)

---

### **🥉 TIER 3: LOW-CONFIDENCE DETECTION** (50-70% accuracy)

#### **Method 6: Power Consumption Baseline Deviation**

**Principle**: Mining có power draw pattern khác AI training.

```python
# So sánh với baseline của legitimate AI workloads
baseline_power_profile = {
    'mean': 180,  # Watts
    'std': 25,    # Variation
    'peak': 220,
    'idle_ratio': 0.15  # % time ở idle
}

def check_power_anomaly(current_power_history):
    mean_power = np.mean(current_power_history)
    std_power = np.std(current_power_history)

    # Mining: higher mean, lower std (sustained load)
    if mean_power > baseline_power_profile['mean'] * 1.15 and \
       std_power < baseline_power_profile['std'] * 0.6:
        return True, 0.65  # Medium confidence

    return False, 0.0
```

**Evasion Resistance**: ⭐⭐ (Power throttling + noise injection có thể defeat)

---

## 🚨 **SIEM RULES & QUERIES** {#siem-rules}

### **Splunk Query**

```spl
index=gpu_metrics sourcetype=nvidia_smi
| stats avg(gpu_util) as avg_util, stdev(gpu_util) as std_util by host, pid
| where avg_util > 85 AND std_util < 10
| eval risk_score = (avg_util / 100) * (1 / (std_util + 1))
| where risk_score > 8
| table host, pid, process_name, avg_util, std_util, risk_score
| sort - risk_score
```

### **Prometheus Alert Rule**

```yaml
groups:
  - name: gpu_mining_detection
    interval: 60s
    rules:
      - alert: PotentialGPUMining
        expr: |
          (
            avg_over_time(nvidia_gpu_utilization[5m]) > 85
            and
            stddev_over_time(nvidia_gpu_utilization[5m]) < 10
          )
        for: 10m
        labels:
          severity: warning
          category: resource_abuse
        annotations:
          summary: "Potential GPU mining detected on {{ $labels.instance }}"
          description: |
            GPU {{ $labels.gpu_id }} shows sustained high utilization ({{ $value }}%)
            with low variation, typical of cryptomining workload.

            Investigate:
            1. Check running processes: nvidia-smi
            2. Verify process legitimacy
            3. Review network connections
```

### **ELK Stack Detection Query**

```json
{
  "query": {
    "bool": {
      "must": [
        {
          "range": {
            "gpu.utilization": {"gte": 85}
          }
        },
        {
          "range": {
            "gpu.memory_used_gb": {"gte": 3.5}
          }
        }
      ],
      "should": [
        {
          "match": {
            "process.name": {
              "query": "inference-cuda kawpow miner xmrig",
              "operator": "or"
            }
          }
        },
        {
          "range": {
            "network.bytes_sent": {"gte": 1000000}
          }
        }
      ],
      "minimum_should_match": 1
    }
  }
}
```

---

## 🔬 **ADVANCED DETECTION TECHNIQUES**

### **1. CUDA Kernel Binary Analysis**

**Tool**: `cuobjdump` (NVIDIA CUDA toolkit)

```bash
#!/bin/bash
# Extract và analyze CUDA kernels từ suspicious process

PID=$1
EXE_PATH=$(readlink -f /proc/$PID/exe)

# Dump CUDA kernels
cuobjdump --dump-ptx "$EXE_PATH" > /tmp/kernels_$PID.ptx

# Search for mining-specific patterns
if grep -qE '(keccak|ethash|kawpow|fnv_hash|dag_item)' /tmp/kernels_$PID.ptx; then
    echo "🔴 HIGH RISK: Mining kernel signatures detected"

    # Extract kernel names
    grep -E '\.visible \.entry' /tmp/kernels_$PID.ptx

    exit 1
else
    echo "✓ No obvious mining signatures in kernel code"
    exit 0
fi
```

**Detection Signatures**:
- Keccak round constants (`0x0000000000000001`, `0x8000000080008000`, ...)
- FNV prime (`0x01000193`)
- DAG access patterns (large stride, pseudo-random indexing)
- Nonce iteration loops

---

### **2. Memory Access Pattern Profiling**

**Tool**: `nvidia-smi dmon` + custom analysis

```bash
# Monitor memory bandwidth patterns
nvidia-smi dmon -s mu -c 300 -d 1 | tee gpu_memory_pattern.log

# Analyze for mining signatures
python3 << 'EOF'
import re
import sys

# Read nvidia-smi dmon output
with open('gpu_memory_pattern.log') as f:
    lines = f.readlines()

mem_utils = []
for line in lines:
    match = re.search(r'\s+(\d+)\s+\d+\s+(\d+)', line)  # Extract memory util
    if match:
        mem_utils.append(int(match.group(2)))

if not mem_utils:
    sys.exit(0)

import numpy as np

mean_mem = np.mean(mem_utils)
std_mem = np.std(mem_utils)

# Mining signature: Sustained high mem util (>70%) với low variance
if mean_mem > 70 and std_mem < 15:
    print(f"🔴 MINING DETECTED: Mean={mean_mem:.1f}%, Std={std_mem:.1f}%")
    print("   Mining có random memory access pattern sustained >70%")
    print("   AI inference thường <50%, training có periodic dips")
    sys.exit(1)
else:
    print(f"✓ Normal pattern: Mean={mean_mem:.1f}%, Std={std_mem:.1f}%")
    sys.exit(0)
EOF
```

---

### **3. Network Traffic Fingerprinting**

**Tool**: Zeek (Bro) IDS

**Zeek Script** (`detect_stratum.zeek`):
```zeek
# Detect Stratum mining protocol
@load base/protocols/conn

module Mining;

export {
    redef enum Notice::Type += {
        Stratum_Protocol_Detected,
        Mining_Pool_Connection
    };
}

# Known mining pool ports
const mining_ports: set[port] = {
    3333/tcp, 6060/tcp, 14444/tcp,  # Common stratum ports
    4444/tcp, 5555/tcp, 9999/tcp
};

# Mining pool domains
const mining_pool_domains = /2miners|ethermine|nanopool|f2pool|hiveon/;

event connection_established(c: connection) {
    # Check for connections to mining ports
    if (c$id$resp_p in mining_ports) {
        NOTICE([
            $note=Stratum_Protocol_Detected,
            $msg=fmt("Potential mining pool connection: %s:%d", c$id$resp_h, c$id$resp_p),
            $conn=c
        ]);
    }
}

event dns_request(c: connection, msg: dns_msg, query: string, qtype: count, qclass: count) {
    # Detect DNS queries to mining pools
    if (mining_pool_domains in query) {
        NOTICE([
            $note=Mining_Pool_Connection,
            $msg=fmt("Mining pool DNS query: %s", query),
            $conn=c
        ]);
    }
}
```

**Stratum Packet Signatures**:
```
Request patterns:
{"id":1,"method":"mining.subscribe","params":[...]}
{"id":2,"method":"mining.authorize","params":["wallet.worker","password"]}
{"id":3,"method":"mining.submit","params":["worker","job","nonce","header","mix"]}

Response patterns:
{"id":1,"result":[[["mining.set_difficulty","1"],["mining.notify","..."]]]}
{"id":null,"method":"mining.set_difficulty","params":[...]}
{"id":null,"method":"mining.notify","params":[...]}
```

---

### **4. Process Behavior Correlation**

**Multi-Signal Detection** (Kết hợp nhiều signals):

```python
#!/usr/bin/env python3
"""
Multi-signal correlation detector
Combines multiple weak signals for high-confidence detection
"""

import psutil
import pynvml
import time
import json

class MiningDetector:
    def __init__(self):
        pynvml.nvmlInit()
        self.gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)

    def collect_signals(self, pid):
        """Thu thập multiple detection signals"""
        signals = {}

        # Signal 1: Process name
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            cmdline = ' '.join(proc.cmdline())

            # Suspicious nếu name/cmdline mismatch
            ai_keywords = ['tensorflow', 'pytorch', 'train', 'model']
            has_ai_keywords = any(kw in cmdline.lower() for kw in ai_keywords)

            signals['proc_name_suspicious'] = 0.3 if not has_ai_keywords else 0.0

        except psutil.NoSuchProcess:
            signals['proc_name_suspicious'] = 1.0  # Process hiding

        # Signal 2: GPU utilization pattern
        util_history = []
        for _ in range(60):  # Sample 60 seconds
            util = pynvml.nvmlDeviceGetUtilizationRates(self.gpu_handle)
            util_history.append(util.gpu)
            time.sleep(1)

        mean_util = sum(util_history) / len(util_history)
        import numpy as np
        std_util = np.std(util_history)

        # High mean + low std = likely mining
        if mean_util > 85 and std_util < 10:
            signals['gpu_pattern_suspicious'] = 0.9
        elif mean_util > 75 and std_util < 15:
            signals['gpu_pattern_suspicious'] = 0.6
        else:
            signals['gpu_pattern_suspicious'] = 0.0

        # Signal 3: Memory allocation pattern
        try:
            procs = pynvml.nvmlDeviceGetComputeRunningProcesses(self.gpu_handle)
            for p in procs:
                if p.pid == pid:
                    vram_gb = p.usedGpuMemory / 1e9

                    # DAG size: 4-5GB is red flag
                    if 3.5 <= vram_gb <= 5.5:
                        signals['vram_pattern_suspicious'] = 0.8
                    else:
                        signals['vram_pattern_suspicious'] = 0.0
                    break
        except Exception:
            signals['vram_pattern_suspicious'] = 0.0

        # Signal 4: Network connections
        try:
            proc = psutil.Process(pid)
            connections = proc.connections(kind='inet')

            # Check for non-standard ports
            suspicious_ports = [3333, 6060, 14444, 4444, 5555, 9999]
            has_mining_port = any(
                conn.raddr.port in suspicious_ports
                for conn in connections if conn.raddr
            )

            signals['network_suspicious'] = 0.7 if has_mining_port else 0.0

        except Exception:
            signals['network_suspicious'] = 0.0

        return signals

    def calculate_risk_score(self, signals):
        """Weighted risk score calculation"""
        weights = {
            'proc_name_suspicious': 0.15,
            'gpu_pattern_suspicious': 0.40,
            'vram_pattern_suspicious': 0.25,
            'network_suspicious': 0.20
        }

        total_score = sum(signals.get(k, 0) * weights[k] for k in weights)
        return total_score

    def detect(self, pid):
        print(f"[DETECTOR] Analyzing PID {pid}...")

        signals = self.collect_signals(pid)
        risk_score = self.calculate_risk_score(signals)

        print(f"\n=== Detection Signals ===")
        for signal_name, score in signals.items():
            status = "🔴" if score > 0.6 else "🟡" if score > 0.3 else "✓"
            print(f"{status} {signal_name}: {score:.2f}")

        print(f"\n=== Overall Risk Score: {risk_score:.2f} ===")

        if risk_score > 0.7:
            print("🔴 HIGH RISK: Likely cryptomining")
            return True, risk_score
        elif risk_score > 0.4:
            print("🟡 MEDIUM RISK: Suspicious activity, investigate further")
            return False, risk_score
        else:
            print("✓ LOW RISK: Appears legitimate")
            return False, risk_score

if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 detector.py <PID>")
        sys.exit(1)

    detector = MiningDetector()
    is_mining, score = detector.detect(int(sys.argv[1]))

    sys.exit(1 if is_mining else 0)
```

---

## 🛡️ **INCIDENT RESPONSE PLAYBOOK** {#incident-response}

### **Phase 1: Detection & Triage** (0-15 minutes)

```bash
#!/bin/bash
# Quick triage script for suspected GPU mining

SUSPICIOUS_PID=$1

echo "=== GPU MINING INCIDENT TRIAGE ==="
echo "Target PID: $SUSPICIOUS_PID"
echo ""

# 1. Capture process snapshot
echo "[1/6] Capturing process information..."
ps aux | grep $SUSPICIOUS_PID > /tmp/triage_$SUSPICIOUS_PID.txt
cat /proc/$SUSPICIOUS_PID/cmdline >> /tmp/triage_$SUSPICIOUS_PID.txt
cat /proc/$SUSPICIOUS_PID/environ >> /tmp/triage_$SUSPICIOUS_PID.txt

# 2. Capture GPU state
echo "[2/6] Capturing GPU state..."
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv \
  >> /tmp/triage_$SUSPICIOUS_PID.txt

# 3. Capture network connections
echo "[3/6] Capturing network connections..."
lsof -p $SUSPICIOUS_PID -i >> /tmp/triage_$SUSPICIOUS_PID.txt

# 4. Capture binary hash
echo "[4/6] Capturing binary hash..."
EXE=$(readlink -f /proc/$SUSPICIOUS_PID/exe)
sha256sum "$EXE" >> /tmp/triage_$SUSPICIOUS_PID.txt

# 5. Capture memory map
echo "[5/6] Capturing memory map..."
cat /proc/$SUSPICIOUS_PID/maps >> /tmp/triage_$SUSPICIOUS_PID.txt

# 6. Quick malware scan
echo "[6/6] Running quick malware scan..."
clamscan "$EXE" >> /tmp/triage_$SUSPICIOUS_PID.txt 2>&1

echo ""
echo "✓ Triage data saved to: /tmp/triage_$SUSPICIOUS_PID.txt"
echo ""
echo "Next steps:"
echo "  1. Review triage data"
echo "  2. If confirmed mining, proceed to containment"
echo "  3. Run full forensics: ./forensics.sh $SUSPICIOUS_PID"
```

### **Phase 2: Containment** (15-30 minutes)

```bash
# Immediate containment actions

# Option A: NICE approach (prevent resource starvation)
renice +19 -p $SUSPICIOUS_PID  # Lowest priority
ionice -c 3 -p $SUSPICIOUS_PID  # Idle I/O priority

# Option B: CGROUP approach (limit GPU access)
# Không thể limit GPU qua cgroup directly, nhưng có thể limit CPU/memory
cgcreate -g cpu,memory:/mining_quarantine
echo $SUSPICIOUS_PID > /sys/fs/cgroup/cpu/mining_quarantine/cgroup.procs
echo "10000" > /sys/fs/cgroup/cpu/mining_quarantine/cpu.cfs_quota_us  # 10% CPU

# Option C: KILL approach (terminate immediately)
kill -TERM $SUSPICIOUS_PID
sleep 5
kill -KILL $SUSPICIOUS_PID

# Verify termination
if ps -p $SUSPICIOUS_PID > /dev/null; then
    echo "⚠️ Process still running after kill attempt"
else
    echo "✓ Process terminated"
fi
```

### **Phase 3: Forensics & Root Cause** (30-120 minutes)

```bash
#!/bin/bash
# Deep forensics analysis

SUSPICIOUS_PID=$1
FORENSICS_DIR="/var/forensics/mining_incident_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$FORENSICS_DIR"

echo "Starting deep forensics analysis..."

# 1. Memory dump (requires root + gcore)
echo "[FORENSICS] Dumping process memory..."
gcore -o "$FORENSICS_DIR/process_dump" $SUSPICIOUS_PID

# 2. Extract CUDA kernels
EXE=$(readlink -f /proc/$SUSPICIOUS_PID/exe)
cp "$EXE" "$FORENSICS_DIR/suspicious_binary"

cuobjdump --dump-ptx "$EXE" > "$FORENSICS_DIR/kernels.ptx"
cuobjdump --dump-sass "$EXE" > "$FORENSICS_DIR/kernels.sass"

# 3. Network forensics
echo "[FORENSICS] Capturing network traffic..."
timeout 300 tcpdump -i any -w "$FORENSICS_DIR/network.pcap" \
  "host $(lsof -p $SUSPICIOUS_PID -i -n | awk 'NR>1 {print $9}' | cut -d: -f1 | sort -u)"

# 4. Analyze network traffic
tshark -r "$FORENSICS_DIR/network.pcap" -Y 'tcp.payload' -T fields -e tcp.payload \
  | grep -oE '"method":"mining\.(subscribe|authorize|submit)"' \
  > "$FORENSICS_DIR/stratum_evidence.txt"

# 5. Check for persistence mechanisms
echo "[FORENSICS] Checking persistence..."
systemctl list-units --type=service --all | grep -i $SUSPICIOUS_PID > "$FORENSICS_DIR/systemd_services.txt"
crontab -l | grep -i "$(basename $EXE)" > "$FORENSICS_DIR/cron_entries.txt" 2>/dev/null

# 6. Timeline analysis
journalctl -u docker -u kubelet --since "1 hour ago" | grep -i "$(basename $EXE)" \
  > "$FORENSICS_DIR/journal_timeline.txt"

echo "✓ Forensics data collected in: $FORENSICS_DIR"
```

---

## 🔐 **PREVENTION STRATEGIES** {#prevention}

### **1. Runtime Security Policies**

#### **Kubernetes PodSecurityPolicy**

```yaml
apiVersion: policy/v1beta1
kind: PodSecurityPolicy
metadata:
  name: restricted-gpu-usage
spec:
  # Prevent privilege escalation
  allowPrivilegeEscalation: false
  requiredDropCapabilities:
    - ALL

  # Read-only root filesystem
  readOnlyRootFilesystem: true

  # No host network/PID namespace
  hostNetwork: false
  hostPID: false

  # Seccomp profile
  seccomp:
    rule: RuntimeDefault

  # SELinux context
  seLinux:
    rule: RunAsAny

  # Resource limits (enforce via LimitRange)
  # Note: K8s không thể directly limit GPU util, cần external solution
```

#### **AppArmor Profile**

```
#include <tunables/global>

/usr/local/bin/tensorflow_gpu {
  #include <abstractions/base>

  # Allow CUDA libraries
  /usr/lib/x86_64-linux-gnu/libcuda.so* mr,
  /usr/lib/x86_64-linux-gnu/libnvidia-*.so* mr,

  # Deny network access to mining pools
  deny network tcp connect,
  deny network udp connect,

  # Allow only specific ports (ML model serving)
  network inet stream connect port 8080,  # Local model server
  network inet stream connect port 443,   # HTTPS only

  # Deny process manipulation
  deny capability sys_ptrace,
  deny capability sys_admin,

  # Limit file writes
  deny /tmp/** w,
  deny /var/tmp/** w,

  # Allow read-only access to datasets
  /data/** r,

  # Deny execution of binaries from /tmp
  deny /tmp/** x,
}
```

---

### **2. Network-Level Controls**

#### **Firewall Rules** (Block mining pool connections)

```bash
#!/bin/bash
# Block known mining pool IPs and ports

# Known mining pool port ranges
MINING_PORTS="3333,4444,5555,6060,9999,14444"

# Block outbound connections to mining ports
iptables -A OUTPUT -p tcp -m multiport --dports $MINING_PORTS -j LOG --log-prefix "MINING_POOL_BLOCKED: "
iptables -A OUTPUT -p tcp -m multiport --dports $MINING_PORTS -j REJECT

# Block known mining pool domains (requires DNS filtering)
# Use PiHole or similar DNS firewall with mining pool blocklist
```

#### **DNS Filtering** (Mining pool blocklist)

```
# /etc/pihole/custom.list or similar DNS firewall

# Major mining pools
0.0.0.0 2miners.com
0.0.0.0 ethermine.org
0.0.0.0 nanopool.org
0.0.0.0 f2pool.com
0.0.0.0 hiveon.net
0.0.0.0 ezil.me
0.0.0.0 woolypooly.com

# Ravencoin specific
0.0.0.0 rvn.2miners.com
0.0.0.0 ravenminer.com
0.0.0.0 minermore.com
```

---

### **3. GPU Access Control**

#### **NVIDIA MIG (Multi-Instance GPU)** - Isolation

```bash
# Enable MIG mode (A100/A30 only)
sudo nvidia-smi -mig 1

# Create GPU instances với resource limits
sudo nvidia-smi mig -cgi 9,9,9,9 -C  # 4x 1g.10gb instances

# Assign specific instance to container
docker run --gpus '"device=0:0"' ...  # MIG instance 0 only
```

#### **Compute Mode Restrictions**

```bash
# Set GPU to EXCLUSIVE_PROCESS mode (only 1 process at a time)
nvidia-smi -c EXCLUSIVE_PROCESS

# Or PROHIBITED mode to completely block compute
nvidia-smi -c PROHIBITED  # Chỉ graphics, no compute
```

---

## 🛠️ **RECOMMENDED TOOLS** {#tools}

### **Open Source**

| Tool | Purpose | Detection Capability |
|------|---------|---------------------|
| **eBPF/bpftrace** | Kernel tracing | ⭐⭐⭐⭐⭐ GPU kernel signatures |
| **Falco** | Runtime security | ⭐⭐⭐⭐ Process + syscall anomalies |
| **Zeek IDS** | Network analysis | ⭐⭐⭐⭐⭐ Stratum protocol detection |
| **Osquery** | Host monitoring | ⭐⭐⭐ Process/network inventory |
| **Prometheus + Grafana** | Metrics + alerting | ⭐⭐⭐ GPU utilization patterns |
| **NVIDIA DCGM** | GPU telemetry | ⭐⭐⭐⭐ Deep GPU metrics |

### **Commercial**

| Tool | Purpose | Effectiveness |
|------|---------|---------------|
| **Wazuh** | SIEM + EDR | ⭐⭐⭐⭐ Full stack detection |
| **Datadog** | APM + GPU monitoring | ⭐⭐⭐⭐ Automated anomaly detection |
| **CrowdStrike Falcon** | EDR | ⭐⭐⭐⭐⭐ Behavior analysis |
| **Sysdig Secure** | Container security | ⭐⭐⭐⭐ Runtime detection |

---

## 📊 **DETECTION EFFECTIVENESS MATRIX**

### **Evasion Technique vs Detection Method**

| Evasion Technique | eBPF Kernel Trace | Memory Pattern | Network Analysis | Power Profile | Process Tree |
|-------------------|-------------------|----------------|------------------|---------------|--------------|
| Process name spoofing | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective | 🟡 Partial |
| Kernel name obfuscation | 🟡 Partial | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective |
| Progressive DAG alloc | ✓ Ineffective | 🟡 Partial | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective |
| TLS pool connection | ✓ Ineffective | ✓ Ineffective | 🟡 Partial | ✓ Ineffective | ✓ Ineffective |
| Mixed workload (mining+AI) | 🟡 Partial | 🟡 Partial | ✓ Ineffective | 🟡 Partial | ✓ Ineffective |
| Dummy worker processes | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective | ❌ Effective |
| Power throttling | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective | ❌ Effective | ✓ Ineffective |
| NVML metric hooking | ✓ Ineffective | ✓ Ineffective | ✓ Ineffective | ❌ Effective | ✓ Ineffective |

**Legend**:
- ✓ **Ineffective**: Detection method vẫn hoạt động tốt
- 🟡 **Partial**: Detection degraded nhưng vẫn có signal
- ❌ **Effective**: Evasion technique thành công bypass detection

**Kết luận**: **eBPF Kernel Tracing** và **Network Analysis** là strongest detection methods, khó evade hoàn toàn.

---

## 🎓 **TRAINING RECOMMENDATIONS**

### **Blue Team Training Labs**

1. **Lab 1: Baseline Establishment**
   - Chạy legitimate AI workloads (TensorFlow, PyTorch)
   - Thu thập GPU metrics, network patterns, process behavior
   - Tạo baseline profile

2. **Lab 2: Detection Rule Development**
   - Deploy red team miner trong controlled environment
   - Test detection rules against various evasion configs
   - Tune thresholds để minimize false positives

3. **Lab 3: Incident Response Drill**
   - Simulate mining infection
   - Practice triage, containment, forensics
   - Measure response time và effectiveness

---

## 📚 **REFERENCES & FURTHER READING**

### **Academic Papers**

- "Detecting Cryptocurrency Mining in Cloud Environments" (IEEE, 2021)
- "GPU-based Malware Detection Using Performance Counters" (ACM CCS, 2020)
- "eBPF for Runtime Security Monitoring" (USENIX, 2022)

### **Industry Reports**

- MITRE ATT&CK: [T1496 - Resource Hijacking](https://attack.mitre.org/techniques/T1496/)
- SANS: "Cloud Security Monitoring Best Practices"
- Gartner: "GPU Security in Cloud Environments"

### **Tools & Frameworks**

- [NVIDIA DCGM](https://developer.nvidia.com/dcgm) - GPU telemetry
- [Falco](https://falco.org/) - Runtime threat detection
- [Zeek](https://zeek.org/) - Network security monitoring
- [BPF Compiler Collection (BCC)](https://github.com/iovisor/bcc) - eBPF tools

---

## ⚖️ **LEGAL & COMPLIANCE**

### **Reporting Requirements**

Nếu phát hiện unauthorized mining:

1. **Document evidence** thoroughly (screenshots, logs, pcap)
2. **Preserve forensics** data (memory dumps, binaries)
3. **Report to management** + legal team
4. **File incident report** theo compliance framework (SOC2, ISO27001)
5. **Consider law enforcement** nếu financial impact lớn

### **Compliance Frameworks**

- **SOC2**: Monitoring controls (CC7.2, CC7.3)
- **ISO 27001**: A.12.6.1 (Technical vulnerability management)
- **NIST CSF**: DE.CM-7 (Monitoring for unauthorized activity)
- **PCI DSS**: Requirement 10 (Logging and monitoring)

---

## 🏁 **CONCLUSION**

### **Key Takeaways**

1. **eBPF kernel tracing** là most effective detection method
2. **Multi-signal correlation** cải thiện accuracy
3. **Prevention > Detection** - restrict GPU access by default
4. **Network controls** block pool access effectively

### **Recommended Detection Stack**

```
┌─────────────────────────────────────────┐
│  Layer 1: eBPF Kernel Monitoring        │  ← Primary detection
│  (Falco + custom BPF programs)          │
├─────────────────────────────────────────┤
│  Layer 2: GPU Telemetry (DCGM)          │  ← Performance anomalies
│  + Prometheus + Alertmanager            │
├─────────────────────────────────────────┤
│  Layer 3: Network IDS (Zeek)            │  ← Protocol detection
│  + Suricata with mining pool signatures │
├─────────────────────────────────────────┤
│  Layer 4: SIEM Correlation (Wazuh/ELK)  │  ← Multi-signal analysis
│  + ML-based anomaly detection           │
└─────────────────────────────────────────┘
```

### **Detection SLA Targets**

- **Time to Detect (TTD)**: <5 minutes (with eBPF)
- **Time to Triage (TTT)**: <15 minutes
- **Time to Contain (TTC)**: <30 minutes
- **False Positive Rate**: <2% (với proper baseline)

---

## 📞 **SUPPORT & RESOURCES**

- **Emergency contacts**: security-oncall@company.com
- **Runbook repository**: https://github.com/company/security-runbooks
- **Threat intel feed**: https://threatfeeds.company.com/gpu-mining

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-01
**Author**: Red Team Research (for Blue Team training)
**Classification**: Internal - Security Team Only
