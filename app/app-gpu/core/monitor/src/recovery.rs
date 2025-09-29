//! **Auto-Recovery System** (Hệ thống phục hồi tự động)
//!
//! Automatic recovery mechanisms for handling system failures and degraded states.

use crate::{MonitorError, Result, RecoveryConfig, RecoveryAction};
use crate::alerts::{AlertManager, Alert, AlertLevel};
use crate::health::{ComponentHealth, HealthStatus};
use async_trait::async_trait;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

/// **Recovery Event** (Sự kiện phục hồi) - Records recovery attempts and outcomes
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecoveryEvent {
    pub id: Uuid,
    pub component_id: String,
    pub component_type: String,
    pub trigger_issue: String,
    pub action_taken: RecoveryAction,
    pub timestamp: DateTime<Utc>,
    pub success: bool,
    pub error_message: Option<String>,
    pub recovery_time_ms: Option<u64>,
    pub attempt_number: u32,
}

impl RecoveryEvent {
    /// Create new recovery event
    pub fn new(
        component_id: String,
        component_type: String,
        trigger_issue: String,
        action_taken: RecoveryAction,
        attempt_number: u32,
    ) -> Self {
        Self {
            id: Uuid::new_v4(),
            component_id,
            component_type,
            trigger_issue,
            action_taken,
            timestamp: Utc::now(),
            success: false,
            error_message: None,
            recovery_time_ms: None,
            attempt_number,
        }
    }

    /// Mark recovery as successful
    pub fn mark_success(&mut self, recovery_time_ms: u64) {
        self.success = true;
        self.recovery_time_ms = Some(recovery_time_ms);
    }

    /// Mark recovery as failed
    pub fn mark_failure(&mut self, error_message: String) {
        self.success = false;
        self.error_message = Some(error_message);
    }
}

/// **Recovery Strategy** (Chiến lược phục hồi) - Different recovery approaches
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RecoveryStrategy {
    /// Immediate recovery action
    Immediate,
    /// Progressive recovery with escalating actions
    Progressive,
    /// Wait and retry approach
    DelayedRetry { delay: std::time::Duration },
    /// Manual intervention required
    Manual,
}

/// **Recovery Rule** (Quy tắc phục hồi) - Configurable recovery rules
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecoveryRule {
    pub id: String,
    pub name: String,
    pub description: String,
    pub enabled: bool,
    pub component_types: Vec<String>,
    pub trigger_conditions: Vec<RecoveryTrigger>,
    pub actions: Vec<RecoveryAction>,
    pub strategy: RecoveryStrategy,
    pub max_attempts: u32,
    pub cooldown: std::time::Duration,
    pub success_criteria: Vec<SuccessCriteria>,
}

/// **Recovery Trigger** (Kích hoạt phục hồi) - Conditions that trigger recovery
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RecoveryTrigger {
    HealthStatus { status: HealthStatus },
    MetricThreshold { metric_name: String, operator: String, value: f64 },
    ErrorCount { count: u64, time_window: std::time::Duration },
    ComponentDown { duration: std::time::Duration },
    CustomCondition { condition: String },
}

/// **Success Criteria** (Tiêu chí thành công) - How to determine if recovery was successful
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SuccessCriteria {
    HealthStatusImproved,
    MetricWithinRange { metric_name: String, min: f64, max: f64 },
    NoErrorsFor { duration: std::time::Duration },
    CustomCheck { check: String },
}

/// **Recovery Action Executor** (Trình thực thi hành động phục hồi) - Executes recovery actions
#[async_trait]
pub trait RecoveryActionExecutor: Send + Sync {
    /// Execute recovery action
    async fn execute(&self, action: &RecoveryAction, component_id: &str) -> Result<()>;

    /// Check if action is applicable for component
    fn can_execute(&self, action: &RecoveryAction, component_id: &str) -> bool;

    /// Get executor name
    fn name(&self) -> &str;
}

/// **Mining Recovery Executor** (Trình thực thi phục hồi mining)
pub struct MiningRecoveryExecutor;

