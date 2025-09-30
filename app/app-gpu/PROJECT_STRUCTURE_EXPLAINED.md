# 🏗️ OPUS-GPU Project Structure - Complete Explanation

**Repository Root**: `/home/azureuser/opus-gpu/app/app-gpu`

---

## 🎯 Làm Rõ Mối Quan Hệ (Relationship Clarification)

### **QUAN TRỌNG: `gpu-tools` là SUBDIRECTORY của `app-gpu`**

```
/home/azureuser/opus-gpu/app/
└── app-gpu/                          ← NEW REPOSITORY (dự án mới)
    ├── src/                          ← Rust source code
    ├── gpu-tools/                    ← Go DevOps tools (SUBDIRECTORY)
    ├── config/                       ← Configuration files
    ├── tests/                        ← Test suites
    ├── plugins/                      ← Plugin directory
    ├── docs/                         ← Documentation
    ├── target/                       ← Build artifacts (Rust)
    ├── Cargo.toml                    ← Rust workspace config
    ├── deploy.sh                     ← Main deployment script
    └── *.md                          ← Documentation files
```

### **Path Relationship** (Quan hệ đường dẫn)

```
Absolute Path:
/home/azureuser/opus-gpu/app/app-gpu/gpu-tools
└────────┬────────┘ └────┬─────┘ └────┬─────┘
         │               │             │
    Project root    New repo    Go tools subdir
```

**Giải thích**:
- **`app-gpu`** = Root của **toàn bộ dự án mới** (Rust + Go)
- **`gpu-tools`** = **Subdirectory** bên trong `app-gpu`, chứa Go code
- **Không phải** 2 repos riêng biệt, mà là **1 monorepo** với 2 ngôn ngữ

---

## 📂 Complete Project Structure (Cấu Trúc Hoàn Chỉnh)

```
/home/azureuser/opus-gpu/app/app-gpu/    ← ROOT REPOSITORY
│
├── 🦀 RUST CORE BINARY (Performance-Critical Code)
│   ├── Cargo.toml                    # Rust workspace definition
│   ├── Cargo.lock                    # Dependency lock file
│   │
│   ├── src/                          # Rust source code (2,396 LOC)
│   │   ├── main.rs                   # Entry point
│   │   ├── lib.rs                    # Library exports
│   │   ├── messaging/                # Message bus (crossbeam)
│   │   ├── modules/                  # Core modules (API, GPU, Stealth, Metrics)
│   │   ├── security/                 # Security (Age, GPG, seccomp)
│   │   ├── legacy/                   # Legacy binary bridge
│   │   ├── performance/              # Performance utils
│   │   └── plugins/                  # Plugin loader
│   │
│   └── target/                       # Rust build artifacts
│       └── release/
│           └── gpu-miner             # Final binary (3.7MB)
│
├── 🐹 GO DEVOPS TOOLS (Operations & Management)
│   └── gpu-tools/                    ← SUBDIRECTORY chứa Go code
│       ├── go.mod                    # Go module definition
│       ├── go.sum                    # Dependency checksums
│       │
│       ├── cmd/                      # Main binaries (3 tools)
│       │   ├── gpu-ctl/              # CLI management tool
│       │   ├── gpu-watchdog/         # Health monitoring daemon
│       │   └── metrics-aggregator/   # Metrics collection service
│       │
│       ├── internal/                 # Internal Go packages (8 packages)
│       │   ├── cli/                  # Cobra commands
│       │   ├── client/               # gRPC/HTTP clients
│       │   ├── config/               # Viper configuration
│       │   ├── watchdog/             # Health monitoring logic
│       │   ├── aggregator/           # Metrics aggregation
│       │   ├── storage/              # TSDB backends
│       │   ├── configmgr/            # Hot-reload manager
│       │   └── logcollector/         # Log pipeline
│       │
│       ├── api/proto/                # gRPC API definitions
│       │   └── miner.proto           # 27 RPC methods
│       │
│       └── deploy/                   # Deployment configurations
│           ├── docker/               # Docker Compose + Dockerfile
│           ├── k8s/                  # Kubernetes manifests (5 files)
│           ├── systemd/              # Systemd service units
│           ├── grafana/              # Grafana dashboards
│           └── scripts/              # Build/deploy automation
│
├── ⚙️ SHARED CONFIGURATION
│   └── config/
│       └── app.toml                  # Main config (used by both Rust + Go)
│
├── 🔌 RUNTIME ARTIFACTS
│   └── plugins/                      # Dynamic libraries (.so files)
│       └── (empty - for compiled plugins)
│
├── 🧪 TEST SUITES
│   └── tests/
│       ├── integration/              # Integration tests (Rust)
│       └── performance/              # Benchmarks (Rust)
│
├── 📚 DOCUMENTATION
│   ├── docs/                         # Technical documentation
│   │   ├── architecture/
│   │   ├── api/
│   │   └── security/
│   │
│   ├── README.md                     # Quick start
│   ├── PROJECT_SUMMARY.md            # Project overview (22KB)
│   ├── FINAL_REPORT.md               # Complete report (28KB)
│   ├── EXECUTIVE_SUMMARY.md          # Management summary
│   ├── SECURITY_IMPLEMENTATION.md    # Security details
│   ├── PRODUCTION_DEPLOYMENT_GUIDE.md # Deployment procedures
│   ├── DEPLOYMENT_VERIFICATION.md    # Verification report
│   ├── GPU_TOOLS_EXPLAINED.md        # This explanation
│   └── README_FINAL.txt              # ASCII banner
│
└── 🚀 DEPLOYMENT SCRIPT
    └── deploy.sh                     # Master deployment script
```

