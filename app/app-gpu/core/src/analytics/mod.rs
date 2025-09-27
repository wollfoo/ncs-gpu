//! Performance analytics and SRE tooling module
//! 
//! Provides performance analysis, SLI/SLO tracking, and error budget monitoring

use std::collections::{HashMap, VecDeque};
use std::sync::Arc;
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};
use chrono::{DateTime, Duration, Utc};
use anyhow::{Result, Context};

/// Service Level Indicator (SLI)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceLevelIndicator {
    /// SLI name
    pub name: String,
    
    /// Description
    pub description: String,
    
    /// Measurement type
    pub measurement: SliMeasurement,
    
    /// Current value
    pub current_value: f64,
    
    /// Target threshold
    pub threshold: f64,
    
    /// Time window for measurement
    pub window: Duration,
    
    /// Last updated
    pub last_updated: DateTime<Utc>,
}

/// SLI measurement types
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SliMeasurement {
    /// Availability (uptime percentage)
    Availability,
    /// Latency (percentile)
    Latency { percentile: f64 },
    /// Error rate
    ErrorRate,
    /// Throughput
    Throughput,
    /// Saturation
    Saturation,
    /// Custom metric
    Custom { metric_name: String },
}

/// Service Level Objective (SLO)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServiceLevelObjective {
    /// SLO identifier
    pub id: String,
    
    /// SLO name
    pub name: String,
    
    /// Description
    pub description: String,
    
    /// Associated SLI
    pub sli: ServiceLevelIndicator,
    
    /// Target percentage (e.g., 99.9)
    pub target: f64,
    
    /// Measurement period
    pub period: Duration,
    
    /// Current compliance
    pub compliance: f64,
    
    /// Error budget remaining
    pub error_budget_remaining: f64,
    
    /// Creation time
    pub created_at: DateTime<Utc>,
}

/// Error budget tracking
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ErrorBudget {
    /// SLO ID
    pub slo_id: String,
    
    /// Total budget (in minutes or percentage)
    pub total_budget: f64,
    
    /// Consumed budget
    pub consumed: f64,
    
    /// Remaining budget
    pub remaining: f64,
    
    /// Budget period
    pub period: Duration,
    
    /// Burn rate (consumption rate)
    pub burn_rate: f64,
    
    /// Time until budget exhaustion
    pub time_until_exhaustion: Option<Duration>,
    
    /// Last reset
    pub last_reset: DateTime<Utc>,
}

/// Performance metrics with percentiles
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    /// Metric name
    pub name: String,
    
    /// Sample count
    pub count: u64,
    
    /// Minimum value
    pub min: f64,
    
    /// Maximum value
    pub max: f64,
    
    /// Mean value
    pub mean: f64,
    
    /// Standard deviation
    pub std_dev: f64,
    
    /// Percentiles
    pub percentiles: PercentileSet,
    
    /// Time window
    pub window: Duration,
    
    /// Last updated
    pub last_updated: DateTime<Utc>,
}

/// Set of percentile values
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PercentileSet {
    pub p50: f64,
    pub p75: f64,
    pub p90: f64,
    pub p95: f64,
    pub p99: f64,
    pub p999: f64,
}

/// Latency breakdown analysis
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LatencyBreakdown {
    /// Total latency
    pub total_ms: f64,
    
    /// Components
    pub components: Vec<LatencyComponent>,
    
    /// Critical path
    pub critical_path: Vec<String>,
    
    /// Optimization suggestions
    pub suggestions: Vec<OptimizationSuggestion>,
}

/// Latency component
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LatencyComponent {
    pub name: String,
    pub duration_ms: f64,
    pub percentage: f64,
    pub is_critical_path: bool,
}

/// Optimization suggestion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OptimizationSuggestion {
    pub component: String,
    pub impact: ImpactLevel,
    pub suggestion: String,
    pub estimated_improvement_ms: f64,
}

/// Impact level for optimizations
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ImpactLevel {
    Low,
    Medium,
    High,
    Critical,
}

/// SRE Analytics Engine
pub struct SreAnalytics {
    /// SLOs registry
    slos: Arc<RwLock<HashMap<String, ServiceLevelObjective>>>,
    
    /// Error budgets
    error_budgets: Arc<RwLock<HashMap<String, ErrorBudget>>>,
    
    /// Performance metrics cache
    metrics_cache: Arc<RwLock<HashMap<String, PerformanceMetrics>>>,
    
    /// Historical data
    history: Arc<RwLock<TimeSeriesData>>,
}