#[async_trait]
impl RecoveryActionExecutor for MiningRecoveryExecutor {
    async fn execute(&self, action: &RecoveryAction, component_id: &str) -> Result<()> {
        match action {
            RecoveryAction::RestartMining => {
                tracing::info!("Restarting mining for component {}", component_id);
                // TODO: Implement mining restart logic
                tokio::time::sleep(std::time::Duration::from_secs(2)).await;
                Ok(())
            }
            RecoveryAction::SwitchPool => {
                tracing::info!("Switching to backup pool for component {}", component_id);
                // TODO: Implement pool switching logic
                tokio::time::sleep(std::time::Duration::from_secs(3)).await;
                Ok(())
            }
            RecoveryAction::ReducePowerLimit => {
                tracing::info!("Reducing power limit for component {}", component_id);
                // TODO: Implement power limit reduction
                tokio::time::sleep(std::time::Duration::from_secs(1)).await;
                Ok(())
            }
            RecoveryAction::RestartGpu { gpu_id } => {
                tracing::info!("Restarting GPU {} for component {}", gpu_id, component_id);
                // TODO: Implement GPU restart logic
                tokio::time::sleep(std::time::Duration::from_secs(5)).await;
                Ok(())
            }
            _ => Err(MonitorError::Configuration {
                config: format!("Mining executor cannot handle action: {:?}", action),
            }),
        }
    }

    fn can_execute(&self, action: &RecoveryAction, _component_id: &str) -> bool {
        matches!(action,
            RecoveryAction::RestartMining |
            RecoveryAction::SwitchPool |
            RecoveryAction::ReducePowerLimit |
            RecoveryAction::RestartGpu { .. }
        )
    }

    fn name(&self) -> &str {
        "mining"
    }
}

/// **System Recovery Executor** (Trình thực thi phục hồi hệ thống)
pub struct SystemRecoveryExecutor;

#[async_trait]
impl RecoveryActionExecutor for SystemRecoveryExecutor {
    async fn execute(&self, action: &RecoveryAction, component_id: &str) -> Result<()> {
        match action {
            RecoveryAction::RestartSystem => {
                tracing::warn!("CRITICAL: System restart requested for component {}", component_id);
                // TODO: Implement safe system restart
                // This should be very careful and probably require additional confirmation
                Err(MonitorError::Configuration {
                    config: "System restart not implemented for safety".to_string(),
                })
            }
            RecoveryAction::NotifyAdmin => {
                tracing::error!("Admin notification triggered for component {}", component_id);
                // TODO: Send notification to admin
                Ok(())
            }
            RecoveryAction::Custom { command, args } => {
                tracing::info!("Executing custom command '{}' with args {:?} for component {}",
                              command, args, component_id);

                let output = tokio::process::Command::new(command)
                    .args(args)
                    .output()
                    .await
                    .map_err(|e| MonitorError::System {
                        resource: format!("Failed to execute command {}: {}", command, e),
                    })?;

                if output.status.success() {
                    tracing::info!("Custom command executed successfully");
                    Ok(())
                } else {
                    let error = String::from_utf8_lossy(&output.stderr);
                    Err(MonitorError::System {
                        resource: format!("Command failed: {}", error),
                    })
                }
            }
            _ => Err(MonitorError::Configuration {
                config: format!("System executor cannot handle action: {:?}", action),
            }),
        }
    }

    fn can_execute(&self, action: &RecoveryAction, _component_id: &str) -> bool {
        matches!(action,
            RecoveryAction::RestartSystem |
            RecoveryAction::NotifyAdmin |
            RecoveryAction::Custom { .. }
        )
    }

    fn name(&self) -> &str {
        "system"
    }
}

/// **Recovery Attempt Tracker** (Trình theo dõi thử phục hồi)
#[derive(Debug, Clone)]
struct RecoveryAttempt {
    component_id: String,
    attempts: u32,
    last_attempt: DateTime<Utc>,
    cooldown_until: DateTime<Utc>,
}

impl RecoveryAttempt {
    fn new(component_id: String) -> Self {
        Self {
            component_id,
            attempts: 0,
            last_attempt: Utc::now(),
            cooldown_until: Utc::now(),
        }
    }

    fn can_attempt(&self, max_attempts: u32) -> bool {
        self.attempts < max_attempts && Utc::now() >= self.cooldown_until
    }

    fn record_attempt(&mut self, cooldown: std::time::Duration) {
        self.attempts += 1;
        self.last_attempt = Utc::now();
        self.cooldown_until = Utc::now() + chrono::Duration::from_std(cooldown).unwrap_or_default();
    }

    fn reset(&mut self) {
        self.attempts = 0;
        self.cooldown_until = Utc::now();
    }
}

