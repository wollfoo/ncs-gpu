//! Configuration validation system with JSON Schema support

use crate::errors::{ConfigError, ConfigResult};
use jsonschema::{Draft, JSONSchema, ValidationError};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::{collections::HashMap, sync::Arc};
use tracing::{debug, info, warn};
use validator::Validate;

/// Configuration validator with schema support
pub struct ConfigValidator {
    /// JSON schemas for different configuration sections
    schemas: HashMap<String, Arc<JSONSchema>>,
    /// Custom validation rules
    custom_rules: Vec<Box<dyn ValidationRule + Send + Sync>>,
    /// Validation configuration
    config: ValidationConfig,
}

/// Validation configuration settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationConfig {
    /// Enable JSON schema validation
    pub enable_schema_validation: bool,
    /// Enable custom rule validation
    pub enable_custom_rules: bool,
    /// Fail fast on first validation error
    pub fail_fast: bool,
    /// Maximum allowed configuration file size in bytes
    pub max_file_size: u64,
    /// Enable strict validation (no additional properties)
    pub strict_mode: bool,
    /// Validation timeout in seconds
    pub timeout_seconds: u64,
}

impl Default for ValidationConfig {
    fn default() -> Self {
        Self {
            enable_schema_validation: true,
            enable_custom_rules: true,
            fail_fast: false,
            max_file_size: 10 * 1024 * 1024, // 10MB
            strict_mode: false,
            timeout_seconds: 30,
        }
    }
}

/// Custom validation rule trait
pub trait ValidationRule {
    /// Rule name for identification
    fn name(&self) -> &'static str;

    /// Validate a configuration value
    fn validate(&self, config: &Value) -> ConfigResult<()>;

    /// Get rule description
    fn description(&self) -> &'static str;

    /// Check if rule applies to specific config section
    fn applies_to(&self, section: &str) -> bool {
        true // Default: apply to all sections
    }
}

/// Validation result with detailed error information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationResult {
    /// Whether validation passed
    pub is_valid: bool,
    /// List of validation errors
    pub errors: Vec<ValidationErrorDetail>,
    /// Validation warnings (non-fatal issues)
    pub warnings: Vec<ValidationWarning>,
    /// Validation statistics
    pub stats: ValidationStats,
}

/// Detailed validation error information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationErrorDetail {
    /// Error message
    pub message: String,
    /// JSON path where error occurred
    pub path: String,
    /// Error source (schema, custom rule, etc.)
    pub source: ValidationSource,
    /// Error severity
    pub severity: ValidationSeverity,
    /// Suggested fix if available
    pub suggestion: Option<String>,
}

/// Validation warning for non-critical issues
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationWarning {
    /// Warning message
    pub message: String,
    /// JSON path where warning occurred
    pub path: String,
    /// Warning category
    pub category: WarningCategory,
    /// Suggested action
    pub suggestion: Option<String>,
}

/// Validation error source
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ValidationSource {
    Schema,
    CustomRule(String),
    BuiltinRule,
    BusinessLogic,
}

/// Validation error severity
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum ValidationSeverity {
    Info,
    Warning,
    Error,
    Critical,
}

/// Warning categories
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WarningCategory {
    Deprecated,
    Performance,
    Security,
    Compatibility,
    BestPractice,
}

/// Validation statistics
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ValidationStats {
    /// Total number of rules checked
    pub rules_checked: usize,
    /// Number of schema validations performed
    pub schema_validations: usize,
    /// Number of custom rule validations performed
    pub custom_validations: usize,
    /// Validation duration in milliseconds
    pub duration_ms: u64,
    /// Number of properties validated
    pub properties_validated: usize,
}

impl ConfigValidator {
    /// Create new configuration validator
    pub fn new(config: ValidationConfig) -> Self {
        Self {
            schemas: HashMap::new(),
            custom_rules: Vec::new(),
            config,
        }
    }

    /// Add JSON schema for configuration section
    pub fn add_schema(&mut self, section: String, schema: Value) -> ConfigResult<()> {
        let compiled = JSONSchema::options()
            .with_draft(Draft::Draft7)
            .compile(&schema)
            .map_err(|e| ConfigError::schema_validation(format!("Schema compilation failed: {}", e)))?;

        self.schemas.insert(section, Arc::new(compiled));
        info!("Added validation schema for section: {}", section);
        Ok(())
    }

