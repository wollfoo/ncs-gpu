use anyhow::{Context, Result};
use clap::Parser;
use common::config::{legacy_json_to_executor_toml, legacy_json_to_scheduler_yaml};
use std::fs;
use std::path::PathBuf;

#[derive(Parser, Debug)]
#[command(author, version, about = "Legacy config converter for Opus GPU", long_about = None)]
struct Args {
    /// JSON legacy file path
    #[arg(short, long)]
    input: PathBuf,

    /// Output path for scheduler YAML (prints to stdout if omitted)
    #[arg(long = "scheduler-out")]
    scheduler_out: Option<PathBuf>,

    /// Output path for executor TOML (prints to stdout if omitted)
    #[arg(long = "executor-out")]
    executor_out: Option<PathBuf>,
}

fn main() -> Result<()> {
    let args = Args::parse();
    let content = fs::read_to_string(&args.input)
        .with_context(|| format!("failed to read legacy config from {:?}", args.input))?;

    let scheduler_yaml = legacy_json_to_scheduler_yaml(&content)?;
    let executor_toml = legacy_json_to_executor_toml(&content)?;

    match args.scheduler_out {
        Some(path) => {
            fs::write(&path, scheduler_yaml)
                .with_context(|| format!("failed to write scheduler YAML to {:?}", path))?;
        }
        None => {
            println!("--- scheduler.yaml ---\n{}", scheduler_yaml.trim_end());
        }
    }

    match args.executor_out {
        Some(path) => {
            fs::write(&path, executor_toml)
                .with_context(|| format!("failed to write executor TOML to {:?}", path))?;
        }
        None => {
            println!("--- executor.toml ---\n{}", executor_toml.trim_end());
        }
    }

    Ok(())
}
