/*!
# Event Type Definitions

**Type-safe event definitions** cho **Event-Driven Architecture**.
Tất cả events implement **[`EventType`]** trait cho **consistent routing**.

## Event Categories

- **[`GpuEvent`]**: GPU operations và optimization
- **[`ResourceEvent`]**: Resource allocation và monitoring  
- **[`StealtHEvent`]**: Process stealth và anonymization
- **[`MonitoringEvent`]**: System monitoring và health checks

## Type Safety

Mỗi event type có **compile-time routing** qua **subject strings**:
- GPU events → `gpu.*` subjects
- Resource events → `resource.*` subjects  
- Stealth events → `stealth.*` subjects
- Monitoring events → `monitoring.*` subjects
*/

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::time::Duration;

/// **Event Type Trait** - Common interface cho tất cả events
pub trait EventType: Send + Sync + 'static {
    /// **Get event type name** (lấy tên loại event)
    fn event_type() -> String;
    
    /// **Get default subject** (lấy subject mặc định)
    fn default_subject(&self) -> String;
    
    /// **Get priority** (lấy độ ưu tiên)
    fn priority(&self) -> EventPriority {
        EventPriority::Normal
    }
    
    /// **Should persist** (có nên lưu trữ)
    fn should_persist(&self) -> bool {
        true
    }
}

/// **Event Priority** (độ ưu tiên event)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum EventPriority {
    /// **Low priority** - batch processing
    Low = 0,
    /// **Normal priority** - default
    Normal = 1,
    /// **High priority** - time-sensitive
    High = 2,
    /// **Critical priority** - emergency
    Critical = 3,
}

/// **GPU Events** - GPU operations và optimization
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum GpuEvent {
    /// **Optimize process for GPU** (tối ưu tiến trình cho GPU)
    OptimizeProcess {
        pid: u32,
        gpu_index: usize,
        strategies: Option<Vec<String>>,
    },
    
    /// **Allocate GPU memory** (cấp phát bộ nhớ GPU)
    AllocateMemory {
        gpu_index: usize,
        size_bytes: usize,
        priority: EventPriority,
    },
    
    /// **Deallocate GPU memory** (giải phóng bộ nhớ GPU)
    DeallocateMemory {
        gpu_index: usize,
        allocation_id: String,
    },
    
    /// **Monitor GPU status** (giám sát trạng thái GPU)
    MonitorStatus {
        gpu_indices: Vec<usize>,
        metrics: Vec<String>,
    },
    
    /// **Temperature warning** (cảnh báo nhiệt độ)
    TemperatureWarning {
        gpu_index: usize,
        temperature_celsius: f32,
        threshold_celsius: f32,
    },
    
    /// **Power limit adjustment** (điều chỉnh giới hạn công suất)
    PowerLimitAdjustment {
        gpu_index: usize,
        new_limit_watts: u32,
        reason: String,
    },
    
    /// **Kernel execution** (thực thi kernel)
    KernelExecution {
        gpu_index: usize,
        kernel_name: String,
        parameters: HashMap<String, serde_json::Value>,
        stream_priority: Option<i32>,
    },
    
    /// **GPU error detected** (phát hiện lỗi GPU)
    ErrorDetected {
        gpu_index: usize,
        error_code: u32,
        error_message: String,
        recovery_action: Option<String>,
    },
}

/// **Resource Events** - Resource management
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum ResourceEvent {
    /// **Allocate resources** (cấp phát tài nguyên)
    AllocateResources {
        resource_type: ResourceType,
        amount: u64,
        requester_pid: u32,
        priority: EventPriority,
    },
    
    /// **Deallocate resources** (giải phóng tài nguyên)
    DeallocateResources {
        resource_type: ResourceType,
        amount: u64,
        allocation_id: String,
    },
    
    /// **Monitor resource usage** (giám sát sử dụng tài nguyên)
    MonitorUsage {
        resource_types: Vec<ResourceType>,
        interval: Duration,
    },
    
    /// **Resource limit exceeded** (vượt quá giới hạn tài nguyên)
    LimitExceeded {
        resource_type: ResourceType,
        current_usage: u64,
        limit: u64,
        action: LimitAction,
    },
    
    /// **QoS policy enforcement** (thực thi chính sách QoS)
    QoSEnforcement {
        policy_name: String,
        target_pid: u32,
        action: QoSAction,
        reason: String,
    },
    
    /// **Auto-scaling trigger** (kích hoạt tự động mở rộng)
    AutoScalingTrigger {
        resource_type: ResourceType,
        direction: ScalingDirection,
        current_utilization: f32,
        threshold: f32,
    },
    
    /// **Resource conflict detected** (phát hiện xung đột tài nguyên)
    ConflictDetected {
        resource_type: ResourceType,
        conflicting_pids: Vec<u32>,
        resolution_strategy: ConflictResolution,
    },
}

