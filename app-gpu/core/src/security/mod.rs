//! Security hardening module for OPUS-GPU
//! 
//! Implements code obfuscation, anti-tampering, and binary protection

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};
use anyhow::{Result, Context, bail};
use sha2::{Sha256, Digest};
use aes_gcm::{
    aead::{Aead, AeadCore, KeyInit, OsRng},
    Aes256Gcm, Key, Nonce
};
use base64::{Engine as _, engine::general_purpose};
use chrono::{DateTime, Duration, Utc};

/// Security configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityConfig {
    /// Enable code obfuscation
    pub obfuscation_enabled: bool,
    
    /// Enable anti-tampering checks
    pub anti_tampering_enabled: bool,
    
    /// Enable binary packing
    pub binary_packing_enabled: bool,
    
    /// Enable runtime integrity checks
    pub integrity_checks_enabled: bool,
    
    /// Maximum allowed debug sessions
    pub max_debug_sessions: u32,
    
    /// Anti-debugging measures
    pub anti_debugging_enabled: bool,
    
    /// Encryption key rotation interval
    pub key_rotation_interval: Duration,
}

impl Default for SecurityConfig {
    fn default() -> Self {
        Self {
            obfuscation_enabled: true,
            anti_tampering_enabled: true,
            binary_packing_enabled: true,
            integrity_checks_enabled: true,
            max_debug_sessions: 0,
            anti_debugging_enabled: true,
            key_rotation_interval: Duration::days(30),
        }
    }
}

/// Anti-tampering protection
pub struct AntiTampering {
    /// Known good checksums
    checksums: Arc<RwLock<HashMap<String, String>>>,
    
    /// Integrity verification intervals
    check_interval: Duration,
    
    /// Last check time
    last_check: Arc<RwLock<DateTime<Utc>>>,
    
    /// Tamper detection callbacks
    callbacks: Arc<RwLock<Vec<Box<dyn Fn() + Send + Sync>>>>,
}

impl AntiTampering {
    pub fn new() -> Self {
        Self {
            checksums: Arc::new(RwLock::new(HashMap::new())),
            check_interval: Duration::minutes(5),
            last_check: Arc::new(RwLock::new(Utc::now())),
            callbacks: Arc::new(RwLock::new(Vec::new())),
        }
    }
    
    /// Register a file for integrity monitoring
    pub async fn register_file(&self, path: &str) -> Result<()> {
        let content = tokio::fs::read(path).await
            .context("Failed to read file for checksum")?;
        
        let checksum = self.calculate_checksum(&content);
        
        let mut checksums = self.checksums.write().await;
        checksums.insert(path.to_string(), checksum);
        
        Ok(())
    }
    
    /// Verify file integrity
    pub async fn verify_integrity(&self, path: &str) -> Result<bool> {
        let checksums = self.checksums.read().await;
        
        let expected = checksums.get(path)
            .context("File not registered for integrity checking")?;
        
        let content = tokio::fs::read(path).await
            .context("Failed to read file for verification")?;
        
        let actual = self.calculate_checksum(&content);
        
        if &actual != expected {
            // Trigger tamper detection callbacks
            let callbacks = self.callbacks.read().await;
            for callback in callbacks.iter() {
                callback();
            }
            return Ok(false);
        }
        
        Ok(true)
    }
    
    /// Calculate SHA-256 checksum
    fn calculate_checksum(&self, data: &[u8]) -> String {
        let mut hasher = Sha256::new();
        hasher.update(data);
        format!("{:x}", hasher.finalize())
    }
    
    /// Add tamper detection callback
    pub async fn on_tamper_detected<F>(&self, callback: F)
    where
        F: Fn() + Send + Sync + 'static,
    {
        let mut callbacks = self.callbacks.write().await;
        callbacks.push(Box::new(callback));
    }
    
    /// Periodic integrity check
    pub async fn periodic_check(&self) -> Result<()> {
        let mut last_check = self.last_check.write().await;
        
        if Utc::now().signed_duration_since(*last_check) < self.check_interval {
            return Ok(());
        }
        
        let checksums = self.checksums.read().await;
        for (path, _) in checksums.iter() {
            if !self.verify_integrity(path).await? {
                bail!("Integrity check failed for: {}", path);
            }
        }
        
        *last_check = Utc::now();
        Ok(())
    }
}

