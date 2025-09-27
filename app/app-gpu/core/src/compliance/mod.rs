//! Compliance and audit module for OPUS-GPU
//! 
//! Implements SBOM generation, license compliance, and security auditing

use std::collections::{HashMap, HashSet};
use std::path::Path;
use serde::{Deserialize, Serialize};
use anyhow::{Result, Context};
use chrono::{DateTime, Utc};
use sha2::{Sha256, Digest};
use serde_json::json;

/// Software Bill of Materials (SBOM)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Sbom {
    /// SBOM format version
    pub format_version: String,
    
    /// SBOM generation timestamp
    pub generated_at: DateTime<Utc>,
    
    /// Tool information
    pub tool: SbomTool,
    
    /// Component metadata
    pub metadata: SbomMetadata,
    
    /// List of components
    pub components: Vec<Component>,
    
    /// Dependencies
    pub dependencies: Vec<Dependency>,
    
    /// Vulnerabilities
    pub vulnerabilities: Vec<Vulnerability>,
}

/// SBOM tool information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SbomTool {
    pub vendor: String,
    pub name: String,
    pub version: String,
}

/// SBOM metadata
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SbomMetadata {
    pub timestamp: DateTime<Utc>,
    pub authors: Vec<String>,
    pub component: ComponentInfo,
    pub supplier: String,
    pub licenses: Vec<License>,
}

/// Component information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentInfo {
    pub name: String,
    pub version: String,
    pub description: String,
    pub purl: String, // Package URL
    pub cpe: String,  // Common Platform Enumeration
}

/// Software component
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Component {
    pub id: String,
    pub name: String,
    pub version: String,
    pub component_type: ComponentType,
    pub supplier: Option<String>,
    pub author: Option<String>,
    pub publisher: Option<String>,
    pub group: Option<String>,
    pub purl: String,
    pub cpe: Option<String>,
    pub licenses: Vec<License>,
    pub hashes: Vec<Hash>,
    pub external_references: Vec<ExternalReference>,
}

/// Component type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ComponentType {
    Application,
    Framework,
    Library,
    Container,
    OperatingSystem,
    Device,
    Firmware,
    File,
}

/// License information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct License {
    pub id: String,
    pub name: String,
    pub url: Option<String>,
    pub license_type: LicenseType,
    pub compliance_status: ComplianceStatus,
}

/// License type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum LicenseType {
    OpenSource,
    Proprietary,
    Commercial,
    Dual,
    Unknown,
}

/// Compliance status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ComplianceStatus {
    Compliant,
    NonCompliant,
    Review,
    Exception,
}

/// Hash information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Hash {
    pub algorithm: String,
    pub value: String,
}

/// External reference
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExternalReference {
    pub reference_type: String,
    pub url: String,
}

/// Dependency relationship
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Dependency {
    pub ref_id: String,
    pub depends_on: Vec<String>,
}

/// Vulnerability information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vulnerability {
    pub id: String,
    pub source: VulnerabilitySource,
    pub ratings: Vec<VulnerabilityRating>,
    pub cwes: Vec<u32>,
    pub description: String,
    pub recommendation: String,
    pub affected_components: Vec<String>,
}

/// Vulnerability source
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VulnerabilitySource {
    pub name: String,
    pub url: String,
}

/// Vulnerability rating
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VulnerabilityRating {
    pub source: VulnerabilitySource,
    pub score: f32,
    pub severity: Severity,
    pub method: String,
    pub vector: Option<String>,
}

/// Severity level
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Severity {
    None,
    Low,
    Medium,
    High,
    Critical,
}

/// License compliance checker
pub struct LicenseChecker {
    /// Allowed licenses
    allowed_licenses: HashSet<String>,
    
    /// Denied licenses
    denied_licenses: HashSet<String>,
    
    /// License compatibility matrix
    compatibility_matrix: HashMap<String, HashSet<String>>,
    
    /// Exception list
    exceptions: HashMap<String, String>,
}

impl LicenseChecker {
    pub fn new() -> Self {
        let mut checker = Self {
            allowed_licenses: HashSet::new(),
            denied_licenses: HashSet::new(),
            compatibility_matrix: HashMap::new(),
            exceptions: HashMap::new(),
        };
        
        // Initialize with common open source licenses
        checker.init_default_licenses();
        checker
    }
    
