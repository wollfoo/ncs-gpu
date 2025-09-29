//! **Dashboard Support** (Hỗ trợ dashboard)
//!
//! Dashboard configuration and integration for monitoring visualization.

use crate::{MonitorError, Result, DashboardConfig};
use serde::{Deserialize, Serialize};
use serde_json::Value as JsonValue;
use std::collections::HashMap;

/// **Dashboard Template** (Mẫu dashboard) - Pre-configured dashboard definitions
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardTemplate {
    pub id: String,
    pub name: String,
    pub description: String,
    pub version: String,
    pub dashboard_type: DashboardType,
    pub template: JsonValue,
    pub variables: HashMap<String, DashboardVariable>,
    pub required_metrics: Vec<String>,
}

/// **Dashboard Type** (Loại dashboard) - Different dashboard platforms
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DashboardType {
    Grafana,
    Prometheus,
    Custom { platform: String },
}

/// **Dashboard Variable** (Biến dashboard) - Template variables
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DashboardVariable {
    pub name: String,
    pub display_name: String,
    pub description: String,
    pub var_type: VariableType,
    pub default_value: Option<String>,
    pub options: Option<Vec<String>>,
}

/// **Variable Type** (Loại biến)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum VariableType {
    Query,
    Custom,
    Constant,
    Datasource,
    Interval,
}

/// **Dashboard Manager** (Trình quản lý dashboard) - Manages dashboard templates and deployment
pub struct DashboardManager {
    config: DashboardConfig,
    templates: HashMap<String, DashboardTemplate>,
}

impl DashboardManager {
    /// Create new dashboard manager
    pub fn new(config: DashboardConfig) -> Self {
        let mut manager = Self {
            config,
            templates: HashMap::new(),
        };

        // Load default templates
        manager.load_default_templates();

        manager
    }

    /// Load default dashboard templates
    fn load_default_templates(&mut self) {
        // GPU Overview Dashboard
        let gpu_dashboard = self.create_gpu_overview_dashboard();
        self.templates.insert(gpu_dashboard.id.clone(), gpu_dashboard);

        // System Overview Dashboard
        let system_dashboard = self.create_system_overview_dashboard();
        self.templates.insert(system_dashboard.id.clone(), system_dashboard);

        // Mining Performance Dashboard
        let mining_dashboard = self.create_mining_performance_dashboard();
        self.templates.insert(mining_dashboard.id.clone(), mining_dashboard);

        // Pool Statistics Dashboard
        let pool_dashboard = self.create_pool_statistics_dashboard();
        self.templates.insert(pool_dashboard.id.clone(), pool_dashboard);

        // Alert & Health Dashboard
        let alert_dashboard = self.create_alert_health_dashboard();
        self.templates.insert(alert_dashboard.id.clone(), alert_dashboard);

        tracing::info!("Loaded {} dashboard templates", self.templates.len());
    }

