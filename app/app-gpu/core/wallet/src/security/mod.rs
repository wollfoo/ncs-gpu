//! Security Layer Module
//!
//! Comprehensive security implementation for wallet operations including encryption,
//! hardware wallet support, and secure key management.

pub mod encryption;
pub mod keystore;
pub mod password;
pub mod secure_storage;

#[cfg(feature = "hardware-wallet")]
pub mod hardware_wallet;

pub use encryption::{EncryptionManager, EncryptionMethod};
pub use keystore::{KeyStore, SecureKeyStore};
pub use password::{PasswordManager, PasswordPolicy, PasswordStrength};
pub use secure_storage::{SecureStorage, SecureStorageBackend};

#[cfg(feature = "hardware-wallet")]
pub use hardware_wallet::{HardwareWalletManager, HardwareWalletType};

use crate::{
    types::WalletConfig,
    WalletError, WalletResult,
};
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;
use zeroize::{Zeroize, ZeroizeOnDrop};

/// Security session identifier
pub type SecuritySessionId = Uuid;

/// Security manager interface
#[async_trait]
pub trait SecurityManagerTrait: Send + Sync {
    /// Authenticate user with password
    async fn authenticate(&self, password: &str) -> WalletResult<SecuritySession>;

    /// Create secure session
    async fn create_session(&self, password: &str) -> WalletResult<SecuritySession>;

    /// Validate existing session
    async fn validate_session(&self, session_id: &SecuritySessionId) -> WalletResult<bool>;

    /// Revoke session
    async fn revoke_session(&self, session_id: &SecuritySessionId) -> WalletResult<()>;

    /// Encrypt sensitive data
    async fn encrypt_data(&self, data: &[u8], session: &SecuritySession) -> WalletResult<Vec<u8>>;

    /// Decrypt sensitive data
    async fn decrypt_data(&self, encrypted_data: &[u8], session: &SecuritySession) -> WalletResult<Vec<u8>>;

    /// Store encrypted data securely
    async fn store_secure(&self, key: &str, data: &[u8], session: &SecuritySession) -> WalletResult<()>;

    /// Retrieve and decrypt stored data
    async fn retrieve_secure(&self, key: &str, session: &SecuritySession) -> WalletResult<Option<Vec<u8>>>;

    /// Change authentication password
    async fn change_password(&self, old_password: &str, new_password: &str) -> WalletResult<()>;

    /// Setup hardware wallet integration
    #[cfg(feature = "hardware-wallet")]
    async fn setup_hardware_wallet(&self) -> WalletResult<()>;

    /// Get security status
    async fn get_security_status(&self) -> WalletResult<SecurityStatus>;
}

/// Core security manager implementation
#[derive(Debug)]
pub struct SecurityManager {
    config: WalletConfig,
    encryption_manager: EncryptionManager,
    password_manager: PasswordManager,
    keystore: SecureKeyStore,
    secure_storage: Box<dyn SecureStorageBackend>,
    sessions: tokio::sync::RwLock<HashMap<SecuritySessionId, SecuritySession>>,

    #[cfg(feature = "hardware-wallet")]
    hardware_wallet_manager: Option<HardwareWalletManager>,
}

impl SecurityManager {
    /// Create new security manager
    pub async fn new(config: WalletConfig) -> WalletResult<Self> {
        let encryption_manager = EncryptionManager::new(config.security.encryption_algorithm.clone())?;
        let password_manager = PasswordManager::new(PasswordPolicy::from_config(&config.security));
        let keystore = SecureKeyStore::new(config.clone()).await?;
        let secure_storage = secure_storage::create_backend(&config).await?;

        #[cfg(feature = "hardware-wallet")]
        let hardware_wallet_manager = if config.hardware_wallet.enable_ledger || config.hardware_wallet.enable_trezor {
            Some(HardwareWalletManager::new(config.hardware_wallet.clone()).await?)
        } else {
            None
        };

        Ok(Self {
            config,
            encryption_manager,
            password_manager,
            keystore,
            secure_storage,
            sessions: tokio::sync::RwLock::new(HashMap::new()),

            #[cfg(feature = "hardware-wallet")]
            hardware_wallet_manager,
        })
    }

