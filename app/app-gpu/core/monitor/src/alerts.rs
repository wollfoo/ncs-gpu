//! **Alert Management** (Quản lý cảnh báo)
//!
//! Alert system with configurable thresholds, multiple channels, and cooldown management.

use crate::{MonitorError, Result, AlertConfig, AlertChannel, AlertThresholds, health::ComponentHealth};
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// **Alert Level** (Mức độ cảnh báo) - Different severity levels for alerts
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum AlertLevel {
    Info,
    Warning,
    Critical,
    Emergency,
}

impl AlertLevel {
    /// Get color representation for UI/logging
    pub fn color(&self) -> &'static str {
        match self {
            Self::Info => "blue",
            Self::Warning => "yellow",
            Self::Critical => "red",
            Self::Emergency => "purple",
        }
    }

    /// Get emoji representation
    pub fn emoji(&self) -> &'static str {
        match self {
            Self::Info => "ℹ️",
            Self::Warning => "⚠️",
            Self::Critical => "🚨",
            Self::Emergency => "🆘",
        }
    }
}

impl std::fmt::Display for AlertLevel {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Info => write!(f, "INFO"),
            Self::Warning => write!(f, "WARNING"),
            Self::Critical => write!(f, "CRITICAL"),
            Self::Emergency => write!(f, "EMERGENCY"),
        }
    }
}

/// **Alert** (Cảnh báo) - Individual alert instance
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Alert {
    pub id: Uuid,
    pub level: AlertLevel,
    pub title: String,
    pub message: String,
    pub component_id: String,
    pub component_type: String,
    pub timestamp: DateTime<Utc>,
    pub resolved: bool,
    pub resolved_at: Option<DateTime<Utc>>,
    pub acknowledged: bool,
    pub acknowledged_at: Option<DateTime<Utc>>,
    pub acknowledged_by: Option<String>,
    pub tags: HashMap<String, String>,
    pub metrics: HashMap<String, f64>,
}

impl Alert {
    /// Create new alert
    pub fn new(
        level: AlertLevel,
        title: String,
        message: String,
        component_id: String,
        component_type: String,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            level,
            title,
            message,
            component_id,
            component_type,
            timestamp: Utc::now(),
            resolved: false,
            resolved_at: None,
            acknowledged: false,
            acknowledged_at: None,
            acknowledged_by: None,
            tags: HashMap::new(),
            metrics: HashMap::new(),
        }
    }

    /// Add tag to alert
    pub fn with_tag(mut self, key: &str, value: &str) -> Self {
        self.tags.insert(key.to_string(), value.to_string());
        self
    }

    /// Add metric to alert
    pub fn with_metric(mut self, key: &str, value: f64) -> Self {
        self.metrics.insert(key.to_string(), value);
        self
    }

    /// Mark alert as resolved
    pub fn resolve(&mut self) {
        self.resolved = true;
        self.resolved_at = Some(Utc::now());
    }

    /// Mark alert as acknowledged
    pub fn acknowledge(&mut self, by: Option<String>) {
        self.acknowledged = true;
        self.acknowledged_at = Some(Utc::now());
        self.acknowledged_by = by;
    }

    /// Get formatted message for display
    pub fn formatted_message(&self) -> String {
        format!("{} {} [{}] {}: {}",
            self.level.emoji(),
            self.timestamp.format("%Y-%m-%d %H:%M:%S UTC"),
            self.component_id,
            self.title,
            self.message
        )
    }

    /// Convert to JSON for API/webhook
    pub fn to_json(&self) -> Result<String> {
        serde_json::to_string_pretty(self)
            .map_err(|e| MonitorError::Alert {
                message: format!("Failed to serialize alert: {}", e)
            })
    }

    /// Get age of alert
    pub fn age(&self) -> chrono::Duration {
        Utc::now().signed_duration_since(self.timestamp)
    }

    /// Check if alert is stale (old and unresolved)
    pub fn is_stale(&self, max_age: chrono::Duration) -> bool {
        !self.resolved && self.age() > max_age
    }
}

/// **Alert Rule** (Quy tắc cảnh báo) - Configurable alert conditions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AlertRule {
    pub id: String,
    pub name: String,
    pub description: String,
    pub enabled: bool,
    pub component_type: String,
    pub metric_name: String,
    pub condition: AlertCondition,
    pub threshold: f64,
    pub level: AlertLevel,
    pub cooldown: std::time::Duration,
    pub tags: HashMap<String, String>,
}

/// **Alert Condition** (Điều kiện cảnh báo) - Different types of alert conditions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AlertCondition {
    GreaterThan,
    LessThan,
    Equals,
    NotEquals,
    GreaterOrEqual,
    LessOrEqual,
    PercentageChange { window: std::time::Duration },
}

