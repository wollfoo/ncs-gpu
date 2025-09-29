//! API Middleware Components
//!
//! **Request/Response middleware** (Middleware request/response) for authentication, logging, and rate limiting

use anyhow::Result;
use std::{
    collections::HashMap,
    sync::{Arc, Mutex},
    time::{Duration, Instant},
};
use tracing::{info, warn, error};

/// **Rate limiting middleware** (Middleware giới hạn tốc độ)
pub struct RateLimiter {
    /// **Request counters per client** (Bộ đếm request mỗi client)
    clients: Arc<Mutex<HashMap<String, ClientState>>>,
    /// **Requests per minute limit** (Giới hạn request mỗi phút)
    requests_per_minute: u32,
    /// **Cleanup interval** (Khoảng thời gian dọn dẹp)
    cleanup_interval: Duration,
}

/// **Client rate limiting state** (Trạng thái giới hạn tốc độ client)
#[derive(Debug, Clone)]
struct ClientState {
    /// **Request count** (Số lượng request)
    request_count: u32,
    /// **Window start time** (Thời điểm bắt đầu cửa sổ)
    window_start: Instant,
    /// **Last request time** (Thời điểm request cuối)
    last_request: Instant,
}

impl RateLimiter {
    /// **Create new rate limiter** (Tạo rate limiter mới)
    pub fn new(requests_per_minute: u32) -> Self {
        Self {
            clients: Arc::new(Mutex::new(HashMap::new())),
            requests_per_minute,
            cleanup_interval: Duration::from_secs(300), // **5 minutes** (5 phút)
        }
    }

    /// **Check if request is allowed** (Kiểm tra request có được phép không)
    pub fn check_rate_limit(&self, client_id: &str) -> Result<bool> {
        let mut clients = self.clients.lock()
            .map_err(|_| anyhow::anyhow!("Failed to acquire rate limiter lock"))?;

        let now = Instant::now();
        let window_duration = Duration::from_secs(60); // **1 minute window** (Cửa sổ 1 phút)

        // **Get or create client state** (Lấy hoặc tạo trạng thái client)
        let client_state = clients.entry(client_id.to_string()).or_insert(ClientState {
            request_count: 0,
            window_start: now,
            last_request: now,
        });

        // **Reset window if expired** (Reset cửa sổ nếu hết hạn)
        if now.duration_since(client_state.window_start) >= window_duration {
            client_state.request_count = 0;
            client_state.window_start = now;
        }

        // **Check rate limit** (Kiểm tra giới hạn tốc độ)
        if client_state.request_count >= self.requests_per_minute {
            warn!("Rate limit exceeded for client: {}", client_id);
            return Ok(false);
        }

        // **Update state** (Cập nhật trạng thái)
        client_state.request_count += 1;
        client_state.last_request = now;

        Ok(true)
    }

    /// **Clean up old client states** (Dọn dẹp trạng thái client cũ)
    pub fn cleanup_old_clients(&self) -> Result<()> {
        let mut clients = self.clients.lock()
            .map_err(|_| anyhow::anyhow!("Failed to acquire rate limiter lock"))?;

        let now = Instant::now();
        let expiry_duration = Duration::from_secs(3600); // **1 hour** (1 giờ)

        clients.retain(|client_id, state| {
            let keep = now.duration_since(state.last_request) < expiry_duration;
            if !keep {
                info!("Cleaning up expired client state: {}", client_id);
            }
            keep
        });

        Ok(())
    }

    /// **Get rate limit status** (Lấy trạng thái giới hạn tốc độ)
    pub fn get_rate_limit_status(&self, client_id: &str) -> Result<RateLimitStatus> {
        let clients = self.clients.lock()
            .map_err(|_| anyhow::anyhow!("Failed to acquire rate limiter lock"))?;

        if let Some(client_state) = clients.get(client_id) {
            let now = Instant::now();
            let window_duration = Duration::from_secs(60);
            let remaining = if now.duration_since(client_state.window_start) >= window_duration {
                self.requests_per_minute // **Fresh window** (Cửa sổ mới)
            } else {
                self.requests_per_minute.saturating_sub(client_state.request_count)
            };

            Ok(RateLimitStatus {
                requests_remaining: remaining,
                reset_time: client_state.window_start + window_duration,
                current_count: client_state.request_count,
            })
        } else {
            Ok(RateLimitStatus {
                requests_remaining: self.requests_per_minute,
                reset_time: Instant::now() + Duration::from_secs(60),
                current_count: 0,
            })
        }
    }
}

/// **Rate limit status information** (Thông tin trạng thái giới hạn tốc độ)
#[derive(Debug, Clone)]
pub struct RateLimitStatus {
    /// **Remaining requests** (Request còn lại)
    pub requests_remaining: u32,
    /// **Reset time** (Thời điểm reset)
    pub reset_time: Instant,
    /// **Current request count** (Số request hiện tại)
    pub current_count: u32,
}