/// Code obfuscation utilities
pub struct CodeObfuscator {
    /// String encryption keys
    string_keys: Arc<RwLock<HashMap<String, Vec<u8>>>>,
    
    /// Control flow flattening enabled
    control_flow_flattening: bool,
    
    /// Dead code injection ratio
    dead_code_ratio: f32,
}

impl CodeObfuscator {
    pub fn new() -> Self {
        Self {
            string_keys: Arc::new(RwLock::new(HashMap::new())),
            control_flow_flattening: true,
            dead_code_ratio: 0.2,
        }
    }
    
    /// Obfuscate string literal
    pub async fn obfuscate_string(&self, input: &str) -> Result<String> {
        let key = Aes256Gcm::generate_key(OsRng);
        let cipher = Aes256Gcm::new(&key);
        let nonce = Aes256Gcm::generate_nonce(&mut OsRng);
        
        let ciphertext = cipher.encrypt(&nonce, input.as_bytes())
            .map_err(|e| anyhow::anyhow!("Encryption failed: {}", e))?;
        
        // Store key for later decryption
        let mut keys = self.string_keys.write().await;
        keys.insert(
            general_purpose::STANDARD.encode(&ciphertext),
            key.to_vec()
        );
        
        // Return base64 encoded ciphertext
        Ok(general_purpose::STANDARD.encode(&ciphertext))
    }
    
    /// Generate obfuscated control flow
    pub fn generate_control_flow(&self, original: &str) -> String {
        if !self.control_flow_flattening {
            return original.to_string();
        }
        
        // Simplified control flow flattening
        // In production, use proper AST manipulation
        let mut obfuscated = String::new();
        
        // Add dispatcher pattern
        obfuscated.push_str("let mut state = 0;\n");
        obfuscated.push_str("loop {\n");
        obfuscated.push_str("  match state {\n");
        
        // Transform original code into state machine
        let lines: Vec<&str> = original.lines().collect();
        for (i, line) in lines.iter().enumerate() {
            obfuscated.push_str(&format!("    {} => {{\n", i));
            obfuscated.push_str(&format!("      {};\n", line));
            obfuscated.push_str(&format!("      state = {};\n", i + 1));
            obfuscated.push_str("    }\n");
        }
        
        // Add exit state
        obfuscated.push_str(&format!("    {} => break,\n", lines.len()));
        obfuscated.push_str("    _ => break,\n");
        obfuscated.push_str("  }\n");
        obfuscated.push_str("}\n");
        
        obfuscated
    }
    
    /// Inject dead code
    pub fn inject_dead_code(&self, original: &str) -> String {
        let mut result = String::from(original);
        
        // Add unreachable code blocks
        let dead_code = vec![
            "if false { println!(\"Never executed\"); }",
            "let _unused = 42 * 13;",
            "fn _dead_fn() { loop {} }",
        ];
        
        // Randomly inject dead code
        for code in dead_code {
            if rand::random::<f32>() < self.dead_code_ratio {
                result.push_str(&format!("\n{}\n", code));
            }
        }
        
        result
    }
}

/// Anti-debugging measures
pub struct AntiDebug {
    /// Debug detection methods
    detection_methods: Vec<Box<dyn Fn() -> bool + Send + Sync>>,
    
    /// Actions to take when debugger detected
    actions: Arc<RwLock<Vec<Box<dyn Fn() + Send + Sync>>>>,
}

impl AntiDebug {
    pub fn new() -> Self {
        let mut detector = Self {
            detection_methods: Vec::new(),
            actions: Arc::new(RwLock::new(Vec::new())),
        };
        
        // Add detection methods
        detector.add_ptrace_detection();
        detector.add_timing_check();
        detector.add_breakpoint_detection();
        
        detector
    }
    
    /// Add ptrace detection (Linux)
    fn add_ptrace_detection(&mut self) {
        #[cfg(target_os = "linux")]
        {
            self.detection_methods.push(Box::new(|| {
                use std::fs;
                
                // Check /proc/self/status for TracerPid
                if let Ok(status) = fs::read_to_string("/proc/self/status") {
                    for line in status.lines() {
                        if line.starts_with("TracerPid:") {
                            let pid: i32 = line.split_whitespace()
                                .nth(1)
                                .and_then(|s| s.parse().ok())
                                .unwrap_or(0);
                            return pid != 0;
                        }
                    }
                }
                false
            }));
        }
    }
    