    /// Create GPU Overview Dashboard template
    fn create_gpu_overview_dashboard(&self) -> DashboardTemplate {
        let dashboard_json = serde_json::json!({
            "dashboard": {
                "id": null,
                "title": "OPUS-GPU - GPU Overview",
                "tags": ["opus-gpu", "gpu", "monitoring"],
                "timezone": "browser",
                "panels": [
                    {
                        "id": 1,
                        "title": "GPU Temperature",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_gpu_temperature_celsius",
                            "legendFormat": "GPU {{gpu_id}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "celsius",
                                "thresholds": {
                                    "steps": [
                                        {"color": "green", "value": null},
                                        {"color": "yellow", "value": 75},
                                        {"color": "red", "value": 85}
                                    ]
                                }
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
                    },
                    {
                        "id": 2,
                        "title": "GPU Utilization",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_gpu_utilization_percent",
                            "legendFormat": "GPU {{gpu_id}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "percent",
                                "thresholds": {
                                    "steps": [
                                        {"color": "red", "value": null},
                                        {"color": "yellow", "value": 70},
                                        {"color": "green", "value": 85}
                                    ]
                                }
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
                    },
                    {
                        "id": 3,
                        "title": "Power Draw",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_gpu_power_draw_watts",
                            "legendFormat": "GPU {{gpu_id}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "watt"
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0}
                    },
                    {
                        "id": 4,
                        "title": "Hash Rate",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_gpu_hashrate_mhs",
                            "legendFormat": "GPU {{gpu_id}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "MH/s"
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0}
                    },
                    {
                        "id": 5,
                        "title": "GPU Temperature Over Time",
                        "type": "timeseries",
                        "targets": [{
                            "expr": "opus_gpu_temperature_celsius",
                            "legendFormat": "GPU {{gpu_id}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "celsius"
                            }
                        },
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                    },
                    {
                        "id": 6,
                        "title": "Hash Rate Over Time",
                        "type": "timeseries",
                        "targets": [{
                            "expr": "opus_gpu_hashrate_mhs",
                            "legendFormat": "GPU {{gpu_id}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "MH/s"
                            }
                        },
                        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
                    }
                ],
                "time": {"from": "now-1h", "to": "now"},
                "refresh": "30s"
            }
        });

        let mut variables = HashMap::new();
        variables.insert("gpu_filter".to_string(), DashboardVariable {
            name: "gpu_filter".to_string(),
            display_name: "GPU Filter".to_string(),
            description: "Filter by GPU ID".to_string(),
            var_type: VariableType::Query,
            default_value: Some(".*".to_string()),
            options: None,
        });

        DashboardTemplate {
            id: "opus_gpu_overview".to_string(),
            name: "OPUS-GPU Overview".to_string(),
            description: "Overview of GPU mining performance and health".to_string(),
            version: "1.0.0".to_string(),
            dashboard_type: DashboardType::Grafana,
            template: dashboard_json,
            variables,
            required_metrics: vec![
                "opus_gpu_temperature_celsius".to_string(),
                "opus_gpu_utilization_percent".to_string(),
                "opus_gpu_power_draw_watts".to_string(),
                "opus_gpu_hashrate_mhs".to_string(),
            ],
        }
    }

    /// Create System Overview Dashboard template
    fn create_system_overview_dashboard(&self) -> DashboardTemplate {
        let dashboard_json = serde_json::json!({
            "dashboard": {
                "id": null,
                "title": "OPUS-GPU - System Overview",
                "tags": ["opus-gpu", "system", "monitoring"],
                "panels": [
                    {
                        "id": 1,
                        "title": "CPU Usage",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_system_cpu_usage_percent",
                            "legendFormat": "CPU"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "percent",
                                "thresholds": {
                                    "steps": [
                                        {"color": "green", "value": null},
                                        {"color": "yellow", "value": 70},
                                        {"color": "red", "value": 90}
                                    ]
                                }
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
                    },
                    {
                        "id": 2,
                        "title": "Memory Usage",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_system_memory_used_bytes / opus_system_memory_total_bytes * 100",
                            "legendFormat": "Memory"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "percent"
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
                    },
                    {
                        "id": 3,
                        "title": "System Uptime",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_system_uptime_seconds",
                            "legendFormat": "Uptime"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "s"
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0}
                    }
                ],
                "time": {"from": "now-6h", "to": "now"},
                "refresh": "1m"
            }
        });

        DashboardTemplate {
            id: "opus_system_overview".to_string(),
            name: "OPUS-GPU System Overview".to_string(),
            description: "System resource monitoring and health".to_string(),
            version: "1.0.0".to_string(),
            dashboard_type: DashboardType::Grafana,
            template: dashboard_json,
            variables: HashMap::new(),
            required_metrics: vec![
                "opus_system_cpu_usage_percent".to_string(),
                "opus_system_memory_used_bytes".to_string(),
                "opus_system_memory_total_bytes".to_string(),
                "opus_system_uptime_seconds".to_string(),
            ],
        }
    }

    /// Create Mining Performance Dashboard template
    fn create_mining_performance_dashboard(&self) -> DashboardTemplate {
        let dashboard_json = serde_json::json!({
            "dashboard": {
                "id": null,
                "title": "OPUS-GPU - Mining Performance",
                "tags": ["opus-gpu", "mining", "performance"],
                "panels": [
                    {
                        "id": 1,
                        "title": "Total Hash Rate",
                        "type": "stat",
                        "targets": [{
                            "expr": "sum(opus_gpu_hashrate_mhs)",
                            "legendFormat": "Total Hash Rate"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "MH/s"
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
                    },
                    {
                        "id": 2,
                        "title": "Power Efficiency",
                        "type": "stat",
                        "targets": [{
                            "expr": "sum(opus_gpu_hashrate_mhs) / sum(opus_gpu_power_draw_watts)",
                            "legendFormat": "Efficiency"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "MH/W"
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
                    },
                    {
                        "id": 3,
                        "title": "Shares Accepted vs Rejected",
                        "type": "timeseries",
                        "targets": [
                            {
                                "expr": "sum(increase(opus_gpu_shares_accepted_total[5m]))",
                                "legendFormat": "Accepted"
                            },
                            {
                                "expr": "sum(increase(opus_gpu_shares_rejected_total[5m]))",
                                "legendFormat": "Rejected"
                            }
                        ],
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                    }
                ],
                "time": {"from": "now-2h", "to": "now"},
                "refresh": "15s"
            }
        });

        DashboardTemplate {
            id: "opus_mining_performance".to_string(),
            name: "OPUS-GPU Mining Performance".to_string(),
            description: "Mining performance metrics and efficiency".to_string(),
            version: "1.0.0".to_string(),
            dashboard_type: DashboardType::Grafana,
            template: dashboard_json,
            variables: HashMap::new(),
            required_metrics: vec![
                "opus_gpu_hashrate_mhs".to_string(),
                "opus_gpu_power_draw_watts".to_string(),
                "opus_gpu_shares_accepted_total".to_string(),
                "opus_gpu_shares_rejected_total".to_string(),
            ],
        }
    }

    /// Create Pool Statistics Dashboard template
    fn create_pool_statistics_dashboard(&self) -> DashboardTemplate {
        let dashboard_json = serde_json::json!({
            "dashboard": {
                "id": null,
                "title": "OPUS-GPU - Pool Statistics",
                "tags": ["opus-gpu", "pool", "statistics"],
                "panels": [
                    {
                        "id": 1,
                        "title": "Pool Connection Status",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_pool_connected",
                            "legendFormat": "{{pool_name}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "mappings": [
                                    {"options": {"0": {"text": "Disconnected"}}, "type": "value"},
                                    {"options": {"1": {"text": "Connected"}}, "type": "value"}
                                ]
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
                    },
                    {
                        "id": 2,
                        "title": "Pool Latency",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_pool_latency_ms",
                            "legendFormat": "{{pool_name}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "ms",
                                "thresholds": {
                                    "steps": [
                                        {"color": "green", "value": null},
                                        {"color": "yellow", "value": 100},
                                        {"color": "red", "value": 500}
                                    ]
                                }
                            }
                        },
                        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
                    },
                    {
                        "id": 3,
                        "title": "Pool Hash Rate",
                        "type": "timeseries",
                        "targets": [{
                            "expr": "opus_pool_hashrate_reported_mhs",
                            "legendFormat": "{{pool_name}}"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "unit": "MH/s"
                            }
                        },
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                    }
                ],
                "time": {"from": "now-1h", "to": "now"},
                "refresh": "30s"
            }
        });

        DashboardTemplate {
            id: "opus_pool_statistics".to_string(),
            name: "OPUS-GPU Pool Statistics".to_string(),
            description: "Mining pool connection and performance statistics".to_string(),
            version: "1.0.0".to_string(),
            dashboard_type: DashboardType::Grafana,
            template: dashboard_json,
            variables: HashMap::new(),
            required_metrics: vec![
                "opus_pool_connected".to_string(),
                "opus_pool_latency_ms".to_string(),
                "opus_pool_hashrate_reported_mhs".to_string(),
            ],
        }
    }

    /// Create Alert & Health Dashboard template
    fn create_alert_health_dashboard(&self) -> DashboardTemplate {
        let dashboard_json = serde_json::json!({
            "dashboard": {
                "id": null,
                "title": "OPUS-GPU - Alerts & Health",
                "tags": ["opus-gpu", "alerts", "health"],
                "panels": [
                    {
                        "id": 1,
                        "title": "System Health Status",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_system_health_status",
                            "legendFormat": "Health"
                        }],
                        "fieldConfig": {
                            "defaults": {
                                "mappings": [
                                    {"options": {"0": {"text": "Healthy", "color": "green"}}, "type": "value"},
                                    {"options": {"1": {"text": "Warning", "color": "yellow"}}, "type": "value"},
                                    {"options": {"2": {"text": "Critical", "color": "red"}}, "type": "value"},
                                    {"options": {"3": {"text": "Down", "color": "red"}}, "type": "value"}
                                ]
                            }
                        },
                        "gridPos": {"h": 8, "w": 8, "x": 0, "y": 0}
                    },
                    {
                        "id": 2,
                        "title": "Active Alerts",
                        "type": "stat",
                        "targets": [{
                            "expr": "opus_active_alerts_total",
                            "legendFormat": "Alerts"
                        }],
                        "gridPos": {"h": 8, "w": 8, "x": 8, "y": 0}
                    },
                    {
                        "id": 3,
                        "title": "Recovery Attempts",
                        "type": "timeseries",
                        "targets": [{
                            "expr": "increase(opus_recovery_attempts_total[1h])",
                            "legendFormat": "Recovery Attempts"
                        }],
                        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
                    }
                ],
                "time": {"from": "now-6h", "to": "now"},
                "refresh": "1m"
            }
        });

        DashboardTemplate {
            id: "opus_alerts_health".to_string(),
            name: "OPUS-GPU Alerts & Health".to_string(),
            description: "System health monitoring and alert overview".to_string(),
            version: "1.0.0".to_string(),
            dashboard_type: DashboardType::Grafana,
            template: dashboard_json,
            variables: HashMap::new(),
            required_metrics: vec![
                "opus_system_health_status".to_string(),
                "opus_active_alerts_total".to_string(),
                "opus_recovery_attempts_total".to_string(),
            ],
        }
    }

    /// Get dashboard template by ID
    pub fn get_template(&self, template_id: &str) -> Option<&DashboardTemplate> {
        self.templates.get(template_id)
    }

    /// List all available templates
    pub fn list_templates(&self) -> Vec<&DashboardTemplate> {
        self.templates.values().collect()
    }

    /// Export dashboard template with variables resolved
    pub fn export_template(&self, template_id: &str, variables: Option<HashMap<String, String>>) -> Result<JsonValue> {
        let template = self.templates.get(template_id)
            .ok_or_else(|| MonitorError::Configuration {
                config: format!("Dashboard template not found: {}", template_id)
            })?;

        let mut dashboard = template.template.clone();

        // Replace variables if provided
        if let Some(vars) = variables {
            let dashboard_str = dashboard.to_string();
            let mut resolved_str = dashboard_str;

            for (key, value) in vars {
                let placeholder = format!("${{{}}}", key);
                resolved_str = resolved_str.replace(&placeholder, &value);
            }

            dashboard = serde_json::from_str(&resolved_str)
                .map_err(|e| MonitorError::Configuration {
                    config: format!("Failed to parse dashboard template: {}", e)
                })?;
        }

        Ok(dashboard)
    }

    /// Generate Grafana provisioning configuration
    pub fn generate_grafana_provisioning(&self) -> Result<JsonValue> {
        let mut dashboards = Vec::new();

        for template in self.templates.values() {
            if matches!(template.dashboard_type, DashboardType::Grafana) {
                dashboards.push(serde_json::json!({
                    "name": template.name,
                    "orgId": 1,
                    "folder": "OPUS-GPU",
                    "type": "file",
                    "disableDeletion": false,
                    "updateIntervalSeconds": 10,
                    "options": {
                        "path": format!("/etc/grafana/provisioning/dashboards/{}.json", template.id)
                    }
                }));
            }
        }

        Ok(serde_json::json!({
            "apiVersion": 1,
            "providers": dashboards
        }))
    }

    /// Generate dashboard deployment manifest
    pub fn generate_deployment_manifest(&self) -> Result<JsonValue> {
        let mut manifests = Vec::new();

        for template in self.templates.values() {
            manifests.push(serde_json::json!({
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "version": template.version,
                "type": template.dashboard_type,
                "required_metrics": template.required_metrics,
                "variables": template.variables
            }));
        }

        Ok(serde_json::json!({
            "version": "1.0.0",
            "dashboards": manifests
        }))
    }
}