/// **Authentication middleware** (Middleware xác thực)
pub struct AuthMiddleware {
    /// **Valid API keys** (Khóa API hợp lệ)
    api_keys: Arc<Mutex<HashMap<String, ApiKeyInfo>>>,
    /// **Authentication required** (Yêu cầu xác thực)
    auth_required: bool,
}

/// **API key information** (Thông tin khóa API)
#[derive(Debug, Clone)]
pub struct ApiKeyInfo {
    /// **Key name/description** (Tên/mô tả khóa)
    pub name: String,
    /// **Permissions** (Quyền)
    pub permissions: Vec<String>,
    /// **Creation time** (Thời gian tạo)
    pub created_at: Instant,
    /// **Last used time** (Thời gian sử dụng cuối)
    pub last_used: Option<Instant>,
    /// **Usage count** (Số lần sử dụng)
    pub usage_count: u64,
}

impl AuthMiddleware {
    /// **Create new auth middleware** (Tạo middleware xác thực mới)
    pub fn new(auth_required: bool) -> Self {
        Self {
            api_keys: Arc::new(Mutex::new(HashMap::new())),
            auth_required,
        }
    }

    /// **Add API key** (Thêm khóa API)
    pub fn add_api_key(&self, key: String, name: String, permissions: Vec<String>) -> Result<()> {
        let mut api_keys = self.api_keys.lock()
            .map_err(|_| anyhow::anyhow!("Failed to acquire API keys lock"))?;

        api_keys.insert(key, ApiKeyInfo {
            name,
            permissions,
            created_at: Instant::now(),
            last_used: None,
            usage_count: 0,
        });

        Ok(())
    }

    /// **Validate API key** (Xác thực khóa API)
    pub fn validate_api_key(&self, key: &str, required_permission: Option<&str>) -> Result<bool> {
        if !self.auth_required {
            return Ok(true);
        }

        let mut api_keys = self.api_keys.lock()
            .map_err(|_| anyhow::anyhow!("Failed to acquire API keys lock"))?;

        if let Some(key_info) = api_keys.get_mut(key) {
            // **Check permissions** (Kiểm tra quyền)
            if let Some(permission) = required_permission {
                if !key_info.permissions.contains(&permission.to_string()) &&
                   !key_info.permissions.contains(&"admin".to_string()) {
                    warn!("API key {} lacks required permission: {}", key, permission);
                    return Ok(false);
                }
            }

            // **Update usage** (Cập nhật sử dụng)
            key_info.last_used = Some(Instant::now());
            key_info.usage_count += 1;

            info!("API key {} authenticated successfully", key_info.name);
            Ok(true)
        } else {
            warn!("Invalid API key provided: {}", key);
            Ok(false)
        }
    }

    /// **Get API key statistics** (Lấy thống kê khóa API)
    pub fn get_api_key_stats(&self) -> Result<Vec<ApiKeyStats>> {
        let api_keys = self.api_keys.lock()
            .map_err(|_| anyhow::anyhow!("Failed to acquire API keys lock"))?;

        let stats = api_keys.iter().map(|(key, info)| {
            ApiKeyStats {
                key_hash: format!("{:x}", md5::compute(key)),
                name: info.name.clone(),
                permissions: info.permissions.clone(),
                created_at: info.created_at,
                last_used: info.last_used,
                usage_count: info.usage_count,
            }
        }).collect();

        Ok(stats)
    }
}

/// **API key statistics** (Thống kê khóa API)
#[derive(Debug, Clone)]
pub struct ApiKeyStats {
    /// **Hashed key** (Khóa đã hash)
    pub key_hash: String,
    /// **Key name** (Tên khóa)
    pub name: String,
    /// **Permissions** (Quyền)
    pub permissions: Vec<String>,
    /// **Creation time** (Thời gian tạo)
    pub created_at: Instant,
    /// **Last used time** (Thời gian sử dụng cuối)
    pub last_used: Option<Instant>,
    /// **Usage count** (Số lần sử dụng)
    pub usage_count: u64,
}

/// **Request logging middleware** (Middleware ghi log request)
pub struct RequestLogger {
    /// **Log requests** (Ghi log request)
    enabled: bool,
}

impl RequestLogger {
    /// **Create new request logger** (Tạo logger request mới)
    pub fn new(enabled: bool) -> Self {
        Self { enabled }
    }

    /// **Log incoming request** (Ghi log request đến)
    pub fn log_request(&self, client_id: &str, method: &str, path: &str, user_agent: Option<&str>) {
        if self.enabled {
            info!(
                "Request: {} {} {} from {} (UA: {})",
                method,
                path,
                client_id,
                client_id,
                user_agent.unwrap_or("unknown")
            );
        }
    }