    /// Add timing-based detection
    fn add_timing_check(&mut self) {
        self.detection_methods.push(Box::new(|| {
            use std::time::Instant;
            
            let start = Instant::now();
            
            // Perform simple operation
            let mut sum = 0u64;
            for i in 0..1000 {
                sum = sum.wrapping_add(i);
            }
            
            let elapsed = start.elapsed();
            
            // If operation takes too long, might be debugged
            elapsed.as_millis() > 10
        }));
    }
    
    /// Add software breakpoint detection
    fn add_breakpoint_detection(&mut self) {
        self.detection_methods.push(Box::new(|| {
            // Check for INT3 instruction (0xCC) in critical functions
            // This is a simplified check
            let critical_fn = critical_function as *const u8;
            unsafe {
                for i in 0..32 {
                    if *critical_fn.add(i) == 0xCC {
                        return true;
                    }
                }
            }
            false
        }));
    }
    
    /// Check for debugger presence
    pub async fn is_debugger_present(&self) -> bool {
        for method in &self.detection_methods {
            if method() {
                // Execute anti-debug actions
                let actions = self.actions.read().await;
                for action in actions.iter() {
                    action();
                }
                return true;
            }
        }
        false
    }
    
    /// Add action when debugger detected
    pub async fn on_debugger_detected<F>(&self, action: F)
    where
        F: Fn() + Send + Sync + 'static,
    {
        let mut actions = self.actions.write().await;
        actions.push(Box::new(action));
    }
}

/// Critical function for breakpoint detection
fn critical_function() {
    // Dummy critical function
    let _ = 1 + 1;
}

/// Binary packer integration
pub struct BinaryPacker {
    /// Packing method
    method: PackingMethod,
    
    /// Compression level
    compression_level: u32,
    
    /// Strip symbols
    strip_symbols: bool,
}

#[derive(Debug, Clone)]
pub enum PackingMethod {
    UPX,
    Custom,
    None,
}

impl BinaryPacker {
    pub fn new(method: PackingMethod) -> Self {
        Self {
            method,
            compression_level: 9,
            strip_symbols: true,
        }
    }
    
    /// Pack binary using UPX
    pub async fn pack_binary(&self, input: &str, output: &str) -> Result<()> {
        match self.method {
            PackingMethod::UPX => {
                // Strip symbols first
                if self.strip_symbols {
                    tokio::process::Command::new("strip")
                        .arg("--strip-all")
                        .arg(input)
                        .output()
                        .await
                        .context("Failed to strip symbols")?;
                }
                
                // Pack with UPX
                let result = tokio::process::Command::new("upx")
                    .arg(format!("-{}", self.compression_level))
                    .arg("-o")
                    .arg(output)
                    .arg(input)
                    .output()
                    .await
                    .context("Failed to run UPX")?;
                
                if !result.status.success() {
                    bail!("UPX packing failed: {}", String::from_utf8_lossy(&result.stderr));
                }
            }
            PackingMethod::Custom => {
                // Custom packing implementation
                self.custom_pack(input, output).await?;
            }
            PackingMethod::None => {
                // Just copy the binary
                tokio::fs::copy(input, output).await?;
            }
        }
        
        Ok(())
    }
    
    /// Custom packing implementation
    async fn custom_pack(&self, input: &str, output: &str) -> Result<()> {
        // Read binary
        let data = tokio::fs::read(input).await?;
        
        // Simple XOR obfuscation (for demonstration)
        let key = 0x42u8;
        let obfuscated: Vec<u8> = data.iter().map(|b| b ^ key).collect();
        
        // Create self-extracting stub
        let mut packed = Vec::new();
        
        // Add decompression stub
        packed.extend_from_slice(b"#!/bin/sh\n");
        packed.extend_from_slice(b"tail -n +3 $0 | base64 -d | xz -d > /tmp/opus_tmp\n");
        packed.extend_from_slice(b"chmod +x /tmp/opus_tmp && /tmp/opus_tmp \"$@\" ; rm /tmp/opus_tmp ; exit\n");
        
        // Add compressed data
        let compressed = self.compress_data(&obfuscated)?;
        packed.extend_from_slice(&general_purpose::STANDARD.encode(&compressed).as_bytes());
        
        // Write packed binary
        tokio::fs::write(output, packed).await?;
        
        // Make executable
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = tokio::fs::metadata(output).await?.permissions();
            perms.set_mode(0o755);
            tokio::fs::set_permissions(output, perms).await?;
        }
        
