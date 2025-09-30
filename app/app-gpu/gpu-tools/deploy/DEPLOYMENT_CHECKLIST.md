# OPUS-GPU Deployment Checklist

## Pre-Deployment

### Environment Setup
- [ ] NVIDIA GPU drivers installed (CUDA 12.0+ compatible)
- [ ] Docker installed (20.10+ with nvidia-docker2 runtime) OR
- [ ] Kubernetes cluster configured with GPU operator OR
- [ ] Systemd-based Linux distribution
- [ ] Network connectivity verified
- [ ] Storage requirements met (10GB+ available)

### Build Artifacts
- [ ] Run `./gpu-tools/deploy/scripts/build.sh`
- [ ] Verify Rust binary: `target/release/gpu-miner`
- [ ] Verify Go tools: `gpu-tools/bin/gpu-ctl`, `gpu-watchdog`, `gpu-monitor`
- [ ] Docker image built: `opus-gpu:latest`

### Configuration
- [ ] Update `config/app.toml` with appropriate values
- [ ] Set wallet address (if mining)
- [ ] Configure GPU settings (max temperature, power limits)
- [ ] Review API authentication settings
- [ ] Configure logging levels

## Docker Deployment

### Pre-Flight
- [ ] Verify nvidia-docker2 runtime: `docker run --rm --gpus all nvidia/cuda:12.0-runtime nvidia-smi`
- [ ] Create config directory: `mkdir -p gpu-tools/deploy/docker/config`
- [ ] Copy configuration: `cp config/app.toml gpu-tools/deploy/docker/config/`
- [ ] Review `docker-compose.yml` settings
- [ ] Update passwords in docker-compose.yml

### Deployment
- [ ] Run: `./gpu-tools/deploy/scripts/deploy.sh docker`
- [ ] Verify services started: `docker-compose ps`
- [ ] Check miner logs: `docker-compose logs -f miner`
- [ ] Test health endpoint: `curl http://localhost:8080/health`
- [ ] Verify GPU metrics: `curl http://localhost:9090/metrics | grep gpu_`

### Post-Deployment
- [ ] Access Grafana dashboard: http://localhost:3000
- [ ] Configure Grafana data source (Prometheus)
- [ ] Import OPUS-GPU dashboard
- [ ] Set up alerts (optional)
- [ ] Configure log rotation
- [ ] Document access credentials

## Kubernetes Deployment

### Pre-Flight
- [ ] Verify kubectl connectivity: `kubectl cluster-info`
- [ ] Check GPU nodes: `kubectl get nodes -l nvidia.com/gpu=true`
- [ ] Verify GPU operator: `kubectl get pods -n gpu-operator-resources`
- [ ] Review namespace configuration: `gpu-tools/deploy/k8s/namespace.yaml`
- [ ] Update secrets: `gpu-tools/deploy/k8s/secret.yaml`

### Configuration
- [ ] Update ConfigMap with correct settings
- [ ] Set resource limits in deployment.yaml
- [ ] Configure node selectors for GPU nodes
- [ ] Review service type (ClusterIP, NodePort, LoadBalancer)
- [ ] Configure persistent volume claims

### Deployment
- [ ] Run: `./gpu-tools/deploy/scripts/deploy.sh k8s`
- [ ] Verify namespace created: `kubectl get ns opus-gpu`
- [ ] Check pods running: `kubectl get pods -n opus-gpu`
- [ ] Wait for deployment: `kubectl rollout status deployment/opus-gpu-miner -n opus-gpu`
- [ ] Test service: `kubectl port-forward svc/opus-gpu-miner 8080:8080 -n opus-gpu`

### Post-Deployment
- [ ] Verify GPU allocation: `kubectl describe pod -n opus-gpu | grep nvidia.com/gpu`
- [ ] Check logs: `kubectl logs -f deployment/opus-gpu-miner -n opus-gpu`
- [ ] Test health endpoint via port-forward
- [ ] Configure ingress (if needed)
- [ ] Set up monitoring (Prometheus operator)
- [ ] Configure backup strategy for PVCs

## Systemd Deployment

### Pre-Flight
- [ ] Root/sudo access confirmed
- [ ] NVIDIA drivers loaded: `nvidia-smi`
- [ ] Binaries built: `./gpu-tools/deploy/scripts/build.sh`
- [ ] User 'miner' exists or will be created
- [ ] Directory permissions planned

### Installation
- [ ] Run: `sudo ./gpu-tools/deploy/scripts/deploy.sh systemd`
- [ ] Verify directories created:
  - [ ] `/opt/opus-gpu/`
  - [ ] `/etc/opus-gpu/`
  - [ ] `/var/log/opus-gpu/`
- [ ] Verify binaries installed: `ls -la /usr/local/bin/gpu-*`
- [ ] Check service file: `systemctl cat opus-gpu`

