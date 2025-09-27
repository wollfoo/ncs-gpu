//! Authentication and Authorization module for OPUS-GPU
//! 
//! Implements mTLS, API key management, and RBAC

use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};
use anyhow::{Result, Context, bail};
use chrono::{DateTime, Duration, Utc};
use jsonwebtoken::{encode, decode, Header, Validation, EncodingKey, DecodingKey, Algorithm};
use uuid::Uuid;
use sha2::{Sha256, Digest};
use rustls::{Certificate, PrivateKey, ServerConfig, ClientConfig};
use rustls_pemfile::{certs, pkcs8_private_keys};
use std::io::BufReader;

/// Authentication configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuthConfig {
    /// Enable mTLS
    pub mtls_enabled: bool,
    
    /// Enable API key authentication
    pub api_key_enabled: bool,
    
    /// Enable JWT authentication
    pub jwt_enabled: bool,
    
    /// JWT secret key
    pub jwt_secret: String,
    
    /// JWT expiration duration
    pub jwt_expiration: Duration,
    
    /// API key rotation interval
    pub api_key_rotation: Duration,
    
    /// Maximum sessions per user
    pub max_sessions_per_user: u32,
    
    /// Session timeout
    pub session_timeout: Duration,
    
    /// Enable RBAC
    pub rbac_enabled: bool,
}

impl Default for AuthConfig {
    fn default() -> Self {
        Self {
            mtls_enabled: true,
            api_key_enabled: true,
            jwt_enabled: true,
            jwt_secret: "change-me-in-production".to_string(),
            jwt_expiration: Duration::hours(24),
            api_key_rotation: Duration::days(90),
            max_sessions_per_user: 5,
            session_timeout: Duration::hours(8),
            rbac_enabled: true,
        }
    }
}

/// User identity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Identity {
    /// User ID
    pub id: Uuid,
    
    /// Username
    pub username: String,
    
    /// Email
    pub email: Option<String>,
    
    /// Roles
    pub roles: Vec<String>,
    
    /// Permissions
    pub permissions: Vec<String>,
    
    /// API keys
    pub api_keys: Vec<ApiKey>,
    
    /// Active sessions
    pub sessions: Vec<Session>,
    
    /// Created at
    pub created_at: DateTime<Utc>,
    
    /// Last activity
    pub last_activity: DateTime<Utc>,
}

/// API Key
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiKey {
    /// Key ID
    pub id: Uuid,
    
    /// Key value (hashed)
    pub key_hash: String,
    
    /// Key name
    pub name: String,
    
    /// Permissions
    pub permissions: Vec<String>,
    
    /// Rate limit
    pub rate_limit: Option<u32>,
    
    /// Expiration
    pub expires_at: Option<DateTime<Utc>>,
    
    /// Created at
    pub created_at: DateTime<Utc>,
    
    /// Last used
    pub last_used: Option<DateTime<Utc>>,
    
    /// Is active
    pub is_active: bool,
}

/// User session
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Session {
    /// Session ID
    pub id: Uuid,
    
    /// User ID
    pub user_id: Uuid,
    
    /// JWT token
    pub token: String,
    
    /// IP address
    pub ip_address: String,
    
    /// User agent
    pub user_agent: String,
    
    /// Created at
    pub created_at: DateTime<Utc>,
    
    /// Last activity
    pub last_activity: DateTime<Utc>,
    
    /// Expires at
    pub expires_at: DateTime<Utc>,
}

/// JWT Claims
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Claims {
    /// Subject (user ID)
    pub sub: String,
    
    /// Issued at
    pub iat: i64,
    
    /// Expiration
    pub exp: i64,
    
    /// Username
    pub username: String,
    
    /// Roles
    pub roles: Vec<String>,
    
    /// Permissions
    pub permissions: Vec<String>,
}

/// Role-Based Access Control
#[derive(Debug, Clone)]
pub struct RBAC {
    /// Roles definition
    roles: Arc<RwLock<HashMap<String, Role>>>,
    