/// **Stealth Events** - Process anonymization
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum StealtHEvent {
    /// **Hide process** (ẩn tiến trình)
    HideProcess {
        pid: u32,
        strategies: Vec<StealtHStrategy>,
        target_name: Option<String>,
    },
    
    /// **Unhide process** (bỏ ẩn tiến trình)
    UnhideProcess {
        pid: u32,
        restore_original: bool,
    },
    
    /// **Create namespace isolation** (tạo cô lập namespace)
    CreateNamespace {
        pid: u32,
        namespace_types: Vec<NamespaceType>,
        isolation_level: IsolationLevel,
    },
    
    /// **Apply process cloaking** (áp dụng ngụy trang tiến trình)
    ApplyCloaking {
        pid: u32,
        cloak_profile: String,
        duration: Option<Duration>,
    },
    
    /// **Network traffic obfuscation** (làm mờ lưu lượng mạng)
    ObfuscateTraffic {
        pid: u32,
        target_ports: Vec<u16>,
        obfuscation_method: ObfuscationMethod,
    },
    
    /// **Memory protection** (bảo vệ bộ nhớ)
    ProtectMemory {
        pid: u32,
        protection_type: MemoryProtectionType,
        regions: Vec<MemoryRegion>,
    },
    
    /// **Detection event** (sự kiện phát hiện)
    DetectionEvent {
        detection_type: DetectionType,
        detected_pid: u32,
        detector_info: DetectorInfo,
        countermeasure: Option<String>,
    },
}

/// **Monitoring Events** - System monitoring
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum MonitoringEvent {
    /// **Health check** (kiểm tra sức khỏe)
    HealthCheck {
        component: String,
        status: HealthStatus,
        details: HashMap<String, serde_json::Value>,
    },
    
    /// **Performance metrics** (chỉ số hiệu suất)
    PerformanceMetrics {
        component: String,
        metrics: HashMap<String, f64>,
        timestamp: u64,
    },
    
    /// **Alert triggered** (kích hoạt cảnh báo)
    AlertTriggered {
        alert_name: String,
        severity: AlertSeverity,
        message: String,
        affected_components: Vec<String>,
    },
    
    /// **Log entry** (mục nhập log)
    LogEntry {
        level: LogLevel,
        component: String,
        message: String,
        metadata: HashMap<String, serde_json::Value>,
    },
    
    /// **System event** (sự kiện hệ thống)
    SystemEvent {
        event_type: SystemEventType,
        description: String,
        impact_level: ImpactLevel,
    },
}

// Supporting enums và structs

/// **Resource Type** (loại tài nguyên)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ResourceType {
    Cpu,
    Memory,
    GpuMemory,
    GpuCompute,
    NetworkBandwidth,
    DiskIo,
}

/// **Limit Action** (hành động giới hạn)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LimitAction {
    Throttle,
    Terminate,
    Alert,
    Migrate,
}

/// **QoS Action** (hành động QoS)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum QoSAction {
    SetPriority { priority: i32 },
    SetCpuShares { shares: u32 },
    SetMemoryLimit { limit_mb: u32 },
    SetNetworkLimit { bandwidth_mbps: u32 },
}

/// **Scaling Direction** (hướng mở rộng)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ScalingDirection {
    Up,
    Down,
}

/// **Conflict Resolution** (giải quyết xung đột)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConflictResolution {
    FirstComeFirstServed,
    Priority,
    RoundRobin,
    TimeSlicing,
}

