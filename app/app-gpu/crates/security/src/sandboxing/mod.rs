//! # Sandboxing (Hộp Cát Bảo Mật)
//!
//! Cô lập process thông qua seccomp và namespaces.

// Re-export namespace isolation types
pub use namespace_isolation::{NamespaceIsolation, NamespaceCapabilities};

pub mod namespace_isolation;
pub mod seccomp_profiles;

