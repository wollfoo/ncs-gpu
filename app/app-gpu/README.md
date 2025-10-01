# Red Team GPU Miner v2.0

**Offensive Security Research Framework for GPU Mining Detection Methodology Development**

[![License: Research](https://img.shields.io/badge/License-Research%20Only-red.svg)](LICENSE)
[![CUDA: 12.2+](https://img.shields.io/badge/CUDA-12.2%2B-green.svg)](https://developer.nvidia.com/cuda-toolkit)
[![C++: 17](https://img.shields.io/badge/C%2B%2B-17-blue.svg)](https://isocpp.org/)
[![Purpose: Blue Team Training](https://img.shields.io/badge/Purpose-Blue%20Team%20Training-yellow.svg)](DETECTION.md)

---

## ⚠️ Research Disclaimer

**This project is designed exclusively for:**
- ✅ **Authorized security research**
- ✅ **Blue team training and detection methodology development**
- ✅ **Academic research in cloud security**
- ✅ **Red team exercises with explicit permission**

**Unauthorized use for cryptocurrency mining is:**
- ❌ **Illegal** in most jurisdictions
- ❌ **Unethical** and violates terms of service
- ❌ **Detectable** and subject to legal action

---

## 📋 Project Overview

This framework implements a **comprehensive GPU mining system** with advanced evasion techniques to help security teams:

1. **Understand attack vectors** - How adversaries abuse GPU resources
2. **Develop detection rules** - Build robust monitoring and alerting
3. **Train incident responders** - Practice threat hunting and forensics
4. **Improve security posture** - Close gaps in cloud security monitoring

### Key Features

- 🔥 **High-Performance Mining Engine**: Optimized CUDA kernels for KawPow algorithm
- 🔐 **Encrypted Pool Communication**: Stratum protocol with TLS 1.2/1.3 support
- 🥷 **Stealth Capabilities**: Process masquerading, metric obfuscation, anti-forensics
- 📊 **Configurable Profiles**: Stealth, Balanced, Aggressive modes
- 🐳 **Containerized Deployment**: Docker with GPU passthrough and monitoring
- 📈 **Monitoring Integration**: Prometheus metrics and Grafana dashboards

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│              Red Team GPU Miner v2.0                │
├─────────────────┬──────────────┬────────────────────┤
│ Core Mining     │ Pool Client  │ Evasion Modules    │
│ • KawPow Kernel │ • Stratum    │ • Process Masq     │
│ • DAG Generator │ • TLS Wrap   │ • NVML Hooking     │
│ • Optimizer     │ • Job Mgmt   │ • Anti-Debug       │
└─────────────────┴──────────────┴────────────────────┘
```

See [TECHNICAL_REPORT.md](TECHNICAL_REPORT.md) for detailed architecture diagrams.

---

## 🚀 Quick Start

### Prerequisites

**System Requirements**:
- Ubuntu 22.04+ (or compatible Linux)
- NVIDIA GPU with CUDA Compute Capability 7.5+ (Turing, Ampere, Ada)
- NVIDIA Driver 525+ and CUDA Toolkit 12.2+
- Docker + nvidia-docker2 (for containerized deployment)

**Software Dependencies**:
```bash
sudo apt-get install -y \
    build-essential cmake ninja-build \
    nvidia-cuda-toolkit libssl-dev pkg-config
```

### Build from Source

```bash
# Clone repository
git clone <repository-url>
cd app-gpu

# Build
./scripts/build_redteam.sh

# Binary output: build/redteam-miner
```

### Configuration

```bash
# Edit main configuration
vim config/miner_config.json

# Available evasion profiles:
# - stealth.json    (Maximum evasion, ~65% performance)
# - balanced.json   (Moderate evasion, ~85% performance)
# - aggressive.json (No evasion, ~100% performance)
```

### Run

```bash
# Native execution
./build/redteam-miner --config config/miner_config.json

# Docker deployment
cd docker
docker-compose -f docker-compose.redteam.yml up -d
```

---

## 📁 Project Structure

```
app-gpu/
├── CMakeLists.txt              # Build configuration
├── README.md                   # This file
├── DETECTION.md                # Blue team detection guide (32KB)
├── TECHNICAL_REPORT.md         # Comprehensive technical documentation
│
├── include/                    # Header files
│   ├── cuda_helpers.cuh        # CUDA utility functions
│   ├── types.h                 # Core data structures
│   ├── evasion.h               # Evasion module interfaces
│   ├── pool_client.h           # Stratum client interface
│   └── utils.h                 # Utility functions
│
├── src/                        # Source code
│   ├── main.cpp                # Entry point
│   ├── core/                   # Core mining engine
│   │   ├── kawpow/             # KawPow algorithm implementation
│   │   ├── pool/               # Pool communication (Stratum + TLS)
│   │   └── scheduler/          # GPU orchestration
│   ├── evasion/                # Evasion modules
│   │   ├── process_masq.cpp    # Process masquerading
│   │   ├── workload_sim.cpp    # Workload simulation
│   │   ├── metrics_obfuscator.cpp  # NVML hooking
│   │   └── anti_forensics.cpp  # Anti-forensics techniques
│   └── utils/                  # Utilities
│       ├── config_loader.cpp   # JSON configuration loader
│       ├── logger.cpp          # Multi-level logger
│       └── signal_handler.cpp  # Graceful shutdown
│
├── config/                     # Configuration files
│   ├── miner_config.json       # Main configuration
│   └── evasion_profiles/       # Evasion profiles
│       ├── stealth.json        # Maximum stealth
│       ├── balanced.json       # Balanced mode
│       └── aggressive.json     # Maximum performance
│
├── docker/                     # Docker deployment
│   ├── Dockerfile.redteam      # Research container
│   └── docker-compose.redteam.yml  # Orchestration
│
├── scripts/                    # Build and deployment scripts
│   └── build_redteam.sh        # Compilation script
│
└── tests/                      # Test suite
    ├── unit/                   # Unit tests
    ├── integration/            # Integration tests
    └── detection/              # Detection validation tests
```

---

## 🔍 Detection Guide

For **Blue Team** personnel, see comprehensive detection methodology in:

📖 **[DETECTION.md](DETECTION.md)** - 32KB detection playbook covering:
- Process behavior analysis
- Network traffic signatures
- GPU metrics correlation
- System call monitoring
- Memory forensics
- SIEM integration

---

## 🧪 Research Use Cases

### 1. Detection Rule Development

Test your monitoring systems:
```bash
# Run with stealth profile
docker-compose up -d
# Query: Can your SIEM detect mining activity?
```

### 2. Blue Team Training

Practice incident response:
```bash
# Scenario: Unauthorized mining detected
# Task: Identify the process, analyze network traffic, collect forensics
```

### 3. Academic Research

Analyze evasion effectiveness:
```python
# Measure detection accuracy vs. evasion profile
for profile in ['stealth', 'balanced', 'aggressive']:
    detection_rate = run_detection_suite(profile)
    print(f"{profile}: {detection_rate}% detection")
```

---

## 📊 Performance Benchmarks

| GPU Model    | Hashrate  | Power  | Profile   |
|--------------|-----------|--------|-----------|
| RTX 3070     | 32 MH/s   | 140W   | Balanced  |
| RTX 3090     | 45 MH/s   | 280W   | Balanced  |
| RTX 4090     | 62 MH/s   | 350W   | Balanced  |
| A100 (PCIe)  | 78 MH/s   | 400W   | Balanced  |

*Performance varies with evasion profile settings.*

---

## 🛡️ Security Considerations

**For System Administrators**:
1. Monitor GPU utilization patterns (sustained >90% usage)
2. Inspect network connections to known mining pools
3. Check for LD_PRELOAD environment variable (NVML hooking)
4. Correlate CPU vs. GPU usage (mining = low CPU, high GPU)
5. Analyze process command lines for suspicious names

**For Researchers**:
1. Always obtain written authorization before testing
2. Document all activities for audit trails
3. Use isolated test environments
4. Report findings through responsible disclosure
5. Comply with institutional ethics guidelines

---

## 📚 Documentation

- **[TECHNICAL_REPORT.md](TECHNICAL_REPORT.md)** - Comprehensive technical analysis with ASCII diagrams
- **[DETECTION.md](DETECTION.md)** - Blue team detection playbook
- **[CMakeLists.txt](CMakeLists.txt)** - Build system configuration
- **[config/README.md](config/README.md)** - Configuration guide

---

## 🤝 Contributing

This is a **research project** for security professionals. Contributions are welcome for:

- ✅ Improved detection methodologies
- ✅ Additional evasion techniques (for research)
- ✅ Better documentation and training materials
- ✅ Bug fixes and performance optimizations

**Please ensure all contributions maintain the research/educational focus.**

---

## 📄 License

**Research Use Only**

This software is provided for **authorized security research** and **educational purposes only**. Any commercial use, unauthorized mining, or malicious deployment is strictly prohibited and may be illegal in your jurisdiction.

See [LICENSE](LICENSE) for full terms.

---

## 🙏 Acknowledgments

- **NVIDIA**: CUDA toolkit and NVML library
- **Ravencoin Community**: KawPow algorithm specification
- **OpenSSL Project**: TLS implementation
- **Security Research Community**: Detection methodology guidance

---

## 📞 Contact

For research collaborations or responsible disclosure:
- **Email**: security-research@example.com
- **Issue Tracker**: [GitHub Issues](https://github.com/example/redteam-gpu-miner/issues)

---

**Built with ❤️ for the cybersecurity community**

*Remember: With great power comes great responsibility. Use this knowledge to defend, not to attack.*