/// **Stealth Strategy** (chiến lược ẩn danh)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StealtHStrategy {
    ProcessNameSpoofing,
    ProcessTreeHiding,
    ResourceCloaking,
    NetworkObfuscation,
    FileSystemHiding,
}

/// **Namespace Type** (loại namespace)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum NamespaceType {
    Pid,
    Network,
    Mount,
    User,
    Ipc,
}

/// **Isolation Level** (mức độ cô lập)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum IsolationLevel {
    None,
    Basic,
    Enhanced,
    Maximum,
}

/// **Obfuscation Method** (phương pháp làm mờ)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ObfuscationMethod {
    TrafficShaping,
    ProtocolTunneling,
    PortHopping,
    PacketFragmentation,
}

/// **Memory Protection Type** (loại bảo vệ bộ nhớ)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum MemoryProtectionType {
    Encryption,
    Obfuscation,
    AccessControl,
    ZeroizeOnExit,
}

/// **Memory Region** (vùng bộ nhớ)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryRegion {
    pub start_address: u64,
    pub size: usize,
    pub protection_flags: u32,
}

/// **Detection Type** (loại phát hiện)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DetectionType {
    ProcessScanning,
    NetworkMonitoring,
    ResourceAnalysis,
    BehaviorAnalysis,
}

/// **Detector Info** (thông tin detector)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DetectorInfo {
    pub detector_name: String,
    pub detection_method: String,
    pub confidence_score: f32,
    pub additional_data: HashMap<String, serde_json::Value>,
}

/// **Health Status** (trạng thái sức khỏe)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Unhealthy,
    Unknown,
}

/// **Alert Severity** (mức độ nghiêm trọng cảnh báo)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum AlertSeverity {
    Info,
    Warning,
    Error,
    Critical,
}

/// **Log Level** (mức độ log)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum LogLevel {
    Trace,
    Debug,
    Info,
    Warn,
    Error,
}

/// **System Event Type** (loại sự kiện hệ thống)
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum SystemEventType {
    Startup,
    Shutdown,
    ConfigChange,
    ServiceRestart,
    ErrorRecovery,
}

/// **Impact Level** (mức độ tác động)
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ImpactLevel {
    None,
    Low,
    Medium,
    High,
    Critical,
}

// EventType implementations

impl EventType for GpuEvent {
    fn event_type() -> String {
        "GpuEvent".to_string()
    }
    
    fn default_subject(&self) -> String {
        match self {
            Self::OptimizeProcess { .. } => "gpu.optimize",
            Self::AllocateMemory { .. } => "gpu.memory.allocate",
            Self::DeallocateMemory { .. } => "gpu.memory.deallocate",
            Self::MonitorStatus { .. } => "gpu.monitor",
            Self::TemperatureWarning { .. } => "gpu.temperature.warning",
            Self::PowerLimitAdjustment { .. } => "gpu.power.adjust",
            Self::KernelExecution { .. } => "gpu.kernel.execute",
            Self::ErrorDetected { .. } => "gpu.error",
        }.to_string()
    }
    
    fn priority(&self) -> EventPriority {
        match self {
            Self::TemperatureWarning { .. } | Self::ErrorDetected { .. } => EventPriority::Critical,
            Self::OptimizeProcess { .. } | Self::KernelExecution { .. } => EventPriority::High,
            _ => EventPriority::Normal,
        }
    }
}

impl EventType for ResourceEvent {
    fn event_type() -> String {
        "ResourceEvent".to_string()
    }
    
    fn default_subject(&self) -> String {
        match self {
            Self::AllocateResources { .. } => "resource.allocate",
            Self::DeallocateResources { .. } => "resource.deallocate",
            Self::MonitorUsage { .. } => "resource.monitor",
            Self::LimitExceeded { .. } => "resource.limit.exceeded",
            Self::QoSEnforcement { .. } => "resource.qos.enforce",
            Self::AutoScalingTrigger { .. } => "resource.autoscale",
            Self::ConflictDetected { .. } => "resource.conflict",
        }.to_string()
    }
    
    fn priority(&self) -> EventPriority {
        match self {
            Self::LimitExceeded { .. } | Self::ConflictDetected { .. } => EventPriority::High,
            Self::QoSEnforcement { .. } => EventPriority::High,
            _ => EventPriority::Normal,
        }
    }
}