    /// Initialize default license configuration
    fn init_default_licenses(&mut self) {
        // Allowed licenses
        self.allowed_licenses.insert("MIT".to_string());
        self.allowed_licenses.insert("Apache-2.0".to_string());
        self.allowed_licenses.insert("BSD-3-Clause".to_string());
        self.allowed_licenses.insert("BSD-2-Clause".to_string());
        self.allowed_licenses.insert("ISC".to_string());
        self.allowed_licenses.insert("MPL-2.0".to_string());
        
        // Denied licenses (copyleft)
        self.denied_licenses.insert("GPL-2.0".to_string());
        self.denied_licenses.insert("GPL-3.0".to_string());
        self.denied_licenses.insert("AGPL-3.0".to_string());
        self.denied_licenses.insert("LGPL-2.1".to_string());
        self.denied_licenses.insert("LGPL-3.0".to_string());
        
        // License compatibility
        let mut apache_compatible = HashSet::new();
        apache_compatible.insert("MIT".to_string());
        apache_compatible.insert("BSD-3-Clause".to_string());
        apache_compatible.insert("BSD-2-Clause".to_string());
        self.compatibility_matrix.insert("Apache-2.0".to_string(), apache_compatible);
        
        let mut mit_compatible = HashSet::new();
        mit_compatible.insert("Apache-2.0".to_string());
        mit_compatible.insert("BSD-3-Clause".to_string());
        mit_compatible.insert("BSD-2-Clause".to_string());
        mit_compatible.insert("ISC".to_string());
        self.compatibility_matrix.insert("MIT".to_string(), mit_compatible);
    }
    
    /// Check license compliance
    pub fn check_compliance(&self, license: &License) -> ComplianceStatus {
        if self.exceptions.contains_key(&license.id) {
            return ComplianceStatus::Exception;
        }
        
        if self.denied_licenses.contains(&license.id) {
            return ComplianceStatus::NonCompliant;
        }
        
        if self.allowed_licenses.contains(&license.id) {
            return ComplianceStatus::Compliant;
        }
        
        ComplianceStatus::Review
    }
    
    /// Check license compatibility
    pub fn check_compatibility(&self, license1: &str, license2: &str) -> bool {
        if let Some(compatible_licenses) = self.compatibility_matrix.get(license1) {
            return compatible_licenses.contains(license2);
        }
        
        if let Some(compatible_licenses) = self.compatibility_matrix.get(license2) {
            return compatible_licenses.contains(license1);
        }
        
        false
    }
    
    /// Add license exception
    pub fn add_exception(&mut self, license_id: String, reason: String) {
        self.exceptions.insert(license_id, reason);
    }
}

/// Security audit manager
pub struct SecurityAuditor {
    /// Known vulnerabilities database
    vulnerabilities: HashMap<String, Vec<Vulnerability>>,
    
    /// Security policies
    policies: Vec<SecurityPolicy>,
    
    /// Audit results
    audit_results: Vec<AuditResult>,
}

/// Security policy
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityPolicy {
    pub id: String,
    pub name: String,
    pub description: String,
    pub severity: Severity,
    pub check_type: CheckType,
    pub remediation: String,
}

/// Security check type
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CheckType {
    Vulnerability,
    Configuration,
    Cryptography,
    Authentication,
    Authorization,
    DataProtection,
    NetworkSecurity,
}

/// Audit result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditResult {
    pub timestamp: DateTime<Utc>,
    pub policy: SecurityPolicy,
    pub status: AuditStatus,
    pub findings: Vec<Finding>,
    pub recommendations: Vec<String>,
}

/// Audit status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AuditStatus {
    Passed,
    Failed,
    Warning,
    Skipped,
}

/// Security finding
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    pub id: String,
    pub title: String,
    pub description: String,
    pub severity: Severity,
    pub location: String,
    pub evidence: String,
    pub remediation: String,
}

impl SecurityAuditor {
    pub fn new() -> Self {
        let mut auditor = Self {
            vulnerabilities: HashMap::new(),
            policies: Vec::new(),
            audit_results: Vec::new(),
        };
        
        auditor.init_default_policies();
        auditor
    }
    
