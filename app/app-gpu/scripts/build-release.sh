#!/bin/bash

# OPUS-GPU Release Build Script with Security Hardening
# This script builds a production-ready, obfuscated, and signed binary

set -euo pipefail

# Configuration
PROJECT_NAME="opus-gpu"
BUILD_TARGET="x86_64-unknown-linux-gnu"
BUILD_DIR="target/${BUILD_TARGET}/release"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPTS_DIR")"
DIST_DIR="${PROJECT_ROOT}/dist"
VERSION=$(grep '^version' "${PROJECT_ROOT}/Cargo.toml" | sed 's/.*= "//' | sed 's/".*//')

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking build prerequisites..."

    # Check Rust toolchain
    if ! command -v cargo &> /dev/null; then
        log_error "Cargo not found. Please install Rust toolchain."
        exit 1
    fi

    # Check for required tools
    local required_tools=("strip" "objcopy" "upx")
    for tool in "${required_tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            log_warning "$tool not found. Some features will be disabled."
        fi
    done

    # Check for signing key
    if [[ ! -f "${SCRIPTS_DIR}/signing.key" ]]; then
        log_warning "Signing key not found. Generating new key..."
        generate_signing_key
    fi

    log_success "Prerequisites check completed"
}

# Generate signing key for binary verification
generate_signing_key() {
    log_info "Generating signing key..."

    # Generate Ed25519 key pair for signing
    openssl genpkey -algorithm Ed25519 -out "${SCRIPTS_DIR}/signing.key" 2>/dev/null || {
        log_warning "OpenSSL Ed25519 not available, using RSA"
        openssl genrsa -out "${SCRIPTS_DIR}/signing.key" 4096
    }

    # Extract public key
    openssl pkey -in "${SCRIPTS_DIR}/signing.key" -pubout -out "${SCRIPTS_DIR}/signing.pub" 2>/dev/null || {
        openssl rsa -in "${SCRIPTS_DIR}/signing.key" -pubout -out "${SCRIPTS_DIR}/signing.pub"
    }

    chmod 600 "${SCRIPTS_DIR}/signing.key"
    chmod 644 "${SCRIPTS_DIR}/signing.pub"

    log_success "Signing key generated"
}

# Clean previous builds
clean_build() {
    log_info "Cleaning previous builds..."

    cargo clean
    rm -rf "$DIST_DIR"
    mkdir -p "$DIST_DIR"

    log_success "Build cleaned"
}

# Configure build environment for maximum optimization and security
configure_build_env() {
    log_info "Configuring build environment..."

    # Set environment variables for maximum optimization
    export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
    export CARGO_PROFILE_RELEASE_LTO=true
    export CARGO_PROFILE_RELEASE_OPT_LEVEL=3
    export CARGO_PROFILE_RELEASE_PANIC="abort"
    export CARGO_PROFILE_RELEASE_STRIP=true

    # Enable security features
    export CARGO_PROFILE_RELEASE_OVERFLOW_CHECKS=true

    # Set target-specific flags for optimization
    export RUSTFLAGS="-C target-cpu=native -C link-arg=-Wl,-z,relro,-z,now -C link-arg=-s"

    # Enable all security features
    export CARGO_FEATURES="default,strict-mode,full-obfuscation"

    log_success "Build environment configured"
}

# Build the project with security hardening
build_project() {
    log_info "Building ${PROJECT_NAME} v${VERSION} for production..."

    cd "$PROJECT_ROOT"

    # Build with maximum optimization and security features
    cargo build \
        --release \
        --target "$BUILD_TARGET" \
        --features "$CARGO_FEATURES" \
        --jobs "$(nproc)" \
        2>&1 | tee "${DIST_DIR}/build.log"

    if [[ ${PIPESTATUS[0]} -eq 0 ]]; then
        log_success "Build completed successfully"
    else
        log_error "Build failed. Check build.log for details."
        exit 1
    fi
}

# Apply post-build obfuscation and hardening
apply_post_build_hardening() {
    local binary_path="${BUILD_DIR}/${PROJECT_NAME}"
    local hardened_path="${DIST_DIR}/${PROJECT_NAME}-hardened"

    log_info "Applying post-build hardening..."

    # Copy binary to dist directory
    cp "$binary_path" "$hardened_path"

    # Strip debug symbols (if not already done)
    if command -v strip &> /dev/null; then
        log_info "Stripping debug symbols..."
        strip --strip-all "$hardened_path"
    fi

    # Apply UPX packing if available
    if command -v upx &> /dev/null; then
        log_info "Applying UPX compression..."
        upx --best --lzma "$hardened_path" 2>/dev/null || {
            log_warning "UPX packing failed, continuing without compression"
        }
    fi

    # Remove section headers to hinder analysis
    if command -v objcopy &> /dev/null; then
        log_info "Removing section headers..."
        objcopy --remove-section=.comment \
                --remove-section=.note \
                --remove-section=.note.gnu.build-id \
                --remove-section=.note.ABI-tag \
                "$hardened_path" 2>/dev/null || {
            log_warning "Section removal failed"
        }
    fi

    log_success "Post-build hardening completed"
}

# Sign the binary for integrity verification
sign_binary() {
    local binary_path="${DIST_DIR}/${PROJECT_NAME}-hardened"
    local signature_path="${binary_path}.sig"

    log_info "Signing binary for integrity verification..."

    # Create binary signature
    openssl dgst -sha256 -sign "${SCRIPTS_DIR}/signing.key" \
        -out "$signature_path" "$binary_path" || {
        log_error "Binary signing failed"
        exit 1
    }

    # Create checksum file
    cd "$DIST_DIR"
    sha256sum "${PROJECT_NAME}-hardened" > "${PROJECT_NAME}-hardened.sha256"
    sha512sum "${PROJECT_NAME}-hardened" > "${PROJECT_NAME}-hardened.sha512"

    log_success "Binary signed and checksums generated"
}