    /// **Log response** (Ghi log phản hồi)
    pub fn log_response(&self, client_id: &str, status_code: u16, response_time_ms: u64) {
        if self.enabled {
            info!(
                "Response: {} -> {} ({}ms)",
                client_id,
                status_code,
                response_time_ms
            );
        }
    }

    /// **Log error** (Ghi log lỗi)
    pub fn log_error(&self, client_id: &str, error: &str) {
        if self.enabled {
            error!("Request error from {}: {}", client_id, error);
        }
    }
}

/// **CORS middleware** (Middleware CORS)
pub struct CorsMiddleware {
    /// **Allowed origins** (Nguồn được phép)
    allowed_origins: Vec<String>,
    /// **Allowed methods** (Phương thức được phép)
    allowed_methods: Vec<String>,
    /// **Allowed headers** (Header được phép)
    allowed_headers: Vec<String>,
}

impl CorsMiddleware {
    /// **Create new CORS middleware** (Tạo middleware CORS mới)
    pub fn new() -> Self {
        Self {
            allowed_origins: vec!["*".to_string()],
            allowed_methods: vec![
                "GET".to_string(),
                "POST".to_string(),
                "PUT".to_string(),
                "DELETE".to_string(),
                "OPTIONS".to_string(),
            ],
            allowed_headers: vec![
                "Content-Type".to_string(),
                "Authorization".to_string(),
                "X-API-Key".to_string(),
            ],
        }
    }

    /// **Configure allowed origins** (Cấu hình nguồn được phép)
    pub fn with_origins(mut self, origins: Vec<String>) -> Self {
        self.allowed_origins = origins;
        self
    }

    /// **Get CORS headers** (Lấy header CORS)
    pub fn get_cors_headers(&self, origin: Option<&str>) -> HashMap<String, String> {
        let mut headers = HashMap::new();

        // **Check if origin is allowed** (Kiểm tra nguồn có được phép không)
        let allowed_origin = if self.allowed_origins.contains(&"*".to_string()) {
            "*"
        } else if let Some(origin) = origin {
            if self.allowed_origins.contains(&origin.to_string()) {
                origin
            } else {
                ""
            }
        } else {
            ""
        };

        if !allowed_origin.is_empty() {
            headers.insert("Access-Control-Allow-Origin".to_string(), allowed_origin.to_string());
            headers.insert("Access-Control-Allow-Methods".to_string(), self.allowed_methods.join(", "));
            headers.insert("Access-Control-Allow-Headers".to_string(), self.allowed_headers.join(", "));
            headers.insert("Access-Control-Max-Age".to_string(), "86400".to_string()); // **24 hours** (24 giờ)
        }

        headers
    }
}

impl Default for CorsMiddleware {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::thread::sleep;

    #[test]
    fn test_rate_limiter() {
        let limiter = RateLimiter::new(5); // **5 requests per minute** (5 request mỗi phút)

        // **Allow first 5 requests** (Cho phép 5 request đầu)
        for i in 0..5 {
            assert!(limiter.check_rate_limit("client1").unwrap(), "Request {} should be allowed", i);
        }

        // **Block 6th request** (Chặn request thứ 6)
        assert!(!limiter.check_rate_limit("client1").unwrap(), "6th request should be blocked");

        // **Different client should be allowed** (Client khác nên được phép)
        assert!(limiter.check_rate_limit("client2").unwrap(), "Different client should be allowed");
    }

    #[test]
    fn test_auth_middleware() {
        let auth = AuthMiddleware::new(true);

        // **Add API key** (Thêm khóa API)
        auth.add_api_key(
            "test_key_123".to_string(),
            "Test Key".to_string(),
            vec!["read".to_string(), "write".to_string()]
        ).unwrap();

        // **Valid key should pass** (Khóa hợp lệ nên qua)
        assert!(auth.validate_api_key("test_key_123", Some("read")).unwrap());

        // **Invalid key should fail** (Khóa không hợp lệ nên thất bại)
        assert!(!auth.validate_api_key("invalid_key", Some("read")).unwrap());

        // **Permission check** (Kiểm tra quyền)
        assert!(!auth.validate_api_key("test_key_123", Some("admin")).unwrap());
    }

    #[test]
    fn test_cors_middleware() {
        let cors = CorsMiddleware::new();
        let headers = cors.get_cors_headers(Some("https://example.com"));

        assert!(headers.contains_key("Access-Control-Allow-Origin"));
        assert!(headers.contains_key("Access-Control-Allow-Methods"));
        assert!(headers.contains_key("Access-Control-Allow-Headers"));
    }
}