    /// Permission registry
    permissions: Arc<RwLock<HashMap<String, Permission>>>,
    
    /// Role hierarchy
    hierarchy: Arc<RwLock<HashMap<String, Vec<String>>>>,
}

/// Role definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Role {
    /// Role name
    pub name: String,
    
    /// Description
    pub description: String,
    
    /// Permissions
    pub permissions: Vec<String>,
    
    /// Parent roles
    pub parents: Vec<String>,
    
    /// Created at
    pub created_at: DateTime<Utc>,
}

/// Permission definition
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Permission {
    /// Permission name
    pub name: String,
    
    /// Resource
    pub resource: String,
    
    /// Action
    pub action: String,
    
    /// Description
    pub description: String,
}

impl RBAC {
    pub fn new() -> Self {
        Self {
            roles: Arc::new(RwLock::new(HashMap::new())),
            permissions: Arc::new(RwLock::new(HashMap::new())),
            hierarchy: Arc::new(RwLock::new(HashMap::new())),
        }
    }
    
    /// Initialize default roles and permissions
    pub async fn initialize_defaults(&self) -> Result<()> {
        // Define default permissions
        let default_permissions = vec![
            Permission {
                name: "gpu.execute".to_string(),
                resource: "gpu".to_string(),
                action: "execute".to_string(),
                description: "Execute GPU tasks".to_string(),
            },
            Permission {
                name: "gpu.monitor".to_string(),
                resource: "gpu".to_string(),
                action: "monitor".to_string(),
                description: "Monitor GPU status".to_string(),
            },
            Permission {
                name: "system.admin".to_string(),
                resource: "system".to_string(),
                action: "admin".to_string(),
                description: "System administration".to_string(),
            },
            Permission {
                name: "api.read".to_string(),
                resource: "api".to_string(),
                action: "read".to_string(),
                description: "Read API data".to_string(),
            },
            Permission {
                name: "api.write".to_string(),
                resource: "api".to_string(),
                action: "write".to_string(),
                description: "Write API data".to_string(),
            },
        ];
        
        let mut permissions = self.permissions.write().await;
        for perm in default_permissions {
            permissions.insert(perm.name.clone(), perm);
        }
        
        // Define default roles
        let default_roles = vec![
            Role {
                name: "admin".to_string(),
                description: "System Administrator".to_string(),
                permissions: vec![
                    "system.admin".to_string(),
                    "gpu.execute".to_string(),
                    "gpu.monitor".to_string(),
                    "api.read".to_string(),
                    "api.write".to_string(),
                ],
                parents: vec![],
                created_at: Utc::now(),
            },
            Role {
                name: "operator".to_string(),
                description: "GPU Operator".to_string(),
                permissions: vec![
                    "gpu.execute".to_string(),
                    "gpu.monitor".to_string(),
                    "api.read".to_string(),
                ],
                parents: vec![],
                created_at: Utc::now(),
            },
            Role {
                name: "viewer".to_string(),
                description: "Read-only Access".to_string(),
                permissions: vec![
                    "gpu.monitor".to_string(),
                    "api.read".to_string(),
                ],
                parents: vec![],
                created_at: Utc::now(),
            },
        ];
        
        let mut roles = self.roles.write().await;
        for role in default_roles {
            roles.insert(role.name.clone(), role);
        }
        
        Ok(())
    }
    
    /// Check if user has permission
    pub async fn check_permission(
        &self,
        user_roles: &[String],
        permission: &str
    ) -> Result<bool> {
        let roles = self.roles.read().await;
        
        for user_role in user_roles {
            if let Some(role) = roles.get(user_role) {
                if role.permissions.contains(&permission.to_string()) {
                    return Ok(true);
                }
                
                // Check parent roles recursively
                if self.check_parent_permissions(&role.parents, permission, &roles).await? {
                    return Ok(true);
                }
            }
        }
        
        Ok(false)
    }
    
