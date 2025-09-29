//! **Dashboard Export Example** (Ví dụ xuất dashboard)
//!
//! Demonstrates how to export monitoring dashboards.

use opus_gpu_monitor::dashboards::{DashboardManager, DashboardDeployment};
use opus_gpu_monitor::DashboardConfig;
use std::path::Path;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize tracing
    tracing_subscriber::fmt::init();

    println!("📊 OPUS-GPU Dashboard Export Example");

    // Create dashboard configuration
    let config = DashboardConfig {
        enabled: true,
        grafana_url: Some("http://localhost:3000".to_string()),
        auto_import_dashboards: true,
        refresh_interval: std::time::Duration::from_secs(30),
    };

    // Create dashboard manager
    let dashboard_manager = DashboardManager::new(config);

    println!("📋 Available dashboard templates:");
    for template in dashboard_manager.list_templates() {
        println!("   - {} ({}): {}", template.name, template.id, template.description);
        println!("     Type: {:?}", template.dashboard_type);
        println!("     Required metrics: {}", template.required_metrics.len());
        println!();
    }

    // Export dashboards to directory
    let output_dir = "./dashboards";
    println!("📁 Exporting dashboards to: {}", output_dir);

    let deployment = DashboardDeployment::new(dashboard_manager);
    let exported_files = deployment.export_all_to_directory(output_dir).await?;

    println!("✅ Exported {} dashboard files:", exported_files.len());
    for file in &exported_files {
        println!("   - {}", file);
    }

    // Check if output directory exists
    if Path::new(output_dir).exists() {
        println!("📂 Dashboard files created in: {}", Path::new(output_dir).canonicalize()?.display());

        println!("\n📖 Usage instructions:");
        println!("1. Copy the JSON files to your Grafana dashboards directory");
        println!("2. Use the provisioning.yml file for automated deployment");
        println!("3. Import dashboards manually through Grafana UI");

        println!("\n🔗 Dashboard URLs (when deployed to Grafana):");
        println!("   - GPU Overview: /d/opus_gpu_overview");
        println!("   - System Overview: /d/opus_system_overview");
        println!("   - Mining Performance: /d/opus_mining_performance");
        println!("   - Pool Statistics: /d/opus_pool_statistics");
        println!("   - Alerts & Health: /d/opus_alerts_health");
    }

    println!("✅ Dashboard export example completed!");

    Ok(())
}