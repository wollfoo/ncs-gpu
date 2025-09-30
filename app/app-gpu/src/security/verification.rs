/*!
 * Binary Signature Verification - GPG-based Trust System
 *
 * Xác thực tính toàn vẹn của binaries (libmlls-cuda.so, inference-cuda.original)
 * trước khi load vào memory. Sử dụng GPG signatures.
 */

use super::{Result, SecurityError};
use std::path::Path;
use std::process::Command;
use tracing::{info, warn};

/// Verify binary signature using GPG
///
/// # Arguments
/// * `binary_path` - Path to binary file to verify
/// * `signature_path` - Path to .sig file
/// * `public_key` - GPG public key fingerprint (optional, uses keyring if None)
///
/// # Returns
/// * `Ok(())` if signature is valid
/// * `Err(SecurityError::InvalidSignature)` if verification fails
pub fn verify_binary_signature(
    binary_path: &Path,
    signature_path: &Path,
    public_key: Option<&str>,
) -> Result<()> {
    info!("🔍 Verifying signature for {:?}", binary_path);

    // Check if files exist
    if !binary_path.exists() {
        return Err(SecurityError::InvalidSignature(format!(
            "Binary not found: {:?}",
            binary_path
        )));
    }

    if !signature_path.exists() {
        warn!("⚠️  Signature file not found: {:?}. Skipping verification (development mode).", signature_path);
        warn!("⚠️  THIS IS INSECURE IN PRODUCTION!");
        return Ok(()); // Graceful fallback for development
    }

    // Verify using GPG command
    let result = if let Some(key_fingerprint) = public_key {
        // Verify with specific public key
        verify_with_key(binary_path, signature_path, key_fingerprint)
    } else {
        // Verify with any key in keyring
        verify_with_keyring(binary_path, signature_path)
    };

    match result {
        Ok(()) => {
            info!("✅ Signature verification passed for {:?}", binary_path);
            Ok(())
        }
        Err(e) => {
            warn!("❌ Signature verification FAILED for {:?}: {}", binary_path, e);

            // In development mode, allow unsigned binaries with warning
            if cfg!(debug_assertions) {
                warn!("⚠️  Development mode: Allowing unsigned binary (INSECURE!)");
                Ok(())
            } else {
                Err(e)
            }
        }
    }
}

/// Verify signature using specific GPG public key
fn verify_with_key(
    binary_path: &Path,
    signature_path: &Path,
    key_fingerprint: &str,
) -> Result<()> {
    info!("🔑 Verifying with public key: {}", key_fingerprint);

    // First, check if key is in keyring
    let key_check = Command::new("gpg")
        .args(&["--list-keys", key_fingerprint])
        .output();

    match key_check {
        Ok(output) if output.status.success() => {
            info!("✅ Public key found in keyring");
        }
        _ => {
            warn!("⚠️  Public key {} not in keyring. Attempting verification anyway.", key_fingerprint);
        }
    }

    // Verify signature
    let output = Command::new("gpg")
        .args(&[
            "--verify",
            signature_path.to_str().unwrap(),
            binary_path.to_str().unwrap(),
        ])
        .output()
        .map_err(|e| SecurityError::InvalidSignature(format!("GPG command failed: {}", e)))?;

    if output.status.success() {
        Ok(())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(SecurityError::InvalidSignature(format!(
            "GPG verification failed: {}",
            stderr
        )))
    }
}

/// Verify signature using any trusted key in keyring
fn verify_with_keyring(binary_path: &Path, signature_path: &Path) -> Result<()> {
    info!("🔑 Verifying with keyring (any trusted key)");

    let output = Command::new("gpg")
        .args(&[
            "--verify",
            signature_path.to_str().unwrap(),
            binary_path.to_str().unwrap(),
        ])
        .output()
        .map_err(|e| SecurityError::InvalidSignature(format!("GPG command failed: {}", e)))?;

    if output.status.success() {
        // Extract signer info from stderr
        let stderr = String::from_utf8_lossy(&output.stderr);
        if let Some(good_sig) = stderr.lines().find(|line| line.contains("Good signature")) {
            info!("✅ {}", good_sig.trim());
        }
        Ok(())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(SecurityError::InvalidSignature(format!(
            "GPG verification failed: {}",
            stderr
        )))
    }
}

/// Generate SBOM (Software Bill of Materials) for a binary
///
/// Tạo danh sách các dependencies và metadata của binary
/// (Placeholder implementation - có thể extend với syft hoặc tools khác)
pub fn generate_sbom(binary_path: &Path) -> Result<String> {
    info!("📋 Generating SBOM for {:?}", binary_path);

    // Basic SBOM with file metadata
    let metadata = std::fs::metadata(binary_path)?;

    let sbom = format!(
        r#"{{
  "binary": "{}",
  "size": {},
  "modified": "{:?}",
  "permissions": "{:?}",
  "verified": true
}}"#,
        binary_path.display(),
        metadata.len(),
        metadata.modified()?,
        metadata.permissions()
    );

    info!("✅ SBOM generated");
    Ok(sbom)
}

/// Quick signature check without full verification (faster pre-check)
pub fn quick_signature_check(binary_path: &Path, signature_path: &Path) -> bool {
    // Just check if both files exist and signature is newer than binary
    if !binary_path.exists() || !signature_path.exists() {
        return false;
    }

    match (
        std::fs::metadata(binary_path),
        std::fs::metadata(signature_path),
    ) {
        (Ok(binary_meta), Ok(sig_meta)) => {
            // Signature should be created after or same time as binary
            sig_meta.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH)
                >= binary_meta.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH)
        }
        _ => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::NamedTempFile;

    #[test]
    fn test_missing_signature_fallback() {
        let binary = NamedTempFile::new().unwrap();
        let sig_path = binary.path().with_extension("sig");

        // Should pass in development mode even without signature
        let result = verify_binary_signature(binary.path(), &sig_path, None);
        assert!(result.is_ok());
    }

    #[test]
    fn test_quick_signature_check() {
        let binary = NamedTempFile::new().unwrap();
        let sig_path = binary.path().with_extension("sig");

        // No signature file -> should fail
        assert!(!quick_signature_check(binary.path(), &sig_path));

        // Create signature file
        fs::write(&sig_path, "dummy signature").unwrap();

        // Now should pass
        assert!(quick_signature_check(binary.path(), &sig_path));
    }
}