    /// Check parent roles for permission
    async fn check_parent_permissions(
        &self,
        parents: &[String],
        permission: &str,
        roles: &HashMap<String, Role>
    ) -> Result<bool> {
        for parent in parents {
            if let Some(parent_role) = roles.get(parent) {
                if parent_role.permissions.contains(&permission.to_string()) {
                    return Ok(true);
                }
                
                // Recursive check
                if self.check_parent_permissions(&parent_role.parents, permission, roles).await? {
                    return Ok(true);
                }
            }
        }
        
        Ok(false)
    }
}

/// mTLS configuration
pub struct MutualTLS {
    /// Server configuration
    server_config: Arc<ServerConfig>,
    
    /// Client configuration
    client_config: Arc<ClientConfig>,
    
    /// Client certificate validation
    client_validator: Arc<dyn Fn(&Certificate) -> bool + Send + Sync>,
}

impl MutualTLS {
    /// Create new mTLS configuration
    pub fn new(
        server_cert_path: &str,
        server_key_path: &str,
        ca_cert_path: &str
    ) -> Result<Self> {
        // Load server certificate and key
        let server_cert_file = std::fs::File::open(server_cert_path)?;
        let server_key_file = std::fs::File::open(server_key_path)?;
        let ca_cert_file = std::fs::File::open(ca_cert_path)?;
        
        let server_certs = certs(&mut BufReader::new(server_cert_file))?
            .into_iter()
            .map(Certificate)
            .collect::<Vec<_>>();
        
        let server_keys = pkcs8_private_keys(&mut BufReader::new(server_key_file))?
            .into_iter()
            .map(PrivateKey)
            .collect::<Vec<_>>();
        
        let ca_certs = certs(&mut BufReader::new(ca_cert_file))?
            .into_iter()
            .map(Certificate)
            .collect::<Vec<_>>();
        
        // Create server config
        let server_config = ServerConfig::builder()
            .with_safe_defaults()
            .with_client_cert_verifier(
                rustls::server::AllowAnyAuthenticatedClient::new(
                    rustls::RootCertStore::from(ca_certs.clone())
                )
            )
            .with_single_cert(server_certs, server_keys[0].clone())?;
        
        // Create client config
        let mut root_store = rustls::RootCertStore::empty();
        for cert in ca_certs {
            root_store.add(&cert)?;
        }
        
        let client_config = ClientConfig::builder()
            .with_safe_defaults()
            .with_root_certificates(root_store)
            .with_no_client_auth();
        
        Ok(Self {
            server_config: Arc::new(server_config),
            client_config: Arc::new(client_config),
            client_validator: Arc::new(|_cert| true), // Default: accept all valid certs
        })
    }
    
    /// Validate client certificate
    pub fn validate_client_cert(&self, cert: &Certificate) -> bool {
        (self.client_validator)(cert)
    }
}

/// Authentication manager
pub struct AuthManager {
    config: AuthConfig,
    users: Arc<RwLock<HashMap<Uuid, Identity>>>,
    sessions: Arc<RwLock<HashMap<Uuid, Session>>>,
    api_keys: Arc<RwLock<HashMap<String, ApiKey>>>,
    rbac: RBAC,
    mtls: Option<MutualTLS>,
}

impl AuthManager {
    pub fn new(config: AuthConfig) -> Self {
        Self {
            config,
            users: Arc::new(RwLock::new(HashMap::new())),
            sessions: Arc::new(RwLock::new(HashMap::new())),
            api_keys: Arc::new(RwLock::new(HashMap::new())),
            rbac: RBAC::new(),
            mtls: None,
        }
    }
    