    /// Initialize default security policies
    fn init_default_policies(&mut self) {
        self.policies = vec![
            SecurityPolicy {
                id: "VULN-001".to_string(),
                name: "Critical Vulnerability Check".to_string(),
                description: "Check for critical CVEs".to_string(),
                severity: Severity::Critical,
                check_type: CheckType::Vulnerability,
                remediation: "Update affected components immediately".to_string(),
            },
            SecurityPolicy {
                id: "AUTH-001".to_string(),
                name: "Authentication Configuration".to_string(),
                description: "Verify authentication is properly configured".to_string(),
                severity: Severity::High,
                check_type: CheckType::Authentication,
                remediation: "Enable mTLS or JWT authentication".to_string(),
            },
            SecurityPolicy {
                id: "CRYPTO-001".to_string(),
                name: "Cryptography Standards".to_string(),
                description: "Verify cryptographic algorithms meet standards".to_string(),
                severity: Severity::High,
                check_type: CheckType::Cryptography,
                remediation: "Use approved cryptographic algorithms".to_string(),
            },
        ];
    }
    
    /// Scan for vulnerabilities
    pub async fn scan_vulnerabilities(&mut self, components: &[Component]) -> Result<Vec<Vulnerability>> {
        let mut found_vulnerabilities = Vec::new();
        
        for component in components {
            let key = format!("{}:{}", component.name, component.version);
            
            // In production, would query vulnerability databases (NVD, OSV, etc.)
            if let Some(vulns) = self.vulnerabilities.get(&key) {
                found_vulnerabilities.extend(vulns.clone());
            }
        }
        
        Ok(found_vulnerabilities)
    }
    
    /// Run security audit
    pub async fn run_audit(&mut self) -> Result<AuditReport> {
        let mut results = Vec::new();
        
        for policy in &self.policies {
            let result = self.check_policy(policy).await?;
            results.push(result);
        }
        
        self.audit_results = results.clone();
        
        Ok(AuditReport {
            timestamp: Utc::now(),
            results,
            summary: self.generate_summary(&results),
        })
    }
    
    /// Check security policy
    async fn check_policy(&self, policy: &SecurityPolicy) -> Result<AuditResult> {
        // In production, would perform actual security checks
        // For now, return mock results
        
        let findings = match policy.check_type {
            CheckType::Vulnerability => {
                // Check for known vulnerabilities
                vec![]
            }
            CheckType::Authentication => {
                // Check authentication configuration
                vec![]
            }
            CheckType::Cryptography => {
                // Check cryptographic standards
                vec![]
            }
            _ => vec![],
        };
        
        let status = if findings.is_empty() {
            AuditStatus::Passed
        } else if findings.iter().any(|f| matches!(f.severity, Severity::Critical | Severity::High)) {
            AuditStatus::Failed
        } else {
            AuditStatus::Warning
        };
        
        Ok(AuditResult {
            timestamp: Utc::now(),
            policy: policy.clone(),
            status,
            findings,
            recommendations: vec![],
        })
    }
    
    /// Generate audit summary
    fn generate_summary(&self, results: &[AuditResult]) -> AuditSummary {
        let total = results.len();
        let passed = results.iter().filter(|r| matches!(r.status, AuditStatus::Passed)).count();
        let failed = results.iter().filter(|r| matches!(r.status, AuditStatus::Failed)).count();
        let warnings = results.iter().filter(|r| matches!(r.status, AuditStatus::Warning)).count();
        
        let critical_findings = results.iter()
            .flat_map(|r| &r.findings)
            .filter(|f| matches!(f.severity, Severity::Critical))
            .count();
        
        let high_findings = results.iter()
            .flat_map(|r| &r.findings)
            .filter(|f| matches!(f.severity, Severity::High))
            .count();
        
        AuditSummary {
            total_checks: total,
            passed,
            failed,
            warnings,
            critical_findings,
            high_findings,
            compliance_score: (passed as f32 / total as f32) * 100.0,
        }
    }
}

/// Audit report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditReport {
    pub timestamp: DateTime<Utc>,
    pub results: Vec<AuditResult>,
    pub summary: AuditSummary,
}

/// Audit summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditSummary {
    pub total_checks: usize,
    pub passed: usize,
    pub failed: usize,
    pub warnings: usize,
    pub critical_findings: usize,
    pub high_findings: usize,
    pub compliance_score: f32,
}

/// SBOM generator
pub struct SbomGenerator;

