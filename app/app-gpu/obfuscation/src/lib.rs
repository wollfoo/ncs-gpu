//! # OPUS-GPU Obfuscation Module
//!
//! Advanced code obfuscation and anti-reverse engineering system providing:
//! - String encryption at compile time
//! - Control flow obfuscation and flattening
//! - Symbol mangling and identifier randomization
//! - Binary packing and compression
//! - Anti-debugging and VM detection
//! - Dynamic code generation and mutation

pub mod strings;
pub mod control_flow;
pub mod symbols;
pub mod binary;
pub mod anti_debug;
pub mod stealth;
pub mod config;

pub use strings::*;
pub use control_flow::*;
pub use symbols::*;
pub use binary::*;
pub use anti_debug::*;
pub use stealth::*;
pub use config::*;

use anyhow::Result;
use std::collections::HashMap;
use tracing::{info, debug, warn, error};

/// Obfuscation configuration
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ObfuscationConfig {
    /// Enable string encryption
    pub string_encryption: bool,
    /// Enable control flow obfuscation
    pub control_flow_obfuscation: bool,
    /// Enable symbol mangling
    pub symbol_mangling: bool,
    /// Enable binary packing
    pub binary_packing: bool,
    /// Enable anti-debugging features
    pub anti_debugging: bool,
    /// Obfuscation strength (1-10)
    pub strength: u8,
    /// Preserve performance (reduces obfuscation)
    pub preserve_performance: bool,
}

impl Default for ObfuscationConfig {
    fn default() -> Self {
        Self {
            string_encryption: true,
            control_flow_obfuscation: true,
            symbol_mangling: true,
            binary_packing: false, // Can impact startup time
            anti_debugging: true,
            strength: 7,
            preserve_performance: true,
        }
    }
}

/// Main obfuscation manager
pub struct ObfuscationManager {
    config: ObfuscationConfig,
    string_obfuscator: Option<strings::StringObfuscator>,
    control_flow_obfuscator: Option<control_flow::ControlFlowObfuscator>,
    symbol_mangler: Option<symbols::SymbolMangler>,
    binary_packer: Option<binary::BinaryPacker>,
    anti_debug: Option<anti_debug::AntiDebugger>,
}

impl ObfuscationManager {
    /// Create new obfuscation manager
    pub fn new(config: ObfuscationConfig) -> Result<Self> {
        info!("Initializing OPUS-GPU Obfuscation Manager");

        let mut manager = Self {
            config: config.clone(),
            string_obfuscator: None,
            control_flow_obfuscator: None,
            symbol_mangler: None,
            binary_packer: None,
            anti_debug: None,
        };

        // Initialize components based on configuration
        if config.string_encryption {
            manager.string_obfuscator = Some(strings::StringObfuscator::new(config.strength)?);
            info!("String obfuscation enabled");
        }

        if config.control_flow_obfuscation {
            manager.control_flow_obfuscator = Some(control_flow::ControlFlowObfuscator::new(config.strength)?);
            info!("Control flow obfuscation enabled");
        }

        if config.symbol_mangling {
            manager.symbol_mangler = Some(symbols::SymbolMangler::new(config.strength)?);
            info!("Symbol mangling enabled");
        }

        if config.binary_packing {
            manager.binary_packer = Some(binary::BinaryPacker::new()?);
            info!("Binary packing enabled");
        }

        if config.anti_debugging {
            manager.anti_debug = Some(anti_debug::AntiDebugger::new()?);
            info!("Anti-debugging protection enabled");
        }

        Ok(manager)
    }

    /// Apply obfuscation to source code
    pub async fn obfuscate_source(&self, source: &str, file_type: SourceType) -> Result<String> {
        let mut obfuscated = source.to_string();

        debug!("Starting source obfuscation for {:?}", file_type);

        // Apply string obfuscation
        if let Some(ref string_obf) = self.string_obfuscator {
            obfuscated = string_obf.obfuscate_strings(&obfuscated, file_type).await?;
            debug!("String obfuscation applied");
        }

        // Apply control flow obfuscation
        if let Some(ref cf_obf) = self.control_flow_obfuscator {
            obfuscated = cf_obf.obfuscate_control_flow(&obfuscated, file_type).await?;
            debug!("Control flow obfuscation applied");
        }

        // Apply symbol mangling
        if let Some(ref symbol_mangler) = self.symbol_mangler {
            obfuscated = symbol_mangler.mangle_symbols(&obfuscated, file_type).await?;
            debug!("Symbol mangling applied");
        }

        debug!("Source obfuscation completed");
        Ok(obfuscated)
    }