        Ok(())
    }
    
    /// Compress data using XZ
    fn compress_data(&self, data: &[u8]) -> Result<Vec<u8>> {
        // In production, use proper XZ compression
        // For now, return as-is (mock)
        Ok(data.to_vec())
    }
}

/// Security manager
pub struct SecurityManager {
    config: SecurityConfig,
    anti_tampering: AntiTampering,
    obfuscator: CodeObfuscator,
    anti_debug: AntiDebug,
    packer: BinaryPacker,
}

impl SecurityManager {
    pub fn new(config: SecurityConfig) -> Self {
        Self {
            config: config.clone(),
            anti_tampering: AntiTampering::new(),
            obfuscator: CodeObfuscator::new(),
            anti_debug: AntiDebug::new(),
            packer: BinaryPacker::new(
                if config.binary_packing_enabled {
                    PackingMethod::UPX
                } else {
                    PackingMethod::None
                }
            ),
        }
    }
    
    /// Initialize security measures
    pub async fn initialize(&self) -> Result<()> {
        // Register critical files for integrity monitoring
        if self.config.integrity_checks_enabled {
            self.anti_tampering.register_file("/proc/self/exe").await?;
        }
        
        // Set up anti-debugging callbacks
        if self.config.anti_debugging_enabled {
            self.anti_debug.on_debugger_detected(|| {
                eprintln!("Debugger detected! Terminating...");
                std::process::exit(1);
            }).await;
        }
        
        // Set up tamper detection callbacks
        if self.config.anti_tampering_enabled {
            self.anti_tampering.on_tamper_detected(|| {
                eprintln!("Tampering detected! Shutting down...");
                std::process::exit(1);
            }).await;
        }
        
        Ok(())
    }
    
    /// Perform security checks
    pub async fn perform_checks(&self) -> Result<()> {
        // Check for debugger
        if self.config.anti_debugging_enabled {
            if self.anti_debug.is_debugger_present().await {
                bail!("Debugger detected");
            }
        }
        
        // Verify integrity
        if self.config.integrity_checks_enabled {
            self.anti_tampering.periodic_check().await?;
        }
        
        Ok(())
    }
    
    /// Harden binary for production
    pub async fn harden_binary(&self, input: &str, output: &str) -> Result<()> {
        // Pack the binary
        self.packer.pack_binary(input, output).await?;
        
        // Register for integrity monitoring
        if self.config.integrity_checks_enabled {
            self.anti_tampering.register_file(output).await?;
        }
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_anti_tampering() {
        let anti_tamper = AntiTampering::new();
        
        // Create test file
        let test_file = "/tmp/test_integrity.txt";
        tokio::fs::write(test_file, b"test content").await.unwrap();
        
        // Register and verify
        anti_tamper.register_file(test_file).await.unwrap();
        assert!(anti_tamper.verify_integrity(test_file).await.unwrap());
        
        // Modify file
        tokio::fs::write(test_file, b"modified content").await.unwrap();
        assert!(!anti_tamper.verify_integrity(test_file).await.unwrap());
        
        // Cleanup
        tokio::fs::remove_file(test_file).await.unwrap();
    }
    
    #[tokio::test]
    async fn test_code_obfuscation() {
        let obfuscator = CodeObfuscator::new();
        
        // Test string obfuscation
        let original = "sensitive data";
        let obfuscated = obfuscator.obfuscate_string(original).await.unwrap();
        assert_ne!(original, obfuscated);
        
        // Test control flow flattening
        let code = "let x = 1;\nlet y = 2;\nlet z = x + y;";
        let flattened = obfuscator.generate_control_flow(code);
        assert!(flattened.contains("match state"));
        
        // Test dead code injection
        let with_dead = obfuscator.inject_dead_code(code);
        assert!(with_dead.len() >= code.len());
    }
}