    /// Initialize authentication system
    pub async fn initialize(&mut self) -> Result<()> {
        // Initialize RBAC
        if self.config.rbac_enabled {
            self.rbac.initialize_defaults().await?;
        }
        
        // Initialize mTLS if enabled
        if self.config.mtls_enabled {
            // In production, load from config
            // self.mtls = Some(MutualTLS::new(
            //     &self.config.server_cert_path,
            //     &self.config.server_key_path,
            //     &self.config.ca_cert_path
            // )?);
        }
        
        // Create default admin user
        self.create_default_admin().await?;
        
        Ok(())
    }
    
    /// Create default admin user
    async fn create_default_admin(&self) -> Result<()> {
        let admin_id = Uuid::new_v4();
        
        let admin = Identity {
            id: admin_id,
            username: "admin".to_string(),
            email: Some("admin@opus-gpu.local".to_string()),
            roles: vec!["admin".to_string()],
            permissions: vec!["system.admin".to_string()],
            api_keys: vec![],
            sessions: vec![],
            created_at: Utc::now(),
            last_activity: Utc::now(),
        };
        
        let mut users = self.users.write().await;
        users.insert(admin_id, admin);
        
        Ok(())
    }
    
    /// Authenticate with API key
    pub async fn authenticate_api_key(&self, key: &str) -> Result<Identity> {
        let key_hash = self.hash_api_key(key);
        
        let api_keys = self.api_keys.read().await;
        let api_key = api_keys.get(&key_hash)
            .context("Invalid API key")?;
        
        if !api_key.is_active {
            bail!("API key is inactive");
        }
        
        if let Some(expires_at) = api_key.expires_at {
            if Utc::now() > expires_at {
                bail!("API key has expired");
            }
        }
        
        // Find user with this API key
        let users = self.users.read().await;
        for user in users.values() {
            if user.api_keys.iter().any(|k| k.id == api_key.id) {
                return Ok(user.clone());
            }
        }
        
        bail!("User not found for API key");
    }
    
    /// Create JWT token
    pub fn create_jwt(&self, identity: &Identity) -> Result<String> {
        let expiration = Utc::now() + self.config.jwt_expiration;
        
        let claims = Claims {
            sub: identity.id.to_string(),
            iat: Utc::now().timestamp(),
            exp: expiration.timestamp(),
            username: identity.username.clone(),
            roles: identity.roles.clone(),
            permissions: identity.permissions.clone(),
        };
        
        let token = encode(
            &Header::default(),
            &claims,
            &EncodingKey::from_secret(self.config.jwt_secret.as_bytes())
        )?;
        
        Ok(token)
    }
    
    /// Validate JWT token
    pub fn validate_jwt(&self, token: &str) -> Result<Claims> {
        let validation = Validation::new(Algorithm::HS256);
        
        let token_data = decode::<Claims>(
            token,
            &DecodingKey::from_secret(self.config.jwt_secret.as_bytes()),
            &validation
        )?;
        
        Ok(token_data.claims)
    }
    
    /// Create new session
    pub async fn create_session(
        &self,
        identity: &Identity,
        ip_address: String,
        user_agent: String
    ) -> Result<Session> {
        // Check max sessions
        let sessions = self.sessions.read().await;
        let user_sessions: Vec<_> = sessions.values()
            .filter(|s| s.user_id == identity.id)
            .collect();
        
        if user_sessions.len() >= self.config.max_sessions_per_user as usize {
            bail!("Maximum sessions reached for user");
        }
        
        drop(sessions);
        
        // Create JWT token
        let token = self.create_jwt(identity)?;
        
        let session = Session {
            id: Uuid::new_v4(),
            user_id: identity.id,
            token: token.clone(),
            ip_address,
            user_agent,
            created_at: Utc::now(),
            last_activity: Utc::now(),
            expires_at: Utc::now() + self.config.session_timeout,
        };
        
        let mut sessions = self.sessions.write().await;
        sessions.insert(session.id, session.clone());
        
        Ok(session)
    }
    