/// **Recovery Manager** (Trình quản lý phục hồi) - Main recovery coordination system
pub struct RecoveryManager {
    config: RecoveryConfig,
    alert_manager: Arc<AlertManager>,
    executors: Vec<Arc<dyn RecoveryActionExecutor>>,
    recovery_attempts: Arc<RwLock<HashMap<String, RecoveryAttempt>>>,
    recovery_history: Arc<RwLock<Vec<RecoveryEvent>>>,
    rules: Arc<RwLock<Vec<RecoveryRule>>>,
    running: Arc<RwLock<bool>>,
}

impl RecoveryManager {
    /// Create new recovery manager
    pub fn new(config: RecoveryConfig, alert_manager: Arc<AlertManager>) -> Result<Self> {
        let executors: Vec<Arc<dyn RecoveryActionExecutor>> = vec![
            Arc::new(MiningRecoveryExecutor),
            Arc::new(SystemRecoveryExecutor),
        ];

        Ok(Self {
            config,
            alert_manager,
            executors,
            recovery_attempts: Arc::new(RwLock::new(HashMap::new())),
            recovery_history: Arc::new(RwLock::new(Vec::new())),
            rules: Arc::new(RwLock::new(Vec::new())),
            running: Arc::new(RwLock::new(false)),
        })
    }

    /// Start recovery manager
    pub async fn start(&self) -> Result<()> {
        let mut running = self.running.write().await;
        if *running {
            return Ok(());
        }

        tracing::info!("Starting auto-recovery manager");

        // Initialize default recovery rules
        self.initialize_default_rules().await?;

        // Start cleanup task
        let recovery_history = self.recovery_history.clone();
        let running_flag = self.running.clone();

        tokio::spawn(async move {
            let mut cleanup_interval = tokio::time::interval(std::time::Duration::from_secs(3600)); // 1 hour

            while *running_flag.read().await {
                cleanup_interval.tick().await;

                // Limit recovery history size
                let mut history = recovery_history.write().await;
                if history.len() > 1000 {
                    history.drain(..history.len() - 1000);
                }
            }
        });

        *running = true;
        tracing::info!("Auto-recovery manager started");
        Ok(())
    }

    /// Stop recovery manager
    pub async fn stop(&self) -> Result<()> {
        let mut running = self.running.write().await;
        *running = false;
        tracing::info!("Auto-recovery manager stopped");
        Ok(())
    }

    /// Initialize default recovery rules
    async fn initialize_default_rules(&self) -> Result<()> {
        let default_rules = vec![
            RecoveryRule {
                id: "gpu_overheat".to_string(),
                name: "GPU Overheating Recovery".to_string(),
                description: "Reduce power limit when GPU overheats".to_string(),
                enabled: true,
                component_types: vec!["gpu".to_string()],
                trigger_conditions: vec![
                    RecoveryTrigger::HealthStatus { status: HealthStatus::Critical }
                ],
                actions: vec![
                    RecoveryAction::ReducePowerLimit,
                    RecoveryAction::RestartMining,
                ],
                strategy: RecoveryStrategy::Progressive,
                max_attempts: 3,
                cooldown: std::time::Duration::from_secs(300), // 5 minutes
                success_criteria: vec![
                    SuccessCriteria::HealthStatusImproved,
                ],
            },

            RecoveryRule {
                id: "pool_connection_lost".to_string(),
                name: "Pool Connection Recovery".to_string(),
                description: "Switch to backup pool when connection is lost".to_string(),
                enabled: true,
                component_types: vec!["pool".to_string()],
                trigger_conditions: vec![
                    RecoveryTrigger::HealthStatus { status: HealthStatus::Down }
                ],
                actions: vec![
                    RecoveryAction::SwitchPool,
                    RecoveryAction::RestartMining,
                ],
                strategy: RecoveryStrategy::Immediate,
                max_attempts: 2,
                cooldown: std::time::Duration::from_secs(120), // 2 minutes
                success_criteria: vec![
                    SuccessCriteria::HealthStatusImproved,
                ],
            },

            RecoveryRule {
                id: "system_critical".to_string(),
                name: "System Critical Recovery".to_string(),
                description: "Notify admin when system is in critical state".to_string(),
                enabled: true,
                component_types: vec!["system".to_string()],
                trigger_conditions: vec![
                    RecoveryTrigger::HealthStatus { status: HealthStatus::Critical }
                ],
                actions: vec![
                    RecoveryAction::NotifyAdmin,
                ],
                strategy: RecoveryStrategy::Immediate,
                max_attempts: 1,
                cooldown: std::time::Duration::from_secs(3600), // 1 hour
                success_criteria: vec![
                    SuccessCriteria::NoErrorsFor { duration: std::time::Duration::from_secs(600) },
                ],
            },
        ];

        let mut rules = self.rules.write().await;
        *rules = default_rules;

        tracing::info!("Initialized {} default recovery rules", rules.len());
        Ok(())
    }