impl AlertCondition {
    /// Evaluate condition against current and previous values
    pub fn evaluate(&self, current: f64, threshold: f64, previous: Option<f64>) -> bool {
        match self {
            Self::GreaterThan => current > threshold,
            Self::LessThan => current < threshold,
            Self::Equals => (current - threshold).abs() < f64::EPSILON,
            Self::NotEquals => (current - threshold).abs() > f64::EPSILON,
            Self::GreaterOrEqual => current >= threshold,
            Self::LessOrEqual => current <= threshold,
            Self::PercentageChange { .. } => {
                if let Some(prev) = previous {
                    if prev != 0.0 {
                        let change_percent = ((current - prev) / prev).abs() * 100.0;
                        change_percent > threshold
                    } else {
                        false
                    }
                } else {
                    false
                }
            }
        }
    }
}

/// **Alert Channel Handler** (Trình xử lý kênh cảnh báo) - Interface for alert delivery
#[async_trait]
pub trait AlertChannelHandler: Send + Sync {
    /// Send alert through this channel
    async fn send_alert(&self, alert: &Alert) -> Result<()>;

    /// Get channel name
    fn channel_name(&self) -> &str;

    /// Check if channel is enabled
    fn is_enabled(&self) -> bool { true }
}

/// **Log Alert Handler** (Trình xử lý cảnh báo log)
pub struct LogAlertHandler;

#[async_trait]
impl AlertChannelHandler for LogAlertHandler {
    async fn send_alert(&self, alert: &Alert) -> Result<()> {
        match alert.level {
            AlertLevel::Info => tracing::info!("{}", alert.formatted_message()),
            AlertLevel::Warning => tracing::warn!("{}", alert.formatted_message()),
            AlertLevel::Critical => tracing::error!("{}", alert.formatted_message()),
            AlertLevel::Emergency => tracing::error!("🆘 EMERGENCY: {}", alert.formatted_message()),
        }
        Ok(())
    }

    fn channel_name(&self) -> &str {
        "log"
    }
}

/// **Webhook Alert Handler** (Trình xử lý cảnh báo webhook)
pub struct WebhookAlertHandler {
    url: String,
    headers: HashMap<String, String>,
    client: reqwest::Client,
}