impl SbomGenerator {
    /// Generate SBOM in CycloneDX format
    pub async fn generate_cyclonedx(components: Vec<Component>) -> Result<String> {
        let sbom = Sbom {
            format_version: "1.4".to_string(),
            generated_at: Utc::now(),
            tool: SbomTool {
                vendor: "OPUS".to_string(),
                name: "OPUS-GPU SBOM Generator".to_string(),
                version: "2.0.0".to_string(),
            },
            metadata: SbomMetadata {
                timestamp: Utc::now(),
                authors: vec!["OPUS Team".to_string()],
                component: ComponentInfo {
                    name: "opus-gpu".to_string(),
                    version: "2.0.0".to_string(),
                    description: "High-performance GPU computing platform".to_string(),
                    purl: "pkg:generic/opus-gpu@2.0.0".to_string(),
                    cpe: "cpe:2.3:a:opus:opus-gpu:2.0.0:*:*:*:*:*:*:*".to_string(),
                },
                supplier: "OPUS".to_string(),
                licenses: vec![
                    License {
                        id: "Apache-2.0".to_string(),
                        name: "Apache License 2.0".to_string(),
                        url: Some("https://www.apache.org/licenses/LICENSE-2.0".to_string()),
                        license_type: LicenseType::OpenSource,
                        compliance_status: ComplianceStatus::Compliant,
                    }
                ],
            },
            components,
            dependencies: Vec::new(),
            vulnerabilities: Vec::new(),
        };
        
        let json = serde_json::to_string_pretty(&sbom)?;
        Ok(json)
    }
    
    /// Generate SBOM in SPDX format
    pub async fn generate_spdx(components: Vec<Component>) -> Result<String> {
        let spdx = json!({
            "spdxVersion": "SPDX-2.3",
            "dataLicense": "CC0-1.0",
            "SPDXID": "SPDXRef-DOCUMENT",
            "name": "OPUS-GPU SBOM",
            "documentNamespace": "https://opus-gpu.io/sbom/2.0.0",
            "creationInfo": {
                "created": Utc::now().to_rfc3339(),
                "creators": ["Tool: OPUS-GPU SBOM Generator-2.0.0"],
                "licenseListVersion": "3.19"
            },
            "packages": components.iter().map(|c| {
                json!({
                    "SPDXID": format!("SPDXRef-Package-{}", c.id),
                    "name": c.name,
                    "downloadLocation": c.external_references.first()
                        .map(|r| r.url.clone())
                        .unwrap_or_else(|| "NOASSERTION".to_string()),
                    "filesAnalyzed": false,
                    "licenseConcluded": c.licenses.first()
                        .map(|l| l.id.clone())
                        .unwrap_or_else(|| "NOASSERTION".to_string()),
                    "copyrightText": "NOASSERTION"
                })
            }).collect::<Vec<_>>()
        });
        
        Ok(spdx.to_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_license_checker() {
        let checker = LicenseChecker::new();
        
        let mit_license = License {
            id: "MIT".to_string(),
            name: "MIT License".to_string(),
            url: None,
            license_type: LicenseType::OpenSource,
            compliance_status: ComplianceStatus::Review,
        };
        
        assert!(matches!(
            checker.check_compliance(&mit_license),
            ComplianceStatus::Compliant
        ));
        
        let gpl_license = License {
            id: "GPL-3.0".to_string(),
            name: "GNU General Public License v3.0".to_string(),
            url: None,
            license_type: LicenseType::OpenSource,
            compliance_status: ComplianceStatus::Review,
        };
        
        assert!(matches!(
            checker.check_compliance(&gpl_license),
            ComplianceStatus::NonCompliant
        ));
    }
    
    #[tokio::test]
    async fn test_security_auditor() {
        let mut auditor = SecurityAuditor::new();
        
        let report = auditor.run_audit().await.unwrap();
        assert!(!report.results.is_empty());
        assert_eq!(report.summary.total_checks, report.results.len());
    }
    
    #[tokio::test]
    async fn test_sbom_generation() {
        let components = vec![
            Component {
                id: "comp-1".to_string(),
                name: "test-component".to_string(),
                version: "1.0.0".to_string(),
                component_type: ComponentType::Library,
                supplier: Some("Test Supplier".to_string()),
                author: None,
                publisher: None,
                group: None,
                purl: "pkg:cargo/test-component@1.0.0".to_string(),
                cpe: None,
                licenses: vec![],
                hashes: vec![],
                external_references: vec![],
            }
        ];
        
        let cyclonedx = SbomGenerator::generate_cyclonedx(components.clone()).await.unwrap();
        assert!(cyclonedx.contains("CycloneDX"));
        
        let spdx = SbomGenerator::generate_spdx(components).await.unwrap();
        assert!(spdx.contains("SPDX"));
    }
}