    /// Add custom validation rule
    pub fn add_custom_rule(&mut self, rule: Box<dyn ValidationRule + Send + Sync>) {
        let rule_name = rule.name();
        self.custom_rules.push(rule);
        info!("Added custom validation rule: {}", rule_name);
    }

    /// Validate configuration with comprehensive checks
    pub async fn validate_config(&self, config: &Value) -> ConfigResult<ValidationResult> {
        let start_time = std::time::Instant::now();
        let mut result = ValidationResult {
            is_valid: true,
            errors: Vec::new(),
            warnings: Vec::new(),
            stats: ValidationStats::default(),
        };

        // Check file size limits
        let config_size = serde_json::to_vec(config)?.len() as u64;
        if config_size > self.config.max_file_size {
            result.errors.push(ValidationErrorDetail {
                message: format!(
                    "Configuration size ({} bytes) exceeds maximum allowed size ({} bytes)",
                    config_size, self.config.max_file_size
                ),
                path: "$".to_string(),
                source: ValidationSource::BuiltinRule,
                severity: ValidationSeverity::Error,
                suggestion: Some("Consider splitting configuration into multiple files".to_string()),
            });
        }

        // Schema validation
        if self.config.enable_schema_validation {
            for (section, schema) in &self.schemas {
                if let Some(section_value) = config.get(section) {
                    self.validate_with_schema(section_value, schema, section, &mut result)?;
                    result.stats.schema_validations += 1;
                }
            }
        }

        // Custom rule validation
        if self.config.enable_custom_rules {
            for rule in &self.custom_rules {
                match rule.validate(config) {
                    Ok(()) => {
                        result.stats.custom_validations += 1;
                    }
                    Err(e) => {
                        result.errors.push(ValidationErrorDetail {
                            message: e.to_string(),
                            path: "$".to_string(),
                            source: ValidationSource::CustomRule(rule.name().to_string()),
                            severity: ValidationSeverity::Error,
                            suggestion: None,
                        });

                        if self.config.fail_fast {
                            break;
                        }
                    }
                }
            }
        }

        // Built-in validation rules
        self.apply_builtin_rules(config, &mut result)?;

        // Set validation result
        result.is_valid = result.errors.is_empty() ||
            result.errors.iter().all(|e| e.severity < ValidationSeverity::Error);

        // Update statistics
        result.stats.duration_ms = start_time.elapsed().as_millis() as u64;
        result.stats.rules_checked = self.custom_rules.len() + self.schemas.len() + 10; // +10 for builtin rules
        result.stats.properties_validated = self.count_properties(config);

        debug!("Configuration validation completed: {} errors, {} warnings",
               result.errors.len(), result.warnings.len());

        Ok(result)
    }

    /// Validate specific configuration section
    pub async fn validate_section(&self, section_name: &str, section_value: &Value) -> ConfigResult<ValidationResult> {
        let start_time = std::time::Instant::now();
        let mut result = ValidationResult {
            is_valid: true,
            errors: Vec::new(),
            warnings: Vec::new(),
            stats: ValidationStats::default(),
        };

        // Schema validation for section
        if let Some(schema) = self.schemas.get(section_name) {
            self.validate_with_schema(section_value, schema, section_name, &mut result)?;
            result.stats.schema_validations += 1;
        }

        // Custom rules that apply to this section
        for rule in &self.custom_rules {
            if rule.applies_to(section_name) {
                match rule.validate(section_value) {
                    Ok(()) => result.stats.custom_validations += 1,
                    Err(e) => {
                        result.errors.push(ValidationErrorDetail {
                            message: e.to_string(),
                            path: format!("$.{}", section_name),
                            source: ValidationSource::CustomRule(rule.name().to_string()),
                            severity: ValidationSeverity::Error,
                            suggestion: None,
                        });
                    }
                }
            }
        }

        result.is_valid = result.errors.is_empty();
        result.stats.duration_ms = start_time.elapsed().as_millis() as u64;
        result.stats.properties_validated = self.count_properties(section_value);

        Ok(result)
    }