impl WebhookAlertHandler {
    pub fn new(url: String, headers: HashMap<String, String>) -> Self {
        Self {
            url,
            headers,
            client: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl AlertChannelHandler for WebhookAlertHandler {
    async fn send_alert(&self, alert: &Alert) -> Result<()> {
        let payload = alert.to_json()?;

        let mut request = self.client.post(&self.url)
            .header("Content-Type", "application/json")
            .body(payload);

        for (key, value) in &self.headers {
            request = request.header(key, value);
        }

        request.send().await
            .map_err(|e| MonitorError::Alert {
                message: format!("Failed to send webhook alert: {}", e)
            })?;

        Ok(())
    }

    fn channel_name(&self) -> &str {
        "webhook"
    }
}

/// **Slack Alert Handler** (Trình xử lý cảnh báo Slack)
pub struct SlackAlertHandler {
    webhook_url: String,
    client: reqwest::Client,
}

impl SlackAlertHandler {
    pub fn new(webhook_url: String) -> Self {
        Self {
            webhook_url,
            client: reqwest::Client::new(),
        }
    }

    fn format_slack_message(&self, alert: &Alert) -> serde_json::Value {
        let color = match alert.level {
            AlertLevel::Info => "good",
            AlertLevel::Warning => "warning",
            AlertLevel::Critical => "danger",
            AlertLevel::Emergency => "danger",
        };

        serde_json::json!({
            "username": "OPUS-GPU Monitor",
            "icon_emoji": ":robot_face:",
            "attachments": [{
                "color": color,
                "title": format!("{} {}", alert.level.emoji(), alert.title),
                "text": alert.message,
                "fields": [
                    {
                        "title": "Component",
                        "value": format!("{} ({})", alert.component_id, alert.component_type),
                        "short": true
                    },
                    {
                        "title": "Level",
                        "value": alert.level.to_string(),
                        "short": true
                    },
                    {
                        "title": "Time",
                        "value": alert.timestamp.format("%Y-%m-%d %H:%M:%S UTC").to_string(),
                        "short": true
                    }
                ],
                "footer": "OPUS-GPU Monitoring",
                "ts": alert.timestamp.timestamp()
            }]
        })
    }
}

#[async_trait]
impl AlertChannelHandler for SlackAlertHandler {
    async fn send_alert(&self, alert: &Alert) -> Result<()> {
        let payload = self.format_slack_message(alert);

        self.client.post(&self.webhook_url)
            .json(&payload)
            .send().await
            .map_err(|e| MonitorError::Alert {
                message: format!("Failed to send Slack alert: {}", e)
            })?;

        Ok(())
    }

    fn channel_name(&self) -> &str {
        "slack"
    }
}

/// **Alert Cooldown Manager** (Trình quản lý thời gian chờ cảnh báo)
#[derive(Debug)]
struct AlertCooldownManager {
    cooldowns: HashMap<String, DateTime<Utc>>,
    default_cooldown: std::time::Duration,
}

impl AlertCooldownManager {
    fn new(default_cooldown: std::time::Duration) -> Self {
        Self {
            cooldowns: HashMap::new(),
            default_cooldown,
        }
    }

    /// Check if alert can be sent (not in cooldown)
    fn can_send_alert(&mut self, alert_key: &str, cooldown: Option<std::time::Duration>) -> bool {
        let cooldown_duration = cooldown.unwrap_or(self.default_cooldown);
        let now = Utc::now();

        if let Some(&last_sent) = self.cooldowns.get(alert_key) {
            let elapsed = now.signed_duration_since(last_sent);
            if elapsed.to_std().unwrap_or(std::time::Duration::MAX) < cooldown_duration {
                return false;
            }
        }

        self.cooldowns.insert(alert_key.to_string(), now);
        true
    }

    /// Clear cooldown for specific alert key
    fn clear_cooldown(&mut self, alert_key: &str) {
        self.cooldowns.remove(alert_key);
    }

    /// Clean up expired cooldowns
    fn cleanup_expired(&mut self) {
        let now = Utc::now();
        let max_cooldown = self.default_cooldown * 10; // Keep up to 10x default cooldown

        self.cooldowns.retain(|_, &mut last_sent| {
            let elapsed = now.signed_duration_since(last_sent);
            elapsed.to_std().unwrap_or(std::time::Duration::MAX) < max_cooldown
        });
    }
}

/// **Alert Manager** (Trình quản lý cảnh báo) - Main alert management system
pub struct AlertManager {
    config: AlertConfig,
    channels: Vec<Arc<dyn AlertChannelHandler>>,
    active_alerts: Arc<RwLock<HashMap<String, Alert>>>,
    alert_history: Arc<RwLock<VecDeque<Alert>>>,
    cooldown_manager: Arc<RwLock<AlertCooldownManager>>,
    rules: Arc<RwLock<Vec<AlertRule>>>,
    running: Arc<RwLock<bool>>,
}

impl AlertManager {
    /// Create new alert manager
    pub fn new(config: AlertConfig) -> Result<Self> {
        let mut channels: Vec<Arc<dyn AlertChannelHandler>> = Vec::new();

        // Create channel handlers
        for channel in &config.channels {
            match channel {
                AlertChannel::Log => {
                    channels.push(Arc::new(LogAlertHandler));
                }
                AlertChannel::Webhook { url, headers } => {
                    channels.push(Arc::new(WebhookAlertHandler::new(
                        url.clone(),
                        headers.clone(),
                    )));
                }
                AlertChannel::Slack { webhook_url } => {
                    channels.push(Arc::new(SlackAlertHandler::new(webhook_url.clone())));
                }
                AlertChannel::Email { recipients: _ } => {
                    // TODO: Implement email handler
                    tracing::warn!("Email alert channel not yet implemented");
                }
                AlertChannel::Discord { webhook_url: _ } => {
                    // TODO: Implement Discord handler
                    tracing::warn!("Discord alert channel not yet implemented");
                }
            }
        }

        let cooldown_manager = AlertCooldownManager::new(config.cooldown);

        Ok(Self {
            config,
            channels,
            active_alerts: Arc::new(RwLock::new(HashMap::new())),
            alert_history: Arc::new(RwLock::new(VecDeque::new())),
            cooldown_manager: Arc::new(RwLock::new(cooldown_manager)),
            rules: Arc::new(RwLock::new(Vec::new())),
            running: Arc::new(RwLock::new(false)),
        })
    }

    /// Start alert manager
    pub async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            return Ok(());
        }

        tracing::info!("Starting alert manager with {} channels", self.channels.len());

        // Start cleanup task
        let cooldown_manager = self.cooldown_manager.clone();
        let alert_history = self.alert_history.clone();
        let running_flag = self.running.clone();

        tokio::spawn(async move {
            let mut cleanup_interval = tokio::time::interval(std::time::Duration::from_minutes(10));

            while *running_flag.read().await {
                cleanup_interval.tick().await;

                // Cleanup expired cooldowns
                cooldown_manager.write().await.cleanup_expired();

                // Limit alert history size
                let mut history = alert_history.write().await;
                while history.len() > 1000 {
                    history.pop_front();
                }
            }
        });

        *running = true;
        tracing::info!("Alert manager started");
        Ok(())
    }

    /// Stop alert manager
    pub async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        *running = false;
        tracing::info!("Alert manager stopped");
        Ok(())
    }