impl SreAnalytics {
    pub fn new() -> Self {
        Self {
            slos: Arc::new(RwLock::new(HashMap::new())),
            error_budgets: Arc::new(RwLock::new(HashMap::new())),
            metrics_cache: Arc::new(RwLock::new(HashMap::new())),
            history: Arc::new(RwLock::new(TimeSeriesData::new())),
        }
    }
    
    /// Register a new SLO
    pub async fn register_slo(&self, slo: ServiceLevelObjective) -> Result<()> {
        let mut slos = self.slos.write().await;
        let id = slo.id.clone();
        
        // Initialize error budget
        let budget = ErrorBudget {
            slo_id: id.clone(),
            total_budget: 100.0 - slo.target,
            consumed: 0.0,
            remaining: 100.0 - slo.target,
            period: slo.period,
            burn_rate: 0.0,
            time_until_exhaustion: None,
            last_reset: Utc::now(),
        };
        
        let mut budgets = self.error_budgets.write().await;
        budgets.insert(id.clone(), budget);
        
        slos.insert(id, slo);
        Ok(())
    }
    
    /// Update SLI measurement
    pub async fn update_sli(&self, slo_id: &str, value: f64) -> Result<()> {
        let mut slos = self.slos.write().await;
        
        let slo = slos.get_mut(slo_id)
            .context("SLO not found")?;
        
        slo.sli.current_value = value;
        slo.sli.last_updated = Utc::now();
        
        // Update compliance
        let compliance = self.calculate_compliance(&slo.sli, slo.target);
        slo.compliance = compliance;
        
        // Update error budget
        self.update_error_budget(slo_id, compliance).await?;
        
        Ok(())
    }
    
    /// Calculate SLO compliance
    fn calculate_compliance(&self, sli: &ServiceLevelIndicator, target: f64) -> f64 {
        match sli.measurement {
            SliMeasurement::Availability => {
                (sli.current_value / 100.0) * 100.0
            }
            SliMeasurement::Latency { percentile: _ } => {
                if sli.current_value <= sli.threshold {
                    100.0
                } else {
                    (sli.threshold / sli.current_value) * 100.0
                }
            }
            SliMeasurement::ErrorRate => {
                ((100.0 - sli.current_value) / 100.0) * 100.0
            }
            _ => sli.current_value
        }
    }
    
    /// Update error budget
    async fn update_error_budget(&self, slo_id: &str, compliance: f64) -> Result<()> {
        let mut budgets = self.error_budgets.write().await;
        
        let budget = budgets.get_mut(slo_id)
            .context("Error budget not found")?;
        
        let violation = 100.0 - compliance;
        budget.consumed += violation;
        budget.remaining = budget.total_budget - budget.consumed;
        
        // Calculate burn rate (violations per hour)
        let hours_elapsed = Utc::now()
            .signed_duration_since(budget.last_reset)
            .num_seconds() as f64 / 3600.0;
        
        if hours_elapsed > 0.0 {
            budget.burn_rate = budget.consumed / hours_elapsed;
            
            // Calculate time until exhaustion
            if budget.burn_rate > 0.0 {
                let hours_remaining = budget.remaining / budget.burn_rate;
                budget.time_until_exhaustion = Some(Duration::hours(hours_remaining as i64));
            }
        }
        
        Ok(())
    }
    
    /// Record performance metric
    pub async fn record_metric(&self, name: String, value: f64) {
        let mut history = self.history.write().await;
        history.add_point(&name, value);
        
        // Update metrics cache
        if let Some(metrics) = self.calculate_metrics(&name, &history).await {
            let mut cache = self.metrics_cache.write().await;
            cache.insert(name, metrics);
        }
    }
    
    /// Calculate performance metrics
    async fn calculate_metrics(&self, name: &str, history: &TimeSeriesData) -> Option<PerformanceMetrics> {
        let values = history.get_recent_values(name, 1000)?;
        
        if values.is_empty() {
            return None;
        }
        
        let count = values.len() as u64;
        let min = values.iter().fold(f64::INFINITY, |a, &b| a.min(b));
        let max = values.iter().fold(f64::NEG_INFINITY, |a, &b| a.max(b));
        let mean = values.iter().sum::<f64>() / count as f64;
        
        let variance = values.iter()
            .map(|v| (v - mean).powi(2))
            .sum::<f64>() / count as f64;
        let std_dev = variance.sqrt();
        
        let percentiles = self.calculate_percentiles(&values);
        
        Some(PerformanceMetrics {
            name: name.to_string(),
            count,
            min,
            max,
            mean,
            std_dev,
            percentiles,
            window: Duration::hours(1),
            last_updated: Utc::now(),
        })
    }
    