    /// Attempt recovery for component health issue
    pub async fn attempt_recovery(&self, health: &ComponentHealth) -> Result<()> {
        if !self.config.enabled {
            return Ok(());
        }

        // Check if recovery is needed
        if !health.status.is_problematic() {
            return Ok(());
        }

        let component_key = health.component_id.clone();

        // Check recovery attempts
        let can_attempt = {
            let mut attempts = self.recovery_attempts.write().await;
            let attempt = attempts.entry(component_key.clone())
                .or_insert_with(|| RecoveryAttempt::new(component_key.clone()));

            attempt.can_attempt(self.config.max_recovery_attempts)
        };

        if !can_attempt {
            tracing::debug!("Recovery cooldown active for component {}", component_key);
            return Ok(());
        }

        // Find applicable recovery rules
        let applicable_rules = self.find_applicable_rules(health).await;

        if applicable_rules.is_empty() {
            tracing::debug!("No applicable recovery rules for component {}", component_key);
            return Ok(());
        }

        // Execute recovery actions
        for rule in applicable_rules {
            if let Err(e) = self.execute_recovery_rule(&rule, health).await {
                tracing::error!("Recovery rule {} failed for component {}: {}",
                               rule.name, component_key, e);
            }
        }

        Ok(())
    }

    /// Find applicable recovery rules for component health
    async fn find_applicable_rules(&self, health: &ComponentHealth) -> Vec<RecoveryRule> {
        let rules = self.rules.read().await;
        let mut applicable = Vec::new();

        for rule in rules.iter() {
            if !rule.enabled {
                continue;
            }

            // Check component type
            if !rule.component_types.is_empty() &&
               !rule.component_types.contains(&health.component_type.to_string()) {
                continue;
            }

            // Check trigger conditions
            let mut triggered = false;
            for trigger in &rule.trigger_conditions {
                match trigger {
                    RecoveryTrigger::HealthStatus { status } => {
                        if health.status == *status {
                            triggered = true;
                            break;
                        }
                    }
                    RecoveryTrigger::ErrorCount { count, .. } => {
                        if health.error_count >= *count {
                            triggered = true;
                            break;
                        }
                    }
                    _ => {
                        // TODO: Implement other trigger conditions
                        continue;
                    }
                }
            }

            if triggered {
                applicable.push(rule.clone());
            }
        }

        applicable
    }

