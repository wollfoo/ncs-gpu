//! Configuration format detection and handling

use crate::errors::{ConfigError, ConfigResult};
use std::path::Path;

/// Supported configuration formats
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ConfigFormat {
    Toml,
    Yaml,
    Json,
}

impl ConfigFormat {
    /// Get file extension for this format
    pub fn extension(&self) -> &'static str {
        match self {
            ConfigFormat::Toml => "toml",
            ConfigFormat::Yaml => "yaml",
            ConfigFormat::Json => "json",
        }
    }

    /// Get MIME type for this format
    pub fn mime_type(&self) -> &'static str {
        match self {
            ConfigFormat::Toml => "application/toml",
            ConfigFormat::Yaml => "application/yaml",
            ConfigFormat::Json => "application/json",
        }
    }

    /// Check if format supports comments
    pub fn supports_comments(&self) -> bool {
        matches!(self, ConfigFormat::Toml | ConfigFormat::Yaml)
    }

    /// Check if format is binary
    pub fn is_binary(&self) -> bool {
        false // All supported formats are text-based
    }
}

impl std::fmt::Display for ConfigFormat {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ConfigFormat::Toml => write!(f, "TOML"),
            ConfigFormat::Yaml => write!(f, "YAML"),
            ConfigFormat::Json => write!(f, "JSON"),
        }
    }
}

impl std::str::FromStr for ConfigFormat {
    type Err = ConfigError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        match s.to_lowercase().as_str() {
            "toml" => Ok(ConfigFormat::Toml),
            "yaml" | "yml" => Ok(ConfigFormat::Yaml),
            "json" => Ok(ConfigFormat::Json),
            _ => Err(ConfigError::invalid_format(format!(
                "Unsupported format: {}. Supported formats: toml, yaml, json", s
            ))),
        }
    }
}

/// Configuration format detection utilities
pub struct FormatDetector;

impl FormatDetector {
    /// Detect format from file path extension
    pub fn detect_from_path<P: AsRef<Path>>(path: P) -> ConfigResult<ConfigFormat> {
        let path = path.as_ref();
        let extension = path
            .extension()
            .and_then(|ext| ext.to_str())
            .ok_or_else(|| {
                ConfigError::invalid_format(format!(
                    "Cannot determine format from path: {}",
                    path.display()
                ))
            })?;

        extension.parse()
    }

    /// Detect format from file content by analyzing syntax
    pub fn detect_from_content(content: &str) -> ConfigResult<ConfigFormat> {
        let content = content.trim();

        if content.is_empty() {
            return Err(ConfigError::invalid_format("Empty content"));
        }

        // JSON detection - starts with { or [
        if content.starts_with('{') || content.starts_with('[') {
            return Ok(ConfigFormat::Json);
        }

        // YAML detection - common YAML patterns
        if content.lines().any(|line| {
            let line = line.trim();
            line.starts_with("---") ||
            line.contains(": ") ||
            line.starts_with("- ") ||
            (line.contains(':') && !line.contains('=') && !line.contains('['))
        }) {
            return Ok(ConfigFormat::Yaml);
        }

        // TOML detection - sections or key=value pairs
        if content.lines().any(|line| {
            let line = line.trim();
            line.starts_with('[') && line.ends_with(']') ||
            line.contains('=') && !line.starts_with('#')
        }) {
            return Ok(ConfigFormat::Toml);
        }

        Err(ConfigError::invalid_format(
            "Cannot detect format from content"
        ))
    }

    /// Get all supported formats
    pub fn supported_formats() -> Vec<ConfigFormat> {
        vec![ConfigFormat::Toml, ConfigFormat::Yaml, ConfigFormat::Json]
    }

    /// Get all supported file extensions
    pub fn supported_extensions() -> Vec<&'static str> {
        vec!["toml", "yaml", "yml", "json"]
    }

    /// Check if file extension is supported
    pub fn is_supported_extension(extension: &str) -> bool {
        Self::supported_extensions().contains(&extension.to_lowercase().as_str())
    }

    /// Get recommended format for new configurations
    pub fn recommended_format() -> ConfigFormat {
        ConfigFormat::Toml // TOML is more human-readable and supports comments
    }
}

/// Format-specific serialization and deserialization
pub struct FormatSerializer;

impl FormatSerializer {
    /// Serialize data to string in specified format
    pub fn serialize<T: serde::Serialize>(
        data: &T,
        format: ConfigFormat,
    ) -> ConfigResult<String> {
        match format {
            ConfigFormat::Toml => {
                toml::to_string_pretty(data).map_err(|e| ConfigError::Serialization(e.into()))
            }
            ConfigFormat::Yaml => {
                serde_yaml::to_string(data).map_err(ConfigError::YamlParsing)
            }
            ConfigFormat::Json => {
                serde_json::to_string_pretty(data).map_err(ConfigError::Serialization)
            }
        }
    }

    /// Deserialize data from string with specified format
    pub fn deserialize<T: serde::de::DeserializeOwned>(
        content: &str,
        format: ConfigFormat,
    ) -> ConfigResult<T> {
        match format {
            ConfigFormat::Toml => {
                toml::from_str(content).map_err(ConfigError::TomlParsing)
            }
            ConfigFormat::Yaml => {
                serde_yaml::from_str(content).map_err(ConfigError::YamlParsing)
            }
            ConfigFormat::Json => {
                serde_json::from_str(content).map_err(ConfigError::Serialization)
            }
        }
    }

    /// Convert configuration between formats
    pub fn convert<T: serde::Serialize + serde::de::DeserializeOwned>(
        content: &str,
        from_format: ConfigFormat,
        to_format: ConfigFormat,
    ) -> ConfigResult<String> {
        let data: T = Self::deserialize(content, from_format)?;
        Self::serialize(&data, to_format)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_format_detection_from_path() {
        assert_eq!(
            FormatDetector::detect_from_path("config.toml").unwrap(),
            ConfigFormat::Toml
        );
        assert_eq!(
            FormatDetector::detect_from_path("config.yaml").unwrap(),
            ConfigFormat::Yaml
        );
        assert_eq!(
            FormatDetector::detect_from_path("config.yml").unwrap(),
            ConfigFormat::Yaml
        );
        assert_eq!(
            FormatDetector::detect_from_path("config.json").unwrap(),
            ConfigFormat::Json
        );
    }

    #[test]
    fn test_format_detection_from_content() {
        // JSON
        assert_eq!(
            FormatDetector::detect_from_content(r#"{"key": "value"}"#).unwrap(),
            ConfigFormat::Json
        );

        // YAML
        assert_eq!(
            FormatDetector::detect_from_content("key: value").unwrap(),
            ConfigFormat::Yaml
        );

        // TOML
        assert_eq!(
            FormatDetector::detect_from_content("[section]\nkey = \"value\"").unwrap(),
            ConfigFormat::Toml
        );
    }

    #[test]
    fn test_format_properties() {
        assert_eq!(ConfigFormat::Toml.extension(), "toml");
        assert_eq!(ConfigFormat::Yaml.extension(), "yaml");
        assert_eq!(ConfigFormat::Json.extension(), "json");

        assert!(ConfigFormat::Toml.supports_comments());
        assert!(ConfigFormat::Yaml.supports_comments());
        assert!(!ConfigFormat::Json.supports_comments());
    }
}