    fn validate_with_schema(
        &self,
        value: &Value,
        schema: &JSONSchema,
        section: &str,
        result: &mut ValidationResult,
    ) -> ConfigResult<()> {
        let validation_result = schema.validate(value);

        match validation_result {
            Ok(()) => {
                debug!("Schema validation passed for section: {}", section);
            }
            Err(errors) => {
                for error in errors {
                    result.errors.push(ValidationErrorDetail {
                        message: error.to_string(),
                        path: format!("$.{}.{}", section, error.instance_path),
                        source: ValidationSource::Schema,
                        severity: ValidationSeverity::Error,
                        suggestion: self.get_schema_error_suggestion(&error),
                    });
                }
            }
        }

        Ok(())
    }

    fn apply_builtin_rules(&self, config: &Value, result: &mut ValidationResult) -> ConfigResult<()> {
        // Check for deprecated configuration options
        self.check_deprecated_options(config, result);

        // Check for security best practices
        self.check_security_practices(config, result);

        // Check for performance implications
        self.check_performance_settings(config, result);

        // Check for common misconfigurations
        self.check_common_misconfigurations(config, result);

        Ok(())
    }

    fn check_deprecated_options(&self, config: &Value, result: &mut ValidationResult) {
        // Example: Check for deprecated settings
        if let Some(mining) = config.get("mining") {
            if mining.get("legacy_mode").is_some() {
                result.warnings.push(ValidationWarning {
                    message: "The 'legacy_mode' option is deprecated and will be removed in a future version".to_string(),
                    path: "$.mining.legacy_mode".to_string(),
                    category: WarningCategory::Deprecated,
                    suggestion: Some("Remove this option or upgrade to the new configuration format".to_string()),
                });
            }
        }
    }

    fn check_security_practices(&self, config: &Value, result: &mut ValidationResult) {
        // Check for insecure default passwords
        if let Some(pool) = config.get("pool") {
            if let Some(password) = pool.get("password") {
                if let Some(pass_str) = password.as_str() {
                    if pass_str == "password" || pass_str == "123456" || pass_str.is_empty() {
                        result.errors.push(ValidationErrorDetail {
                            message: "Insecure default password detected".to_string(),
                            path: "$.pool.password".to_string(),
                            source: ValidationSource::BuiltinRule,
                            severity: ValidationSeverity::Critical,
                            suggestion: Some("Use a strong, unique password".to_string()),
                        });
                    }
                }
            }
        }

        // Check for unencrypted sensitive data
        if let Some(wallet) = config.get("wallet") {
            if let Some(encryption_enabled) = wallet.get("encryption_enabled") {
                if encryption_enabled == &Value::Bool(false) {
                    result.warnings.push(ValidationWarning {
                        message: "Wallet encryption is disabled".to_string(),
                        path: "$.wallet.encryption_enabled".to_string(),
                        category: WarningCategory::Security,
                        suggestion: Some("Enable wallet encryption for better security".to_string()),
                    });
                }
            }
        }
    }

    fn check_performance_settings(&self, config: &Value, result: &mut ValidationResult) {
        // Check for performance-impacting settings
        if let Some(mining) = config.get("mining") {
            if let Some(max_workers) = mining.get("max_workers") {
                if let Some(workers) = max_workers.as_u64() {
                    if workers > 32 {
                        result.warnings.push(ValidationWarning {
                            message: format!("High worker count ({}) may impact performance", workers),
                            path: "$.mining.max_workers".to_string(),
                            category: WarningCategory::Performance,
                            suggestion: Some("Consider reducing worker count based on system resources".to_string()),
                        });
                    }
                }
            }
        }

        // Check memory settings
        if let Some(mining) = config.get("mining") {
            if let Some(memory_size) = mining.get("memory_size") {
                if let Some(mem) = memory_size.as_u64() {
                    let mem_gb = mem / (1024 * 1024 * 1024);
                    if mem_gb > 16 {
                        result.warnings.push(ValidationWarning {
                            message: format!("High memory allocation ({} GB) detected", mem_gb),
                            path: "$.mining.memory_size".to_string(),
                            category: WarningCategory::Performance,
                            suggestion: Some("Ensure system has sufficient RAM available".to_string()),
                        });
                    }
                }
            }
        }
    }