/// **Dashboard Deployment** (Triển khai dashboard) - Deploy dashboards to target platforms
pub struct DashboardDeployment {
    manager: DashboardManager,
}

impl DashboardDeployment {
    /// Create new dashboard deployment
    pub fn new(manager: DashboardManager) -> Self {
        Self { manager }
    }

    /// Deploy dashboard to Grafana
    pub async fn deploy_to_grafana(&self, grafana_url: &str, api_key: &str, template_id: &str) -> Result<()> {
        let template = self.manager.get_template(template_id)
            .ok_or_else(|| MonitorError::Configuration {
                config: format!("Template not found: {}", template_id)
            })?;

        if !matches!(template.dashboard_type, DashboardType::Grafana) {
            return Err(MonitorError::Configuration {
                config: format!("Template {} is not a Grafana dashboard", template_id)
            });
        }

        let dashboard_json = self.manager.export_template(template_id, None)?;

        let client = reqwest::Client::new();
        let response = client
            .post(&format!("{}/api/dashboards/db", grafana_url))
            .header("Authorization", format!("Bearer {}", api_key))
            .header("Content-Type", "application/json")
            .json(&dashboard_json)
            .send()
            .await
            .map_err(|e| MonitorError::Export {
                exporter: "grafana".to_string(),
                reason: format!("Failed to deploy dashboard: {}", e)
            })?;

        if response.status().is_success() {
            tracing::info!("Successfully deployed dashboard {} to Grafana", template.name);
            Ok(())
        } else {
            let error_text = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            Err(MonitorError::Export {
                exporter: "grafana".to_string(),
                reason: format!("Deployment failed: {}", error_text)
            })
        }
    }