    /// Calculate percentiles
    fn calculate_percentiles(&self, values: &[f64]) -> PercentileSet {
        let mut sorted = values.to_vec();
        sorted.sort_by(|a, b| a.partial_cmp(b).unwrap());
        
        let len = sorted.len();
        
        PercentileSet {
            p50: sorted[len * 50 / 100],
            p75: sorted[len * 75 / 100],
            p90: sorted[len * 90 / 100],
            p95: sorted[len * 95 / 100],
            p99: sorted[len * 99 / 100],
            p999: sorted[len.min(len * 999 / 1000).max(len - 1)],
        }
    }
    
    /// Analyze latency breakdown
    pub async fn analyze_latency(&self, trace_id: &str) -> Result<LatencyBreakdown> {
        // In real implementation, would analyze trace data
        // For now, return mock analysis
        
        let components = vec![
            LatencyComponent {
                name: "Network".to_string(),
                duration_ms: 10.5,
                percentage: 15.0,
                is_critical_path: true,
            },
            LatencyComponent {
                name: "GPU Scheduling".to_string(),
                duration_ms: 5.2,
                percentage: 7.5,
                is_critical_path: true,
            },
            LatencyComponent {
                name: "GPU Execution".to_string(),
                duration_ms: 45.3,
                percentage: 65.0,
                is_critical_path: true,
            },
            LatencyComponent {
                name: "Result Serialization".to_string(),
                duration_ms: 8.7,
                percentage: 12.5,
                is_critical_path: false,
            },
        ];
        
        let suggestions = vec![
            OptimizationSuggestion {
                component: "GPU Execution".to_string(),
                impact: ImpactLevel::High,
                suggestion: "Consider kernel fusion to reduce launch overhead".to_string(),
                estimated_improvement_ms: 10.0,
            },
            OptimizationSuggestion {
                component: "Network".to_string(),
                impact: ImpactLevel::Medium,
                suggestion: "Enable compression for large payloads".to_string(),
                estimated_improvement_ms: 3.0,
            },
        ];
        
        Ok(LatencyBreakdown {
            total_ms: 69.7,
            components,
            critical_path: vec![
                "Network".to_string(),
                "GPU Scheduling".to_string(),
                "GPU Execution".to_string(),
            ],
            suggestions,
        })
    }
    
    /// Generate SRE report
    pub async fn generate_report(&self) -> SreReport {
        let slos = self.slos.read().await;
        let budgets = self.error_budgets.read().await;
        let metrics = self.metrics_cache.read().await;
        
        let slo_status: Vec<SloStatus> = slos.values().map(|slo| {
            let budget = budgets.get(&slo.id);
            
            SloStatus {
                name: slo.name.clone(),
                target: slo.target,
                current: slo.compliance,
                is_meeting: slo.compliance >= slo.target,
                error_budget_remaining: budget.map(|b| b.remaining).unwrap_or(0.0),
                burn_rate: budget.map(|b| b.burn_rate).unwrap_or(0.0),
            }
        }).collect();
        
        let performance_summary: Vec<MetricSummary> = metrics.values().map(|m| {
            MetricSummary {
                name: m.name.clone(),
                p50: m.percentiles.p50,
                p95: m.percentiles.p95,
                p99: m.percentiles.p99,
                mean: m.mean,
                std_dev: m.std_dev,
            }
        }).collect();
        
        SreReport {
            generated_at: Utc::now(),
            slo_status,
            performance_summary,
            recommendations: self.generate_recommendations(&slo_status),
        }
    }
    
    /// Generate recommendations based on current state
    fn generate_recommendations(&self, slo_status: &[SloStatus]) -> Vec<String> {
        let mut recommendations = Vec::new();
        
        for slo in slo_status {
            if !slo.is_meeting {
                recommendations.push(format!(
                    "SLO '{}' is below target ({:.2}% vs {:.2}%). Review error budget burn rate.",
                    slo.name, slo.current, slo.target
                ));
            }
            
            if slo.burn_rate > 1.0 {
                recommendations.push(format!(
                    "SLO '{}' has high burn rate ({:.2}x). Consider immediate action.",
                    slo.name, slo.burn_rate
                ));
            }
            
            if slo.error_budget_remaining < 10.0 {
                recommendations.push(format!(
                    "SLO '{}' has low error budget ({:.2}% remaining). Freeze risky changes.",
                    slo.name, slo.error_budget_remaining
                ));
            }
        }
        
        if recommendations.is_empty() {
            recommendations.push("All SLOs are meeting targets. System is healthy.".to_string());
        }
        
        recommendations
    }
}

