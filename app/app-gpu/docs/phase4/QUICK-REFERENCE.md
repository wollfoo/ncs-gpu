# 🚀 Phase 4 Performance Monitoring - Quick Reference

**Version**: 1.0
**Date**: 2025-10-02

---

## 📊 Benchmark Tools Decision

| Tool | Usage | Justification |
|------|-------|---------------|
| **Criterion.rs** | CPU/coordination overhead, Stratum latency | Industry standard, statistical rigor, CI integration |
| **Custom GPU Harness** | GPU kernel execution, memory bandwidth | Direct CUDA profiling, precise GPU metrics |
| **nvprof/nsys** | Deep GPU debugging (auxiliary) | Official NVIDIA profiling tools |

**Verdict**: **Hybrid approach** - Criterion.rs for CPU workload + Custom GPU Harness for GPU workload

---

## 🎯 Key Benchmark Specifications

### Ethash
- **Hashrate Target**: ≥60 MH/s (RTX 3090)
- **GPU Utilization**: ≥95%
- **Memory Bandwidth**: ≥80% of theoretical peak
- **Variance Threshold**: ±5%

### KawPow
- **Hashrate Target**: ≥30 MH/s (RTX 3090)
- **Power Efficiency**: ≥0.12 MH/W
- **Thermal Stability**: ≤85°C sustained
- **Variance Threshold**: ±5%

### Stratum Latency
- **Getwork P50**: ≤50ms (local), ≤150ms (network)
- **Getwork P95**: ≤100ms (local), ≤300ms (network)
- **Submission P50**: ≤100ms
- **Stale Rate**: ≤2%

---

## 📈 Monitoring Architecture

```
Mining App (:9100) --HTTP Pull--> Prometheus (:9090) --PromQL--> Grafana (:3000)
                                        │
                                        ↓
                              Alert Manager (:9093) ---> [Email, Slack, PagerDuty]
```

**Strategy**: Pull-based scraping (10s interval)
**Retention**: 30 days hot, 1 year cold storage

---

## 🔔 Critical Alert Rules

| Alert | Condition | Threshold | Action |
|-------|-----------|-----------|--------|
| **HighGPUTemperature** | Temp >85°C for 5min | 85°C | Email + Slack + PagerDuty, reduce power |
| **HashrateDropSignificant** | Drop >15% for 5min | -15% | Email + Slack, restart worker |
| **StratumDisconnected** | Disconnected >2min | 2min | Email + Slack, reconnect |
| **HighShareRejectionRate** | Rejection >5% for 5min | 5% | Slack, log reasons |

---

## 📊 Core Prometheus Metrics (25 Total)

**Hashrate**:
- `mining_hashrate_mhs{device_id, algorithm}`
- `mining_hashrate_peak_mhs{device_id, algorithm}`
- `mining_hashrate_average_1m_mhs{device_id, algorithm}`

**Shares**:
- `mining_shares_submitted_total{device_id, pool}`
- `mining_shares_accepted_total{device_id, pool}`
- `mining_shares_rejected_total{device_id, pool, reason}`
- `mining_share_acceptance_rate{device_id, pool}`

**GPU Health**:
- `gpu_temperature_celsius{device_id, gpu_model}`
- `gpu_utilization_percent{device_id, gpu_model}`
- `gpu_memory_used_bytes{device_id, gpu_model}`
- `gpu_power_usage_watts{device_id, gpu_model}`

**Stratum**:
- `stratum_getwork_latency_ms{pool_url}` (histogram)
- `stratum_share_submission_latency_ms{pool_url}` (histogram)
- `stratum_reconnects_total{pool_url, reason}`

---

## 🏗️ Docker Compose Stack

**Services**:
1. `mining-app` - GPU mining with Prometheus exporter on :9100
2. `prometheus` - Metrics server on :9090
3. `grafana` - Dashboards on :3000
4. `alertmanager` - Alert routing on :9093

**Storage**:
- Prometheus: 100GB SSD
- Grafana: 10GB SSD
- Total: ~135GB per node

**Deploy**:
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```

---

## 🛠️ Implementation Roadmap

### Wave 3: Benchmarks (Week 13-14)
- [ ] Setup Criterion.rs infrastructure (2 days)
- [ ] Implement GPU benchmark harness (3 days)
- [ ] Establish baselines (2 days)
- [ ] CI/CD integration (1 day)

### Wave 4: Monitoring (Week 15-16)
- [ ] Implement Prometheus exporter (3 days)
- [ ] Deploy Prometheus server (1 day)
- [ ] Create Grafana dashboards (2 days)
- [ ] Configure Alert Manager (1 day)
- [ ] Docker Compose integration (1 day)

**Total Duration**: 2 weeks (14 days)

---

## ✅ Success Criteria

**Wave 3**:
- ✅ Benchmarks runnable via `cargo bench`
- ✅ Baselines established with ±5% variance
- ✅ CI regression detection working

**Wave 4**:
- ✅ Prometheus collecting from all nodes
- ✅ Grafana dashboards visualizing performance
- ✅ Alerts sending notifications
- ✅ Full stack deployable via Docker Compose

---

## 🔗 Full Documentation

**Main Document**: `docs/phase4/performance-monitoring.md` (15,000+ words)

**Sections**:
1. Benchmark Tool Selection
2. Detailed Benchmark Specifications
3. Baseline Establishment Strategy
4. Monitoring Architecture
5. Alerting Rules Framework
6. Infrastructure Requirements
7. Implementation Roadmap

---

**Status**: ✅ **DESIGN COMPLETE - READY FOR IMPLEMENTATION**
**Next Action**: Begin Wave 3 benchmark implementation
