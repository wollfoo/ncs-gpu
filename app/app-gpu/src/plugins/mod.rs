//! Plugin system for extensibility
//!
//! Dynamic plugin loading using libloading:
//! - Stealth plugins
//! - Mining algorithm plugins
//! - Network protocol plugins
//!
//! # Plugin API
//! Plugins must export the following symbols:
//! - `plugin_init()` - Initialize plugin
//! - `plugin_shutdown()` - Cleanup plugin
//! - `plugin_version()` - Get plugin version

use crate::error::{MinerError, Result};
use libloading::{Library, Symbol};
use semver::Version;
use std::path::{Path, PathBuf};
use tracing::{debug, info, warn};

/// Plugin metadata
#[derive(Debug)]
pub struct PluginInfo {
    pub name: String,
    pub version: Version,
    pub path: PathBuf,
}

/// Plugin handle
pub struct Plugin {
    pub info: PluginInfo,
    _library: Library,
}

/// Plugin initialization function signature
pub type PluginInitFn = unsafe extern "C" fn() -> i32;

/// Plugin shutdown function signature
pub type PluginShutdownFn = unsafe extern "C" fn() -> i32;

/// Plugin version function signature
pub type PluginVersionFn = unsafe extern "C" fn() -> *const i8;

/// Load a plugin from a shared library file
///
/// # Arguments
/// * `path` - Path to the plugin shared library (.so/.dll/.dylib)
///
/// # Safety
/// This function loads and executes code from an external library.
/// Only load plugins from trusted sources.
pub fn load_plugin<P: AsRef<Path>>(path: P) -> Result<Plugin> {
    let path = path.as_ref();
    info!(?path, "Loading plugin");

    // Load the shared library
    let library = unsafe {
        Library::new(path).map_err(|e| {
            MinerError::Plugin(format!("Failed to load plugin {:?}: {}", path, e))
        })?
    };

    // Get plugin version
    let version = unsafe {
        let version_fn: Symbol<PluginVersionFn> = library
            .get(b"plugin_version")
            .map_err(|e| MinerError::Plugin(format!("plugin_version symbol not found: {}", e)))?;

        let version_cstr = std::ffi::CStr::from_ptr(version_fn());
        let version_str = version_cstr
            .to_str()
            .map_err(|e| MinerError::Plugin(format!("Invalid version string: {}", e)))?;

        Version::parse(version_str).map_err(|e| {
            MinerError::Plugin(format!("Failed to parse plugin version: {}", e))
        })?
    };

    // Initialize the plugin
    unsafe {
        let init_fn: Symbol<PluginInitFn> = library
            .get(b"plugin_init")
            .map_err(|e| MinerError::Plugin(format!("plugin_init symbol not found: {}", e)))?;

        let result = init_fn();
        if result != 0 {
            return Err(MinerError::Plugin(format!(
                "Plugin initialization failed with code {}",
                result
            )));
        }
    }

    let plugin_name = path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("unknown")
        .to_string();

    info!(name = %plugin_name, version = %version, "Plugin loaded successfully");

    Ok(Plugin {
        info: PluginInfo {
            name: plugin_name,
            version,
            path: path.to_path_buf(),
        },
        _library: library,
    })
}

/// Load all plugins from a directory
///
/// # Arguments
/// * `plugin_dir` - Directory containing plugin shared libraries
pub fn load_plugins_from_dir<P: AsRef<Path>>(plugin_dir: P) -> Result<Vec<Plugin>> {
    let plugin_dir = plugin_dir.as_ref();
    info!(?plugin_dir, "Loading plugins from directory");

    if !plugin_dir.exists() {
        warn!(?plugin_dir, "Plugin directory does not exist");
        return Ok(Vec::new());
    }

    let mut plugins = Vec::new();

    for entry in std::fs::read_dir(plugin_dir).map_err(|e| {
        MinerError::Plugin(format!("Failed to read plugin directory: {}", e))
    })? {
        let entry = entry.map_err(|e| MinerError::Plugin(format!("Directory entry error: {}", e)))?;
        let path = entry.path();

        // Only load shared libraries
        if is_shared_library(&path) {
            match load_plugin(&path) {
                Ok(plugin) => {
                    debug!(name = %plugin.info.name, "Plugin loaded");
                    plugins.push(plugin);
                }
                Err(e) => {
                    warn!(error = %e, ?path, "Failed to load plugin");
                }
            }
        }
    }

    info!(count = plugins.len(), "Plugins loaded from directory");
    Ok(plugins)
}

/// Check if a file is a shared library
fn is_shared_library(path: &Path) -> bool {
    if let Some(ext) = path.extension() {
        match ext.to_str() {
            Some("so") => true,  // Linux
            Some("dll") => true, // Windows
            Some("dylib") => true, // macOS
            _ => false,
        }
    } else {
        false
    }
}

impl Drop for Plugin {
    fn drop(&mut self) {
        // Call plugin shutdown function
        unsafe {
            if let Ok(shutdown_fn) = self._library.get::<Symbol<PluginShutdownFn>>(b"plugin_shutdown") {
                let result = shutdown_fn();
                if result != 0 {
                    warn!(
                        name = %self.info.name,
                        code = result,
                        "Plugin shutdown returned error code"
                    );
                }
            }
        }

        info!(name = %self.info.name, "Plugin unloaded");
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_shared_library() {
        assert!(is_shared_library(Path::new("plugin.so")));
        assert!(is_shared_library(Path::new("plugin.dll")));
        assert!(is_shared_library(Path::new("plugin.dylib")));
        assert!(!is_shared_library(Path::new("plugin.txt")));
    }

    #[test]
    fn test_load_nonexistent_directory() {
        let result = load_plugins_from_dir("/nonexistent/path");
        assert!(result.is_ok(), "Should handle missing directory gracefully");
    }
}