/// Time series data storage
struct TimeSeriesData {
    data: HashMap<String, VecDeque<(DateTime<Utc>, f64)>>,
    max_points: usize,
}

impl TimeSeriesData {
    fn new() -> Self {
        Self {
            data: HashMap::new(),
            max_points: 10000,
        }
    }
    
    fn add_point(&mut self, metric: &str, value: f64) {
        let entry = self.data.entry(metric.to_string())
            .or_insert_with(VecDeque::new);
        
        entry.push_back((Utc::now(), value));
        
        while entry.len() > self.max_points {
            entry.pop_front();
        }
    }
    
    fn get_recent_values(&self, metric: &str, count: usize) -> Option<Vec<f64>> {
        self.data.get(metric).map(|series| {
            series.iter()
                .rev()
                .take(count)
                .map(|(_, v)| *v)
                .collect()
        })
    }
}

/// SRE report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SreReport {
    pub generated_at: DateTime<Utc>,
    pub slo_status: Vec<SloStatus>,
    pub performance_summary: Vec<MetricSummary>,
    pub recommendations: Vec<String>,
}

/// SLO status summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SloStatus {
    pub name: String,
    pub target: f64,
    pub current: f64,
    pub is_meeting: bool,
    pub error_budget_remaining: f64,
    pub burn_rate: f64,
}

/// Metric summary
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetricSummary {
    pub name: String,
    pub p50: f64,
    pub p95: f64,
    pub p99: f64,
    pub mean: f64,
    pub std_dev: f64,
}

/// Postmortem template
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PostmortemTemplate {
    pub incident_id: String,
    pub title: String,
    pub severity: IncidentSeverity,
    pub date: DateTime<Utc>,
    pub duration: Duration,
    pub impact: ImpactDescription,
    pub timeline: Vec<TimelineEntry>,
    pub root_causes: Vec<RootCause>,
    pub action_items: Vec<ActionItem>,
    pub lessons_learned: Vec<String>,
}

/// Incident severity
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum IncidentSeverity {
    Low,
    Medium,
    High,
    Critical,
}

/// Impact description
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImpactDescription {
    pub users_affected: u64,
    pub revenue_impact: Option<f64>,
    pub slos_violated: Vec<String>,
    pub description: String,
}

/// Timeline entry
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TimelineEntry {
    pub time: DateTime<Utc>,
    pub event: String,
    pub actor: String,
}

/// Root cause
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RootCause {
    pub category: String,
    pub description: String,
    pub contributing_factors: Vec<String>,
}

/// Action item
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ActionItem {
    pub id: String,
    pub description: String,
    pub owner: String,
    pub priority: ImpactLevel,
    pub due_date: DateTime<Utc>,
    pub status: ActionStatus,
}

/// Action status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ActionStatus {
    NotStarted,
    InProgress,
    Completed,
    Blocked,
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_sre_analytics() {
        let analytics = SreAnalytics::new();
        
        // Register SLO
        let sli = ServiceLevelIndicator {
            name: "API Latency".to_string(),
            description: "95th percentile API latency".to_string(),
            measurement: SliMeasurement::Latency { percentile: 95.0 },
            current_value: 150.0,
            threshold: 200.0,
            window: Duration::hours(24),
            last_updated: Utc::now(),
        };
        
        let slo = ServiceLevelObjective {
            id: "slo-1".to_string(),
            name: "API Latency SLO".to_string(),
            description: "API latency should be under 200ms".to_string(),
            sli,
            target: 99.5,
            period: Duration::days(30),
            compliance: 100.0,
            error_budget_remaining: 0.5,
            created_at: Utc::now(),
        };
        
        analytics.register_slo(slo).await.unwrap();
        
        // Update SLI
        analytics.update_sli("slo-1", 180.0).await.unwrap();
        
        // Record metrics
        for i in 0..100 {
            analytics.record_metric("latency".to_string(), 150.0 + (i as f64 * 0.5)).await;
        }
        
        // Generate report
        let report = analytics.generate_report().await;
        assert!(!report.slo_status.is_empty());
        assert!(!report.recommendations.is_empty());
    }
    
    #[tokio::test]
    async fn test_latency_analysis() {
        let analytics = SreAnalytics::new();
        
        let breakdown = analytics.analyze_latency("trace-123").await.unwrap();
        assert!(!breakdown.components.is_empty());
        assert!(!breakdown.critical_path.is_empty());
        assert!(!breakdown.suggestions.is_empty());
        
        // Verify total matches sum of components
        let component_sum: f64 = breakdown.components.iter()
            .map(|c| c.duration_ms)
            .sum();
        assert_eq!(breakdown.total_ms, component_sum);
    }
}