    /// Initialize security manager
    pub async fn initialize(&self) -> WalletResult<()> {
        tracing::info!("Initializing security manager");

        // Initialize encryption manager
        self.encryption_manager.initialize().await?;

        // Initialize keystore
        self.keystore.initialize().await?;

        // Initialize secure storage
        self.secure_storage.initialize().await?;

        #[cfg(feature = "hardware-wallet")]
        if let Some(ref hw_manager) = self.hardware_wallet_manager {
            hw_manager.initialize().await?;
        }

        tracing::info!("Security manager initialized successfully");
        Ok(())
    }

    /// Shutdown security manager
    pub async fn shutdown(&self) -> WalletResult<()> {
        tracing::info!("Shutting down security manager");

        // Clear all active sessions
        {
            let mut sessions = self.sessions.write().await;
            for (_, mut session) in sessions.drain() {
                session.zeroize();
            }
        }

        // Shutdown components
        self.keystore.shutdown().await?;
        self.secure_storage.shutdown().await?;

        #[cfg(feature = "hardware-wallet")]
        if let Some(ref hw_manager) = self.hardware_wallet_manager {
            hw_manager.shutdown().await?;
        }

        tracing::info!("Security manager shutdown complete");
        Ok(())
    }

    /// Cleanup expired sessions
    async fn cleanup_expired_sessions(&self) {
        let mut sessions = self.sessions.write().await;
        let now = chrono::Utc::now();

        sessions.retain(|_, session| {
            if now.signed_duration_since(session.created_at).num_minutes()
                < self.config.security.session_timeout_minutes as i64 {
                true
            } else {
                tracing::debug!("Removing expired session: {}", session.id);
                false
            }
        });
    }

    /// Generate session encryption key
    async fn generate_session_key(&self, password: &str) -> WalletResult<Vec<u8>> {
        self.encryption_manager.derive_key_from_password(
            password,
            &self.keystore.get_salt().await?,
            self.config.security.key_derivation_iterations,
        ).await
    }

    /// Create secure session with timeout
    async fn create_secure_session(&self, password: &str) -> WalletResult<SecuritySession> {
        // Verify password strength
        let strength = self.password_manager.check_strength(password)?;
        if strength < PasswordStrength::Good {
            return Err(WalletError::SecurityPolicyViolation {
                reason: format!("Password strength insufficient: {:?}", strength),
            });
        }

        // Verify password against stored hash
        let password_valid = self.keystore.verify_password(password).await?;
        if !password_valid {
            return Err(WalletError::AuthenticationError {
                reason: "Invalid password".to_string(),
            });
        }

        // Generate session key
        let session_key = self.generate_session_key(password).await?;

        let session = SecuritySession::new(session_key);

        // Store session
        {
            let mut sessions = self.sessions.write().await;
            sessions.insert(session.id, session.clone());
        }

        // Schedule cleanup
        tokio::spawn({
            let sessions = self.sessions.clone();
            let timeout = self.config.security.session_timeout_minutes;
            async move {
                tokio::time::sleep(std::time::Duration::from_secs((timeout * 60) as u64)).await;
                let mut sessions = sessions.write().await;
                sessions.remove(&session.id);
            }
        });

        Ok(session)
    }
}

#[async_trait]
impl SecurityManagerTrait for SecurityManager {
    async fn authenticate(&self, password: &str) -> WalletResult<SecuritySession> {
        self.create_secure_session(password).await
    }

    async fn create_session(&self, password: &str) -> WalletResult<SecuritySession> {
        self.create_secure_session(password).await
    }

    async fn validate_session(&self, session_id: &SecuritySessionId) -> WalletResult<bool> {
        // Cleanup expired sessions first
        self.cleanup_expired_sessions().await;

        let sessions = self.sessions.read().await;
        Ok(sessions.contains_key(session_id))
    }

    async fn revoke_session(&self, session_id: &SecuritySessionId) -> WalletResult<()> {
        let mut sessions = self.sessions.write().await;
        if let Some(mut session) = sessions.remove(session_id) {
            session.zeroize();
            tracing::info!("Session {} revoked", session_id);
        }
        Ok(())
    }

    async fn encrypt_data(&self, data: &[u8], session: &SecuritySession) -> WalletResult<Vec<u8>> {
        if !self.validate_session(&session.id).await? {
            return Err(WalletError::SecurityPolicyViolation {
                reason: "Invalid or expired session".to_string(),
            });
        }

        self.encryption_manager.encrypt(data, &session.key).await
    }

    async fn decrypt_data(&self, encrypted_data: &[u8], session: &SecuritySession) -> WalletResult<Vec<u8>> {
        if !self.validate_session(&session.id).await? {
            return Err(WalletError::SecurityPolicyViolation {
                reason: "Invalid or expired session".to_string(),
            });
        }

        self.encryption_manager.decrypt(encrypted_data, &session.key).await
    }

