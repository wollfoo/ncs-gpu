# 🔐 OPUS-GPU Security Guide

**Version**: 0.1.0-alpha
**Last Updated**: 2025-09-30
**Security Level**: Development (Target: Production-ready v0.2.0)

---

## Table of Contents

- [Security Overview](#security-overview)
- [Threat Model](#threat-model)
- [Security Architecture](#security-architecture)
- [Implemented Mitigations](#implemented-mitigations)
- [Planned Security Features](#planned-security-features)
- [Best Practices](#best-practices)
- [Incident Response](#incident-response)
- [Responsible Disclosure](#responsible-disclosure)

---

## Security Overview

### Current Security Posture (v0.1.0-alpha)

| Category | Status | Score |
|----------|--------|-------|
| **Application Security** | ⚠️ Partial | 6/10 |
| **Process Isolation** | ❌ Not Implemented | 3/10 |
| **Secrets Management** | ❌ Not Implemented | 2/10 |
| **Supply Chain** | ⚠️ Basic | 5/10 |
| **Observability** | ✅ Implemented | 8/10 |
| **Overall Score** | ⚠️ Development | 5/10 |

**Target Score** (v0.2.0): 8/10

### Security Principles

1. **Defense-in-Depth** - Multiple layers of security controls
2. **Least Privilege** - Minimal permissions required
3. **Fail-Safe Defaults** - Secure by default configuration
4. **Complete Mediation** - Every access checked
5. **Open Design** - Security through design, not obscurity

---

## Threat Model

### Threat Actors

| Actor | Motivation | Capability | Likelihood |
|-------|------------|------------|------------|
| **External Attacker** | Steal resources, disrupt service | High | Medium |
| **Malicious Insider** | Sabotage, data theft | Medium | Low |
| **Supply Chain Attacker** | Inject malware | High | Medium |
| **Automated Bot** | Cryptocurrency theft | Low | High |

### Attack Vectors

```
Attack Surface Analysis:

1. Network Exposure
   ├─ HTTP API (port 8080)
   │  ├─ Unauthenticated endpoints
   │  ├─ No rate limiting
   │  └─ No input validation
   │
   ├─ Metrics endpoint (port 9090)
   │  └─ Information disclosure
   │
   └─ Mining pool connection (port 3333)
      └─ Man-in-the-middle risk

2. Process Vulnerabilities
   ├─ Binary tampering
   ├─ Memory corruption
   └─ Privilege escalation

3. Configuration Risks
   ├─ Plaintext secrets
   ├─ Weak file permissions
   └─ Environment variable leakage

4. Supply Chain
   ├─ Malicious dependencies
   ├─ Compromised build pipeline
   └─ Unsigned binaries

5. Container Escape
   ├─ Privileged containers
   ├─ Host namespace sharing
   └─ Kernel exploits
```

### Threat Scenarios

**Scenario 1: API Exploitation**
```
Threat: Unauthenticated API access
Impact: Service disruption, unauthorized control
Likelihood: High (no authentication in v0.1.0)
Mitigation: Implement JWT authentication (v0.2.0)
```

**Scenario 2: Credential Theft**
```
Threat: Wallet address stolen from config file
Impact: Cryptocurrency theft
Likelihood: Medium (plaintext config)
Mitigation: Age encryption + OS keyring
```

**Scenario 3: Supply Chain Attack**
```
Threat: Malicious dependency injected
Impact: Complete system compromise
Likelihood: Medium
Mitigation: Dependency auditing, signature verification
```

**Scenario 4: Container Escape**
```
Threat: Attacker escapes Docker container
Impact: Host system compromise
Likelihood: Low (requires privileged container)
Mitigation: Capability dropping, seccomp filters
```

---

## Security Architecture

### Defense-in-Depth Layers

```
┌────────────────────────────────────────────┐
│  Layer 1: Application Security             │
│  • Input validation                        │
│  • Authentication (v0.2.0)                 │
│  • Authorization                           │
│  • Rate limiting                           │
└────────┬───────────────────────────────────┘
         │
┌────────▼───────────────────────────────────┐
│  Layer 2: Process Isolation                │
│  • Capability dropping (CAP_NET_BIND_SERVICE)│
│  • Seccomp filters (syscall allowlist)    │
│  • Namespaces (PID, network, mount)       │
└────────┬───────────────────────────────────┘
         │
┌────────▼───────────────────────────────────┐
│  Layer 3: Secrets Management               │
│  • Age encryption (config files)           │
│  • OS keyring integration                  │
│  • Zero environment vars for credentials   │
└────────┬───────────────────────────────────┘
         │
┌────────▼───────────────────────────────────┐
│  Layer 4: Supply Chain Security            │
│  • Dependency auditing (cargo audit)       │
│  • GPG signature verification              │
│  • SBOM generation                         │
│  • Reproducible builds                     │
└────────┬───────────────────────────────────┘
         │
┌────────▼───────────────────────────────────┐
│  Layer 5: Observability & Response         │
│  • Audit logging (all security events)     │
│  • Anomaly detection                       │
│  • Incident response procedures            │
│  • Security metrics (Prometheus)           │
└────────────────────────────────────────────┘
```

---

## Implemented Mitigations

### 1. Audit Logging ✅

**Status**: Implemented

**Implementation**:
```rust
use tracing::{info, warn, error};

// Security event logging
info!(
    security_event = "api_access",
    endpoint = "/api/v1/status",
    source_ip = "192.168.1.100",
    "API access logged"
);

warn!(
    security_event = "authentication_failure",
    username = "admin",
    source_ip = "192.168.1.100",
    "Failed login attempt"
);
```

**Audit Events**:
- API endpoint access
- Configuration changes
- Process startup/shutdown
- GPU device access
- Plugin loading

### 2. Structured Logging ✅

**Status**: Implemented

**Format**: JSON (machine-readable)

**Example**:
```json
{
  "timestamp": "2025-09-30T10:30:45Z",
  "level": "INFO",
  "target": "opus_gpu::modules::api",
  "fields": {
    "message": "API server started",
    "bind_address": "0.0.0.0:8080"
  }
}
```

### 3. Type-Safe Error Handling ✅

**Status**: Implemented

**Implementation**:
```rust
use thiserror::Error;

#[derive(Error, Debug)]
pub enum MinerError {
    #[error("GPU error: {0}")]
    Gpu(String),

    #[error("API error: {0}")]
    Api(String),

    #[error("Configuration error: {0}")]
    Config(String),
}

// No silent failures
fn operation() -> Result<(), MinerError> {
    Err(MinerError::Gpu("CUDA error".to_string()))
}
```

---

## Planned Security Features

### Phase 5 Security Roadmap

#### 1. Secrets Management (P0)

**Goal**: Eliminate plaintext secrets in configuration.

**Implementation**:

```bash
# 1. Age Encryption
age-keygen -o /etc/opus-gpu/age-key.txt
age -e -i /etc/opus-gpu/age-key.txt -o config.toml.age config.toml

# 2. OS Keyring Integration
# Store wallet in system keyring
secret-tool store --label="OPUS Wallet" service opus-gpu username wallet

# 3. Retrieve at runtime
wallet=$(secret-tool lookup service opus-gpu username wallet)
```

**Configuration**:
```toml
[secrets]
encryption = "age"
keyring_service = "opus-gpu"
allow_env_vars = false  # Disable environment variable secrets
```

#### 2. Binary Trust (P0)

**Goal**: Verify binary integrity.

**Implementation**:

```bash
# 1. Generate GPG key
gpg --full-generate-key

# 2. Sign binary
gpg --detach-sign --armor target/release/gpu-miner
# Creates gpu-miner.asc

# 3. Verify signature
gpg --verify gpu-miner.asc target/release/gpu-miner

# 4. SBOM generation
cargo install cargo-sbom
cargo sbom > opus-gpu-sbom.json
```

**Verification in Code**:
```rust
use gpgme::{Context, Protocol};

fn verify_binary_signature(binary_path: &str) -> Result<bool> {
    let mut ctx = Context::from_protocol(Protocol::OpenPgp)?;
    let signature = std::fs::read(format!("{}.asc", binary_path))?;
    let data = std::fs::read(binary_path)?;

    let result = ctx.verify_detached(&signature, &data)?;
    Ok(result.is_valid())
}
```

#### 3. Capability Dropping (P1)

**Goal**: Run with minimal Linux capabilities.

**Implementation**:
```rust
use caps::{Capability, CapSet};

fn drop_capabilities() -> Result<()> {
    // Keep only CAP_NET_BIND_SERVICE (bind to ports <1024)
    caps::clear(None, CapSet::Permitted)?;
    caps::set(None, CapSet::Permitted, &[Capability::CAP_NET_BIND_SERVICE])?;
    caps::set(None, CapSet::Effective, &[Capability::CAP_NET_BIND_SERVICE])?;

    info!("Dropped all capabilities except CAP_NET_BIND_SERVICE");
    Ok(())
}
```

**Systemd Service**:
```ini
[Service]
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
AmbientCapabilities=CAP_NET_BIND_SERVICE
```

#### 4. Seccomp Filters (P1)

**Goal**: Restrict system calls.

**Implementation**:
```rust
use seccompiler::{BpfProgram, SeccompAction, SeccompFilter};

fn apply_seccomp_filter() -> Result<()> {
    let mut filter = SeccompFilter::new(
        vec![
            // Allow essential syscalls
            (libc::SYS_read, vec![]),
            (libc::SYS_write, vec![]),
            (libc::SYS_open, vec![]),
            (libc::SYS_close, vec![]),
            (libc::SYS_mmap, vec![]),
            (libc::SYS_munmap, vec![]),
            (libc::SYS_futex, vec![]),
            (libc::SYS_ioctl, vec![]),  // CUDA driver
            // ... GPU-specific syscalls
        ]
        .into_iter()
        .collect(),
        SeccompAction::Errno(libc::EPERM),  // Deny unlisted syscalls
    )?;

    filter.apply()?;
    info!("Applied seccomp filter");
    Ok(())
}
```

**Allowlist**:
```
Essential Syscalls:
├─ read, write, open, close
├─ mmap, munmap, mprotect
├─ futex, clone, exit
├─ ioctl (CUDA driver)
└─ socket, connect (pool connection)

Blocked Syscalls:
├─ execve (no child processes)
├─ ptrace (no debugging)
├─ kexec_load (no kernel loading)
└─ reboot (no system control)
```

#### 5. API Authentication (P0)

**Goal**: Secure API endpoints.

**Implementation**:
```rust
use jsonwebtoken::{encode, decode, Header, Validation, EncodingKey, DecodingKey};
use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize)]
struct Claims {
    sub: String,  // Username
    exp: usize,   // Expiration time
    role: String, // User role
}

async fn login_handler(credentials: Credentials) -> Result<Response> {
    // Validate credentials (bcrypt password hash)
    if !verify_credentials(&credentials) {
        return Err(Error::Unauthorized);
    }

    // Generate JWT token
    let claims = Claims {
        sub: credentials.username,
        exp: chrono::Utc::now().timestamp() as usize + 3600,  // 1 hour
        role: "admin".to_string(),
    };

    let token = encode(&Header::default(), &claims, &EncodingKey::from_secret(b"secret"))?;

    Ok(Response::json(json!({ "token": token })))
}

// Middleware for protected endpoints
async fn auth_middleware(req: Request, next: Next) -> Result<Response> {
    let token = req.headers()
        .get("Authorization")
        .and_then(|h| h.to_str().ok())
        .and_then(|h| h.strip_prefix("Bearer "))
        .ok_or(Error::Unauthorized)?;

    let claims = decode::<Claims>(
        token,
        &DecodingKey::from_secret(b"secret"),
        &Validation::default()
    )?;

    // Attach user info to request
    req.extensions_mut().insert(claims);
    next.run(req).await
}
```

---

## Best Practices

### Production Deployment Checklist

**Pre-Deployment**:
- [ ] Enable Age encryption for config files
- [ ] Store wallet address in OS keyring (never in config/env vars)
- [ ] Verify binary GPG signature before deployment
- [ ] Run `cargo audit` to check for vulnerable dependencies
- [ ] Enable JWT authentication for API endpoints
- [ ] Configure rate limiting (token bucket)
- [ ] Set up firewall rules (allow only necessary ports)
- [ ] Use non-root user for service execution
- [ ] Enable seccomp filters and capability dropping
- [ ] Configure audit logging to secure storage

**Post-Deployment**:
- [ ] Monitor security metrics (failed auth attempts, API errors)
- [ ] Set up alerting for anomalous behavior
- [ ] Regularly update dependencies (`cargo update`)
- [ ] Rotate JWT signing keys every 90 days
- [ ] Review audit logs weekly
- [ ] Perform security scans (Trivy, Grype)
- [ ] Test incident response procedures

### Secure Configuration

**Minimal Config** (production):
```toml
[api]
host = "127.0.0.1"  # Localhost only
port = 8080
require_auth = true  # Enable JWT auth
rate_limit_rpm = 30  # 30 requests/minute

[secrets]
encryption = "age"
key_file = "/etc/opus-gpu/age-key.txt"
keyring_service = "opus-gpu"

[security]
drop_capabilities = true
seccomp_filter = "strict"
audit_log = "/var/log/opus-gpu/audit.log"

[logging]
level = "warn"  # Minimize log noise
format = "json"
```

**File Permissions**:
```bash
# Config file (readable only by owner)
chmod 600 /etc/opus-gpu/app.toml
chown opus:opus /etc/opus-gpu/app.toml

# Age encryption key (strict permissions)
chmod 400 /etc/opus-gpu/age-key.txt
chown opus:opus /etc/opus-gpu/age-key.txt

# Binary (executable, not writable)
chmod 555 /opt/opus-gpu/bin/gpu-miner
chown root:root /opt/opus-gpu/bin/gpu-miner
```

### Network Security

**Firewall Rules** (iptables):
```bash
# Allow localhost API access only
iptables -A INPUT -p tcp --dport 8080 -s 127.0.0.1 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j DROP

# Allow Prometheus scraping from specific IP
iptables -A INPUT -p tcp --dport 9090 -s 10.0.0.10 -j ACCEPT
iptables -A INPUT -p tcp --dport 9090 -j DROP

# Allow outbound pool connection
iptables -A OUTPUT -p tcp --dport 3333 -m state --state NEW,ESTABLISHED -j ACCEPT
```

**TLS Configuration** (future):
```toml
[api]
tls_enabled = true
tls_cert_path = "/etc/opus-gpu/tls/cert.pem"
tls_key_path = "/etc/opus-gpu/tls/key.pem"
tls_min_version = "1.3"  # TLS 1.3 only
```

---

## Incident Response

### Security Incident Procedure

**1. Detection**:
- Monitor security metrics (failed logins, API errors)
- Set up alerting rules in Prometheus/Grafana
- Review audit logs daily

**2. Containment**:
```bash
# Immediate actions
sudo systemctl stop opus-gpu  # Stop service
sudo iptables -A INPUT -j DROP  # Block all incoming traffic
sudo iptables -A OUTPUT -j DROP  # Block all outgoing traffic

# Preserve evidence
sudo tar -czf /tmp/evidence-$(date +%Y%m%d).tar.gz \
    /var/log/opus-gpu/ \
    /etc/opus-gpu/ \
    /opt/opus-gpu/
```

**3. Analysis**:
```bash
# Review logs
sudo journalctl -u opus-gpu --since "1 hour ago" > incident-logs.txt

# Check for unauthorized changes
sudo find /opt/opus-gpu -type f -mtime -1  # Files modified in last 24h

# Analyze network connections
sudo ss -tunap | grep gpu-miner
```

**4. Eradication**:
```bash
# Remove malicious files
sudo rm -f /path/to/malicious/file

# Update dependencies
cd /opt/opus-gpu
sudo -u opus cargo update
sudo -u opus cargo build --release

# Verify binary signature
gpg --verify gpu-miner.asc target/release/gpu-miner
```

**5. Recovery**:
```bash
# Restore from backup
sudo systemctl start opus-gpu

# Verify health
curl http://localhost:8080/health

# Monitor for 24 hours
sudo journalctl -u opus-gpu -f
```

**6. Post-Incident**:
- Document timeline and root cause
- Update security controls
- Notify stakeholders
- Review and improve procedures

### Security Contacts

**Incident Reporting**:
- Email: security@your-org.com
- PGP Key: [Fingerprint]
- Response SLA: 24 hours

---

## Responsible Disclosure

### Vulnerability Reporting

**How to Report**:
1. **Email**: Send encrypted email to security@your-org.com
2. **PGP Key**: Use our public key (fingerprint: XXXX-XXXX-XXXX)
3. **Include**:
   - Vulnerability description
   - Affected versions
   - Steps to reproduce
   - Proof of concept (optional)
   - Suggested fix (optional)

**What to Expect**:
- **Acknowledgment**: Within 24 hours
- **Initial Assessment**: Within 3 business days
- **Fix Timeline**: Based on severity (Critical: 7 days, High: 14 days)
- **Public Disclosure**: Coordinated disclosure after fix is released

### Security Hall of Fame

**Contributors**:
- [Researcher Name] - [Vulnerability ID] - [Date]

**Rewards**:
- Acknowledgment in security advisories
- Hall of fame listing
- Swag (t-shirts, stickers)

---

## Appendix

### Security Tools

**Dependency Auditing**:
```bash
cargo install cargo-audit
cargo audit

# Automated CI check
cargo audit --deny warnings
```

**SBOM Generation**:
```bash
cargo install cargo-sbom
cargo sbom > opus-gpu-sbom.json
```

**Container Scanning**:
```bash
# Trivy
trivy image opus-gpu:latest

# Grype
grype opus-gpu:latest
```

**Static Analysis**:
```bash
# Clippy (security lints)
cargo clippy -- -W clippy::all -W clippy::pedantic

# RustSec advisory check
cargo install cargo-deny
cargo deny check advisories
```

### References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [Rust Security Working Group](https://www.rust-lang.org/governance/wgs/wg-security-response)

---

**Document Version**: 1.0
**Authors**: OPUS-GPU Security Team
**License**: MIT