### Service Management
- [ ] Enable service: `sudo systemctl enable opus-gpu`
- [ ] Start service: `sudo systemctl start opus-gpu`
- [ ] Check status: `systemctl status opus-gpu`
- [ ] Verify logs: `journalctl -u opus-gpu -f`
- [ ] Test health endpoint: `curl http://localhost:8080/health`

### Post-Deployment
- [ ] Configure log rotation: `/etc/logrotate.d/opus-gpu`
- [ ] Set up monitoring alerts
- [ ] Test automatic restart: `sudo systemctl restart opus-gpu`
- [ ] Verify GPU access: `journalctl -u opus-gpu | grep -i gpu`
- [ ] Document service management procedures

## Security Hardening

### Docker
- [ ] Use non-root user (already configured)
- [ ] Enable security options: `no-new-privileges:true`
- [ ] Limit container resources
- [ ] Use read-only volumes where possible
- [ ] Scan image for vulnerabilities: `docker scan opus-gpu:latest`

### Kubernetes
- [ ] Apply Pod Security Standards
- [ ] Use NetworkPolicies to restrict traffic
- [ ] Enable RBAC for service accounts
- [ ] Use secrets for sensitive data (not ConfigMaps)
- [ ] Enable audit logging
- [ ] Configure resource quotas

### Systemd
- [ ] Review security directives in service file
- [ ] Enable `NoNewPrivileges=true`
- [ ] Configure `ProtectSystem=strict`
- [ ] Set up firewall rules (ufw/iptables)
- [ ] Enable SELinux/AppArmor policies (if applicable)

### General
- [ ] Change default passwords
- [ ] Generate strong JWT secrets
- [ ] Enable API authentication
- [ ] Configure TLS/SSL certificates
- [ ] Set up access logging
- [ ] Regular security updates scheduled

## Monitoring & Alerting

### Metrics
- [ ] Prometheus scraping configured
- [ ] Verify metrics endpoint: `/metrics`
- [ ] Key metrics visible:
  - [ ] `mining_hashrate_mhs`
  - [ ] `gpu_temperature_celsius`
  - [ ] `gpu_power_watts`
  - [ ] `gpu_memory_used_bytes`

### Dashboards
- [ ] Grafana dashboard imported
- [ ] Data source configured
- [ ] Panels displaying data correctly
- [ ] Refresh rate appropriate

### Alerts
- [ ] High GPU temperature alert (>85°C)
- [ ] High memory usage alert (>95%)
- [ ] Service down alert
- [ ] Low hashrate alert
- [ ] Notification channels configured (email, Slack, PagerDuty)

## Performance Validation

### Baseline Testing
- [ ] Run benchmark: `gpu-ctl benchmark --duration 60s`
- [ ] Record baseline hashrate
- [ ] Monitor GPU temperature under load
- [ ] Check power consumption
- [ ] Verify no thermal throttling

### Load Testing
- [ ] Sustained operation test (24 hours)
- [ ] Peak performance measurement
- [ ] Stability verification
- [ ] Memory leak check
- [ ] Error rate monitoring

### Optimization
- [ ] Tune batch size for optimal performance
- [ ] Adjust thread count per GPU
- [ ] Configure power limits if needed
- [ ] Verify cooling effectiveness
- [ ] Document optimal settings

## Backup & Recovery

### Configuration Backup
- [ ] Backup configuration files
- [ ] Document custom settings
- [ ] Version control configuration
- [ ] Test configuration restore

### Data Backup (if applicable)
- [ ] Identify data to backup
- [ ] Configure backup schedule
- [ ] Test backup restoration
- [ ] Document recovery procedures

### Disaster Recovery
- [ ] Document recovery steps
- [ ] Create runbook for common issues
- [ ] Test failover procedures (if HA)
- [ ] Establish RTO/RPO targets

## Documentation

### Operational
- [ ] Document deployment method chosen
- [ ] Record configuration decisions
- [ ] Create troubleshooting guide
- [ ] Document access credentials (securely)
- [ ] Create runbook for common tasks

### Technical
- [ ] Architecture diagram
- [ ] Network topology
- [ ] Resource allocation
- [ ] Monitoring setup
- [ ] Security measures

## Handoff

### Knowledge Transfer
- [ ] Walk through deployment
- [ ] Demonstrate monitoring
- [ ] Explain troubleshooting procedures
- [ ] Review security measures
- [ ] Provide access credentials

### Support
- [ ] Escalation procedures defined
- [ ] Contact information documented
- [ ] Issue tracking setup
- [ ] On-call rotation (if applicable)

## Sign-Off

### Deployment Team
- [ ] Infrastructure Engineer: _________________ Date: _______
- [ ] DevOps Engineer: _________________ Date: _______
- [ ] Security Engineer: _________________ Date: _______

### Acceptance
- [ ] Operations Team: _________________ Date: _______
- [ ] Product Owner: _________________ Date: _______

### Notes
```
Additional notes and observations:




```

---

**Deployment Status**: [ ] Not Started | [ ] In Progress | [ ] Complete | [ ] Failed

**Rollback Plan**: ________________________________________________

**Next Review Date**: _______________