    async fn store_secure(&self, key: &str, data: &[u8], session: &SecuritySession) -> WalletResult<()> {
        let encrypted_data = self.encrypt_data(data, session).await?;
        self.secure_storage.store(key, &encrypted_data).await
    }

    async fn retrieve_secure(&self, key: &str, session: &SecuritySession) -> WalletResult<Option<Vec<u8>>> {
        if let Some(encrypted_data) = self.secure_storage.retrieve(key).await? {
            let decrypted_data = self.decrypt_data(&encrypted_data, session).await?;
            Ok(Some(decrypted_data))
        } else {
            Ok(None)
        }
    }

    async fn change_password(&self, old_password: &str, new_password: &str) -> WalletResult<()> {
        // Verify old password
        if !self.keystore.verify_password(old_password).await? {
            return Err(WalletError::AuthenticationError {
                reason: "Current password is incorrect".to_string(),
            });
        }

        // Validate new password
        let strength = self.password_manager.check_strength(new_password)?;
        if strength < PasswordStrength::Good {
            return Err(WalletError::SecurityPolicyViolation {
                reason: format!("New password strength insufficient: {:?}", strength),
            });
        }

        // Update password
        self.keystore.update_password(new_password).await?;

        // Revoke all existing sessions
        {
            let mut sessions = self.sessions.write().await;
            for (_, mut session) in sessions.drain() {
                session.zeroize();
            }
        }

        tracing::info!("Password changed successfully, all sessions revoked");
        Ok(())
    }

    #[cfg(feature = "hardware-wallet")]
    async fn setup_hardware_wallet(&self) -> WalletResult<()> {
        if let Some(ref hw_manager) = self.hardware_wallet_manager {
            hw_manager.setup().await
        } else {
            Err(WalletError::OperationNotSupported {
                operation: "Hardware wallet support not enabled".to_string(),
            })
        }
    }

    async fn get_security_status(&self) -> WalletResult<SecurityStatus> {
        let sessions = self.sessions.read().await;
        let active_sessions = sessions.len();

        #[cfg(feature = "hardware-wallet")]
        let hardware_wallet_connected = if let Some(ref hw_manager) = self.hardware_wallet_manager {
            hw_manager.is_connected().await.unwrap_or(false)
        } else {
            false
        };

        #[cfg(not(feature = "hardware-wallet"))]
        let hardware_wallet_connected = false;

        Ok(SecurityStatus {
            encryption_enabled: true,
            password_protected: self.keystore.has_password().await?,
            hardware_wallet_connected,
            active_sessions,
            last_authentication: None, // Would track last auth time
            security_level: self.calculate_security_level().await?,
        })
    }
}

impl SecurityManager {
    /// Calculate overall security level
    async fn calculate_security_level(&self) -> WalletResult<SecurityLevel> {
        let mut score = 0;

        // Base encryption
        score += 20;

        // Password protection
        if self.keystore.has_password().await? {
            score += 30;
        }

        // Hardware wallet
        #[cfg(feature = "hardware-wallet")]
        if let Some(ref hw_manager) = self.hardware_wallet_manager {
            if hw_manager.is_connected().await.unwrap_or(false) {
                score += 40;
            }
        }

        // Session management
        score += 10;

        match score {
            0..=30 => Ok(SecurityLevel::Low),
            31..=60 => Ok(SecurityLevel::Medium),
            61..=80 => Ok(SecurityLevel::High),
            _ => Ok(SecurityLevel::Maximum),
        }
    }
}

/// Security session for authenticated operations
#[derive(Debug, Clone, Zeroize, ZeroizeOnDrop)]
pub struct SecuritySession {
    pub id: SecuritySessionId,
    #[zeroize(skip)]
    pub created_at: chrono::DateTime<chrono::Utc>,
    pub key: Vec<u8>,
}

impl SecuritySession {
    /// Create new security session
    pub fn new(key: Vec<u8>) -> Self {
        Self {
            id: Uuid::new_v4(),
            created_at: chrono::Utc::now(),
            key,
        }
    }

    /// Check if session is expired
    pub fn is_expired(&self, timeout_minutes: u32) -> bool {
        let now = chrono::Utc::now();
        now.signed_duration_since(self.created_at).num_minutes() >= timeout_minutes as i64
    }