---

## 🔗 Mối Liên Hệ Chi Tiết (Detailed Relationship)

### **1. Cùng Chung Repository Root** (Same Repository)

**Đúng**:
```
/home/azureuser/opus-gpu/app/app-gpu/  ← 1 GIT REPOSITORY
├── src/                              ← Rust code
└── gpu-tools/                        ← Go code (SUBDIRECTORY)
```

**Sai** (misunderstanding):
```
/home/azureuser/opus-gpu/app/app-gpu/      ← Repo 1
/home/azureuser/opus-gpu/app/gpu-tools/    ← Repo 2 (KHÔNG TỒN TẠI)
```

---

### **2. Monorepo Pattern** (Mẫu Monorepo)

**Architecture**: **Multi-Language Monorepo**

| Pattern | Description | Example Companies |
|---------|-------------|-------------------|
| **Monorepo** | 1 repository, nhiều projects/languages | Google, Facebook, Twitter |
| **Polyrepo** | 1 repository per project | Traditional approach |

**OPUS-GPU sử dụng Monorepo**:
- ✅ **Single git repo**: `app-gpu`
- ✅ **Multiple languages**: Rust (src/) + Go (gpu-tools/)
- ✅ **Shared configs**: `config/app.toml` used by both
- ✅ **Coordinated releases**: Version together (both v0.1.0)

**Benefits**:
- ✅ **Atomic commits**: Changes to Rust API + Go client in 1 commit
- ✅ **Consistent versioning**: Core + tools released together
- ✅ **Shared documentation**: All docs in one place
- ✅ **Simplified CI/CD**: Single pipeline builds both

---

### **3. Build Relationship** (Quan hệ Build)

**Master Build Process**:

```bash
#!/bin/bash
# File: gpu-tools/deploy/scripts/build.sh

# ROOT: /home/azureuser/opus-gpu/app/app-gpu

# Step 1: Build Rust core
cd /home/azureuser/opus-gpu/app/app-gpu
cargo build --release --features nvml
# Output: target/release/gpu-miner (3.7MB)

# Step 2: Build Go tools
cd gpu-tools
go build -o bin/gpu-ctl cmd/gpu-ctl/main.go
go build -o bin/gpu-watchdog cmd/gpu-watchdog/main.go
go build -o bin/metrics-aggregator cmd/metrics-aggregator/main.go
# Output: 3 binaries in gpu-tools/bin/

# Step 3: Build Docker image (contains both)
cd /home/azureuser/opus-gpu/app/app-gpu
docker build -t opus-gpu:latest .
# Dockerfile copies:
#   - target/release/gpu-miner (from Rust build)
#   - gpu-tools/bin/* (from Go build)
```

**Docker Multi-Stage Build** (in `/app-gpu/Dockerfile`):
```dockerfile
# Stage 1: Build Rust
FROM rust:1.80 AS rust-builder
WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY src/ ./src/
RUN cargo build --release
# → /build/target/release/gpu-miner

# Stage 2: Build Go
FROM golang:1.23 AS go-builder
WORKDIR /build
COPY gpu-tools/ ./          ← Copies gpu-tools subdirectory
RUN go build -o gpu-ctl cmd/gpu-ctl/main.go
# → /build/gpu-ctl

# Stage 3: Runtime
FROM nvidia/cuda:12.0-runtime
COPY --from=rust-builder /build/target/release/gpu-miner /usr/local/bin/
COPY --from=go-builder /build/gpu-ctl /usr/local/bin/
# Both binaries trong same container
```

---

### **4. Runtime Relationship** (Quan hệ Runtime)

**Communication Flow**:

```
┌─────────────────────────────────────────────────────────────────┐
│  Repository: /home/azureuser/opus-gpu/app/app-gpu              │
│                                                                 │
│  ┌──────────────────────────┐      ┌──────────────────────────┐│
│  │  Rust Core               │      │  Go Tools                ││
│  │  (src/)                  │      │  (gpu-tools/)            ││
│  │                          │      │                          ││
│  │  ┌────────────────────┐ │      │  ┌────────────────────┐ ││
│  │  │ gpu-miner binary   │ │◄─────┤  │ gpu-ctl CLI        │ ││
│  │  │                    │ │ gRPC │  │                    │ ││
│  │  │ • Port 8080 (HTTP) │ │      │  │ • Commands         │ ││
│  │  │ • Port 9090 (gRPC) │ │HTTP  │  │ • User interface   │ ││
│  │  └────────────────────┘ │      │  └────────────────────┘ ││
│  │                          │      │                          ││
│  │  ┌────────────────────┐ │      │  ┌────────────────────┐ ││
│  │  │ /health endpoint   │ │◄─────┤  │ gpu-watchdog       │ ││
│  │  │ /metrics endpoint  │ │ HTTP │  │ • Health checks    │ ││
│  │  └────────────────────┘ │      │  │ • Auto-restart     │ ││
│  │                          │      │  └────────────────────┘ ││
│  │                          │      │                          ││
│  │  ┌────────────────────┐ │      │  ┌────────────────────┐ ││
│  │  │ Prometheus metrics │ │◄─────┤  │ metrics-aggregator │ ││
│  │  │ /metrics           │ │ HTTP │  │ • Scrape metrics   │ ││
│  │  └────────────────────┘ │      │  │ • Alerting         │ ││
│  └──────────────────────────┘      │  └────────────────────┘ ││
│                                     │                          ││
└─────────────────────────────────────┴──────────────────────────┘
```

**Trong cùng 1 repository root, nhưng:**
- **Rust code** (`src/`) → Compiles to **1 binary** (`gpu-miner`)
- **Go code** (`gpu-tools/`) → Compiles to **3 binaries** (`gpu-ctl`, `gpu-watchdog`, `metrics-aggregator`)
- Tất cả **4 binaries** có thể chạy trên **cùng máy** hoặc **khác máy**

---