    /// Auto-deploy all compatible dashboards
    pub async fn auto_deploy(&self, grafana_url: &str, api_key: &str) -> Result<Vec<String>> {
        let mut deployed = Vec::new();

        for template in self.manager.list_templates() {
            if matches!(template.dashboard_type, DashboardType::Grafana) {
                match self.deploy_to_grafana(grafana_url, api_key, &template.id).await {
                    Ok(()) => {
                        deployed.push(template.name.clone());
                        tracing::info!("Auto-deployed dashboard: {}", template.name);
                    }
                    Err(e) => {
                        tracing::error!("Failed to auto-deploy dashboard {}: {}", template.name, e);
                    }
                }
            }
        }

        Ok(deployed)
    }

    /// Export all dashboard files to directory
    pub async fn export_all_to_directory(&self, output_dir: &str) -> Result<Vec<String>> {
        use std::path::Path;
        use tokio::fs;

        let output_path = Path::new(output_dir);
        if !output_path.exists() {
            fs::create_dir_all(output_path).await
                .map_err(|e| MonitorError::Configuration {
                    config: format!("Failed to create output directory: {}", e)
                })?;
        }

        let mut exported_files = Vec::new();

        for template in self.manager.list_templates() {
            let dashboard_json = self.manager.export_template(&template.id, None)?;
            let file_path = output_path.join(format!("{}.json", template.id));

            fs::write(&file_path, serde_json::to_string_pretty(&dashboard_json).unwrap())
                .await
                .map_err(|e| MonitorError::Configuration {
                    config: format!("Failed to write dashboard file: {}", e)
                })?;

            exported_files.push(file_path.to_string_lossy().to_string());
            tracing::info!("Exported dashboard {} to {}", template.name, file_path.display());
        }

        // Export provisioning configuration
        let provisioning_config = self.manager.generate_grafana_provisioning()?;
        let provisioning_path = output_path.join("provisioning.yml");
        fs::write(&provisioning_path, serde_yaml::to_string(&provisioning_config).unwrap())
            .await
            .map_err(|e| MonitorError::Configuration {
                config: format!("Failed to write provisioning config: {}", e)
            })?;

        exported_files.push(provisioning_path.to_string_lossy().to_string());

        Ok(exported_files)
    }
}