    /// Execute recovery rule
    async fn execute_recovery_rule(&self, rule: &RecoveryRule, health: &ComponentHealth) -> Result<()> {
        let start_time = std::time::Instant::now();

        // Record attempt
        {
            let mut attempts = self.recovery_attempts.write().await;
            let attempt = attempts.entry(health.component_id.clone())
                .or_insert_with(|| RecoveryAttempt::new(health.component_id.clone()));

            attempt.record_attempt(rule.cooldown);
        }

        tracing::info!("Executing recovery rule '{}' for component {}", rule.name, health.component_id);

        // Create alert for recovery attempt
        let recovery_alert = Alert::new(
            AlertLevel::Warning,
            "Auto-Recovery Initiated".to_string(),
            format!("Recovery rule '{}' triggered for: {}", rule.name,
                   health.last_error.as_deref().unwrap_or("Health check failure")),
            health.component_id.clone(),
            health.component_type.to_string(),
        ).with_tag("recovery_rule", &rule.name);

        if let Err(e) = self.alert_manager.send_alert(recovery_alert).await {
            tracing::warn!("Failed to send recovery alert: {}", e);
        }

        // Execute actions based on strategy
        let mut recovery_success = false;
        let mut last_error = None;

        match rule.strategy {
            RecoveryStrategy::Immediate => {
                recovery_success = self.execute_actions(&rule.actions, &health.component_id).await.is_ok();
            }
            RecoveryStrategy::Progressive => {
                // Try actions one by one until one succeeds
                for action in &rule.actions {
                    if self.execute_single_action(action, &health.component_id).await.is_ok() {
                        recovery_success = true;
                        break;
                    }
                }
            }
            RecoveryStrategy::DelayedRetry { delay } => {
                tokio::time::sleep(delay).await;
                recovery_success = self.execute_actions(&rule.actions, &health.component_id).await.is_ok();
            }
            RecoveryStrategy::Manual => {
                // Just notify, don't execute automatic actions
                recovery_success = true;
            }
        }

        let recovery_time = start_time.elapsed();

        // Create recovery event
        let current_attempt = {
            let attempts = self.recovery_attempts.read().await;
            attempts.get(&health.component_id)
                .map(|a| a.attempts)
                .unwrap_or(1)
        };

        let mut recovery_event = RecoveryEvent::new(
            health.component_id.clone(),
            health.component_type.to_string(),
            health.last_error.clone().unwrap_or_else(|| "Health check failure".to_string()),
            rule.actions.first().cloned().unwrap_or(RecoveryAction::NotifyAdmin),
            current_attempt,
        );

        if recovery_success {
            recovery_event.mark_success(recovery_time.as_millis() as u64);
            tracing::info!("Recovery successful for component {} in {}ms",
                          health.component_id, recovery_time.as_millis());

            // Send success alert
            let success_alert = Alert::new(
                AlertLevel::Info,
                "Auto-Recovery Successful".to_string(),
                format!("Component {} recovered using rule '{}'", health.component_id, rule.name),
                health.component_id.clone(),
                health.component_type.to_string(),
            ).with_tag("recovery_rule", &rule.name)
             .with_metric("recovery_time_ms", recovery_time.as_millis() as f64);

            if let Err(e) = self.alert_manager.send_alert(success_alert).await {
                tracing::warn!("Failed to send recovery success alert: {}", e);
            }

            // Reset recovery attempts on success
            let mut attempts = self.recovery_attempts.write().await;
            if let Some(attempt) = attempts.get_mut(&health.component_id) {
                attempt.reset();
            }
        } else {
            let error_msg = last_error.unwrap_or_else(|| "Unknown recovery failure".to_string());
            recovery_event.mark_failure(error_msg.clone());
            tracing::error!("Recovery failed for component {}: {}", health.component_id, error_msg);

            // Send failure alert
            let failure_alert = Alert::new(
                AlertLevel::Critical,
                "Auto-Recovery Failed".to_string(),
                format!("Failed to recover component {} using rule '{}': {}",
                       health.component_id, rule.name, error_msg),
                health.component_id.clone(),
                health.component_type.to_string(),
            ).with_tag("recovery_rule", &rule.name);

            if let Err(e) = self.alert_manager.send_alert(failure_alert).await {
                tracing::warn!("Failed to send recovery failure alert: {}", e);
            }
        }

        // Store recovery event
        {
            let mut history = self.recovery_history.write().await;
            history.push(recovery_event);
        }

        Ok(())
    }

    /// Execute multiple recovery actions
    async fn execute_actions(&self, actions: &[RecoveryAction], component_id: &str) -> Result<()> {
        for action in actions {
            self.execute_single_action(action, component_id).await?;
        }
        Ok(())
    }

    /// Execute single recovery action
    async fn execute_single_action(&self, action: &RecoveryAction, component_id: &str) -> Result<()> {
        for executor in &self.executors {
            if executor.can_execute(action, component_id) {
                return executor.execute(action, component_id).await;
            }
        }

        Err(MonitorError::Configuration {
            config: format!("No executor available for action: {:?}", action),
        })
    }

    /// Get recovery history
    pub async fn get_recovery_history(&self, limit: Option<usize>) -> Vec<RecoveryEvent> {
        let history = self.recovery_history.read().await;
        let limit = limit.unwrap_or(100);

        history.iter()
            .rev()
            .take(limit)
            .cloned()
            .collect()
    }

    /// Get recovery statistics
    pub async fn get_recovery_stats(&self) -> HashMap<String, u32> {
        let history = self.recovery_history.read().await;
        let mut stats = HashMap::new();

        let total = history.len() as u32;
        let successful = history.iter().filter(|e| e.success).count() as u32;
        let failed = total - successful;

        stats.insert("total_attempts".to_string(), total);
        stats.insert("successful_recoveries".to_string(), successful);
        stats.insert("failed_recoveries".to_string(), failed);

        if total > 0 {
            let success_rate = (successful as f32 / total as f32 * 100.0) as u32;
            stats.insert("success_rate_percent".to_string(), success_rate);
        }

        stats
    }
}