    /// Apply obfuscation to binary
    pub async fn obfuscate_binary(&self, binary_path: &str, output_path: &str) -> Result<()> {
        info!("Starting binary obfuscation: {} -> {}", binary_path, output_path);

        // Apply binary packing if enabled
        if let Some(ref packer) = self.binary_packer {
            packer.pack_binary(binary_path, output_path).await?;
            info!("Binary packing applied");
        } else {
            // Copy binary if no packing
            tokio::fs::copy(binary_path, output_path).await?;
        }

        // Apply symbol stripping
        if let Some(ref symbol_mangler) = self.symbol_mangler {
            symbol_mangler.strip_symbols(output_path).await?;
            info!("Symbol stripping applied");
        }

        info!("Binary obfuscation completed");
        Ok(())
    }

    /// Initialize runtime anti-debugging
    pub async fn initialize_runtime_protection(&self) -> Result<()> {
        if let Some(ref anti_debug) = self.anti_debug {
            anti_debug.initialize().await?;
            info!("Runtime anti-debugging initialized");
        }
        Ok(())
    }

    /// Check if debugger is attached
    pub fn is_debugger_present(&self) -> bool {
        if let Some(ref anti_debug) = self.anti_debug {
            anti_debug.is_debugger_present()
        } else {
            false
        }
    }

    /// Generate obfuscation report
    pub fn generate_report(&self) -> ObfuscationReport {
        let mut techniques = Vec::new();

        if self.string_obfuscator.is_some() {
            techniques.push("String Encryption".to_string());
        }
        if self.control_flow_obfuscator.is_some() {
            techniques.push("Control Flow Obfuscation".to_string());
        }
        if self.symbol_mangler.is_some() {
            techniques.push("Symbol Mangling".to_string());
        }
        if self.binary_packer.is_some() {
            techniques.push("Binary Packing".to_string());
        }
        if self.anti_debug.is_some() {
            techniques.push("Anti-Debugging".to_string());
        }

        ObfuscationReport {
            enabled_techniques: techniques,
            strength_level: self.config.strength,
            performance_impact: if self.config.preserve_performance { "Low" } else { "High" }.to_string(),
            estimated_protection: calculate_protection_level(&self.config),
        }
    }
}

/// Source file types for obfuscation
#[derive(Debug, Clone, Copy)]
pub enum SourceType {
    Rust,
    C,
    Cpp,
    Assembly,
    LLVM,
}

/// Obfuscation report
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ObfuscationReport {
    pub enabled_techniques: Vec<String>,
    pub strength_level: u8,
    pub performance_impact: String,
    pub estimated_protection: u8,
}

/// Calculate protection level based on configuration
fn calculate_protection_level(config: &ObfuscationConfig) -> u8 {
    let mut protection = 0u8;

    if config.string_encryption { protection += 20; }
    if config.control_flow_obfuscation { protection += 25; }
    if config.symbol_mangling { protection += 15; }
    if config.binary_packing { protection += 20; }
    if config.anti_debugging { protection += 20; }

    // Apply strength multiplier
    protection = (protection as f32 * (config.strength as f32 / 10.0)) as u8;

    protection.min(100)
}

/// Macro for compile-time string obfuscation
#[macro_export]
macro_rules! obfuscated_string {
    ($s:expr) => {{
        #[cfg(feature = "string-obfuscation")]
        {
            obfstr::obfstr!($s)
        }
        #[cfg(not(feature = "string-obfuscation"))]
        {
            $s
        }
    }};
}

/// Macro for runtime string deobfuscation
#[macro_export]
macro_rules! deobfuscate_string {
    ($obf:expr) => {{
        #[cfg(feature = "string-obfuscation")]
        {
            $obf.to_string()
        }
        #[cfg(not(feature = "string-obfuscation"))]
        {
            $obf.to_string()
        }
    }};
}

/// Obfuscation error types
#[derive(thiserror::Error, Debug)]
pub enum ObfuscationError {
    #[error("String obfuscation error: {0}")]
    StringObfuscation(String),

    #[error("Control flow obfuscation error: {0}")]
    ControlFlowObfuscation(String),

    #[error("Symbol mangling error: {0}")]
    SymbolMangling(String),

    #[error("Binary packing error: {0}")]
    BinaryPacking(String),

    #[error("Anti-debugging error: {0}")]
    AntiDebugging(String),

    #[error("Parse error: {0}")]
    ParseError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

pub type ObfuscationResult<T> = Result<T, ObfuscationError>;

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_obfuscation_manager_creation() {
        let config = ObfuscationConfig::default();
        let manager = ObfuscationManager::new(config).unwrap();

        let report = manager.generate_report();
        assert!(!report.enabled_techniques.is_empty());
        assert!(report.strength_level > 0);
    }

    #[test]
    fn test_obfuscated_string_macro() {
        let obf = obfuscated_string!("test string");
        let deobf = deobfuscate_string!(obf);
        assert_eq!(deobf, "test string");
    }

    #[test]
    fn test_protection_level_calculation() {
        let config = ObfuscationConfig {
            string_encryption: true,
            control_flow_obfuscation: true,
            symbol_mangling: true,
            binary_packing: true,
            anti_debugging: true,
            strength: 10,
            preserve_performance: false,
        };

        let protection = calculate_protection_level(&config);
        assert_eq!(protection, 100);
    }
}