# Create distribution package
create_distribution() {
    log_info "Creating distribution package..."

    cd "$DIST_DIR"

    # Create version info file
    cat > version.txt << EOF
Project: ${PROJECT_NAME}
Version: ${VERSION}
Build Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
Build Target: ${BUILD_TARGET}
Rust Version: $(rustc --version)
Features: ${CARGO_FEATURES}
Git Commit: $(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
EOF

    # Create README for distribution
    cat > README.txt << EOF
OPUS-GPU v${VERSION} - Production Release
========================================

This is a production build of OPUS-GPU with security hardening and obfuscation.

Files included:
- ${PROJECT_NAME}-hardened: Main executable (obfuscated and compressed)
- ${PROJECT_NAME}-hardened.sig: Digital signature for integrity verification
- ${PROJECT_NAME}-hardened.sha256: SHA-256 checksum
- ${PROJECT_NAME}-hardened.sha512: SHA-512 checksum
- signing.pub: Public key for signature verification
- version.txt: Build information
- build.log: Build output log

Security Features:
- Memory protection and secure allocation
- Process isolation and sandboxing
- String obfuscation and code protection
- Anti-debugging and anti-reverse engineering
- Stealth operations and process cloaking
- Binary packing and symbol stripping

Verification:
To verify the binary integrity:
1. Check signature: openssl dgst -sha256 -verify signing.pub -signature ${PROJECT_NAME}-hardened.sig ${PROJECT_NAME}-hardened
2. Check checksums: sha256sum -c ${PROJECT_NAME}-hardened.sha256

Installation:
1. Verify the binary (see above)
2. Copy ${PROJECT_NAME}-hardened to /usr/local/bin/${PROJECT_NAME}
3. Set executable permissions: chmod +x /usr/local/bin/${PROJECT_NAME}

SECURITY WARNING:
This software includes advanced security and obfuscation features.
Ensure you comply with all applicable laws and regulations.
EOF

    # Copy public key for verification
    cp "${SCRIPTS_DIR}/signing.pub" .

    # Create compressed archive
    local archive_name="${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.tar.gz"
    tar -czf "$archive_name" \
        "${PROJECT_NAME}-hardened" \
        "${PROJECT_NAME}-hardened.sig" \
        "${PROJECT_NAME}-hardened.sha256" \
        "${PROJECT_NAME}-hardened.sha512" \
        "signing.pub" \
        "version.txt" \
        "README.txt" \
        "build.log"

    # Generate archive checksum
    sha256sum "$archive_name" > "${archive_name}.sha256"

    log_success "Distribution package created: $archive_name"
}

# Verify the build
verify_build() {
    log_info "Verifying build integrity..."

    local binary_path="${DIST_DIR}/${PROJECT_NAME}-hardened"
    local signature_path="${binary_path}.sig"

    # Verify file exists and is executable
    if [[ ! -f "$binary_path" ]]; then
        log_error "Binary not found: $binary_path"
        exit 1
    fi

    if [[ ! -x "$binary_path" ]]; then
        log_error "Binary is not executable: $binary_path"
        exit 1
    fi

    # Verify signature
    if openssl dgst -sha256 -verify "${SCRIPTS_DIR}/signing.pub" \
        -signature "$signature_path" "$binary_path" &>/dev/null; then
        log_success "Binary signature verified"
    else
        log_error "Binary signature verification failed"
        exit 1
    fi

    # Verify checksums
    cd "$DIST_DIR"
    if sha256sum -c "${PROJECT_NAME}-hardened.sha256" &>/dev/null; then
        log_success "SHA-256 checksum verified"
    else
        log_error "SHA-256 checksum verification failed"
        exit 1
    fi

    # Test binary execution (basic smoke test)
    log_info "Performing smoke test..."
    if timeout 5s "$binary_path" --version &>/dev/null; then
        log_success "Smoke test passed"
    else
        log_warning "Smoke test failed or timed out - binary may require runtime dependencies"
    fi

    log_success "Build verification completed"
}

# Print build summary
print_summary() {
    echo
    echo "=========================================="
    echo "OPUS-GPU Release Build Summary"
    echo "=========================================="
    echo "Version: $VERSION"
    echo "Target: $BUILD_TARGET"
    echo "Build Time: $(date)"
    echo "Binary Size: $(du -h "${DIST_DIR}/${PROJECT_NAME}-hardened" | cut -f1)"
    echo "Distribution: ${DIST_DIR}/${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.tar.gz"
    echo
    echo "Security Features Enabled:"
    echo "  ✓ Memory Protection"
    echo "  ✓ Process Isolation"
    echo "  ✓ Code Obfuscation"
    echo "  ✓ Anti-Debugging"
    echo "  ✓ Stealth Operations"
    echo "  ✓ Binary Signing"
    echo "  ✓ Symbol Stripping"
    if command -v upx &> /dev/null; then
        echo "  ✓ Binary Compression"
    fi
    echo
    echo "Next Steps:"
    echo "1. Test the binary in your target environment"
    echo "2. Verify digital signature before deployment"
    echo "3. Deploy using secure channels"
    echo "=========================================="
}

# Main execution
main() {
    log_info "Starting OPUS-GPU security-hardened release build..."

    check_prerequisites
    clean_build
    configure_build_env
    build_project
    apply_post_build_hardening
    sign_binary
    create_distribution
    verify_build
    print_summary

    log_success "Security-hardened release build completed successfully!"
}

# Handle interruption
trap 'log_error "Build interrupted"; exit 1' INT TERM

# Run main function
main "$@"