    fn check_common_misconfigurations(&self, config: &Value, result: &mut ValidationResult) {
        // Check for localhost-only bindings in production
        if let Some(api) = config.get("api") {
            if let Some(rest) = api.get("rest") {
                if let Some(host) = rest.get("host") {
                    if host == "127.0.0.1" || host == "localhost" {
                        result.warnings.push(ValidationWarning {
                            message: "API is bound to localhost only".to_string(),
                            path: "$.api.rest.host".to_string(),
                            category: WarningCategory::BestPractice,
                            suggestion: Some("Consider using 0.0.0.0 or specific interface for production".to_string()),
                        });
                    }
                }
            }
        }

        // Check for disabled monitoring in production
        if let Some(monitoring) = config.get("monitoring") {
            if let Some(enabled) = monitoring.get("enabled") {
                if enabled == &Value::Bool(false) {
                    result.warnings.push(ValidationWarning {
                        message: "Monitoring is disabled".to_string(),
                        path: "$.monitoring.enabled".to_string(),
                        category: WarningCategory::BestPractice,
                        suggestion: Some("Enable monitoring for production deployments".to_string()),
                    });
                }
            }
        }
    }

    fn get_schema_error_suggestion(&self, error: &ValidationError) -> Option<String> {
        match error {
            e if e.to_string().contains("required") => {
                Some("Add the required property to your configuration".to_string())
            }
            e if e.to_string().contains("type") => {
                Some("Check the data type of this property".to_string())
            }
            e if e.to_string().contains("minimum") => {
                Some("Increase the value to meet the minimum requirement".to_string())
            }
            e if e.to_string().contains("maximum") => {
                Some("Decrease the value to meet the maximum requirement".to_string())
            }
            _ => None,
        }
    }

    fn count_properties(&self, value: &Value) -> usize {
        match value {
            Value::Object(map) => {
                let mut count = map.len();
                for v in map.values() {
                    count += self.count_properties(v);
                }
                count
            }
            Value::Array(arr) => {
                let mut count = 0;
                for v in arr {
                    count += self.count_properties(v);
                }
                count
            }
            _ => 1,
        }
    }

    /// Get validation configuration
    pub fn config(&self) -> &ValidationConfig {
        &self.config
    }

    /// Update validation configuration
    pub fn update_config(&mut self, config: ValidationConfig) {
        self.config = config;
        info!("Updated validation configuration");
    }

    /// List available schemas
    pub fn list_schemas(&self) -> Vec<String> {
        self.schemas.keys().cloned().collect()
    }

    /// List available custom rules
    pub fn list_custom_rules(&self) -> Vec<(String, String)> {
        self.custom_rules
            .iter()
            .map(|rule| (rule.name().to_string(), rule.description().to_string()))
            .collect()
    }
}

/// Built-in validation rules
pub mod builtin_rules {
    use super::*;

    /// Port conflict validation rule
    pub struct PortConflictRule;

    impl ValidationRule for PortConflictRule {
        fn name(&self) -> &'static str {
            "port_conflict_check"
        }