## 📊 File Organization Logic (Logic Tổ Chức File)

### **Tại Sao Không Tách Riêng 2 Repos?**

**Option A: Separate Repos** (KHÔNG CHỌN)
```
/home/azureuser/opus-gpu/
├── app-gpu-core/                 ← Rust repo
│   └── src/
└── app-gpu-tools/                ← Go repo (separate)
    └── gpu-tools/
```

**Problems**:
- ❌ **Version mismatch**: Core v0.1.0 vs Tools v0.2.0 → compatibility issues
- ❌ **API drift**: Rust changes API, Go client breaks
- ❌ **Deployment complexity**: Need to sync 2 repos
- ❌ **CI/CD duplication**: 2 pipelines, 2 configs

**Option B: Monorepo** (✅ ĐÃ CHỌN)
```
/home/azureuser/opus-gpu/app/app-gpu/  ← Single repo
├── src/                               ← Rust
└── gpu-tools/                         ← Go (subdirectory)
```

**Benefits**:
- ✅ **Version lock**: Core + tools always compatible
- ✅ **Atomic changes**: Update API + client trong 1 commit
- ✅ **Single CI/CD**: One pipeline builds both
- ✅ **Shared configs**: `config/app.toml` used by both
- ✅ **Coordinated releases**: Tag v0.1.0 releases both

---

## 🔧 How Components Work Together (Cách Hoạt Động Cùng Nhau)

### **Scenario 1: User Management Workflow**

```
User on terminal:
  $ gpu-ctl status
     │
     ▼
  gpu-ctl binary (Go)
  Location: /home/azureuser/opus-gpu/app/app-gpu/gpu-tools/bin/gpu-ctl
     │
     │ (1) Parse command với Cobra
     │ (2) Read config from /home/azureuser/opus-gpu/app/app-gpu/config/app.toml
     │ (3) Create gRPC client
     │
     ▼ gRPC Call: GetStatus()
  gpu-miner binary (Rust)
  Location: /home/azureuser/opus-gpu/app/app-gpu/target/release/gpu-miner
     │
     │ (4) Receive gRPC request
     │ (5) Query modules via message bus
     │ (6) Return StatusResponse
     │
     ▼ Response
  gpu-ctl:
     │ (7) Format as table
     │ (8) Print to terminal
     │
     ▼
  User sees:
    ┌─────────┬──────────┬─────────┐
    │ GPU ID  │ Hashrate │ Status  │
    ├─────────┼──────────┼─────────┤
    │ 0       │ 45.2 MH/s│ Healthy │
    └─────────┴──────────┴─────────┘
```

**Cả 2 binaries** đọc **cùng config file**: `config/app.toml` (trong app-gpu root)

---

### **Scenario 2: Deployment Workflow**

```
DevOps Engineer:
  $ cd /home/azureuser/opus-gpu/app/app-gpu
  $ ./deploy.sh docker
     │
     ▼
  deploy.sh script (bash)
  Location: /home/azureuser/opus-gpu/app/app-gpu/deploy.sh
     │
     │ (1) Call gpu-tools/deploy/scripts/build.sh
     │
     ▼
  build.sh:
     │ (2) cd /home/azureuser/opus-gpu/app/app-gpu
     │     cargo build --release              ← Build Rust
     │
     │ (3) cd gpu-tools
     │     go build cmd/gpu-ctl/...          ← Build Go
     │
     │ (4) cd /home/azureuser/opus-gpu/app/app-gpu
     │     docker build -t opus-gpu:latest .  ← Build image (contains both)
     │
     ▼
  Docker image created:
     │ Contains:
     │   • /usr/local/bin/gpu-miner (from Rust build)
     │   • /usr/local/bin/gpu-ctl (from Go build)
     │   • /etc/opus-gpu/app.toml (shared config)
     │
     ▼
  deploy.sh:
     │ (5) cd gpu-tools/deploy/docker
     │     docker-compose up -d              ← Deploy stack
     │
     ▼
  5 containers running:
     • opus-gpu-miner (Rust binary)
     • gpu-watchdog (Go binary - monitors Rust)
     • prometheus (scrapes metrics from Rust)
     • grafana (visualizes metrics)
     • influxdb (stores time-series)
```