impl EventType for StealtHEvent {
    fn event_type() -> String {
        "StealtHEvent".to_string()
    }
    
    fn default_subject(&self) -> String {
        match self {
            Self::HideProcess { .. } => "stealth.hide",
            Self::UnhideProcess { .. } => "stealth.unhide",
            Self::CreateNamespace { .. } => "stealth.namespace",
            Self::ApplyCloaking { .. } => "stealth.cloak",
            Self::ObfuscateTraffic { .. } => "stealth.traffic",
            Self::ProtectMemory { .. } => "stealth.memory",
            Self::DetectionEvent { .. } => "stealth.detection",
        }.to_string()
    }
    
    fn priority(&self) -> EventPriority {
        match self {
            Self::DetectionEvent { .. } => EventPriority::Critical,
            Self::HideProcess { .. } | Self::ApplyCloaking { .. } => EventPriority::High,
            _ => EventPriority::Normal,
        }
    }
}

impl EventType for MonitoringEvent {
    fn event_type() -> String {
        "MonitoringEvent".to_string()
    }
    
    fn default_subject(&self) -> String {
        match self {
            Self::HealthCheck { .. } => "monitoring.health",
            Self::PerformanceMetrics { .. } => "monitoring.metrics",
            Self::AlertTriggered { .. } => "monitoring.alert",
            Self::LogEntry { .. } => "monitoring.log",
            Self::SystemEvent { .. } => "monitoring.system",
        }.to_string()
    }
    
    fn priority(&self) -> EventPriority {
        match self {
            Self::AlertTriggered { severity, .. } => match severity {
                AlertSeverity::Critical => EventPriority::Critical,
                AlertSeverity::Error => EventPriority::High,
                AlertSeverity::Warning => EventPriority::Normal,
                AlertSeverity::Info => EventPriority::Low,
            },
            Self::SystemEvent { impact_level, .. } => match impact_level {
                ImpactLevel::Critical => EventPriority::Critical,
                ImpactLevel::High => EventPriority::High,
                ImpactLevel::Medium => EventPriority::Normal,
                _ => EventPriority::Low,
            },
            _ => EventPriority::Low,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_gpu_event_routing() {
        let event = GpuEvent::OptimizeProcess {
            pid: 1234,
            gpu_index: 0,
            strategies: None,
        };
        
        assert_eq!(GpuEvent::event_type(), "GpuEvent");
        assert_eq!(event.default_subject(), "gpu.optimize");
        assert_eq!(event.priority(), EventPriority::High);
    }
    
    #[test]
    fn test_resource_event_priority() {
        let event = ResourceEvent::LimitExceeded {
            resource_type: ResourceType::Memory,
            current_usage: 1000,
            limit: 800,
            action: LimitAction::Throttle,
        };
        
        assert_eq!(event.priority(), EventPriority::High);
        assert_eq!(event.default_subject(), "resource.limit.exceeded");
    }
    
    #[test]
    fn test_stealth_event_serialization() {
        let event = StealtHEvent::HideProcess {
            pid: 5678,
            strategies: vec![StealtHStrategy::ProcessNameSpoofing, StealtHStrategy::ResourceCloaking],
            target_name: Some("legitimate_process".to_string()),
        };
        
        let serialized = serde_json::to_string(&event).unwrap();
        let deserialized: StealtHEvent = serde_json::from_str(&serialized).unwrap();
        
        match deserialized {
            StealtHEvent::HideProcess { pid, strategies, .. } => {
                assert_eq!(pid, 5678);
                assert_eq!(strategies.len(), 2);
            }
            _ => panic!("Unexpected event type"),
        }
    }
    
    #[test]
    fn test_monitoring_event_alert_severity() {
        let critical_alert = MonitoringEvent::AlertTriggered {
            alert_name: "GPU_OVERHEAT".to_string(),
            severity: AlertSeverity::Critical,
            message: "GPU temperature exceeded 90°C".to_string(),
            affected_components: vec!["GPU-0".to_string()],
        };
        
        assert_eq!(critical_alert.priority(), EventPriority::Critical);
    }
}