        fn description(&self) -> &'static str {
            "Checks for port conflicts between different services"
        }

        fn validate(&self, config: &Value) -> ConfigResult<()> {
            let mut ports = Vec::new();

            // Collect all port numbers
            if let Some(api) = config.get("api") {
                if let Some(rest_port) = api.get("rest").and_then(|r| r.get("port")) {
                    if let Some(port) = rest_port.as_u64() {
                        ports.push(("api.rest", port));
                    }
                }
                if let Some(ws_port) = api.get("websocket").and_then(|ws| ws.get("port")) {
                    if let Some(port) = ws_port.as_u64() {
                        ports.push(("api.websocket", port));
                    }
                }
                if let Some(grpc_port) = api.get("grpc").and_then(|g| g.get("port")) {
                    if let Some(port) = grpc_port.as_u64() {
                        ports.push(("api.grpc", port));
                    }
                }
            }

            if let Some(monitoring) = config.get("monitoring") {
                if let Some(metrics_port) = monitoring.get("metrics_port") {
                    if let Some(port) = metrics_port.as_u64() {
                        ports.push(("monitoring.metrics_port", port));
                    }
                }
            }

            // Check for duplicates
            for i in 0..ports.len() {
                for j in i + 1..ports.len() {
                    if ports[i].1 == ports[j].1 {
                        return Err(ConfigError::validation(format!(
                            "Port conflict: {} and {} both use port {}",
                            ports[i].0, ports[j].0, ports[i].1
                        )));
                    }
                }
            }

            Ok(())
        }
    }

    /// Resource usage validation rule
    pub struct ResourceUsageRule;

    impl ValidationRule for ResourceUsageRule {
        fn name(&self) -> &'static str {
            "resource_usage_check"
        }

        fn description(&self) -> &'static str {
            "Validates resource usage limits and requirements"
        }

        fn validate(&self, config: &Value) -> ConfigResult<()> {
            if let Some(mining) = config.get("mining") {
                // Check GPU memory requirements
                if let Some(memory_size) = mining.get("memory_size") {
                    if let Some(mem) = memory_size.as_u64() {
                        if mem < 1024 * 1024 { // Less than 1MB
                            return Err(ConfigError::validation(
                                "Mining memory size too small (minimum 1MB required)".to_string()
                            ));
                        }
                        if mem > 32 * 1024 * 1024 * 1024 { // More than 32GB
                            return Err(ConfigError::validation(
                                "Mining memory size too large (maximum 32GB allowed)".to_string()
                            ));
                        }
                    }
                }

                // Check worker count vs GPU devices
                if let Some(max_workers) = mining.get("max_workers") {
                    if let Some(gpu_devices) = mining.get("gpu_devices") {
                        if let (Some(workers), Some(devices)) = (max_workers.as_u64(), gpu_devices.as_array()) {
                            if workers > devices.len() as u64 * 8 { // Arbitrary limit of 8 workers per GPU
                                return Err(ConfigError::validation(format!(
                                    "Too many workers ({}) for {} GPU devices (recommended: max {} workers)",
                                    workers, devices.len(), devices.len() * 8
                                )));
                            }
                        }
                    }
                }
            }

            Ok(())
        }

        fn applies_to(&self, section: &str) -> bool {
            section == "mining"
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[tokio::test]
    async fn test_validator_creation() {
        let config = ValidationConfig::default();
        let validator = ConfigValidator::new(config);
        assert_eq!(validator.schemas.len(), 0);
        assert_eq!(validator.custom_rules.len(), 0);
    }

    #[tokio::test]
    async fn test_schema_validation() {
        let mut validator = ConfigValidator::new(ValidationConfig::default());

        let schema = json!({
            "type": "object",
            "properties": {
                "port": {"type": "number", "minimum": 1024, "maximum": 65535}
            },
            "required": ["port"]
        });

        validator.add_schema("api".to_string(), schema).unwrap();

        let valid_config = json!({
            "api": {"port": 8080}
        });

        let result = validator.validate_config(&valid_config).await.unwrap();
        assert!(result.is_valid);

        let invalid_config = json!({
            "api": {"port": 80} // Below minimum
        });

        let result = validator.validate_config(&invalid_config).await.unwrap();
        assert!(!result.is_valid);
        assert!(!result.errors.is_empty());
    }

    #[tokio::test]
    async fn test_custom_rule_validation() {
        let mut validator = ConfigValidator::new(ValidationConfig::default());
        validator.add_custom_rule(Box::new(builtin_rules::PortConflictRule));

        let config_with_conflict = json!({
            "api": {
                "rest": {"port": 8080},
                "websocket": {"port": 8080}
            }
        });

        let result = validator.validate_config(&config_with_conflict).await.unwrap();
        assert!(!result.is_valid);
        assert!(result.errors.iter().any(|e| e.message.contains("Port conflict")));
    }

    #[test]
    fn test_validation_severity() {
        assert!(ValidationSeverity::Critical > ValidationSeverity::Error);
        assert!(ValidationSeverity::Error > ValidationSeverity::Warning);
        assert!(ValidationSeverity::Warning > ValidationSeverity::Info);
    }

    #[tokio::test]
    async fn test_builtin_rules() {
        let config = ValidationConfig::default();
        let validator = ConfigValidator::new(config);

        let insecure_config = json!({
            "pool": {
                "password": "password" // Insecure default
            },
            "wallet": {
                "encryption_enabled": false
            }
        });

        let result = validator.validate_config(&insecure_config).await.unwrap();
        assert!(!result.errors.is_empty() || !result.warnings.is_empty());
    }
}