    /// Get session age in minutes
    pub fn age_minutes(&self) -> i64 {
        let now = chrono::Utc::now();
        now.signed_duration_since(self.created_at).num_minutes()
    }
}

/// Security status information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SecurityStatus {
    pub encryption_enabled: bool,
    pub password_protected: bool,
    pub hardware_wallet_connected: bool,
    pub active_sessions: usize,
    pub last_authentication: Option<chrono::DateTime<chrono::Utc>>,
    pub security_level: SecurityLevel,
}

/// Security level enumeration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum SecurityLevel {
    Low,
    Medium,
    High,
    Maximum,
}

impl SecurityLevel {
    pub fn description(&self) -> &'static str {
        match self {
            SecurityLevel::Low => "Basic security (encryption only)",
            SecurityLevel::Medium => "Good security (password protected)",
            SecurityLevel::High => "High security (hardware wallet or advanced features)",
            SecurityLevel::Maximum => "Maximum security (all features enabled)",
        }
    }

    pub fn score(&self) -> u8 {
        match self {
            SecurityLevel::Low => 25,
            SecurityLevel::Medium => 50,
            SecurityLevel::High => 75,
            SecurityLevel::Maximum => 100,
        }
    }
}

impl std::fmt::Display for SecurityLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SecurityLevel::Low => write!(f, "Low"),
            SecurityLevel::Medium => write!(f, "Medium"),
            SecurityLevel::High => write!(f, "High"),
            SecurityLevel::Maximum => write!(f, "Maximum"),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    async fn create_test_security_manager() -> (SecurityManager, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let config = WalletConfig::default_with_path(temp_dir.path().to_path_buf());
        let manager = SecurityManager::new(config).await.unwrap();
        (manager, temp_dir)
    }

    #[tokio::test]
    async fn test_security_manager_creation() {
        let (_manager, _temp_dir) = create_test_security_manager().await;
        // Success if no panic
    }

    #[tokio::test]
    async fn test_security_session() {
        let key = vec![1u8; 32];
        let session = SecuritySession::new(key.clone());

        assert_eq!(session.key, key);
        assert!(!session.is_expired(30)); // Should not be expired immediately
        assert!(session.age_minutes() >= 0);
    }

    #[tokio::test]
    async fn test_session_validation() {
        let (manager, _temp_dir) = create_test_security_manager().await;
        manager.initialize().await.unwrap();

        // Setup password first
        manager.keystore.setup_password("test_password_123").await.unwrap();

        let session = manager.create_session("test_password_123").await.unwrap();
        assert!(manager.validate_session(&session.id).await.unwrap());

        // Revoke session
        manager.revoke_session(&session.id).await.unwrap();
        assert!(!manager.validate_session(&session.id).await.unwrap());
    }

    #[tokio::test]
    async fn test_encryption_decryption() {
        let (manager, _temp_dir) = create_test_security_manager().await;
        manager.initialize().await.unwrap();

        // Setup password
        manager.keystore.setup_password("test_password_123").await.unwrap();

        let session = manager.create_session("test_password_123").await.unwrap();
        let test_data = b"sensitive data";

        let encrypted = manager.encrypt_data(test_data, &session).await.unwrap();
        assert_ne!(encrypted, test_data);

        let decrypted = manager.decrypt_data(&encrypted, &session).await.unwrap();
        assert_eq!(decrypted, test_data);
    }

    #[tokio::test]
    async fn test_secure_storage() {
        let (manager, _temp_dir) = create_test_security_manager().await;
        manager.initialize().await.unwrap();

        // Setup password
        manager.keystore.setup_password("test_password_123").await.unwrap();

        let session = manager.create_session("test_password_123").await.unwrap();
        let test_data = b"stored data";

        // Store data
        manager.store_secure("test_key", test_data, &session).await.unwrap();

        // Retrieve data
        let retrieved = manager.retrieve_secure("test_key", &session).await.unwrap();
        assert_eq!(retrieved, Some(test_data.to_vec()));

        // Try non-existent key
        let not_found = manager.retrieve_secure("non_existent", &session).await.unwrap();
        assert_eq!(not_found, None);
    }

    #[tokio::test]
    async fn test_security_status() {
        let (manager, _temp_dir) = create_test_security_manager().await;
        manager.initialize().await.unwrap();

        let status = manager.get_security_status().await.unwrap();
        assert!(status.encryption_enabled);
        assert!(!status.password_protected); // No password set yet
        assert_eq!(status.active_sessions, 0);
    }
}