    /// Generate new API key
    pub async fn generate_api_key(
        &self,
        user_id: Uuid,
        name: String,
        permissions: Vec<String>
    ) -> Result<String> {
        // Generate random key
        let key = Uuid::new_v4().to_string();
        let key_hash = self.hash_api_key(&key);
        
        let api_key = ApiKey {
            id: Uuid::new_v4(),
            key_hash: key_hash.clone(),
            name,
            permissions,
            rate_limit: Some(1000), // Default rate limit
            expires_at: Some(Utc::now() + self.config.api_key_rotation),
            created_at: Utc::now(),
            last_used: None,
            is_active: true,
        };
        
        // Add to user
        let mut users = self.users.write().await;
        if let Some(user) = users.get_mut(&user_id) {
            user.api_keys.push(api_key.clone());
        } else {
            bail!("User not found");
        }
        
        // Add to global registry
        let mut api_keys = self.api_keys.write().await;
        api_keys.insert(key_hash, api_key);
        
        Ok(key)
    }
    
    /// Hash API key
    fn hash_api_key(&self, key: &str) -> String {
        let mut hasher = Sha256::new();
        hasher.update(key);
        format!("{:x}", hasher.finalize())
    }
    
    /// Check authorization
    pub async fn authorize(
        &self,
        identity: &Identity,
        permission: &str
    ) -> Result<bool> {
        if !self.config.rbac_enabled {
            return Ok(true); // No RBAC, allow all
        }
        
        self.rbac.check_permission(&identity.roles, permission).await
    }
    
    /// Revoke session
    pub async fn revoke_session(&self, session_id: Uuid) -> Result<()> {
        let mut sessions = self.sessions.write().await;
        sessions.remove(&session_id)
            .context("Session not found")?;
        
        Ok(())
    }
    
    /// Revoke API key
    pub async fn revoke_api_key(&self, key_hash: &str) -> Result<()> {
        let mut api_keys = self.api_keys.write().await;
        
        if let Some(api_key) = api_keys.get_mut(key_hash) {
            api_key.is_active = false;
        } else {
            bail!("API key not found");
        }
        
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_rbac() {
        let rbac = RBAC::new();
        rbac.initialize_defaults().await.unwrap();
        
        // Test admin role
        assert!(rbac.check_permission(&["admin".to_string()], "system.admin").await.unwrap());
        assert!(rbac.check_permission(&["admin".to_string()], "gpu.execute").await.unwrap());
        
        // Test operator role
        assert!(rbac.check_permission(&["operator".to_string()], "gpu.execute").await.unwrap());
        assert!(!rbac.check_permission(&["operator".to_string()], "system.admin").await.unwrap());
        
        // Test viewer role
        assert!(rbac.check_permission(&["viewer".to_string()], "gpu.monitor").await.unwrap());
        assert!(!rbac.check_permission(&["viewer".to_string()], "gpu.execute").await.unwrap());
    }
    
    #[tokio::test]
    async fn test_auth_manager() {
        let config = AuthConfig::default();
        let mut auth_manager = AuthManager::new(config);
        auth_manager.initialize().await.unwrap();
        
        // Get admin user
        let users = auth_manager.users.read().await;
        let admin = users.values()
            .find(|u| u.username == "admin")
            .unwrap()
            .clone();
        drop(users);
        
        // Create session
        let session = auth_manager.create_session(
            &admin,
            "127.0.0.1".to_string(),
            "test-agent".to_string()
        ).await.unwrap();
        
        // Validate JWT
        let claims = auth_manager.validate_jwt(&session.token).unwrap();
        assert_eq!(claims.username, "admin");
        
        // Generate API key
        let api_key = auth_manager.generate_api_key(
            admin.id,
            "test-key".to_string(),
            vec!["api.read".to_string()]
        ).await.unwrap();
        
        // Authenticate with API key
        let authenticated = auth_manager.authenticate_api_key(&api_key).await.unwrap();
        assert_eq!(authenticated.id, admin.id);
        
        // Test authorization
        assert!(auth_manager.authorize(&admin, "system.admin").await.unwrap());
    }
}