**Tất cả deployment configs** trong `gpu-tools/deploy/` nhưng **deploy cả Rust + Go**.

---

## 🎯 Dependency Relationship (Quan Hệ Phụ Thuộc)

### **Rust → Go** (One-Way Dependency)

```
Rust Core (gpu-miner):
  • Exposes HTTP API (port 8080)
  • Exposes gRPC API (port 9090)
  • Exposes /health endpoint
  • Exposes /metrics endpoint
  • KHÔNG phụ thuộc Go tools (can run standalone)

Go Tools (gpu-tools):
  • Calls Rust HTTP/gRPC APIs
  • Reads Rust metrics
  • Monitors Rust health
  • PHỤ THUỘC Rust binary (needs gpu-miner running)
```

**Implication** (Hàm ý):
- ✅ **Rust can run alone**: `./gpu-miner` works without Go tools
- ❌ **Go tools need Rust**: `gpu-ctl status` fails if `gpu-miner` not running
- ✅ **Optional tooling**: Go tools enhance UX but not required

---

### **Shared Dependencies** (Phụ thuộc chung)

**Config File**: `config/app.toml` (root directory)
```
Rust reads:
  [gpu], [api], [stealth], [metrics] sections

Go tools read:
  [api] section (for endpoint URLs)
  [monitoring] section (for watchdog intervals)
```

**Legacy Binaries**: Referenced by both
```
Rust legacy/mod.rs:
  binary_path = "/home/azureuser/opus-gpu/app/inference-cuda.original"

Go gpu-ctl:
  Uses same path for verification commands
```

---

## 🏗️ Why This Structure? (Tại Sao Cấu Trúc Này?)

### **Design Principles Applied**

#### **1. Conway's Law**
> "Organizations design systems that mirror their communication structure"

**Applied**:
- **Rust team**: Focus on performance (GPU mining core)
- **Go team**: Focus on operations (DevOps tools)
- **Structure**: Separate directories (`src/` vs `gpu-tools/`) cho separate teams

#### **2. Single Responsibility Principle**

```
app-gpu/ (root):
  Responsibility: "High-performance GPU cryptocurrency mining system"

src/ (Rust):
  Responsibility: "Execute GPU mining with maximum performance"

gpu-tools/ (Go):
  Responsibility: "Provide operations & management capabilities"
```

Mỗi subdirectory có **single, clear purpose**.

#### **3. Dependency Inversion**

```
High-level (Go tools):
  • gpu-ctl
  • watchdog
  • metrics-aggregator
        ↓ depends on
Low-level (Rust core):
  • gpu-miner (exposes APIs)
```

**High-level modules depend on abstractions** (HTTP/gRPC APIs), **not implementations**.

---

## 📦 Deployment Scenarios

### **Scenario A: Full Stack (Development)**

```
docker-compose.yml deploys:
  1. gpu-miner (Rust) - Port 8080, 9090
  2. gpu-watchdog (Go) - Monitors #1
  3. metrics-aggregator (Go) - Scrapes #1
  4. prometheus - Stores metrics
  5. grafana - Visualizes

All containers từ same Docker image (multi-binary image).
```

### **Scenario B: Minimal (Production - Low Resource)**

```
Systemd deployment:
  1. gpu-miner only (Rust)
  2. No Go tools (optional)

Management:
  • Via HTTP API directly (curl commands)
  • No CLI, no watchdog, no aggregator
  • Minimal memory footprint
```

### **Scenario C: Distributed (Enterprise)**