    /// Send alert
    pub async fn send_alert(&self, alert: Alert) -> Result<()> {
        if !self.config.enabled {
            return Ok(());
        }

        let alert_key = format!("{}:{}", alert.component_id, alert.title);

        // Check cooldown
        let can_send = self.cooldown_manager.write().await
            .can_send_alert(&alert_key, Some(self.config.cooldown));

        if !can_send {
            tracing::debug!("Alert {} is in cooldown, skipping", alert_key);
            return Ok(());
        }

        // Store alert
        let alert_id = alert.id;
        self.active_alerts.write().await.insert(alert_id.to_string(), alert.clone());
        self.alert_history.write().await.push_back(alert.clone());

        // Send through all channels
        for channel in &self.channels {
            if let Err(e) = channel.send_alert(&alert).await {
                tracing::error!("Failed to send alert through {}: {}", channel.channel_name(), e);
            } else {
                tracing::debug!("Alert sent through {}: {}", channel.channel_name(), alert.title);
            }
        }

        Ok(())
    }

    /// Create alert from component health
    pub async fn alert_from_health(&self, health: &ComponentHealth) -> Result<()> {
        let level = match health.status {
            crate::health::HealthStatus::Healthy => return Ok(()), // No alert for healthy status
            crate::health::HealthStatus::Warning => AlertLevel::Warning,
            crate::health::HealthStatus::Critical => AlertLevel::Critical,
            crate::health::HealthStatus::Down => AlertLevel::Emergency,
            crate::health::HealthStatus::Unknown => AlertLevel::Info,
        };

        let title = match health.status {
            crate::health::HealthStatus::Warning => "Component Warning".to_string(),
            crate::health::HealthStatus::Critical => "Component Critical".to_string(),
            crate::health::HealthStatus::Down => "Component Down".to_string(),
            crate::health::HealthStatus::Unknown => "Component Status Unknown".to_string(),
            _ => return Ok(()),
        };

        let message = if let Some(error) = &health.last_error {
            error.clone()
        } else if let Some(warning) = &health.last_warning {
            warning.clone()
        } else {
            format!("Component {} is in {} state", health.component_id, health.status)
        };

        let mut alert = Alert::new(
            level,
            title,
            message,
            health.component_id.clone(),
            health.component_type.to_string(),
        );

        // Add diagnostics as metrics
        for (key, value) in &health.diagnostics {
            if let Ok(numeric_value) = value.parse::<f64>() {
                alert = alert.with_metric(key, numeric_value);
            } else {
                alert = alert.with_tag(key, value);
            }
        }

        self.send_alert(alert).await
    }

    /// Resolve alert
    pub async fn resolve_alert(&self, alert_id: &str) -> Result<()> {
        let mut active = self.active_alerts.write().await;

        if let Some(mut alert) = active.remove(alert_id) {
            alert.resolve();
            self.alert_history.write().await.push_back(alert);
            tracing::info!("Alert {} resolved", alert_id);
        }

        Ok(())
    }

    /// Acknowledge alert
    pub async fn acknowledge_alert(&self, alert_id: &str, acknowledged_by: Option<String>) -> Result<()> {
        let mut active = self.active_alerts.write().await;

        if let Some(alert) = active.get_mut(alert_id) {
            alert.acknowledge(acknowledged_by);
            tracing::info!("Alert {} acknowledged", alert_id);
        }

        Ok(())
    }

    /// Get active alerts
    pub async fn get_active_alerts(&self) -> Vec<Alert> {
        self.active_alerts.read().await.values().cloned().collect()
    }

    /// Get alert history
    pub async fn get_alert_history(&self, limit: Option<usize>) -> Vec<Alert> {
        let history = self.alert_history.read().await;
        let limit = limit.unwrap_or(100);

        history.iter()
            .rev()
            .take(limit)
            .cloned()
            .collect()
    }

    /// Get alerts by component
    pub async fn get_alerts_by_component(&self, component_id: &str) -> Vec<Alert> {
        let active = self.active_alerts.read().await;
        active.values()
            .filter(|alert| alert.component_id == component_id)
            .cloned()
            .collect()
    }
}