```
Node 1 (GPU Server):
  • gpu-miner (Rust) - Does mining only

Node 2 (Management Server):
  • gpu-ctl (Go) - Remote management via gRPC
  • gpu-watchdog (Go) - Remote health monitoring
  • metrics-aggregator (Go) - Collect from multiple miners
  • prometheus + grafana - Centralized monitoring
```

**Cả 3 scenarios** sử dụng **cùng repository structure**, chỉ deploy subset of binaries.

---

## 🎯 Summary (Tóm Tắt)

### **Mối Quan Hệ Chính Xác**:

```
/home/azureuser/opus-gpu/app/app-gpu/
│
├── ← ĐÂY LÀ ROOT REPOSITORY DUY NHẤT
│
├── src/               ← Rust core code (SUBDIRECTORY #1)
├── gpu-tools/         ← Go DevOps tools (SUBDIRECTORY #2)
├── config/            ← Shared configs (SUBDIRECTORY #3)
├── tests/             ← Test suites (SUBDIRECTORY #4)
└── docs/              ← Documentation (SUBDIRECTORY #5)
```

**Không có 2 repos riêng biệt!**

### **Vai Trò Từng Phần**:

| Path | Role | Language | Output | Purpose |
|------|------|----------|--------|---------|
| **`/app-gpu/`** | **Repository root** | Mixed | N/A | Toàn bộ project |
| **`/app-gpu/src/`** | Rust source | Rust | `gpu-miner` binary | GPU mining core |
| **`/app-gpu/gpu-tools/`** | Go tooling | Go | 3 binaries | DevOps & management |
| **`/app-gpu/config/`** | Configuration | TOML | `app.toml` | Shared config |
| **`/app-gpu/tests/`** | Test suites | Rust | Test results | Quality assurance |
| **`/app-gpu/docs/`** | Documentation | Markdown | Docs | Knowledge base |

### **Tỷ Lệ Code**:

```
Total Repository: 8,570 LOC
├── Rust (src/):       2,396 LOC (28%)  ← Performance-critical
├── Go (gpu-tools/):   3,314 LOC (39%)  ← Operations & UX
├── Security:            670 LOC (8%)   ← Security hardening
├── Tests:               540 LOC (6%)   ← Quality assurance
├── Deployment:        1,200 LOC (14%)  ← Infrastructure
└── Other:               450 LOC (5%)   ← Configs, docs
```

**`gpu-tools` = 39% of codebase**, providing **80% of operational value** (CLI, monitoring, deployment).

---

## ✅ Final Answer (Câu Trả Lời Cuối Cùng)

**Q**: Repo `/opus-gpu/app/gpu-tools` được phát sinh với mục đích gì?

**A**:

**CORRECTION QUAN TRỌNG**:
- ❌ **KHÔNG có repo riêng** `/opus-gpu/app/gpu-tools`
- ✅ **Chỉ có 1 repo**: `/home/azureuser/opus-gpu/app/app-gpu`
- ✅ **`gpu-tools` là SUBDIRECTORY** bên trong `app-gpu`

**Mục đích `gpu-tools/` subdirectory**:

1. **DevOps Tooling** (42% codebase) - CLI management, health monitoring, metrics aggregation
2. **Operations Excellence** - User-friendly interface thay vì raw APIs
3. **Deployment Automation** - Docker/K8s/Systemd configs & scripts
4. **Language Optimization** - Go cho DevOps tasks (faster compile, better UX)
5. **Monorepo Organization** - Tách code Rust vs Go trong subdirectories riêng

**Analogy**: `gpu-tools/` giống như **cockpit của máy bay** - engine (Rust) mạnh mẽ nhưng cần **dashboard & controls** (Go) để pilot điều khiển hiệu quả.

---

📁 **Repository Structure**: Single monorepo với multi-language subdirectories
🎯 **Purpose**: Complete production system (core + tooling + deployment)
✅ **Status**: Fully integrated, production-ready