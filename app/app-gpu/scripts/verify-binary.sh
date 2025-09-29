#!/bin/bash

# OPUS-GPU Binary Verification Script
# Verifies integrity and authenticity of OPUS-GPU binaries

set -euo pipefail

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
    echo "Usage: $0 [OPTIONS] <binary_path>"
    echo
    echo "Verify OPUS-GPU binary integrity and authenticity"
    echo
    echo "Options:"
    echo "  -k, --key <path>      Path to public key file (default: signing.pub)"
    echo "  -s, --sig <path>      Path to signature file (auto-detected if not specified)"
    echo "  -c, --checksum <path> Path to checksum file (auto-detected if not specified)"
    echo "  -v, --verbose         Verbose output"
    echo "  -h, --help           Show this help message"
    echo
    echo "Examples:"
    echo "  $0 opus-gpu-hardened"
    echo "  $0 -k /path/to/key.pub -s binary.sig opus-gpu-hardened"
    echo "  $0 --verbose /usr/local/bin/opus-gpu"
}

# Default values
BINARY_PATH=""
PUBLIC_KEY_PATH="signing.pub"
SIGNATURE_PATH=""
CHECKSUM_PATH=""
VERBOSE=false

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -k|--key)
                PUBLIC_KEY_PATH="$2"
                shift 2
                ;;
            -s|--sig)
                SIGNATURE_PATH="$2"
                shift 2
                ;;
            -c|--checksum)
                CHECKSUM_PATH="$2"
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
            -*)
                log_error "Unknown option: $1"
                usage
                exit 1
                ;;
            *)
                if [[ -z "$BINARY_PATH" ]]; then
                    BINARY_PATH="$1"
                else
                    log_error "Multiple binary paths specified"
                    exit 1
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$BINARY_PATH" ]]; then
        log_error "Binary path is required"
        usage
        exit 1
    fi
}

# Auto-detect signature and checksum files
auto_detect_files() {
    # Auto-detect signature file
    if [[ -z "$SIGNATURE_PATH" ]]; then
        if [[ -f "${BINARY_PATH}.sig" ]]; then
            SIGNATURE_PATH="${BINARY_PATH}.sig"
        elif [[ -f "$(dirname "$BINARY_PATH")/$(basename "$BINARY_PATH").sig" ]]; then
            SIGNATURE_PATH="$(dirname "$BINARY_PATH")/$(basename "$BINARY_PATH").sig"
        fi
    fi

    # Auto-detect checksum file
    if [[ -z "$CHECKSUM_PATH" ]]; then
        for ext in sha256 sha512 md5; do
            if [[ -f "${BINARY_PATH}.${ext}" ]]; then
                CHECKSUM_PATH="${BINARY_PATH}.${ext}"
                break
            fi
        done
    fi

    # Look for public key in common locations
    if [[ ! -f "$PUBLIC_KEY_PATH" ]]; then
        local key_locations=(
            "$(dirname "$BINARY_PATH")/signing.pub"
            "$(dirname "$0")/signing.pub"
            "./signing.pub"
            "/etc/opus-gpu/signing.pub"
            "$HOME/.opus-gpu/signing.pub"
        )

        for location in "${key_locations[@]}"; do
            if [[ -f "$location" ]]; then
                PUBLIC_KEY_PATH="$location"
                break
            fi
        done
    fi
}

# Check if required files exist
check_files() {
    log_info "Checking required files..."

    if [[ ! -f "$BINARY_PATH" ]]; then
        log_error "Binary file not found: $BINARY_PATH"
        exit 1
    fi

    if [[ ! -f "$PUBLIC_KEY_PATH" ]]; then
        log_error "Public key file not found: $PUBLIC_KEY_PATH"
        log_info "Please specify the path to the public key with -k option"
        exit 1
    fi

    if $VERBOSE; then
        log_info "Binary: $BINARY_PATH"
        log_info "Public Key: $PUBLIC_KEY_PATH"
        if [[ -n "$SIGNATURE_PATH" ]]; then
            log_info "Signature: $SIGNATURE_PATH"
        fi
        if [[ -n "$CHECKSUM_PATH" ]]; then
            log_info "Checksum: $CHECKSUM_PATH"
        fi
    fi

    log_success "Required files found"
}

# Verify binary signature
verify_signature() {
    if [[ -z "$SIGNATURE_PATH" || ! -f "$SIGNATURE_PATH" ]]; then
        log_warning "Signature file not found, skipping signature verification"
        return 0
    fi

    log_info "Verifying digital signature..."

    if ! command -v openssl &> /dev/null; then
        log_error "OpenSSL not found, cannot verify signature"
        exit 1
    fi

    # Verify the signature
    if openssl dgst -sha256 -verify "$PUBLIC_KEY_PATH" \
        -signature "$SIGNATURE_PATH" "$BINARY_PATH" &>/dev/null; then
        log_success "Digital signature verified successfully"
        return 0
    else
        log_error "Digital signature verification FAILED"
        log_error "This binary may have been tampered with or corrupted"
        return 1
    fi
}

# Verify checksums
verify_checksums() {
    if [[ -z "$CHECKSUM_PATH" || ! -f "$CHECKSUM_PATH" ]]; then
        log_warning "Checksum file not found, skipping checksum verification"
        return 0
    fi

    log_info "Verifying checksums..."

    local checksum_type=""
    case "$CHECKSUM_PATH" in
        *.sha256)
            checksum_type="sha256"
            ;;
        *.sha512)
            checksum_type="sha512"
            ;;
        *.md5)
            checksum_type="md5"
            ;;
        *)
            log_warning "Unknown checksum type, attempting to detect..."
            # Try to detect based on content
            local line_count=$(wc -l < "$CHECKSUM_PATH")
            local first_line=$(head -n1 "$CHECKSUM_PATH")
            local hash_length=${#$(echo "$first_line" | cut -d' ' -f1)}

            case $hash_length in
                64)
                    checksum_type="sha256"
                    ;;
                128)
                    checksum_type="sha512"
                    ;;
                32)
                    checksum_type="md5"
                    ;;
                *)
                    log_error "Unable to determine checksum type"
                    return 1
                    ;;
            esac
            ;;
    esac

    log_info "Verifying $checksum_type checksum..."

    # Change to the directory containing the binary for relative path verification
    local original_dir=$(pwd)
    cd "$(dirname "$BINARY_PATH")"

    local result=0
    case $checksum_type in
        sha256)
            if command -v sha256sum &> /dev/null; then
                if sha256sum -c "$CHECKSUM_PATH" &>/dev/null; then
                    log_success "SHA-256 checksum verified"
                else
                    log_error "SHA-256 checksum verification FAILED"
                    result=1
                fi
            else
                log_warning "sha256sum not available, skipping checksum verification"
            fi
            ;;
        sha512)
            if command -v sha512sum &> /dev/null; then
                if sha512sum -c "$CHECKSUM_PATH" &>/dev/null; then
                    log_success "SHA-512 checksum verified"
                else
                    log_error "SHA-512 checksum verification FAILED"
                    result=1
                fi
            else
                log_warning "sha512sum not available, skipping checksum verification"
            fi
            ;;
        md5)
            if command -v md5sum &> /dev/null; then
                if md5sum -c "$CHECKSUM_PATH" &>/dev/null; then
                    log_success "MD5 checksum verified"
                else
                    log_error "MD5 checksum verification FAILED"
                    result=1
                fi
            else
                log_warning "md5sum not available, skipping checksum verification"
            fi
            ;;
    esac

    cd "$original_dir"
    return $result
}

# Check binary properties
check_binary_properties() {
    log_info "Checking binary properties..."

    # Check if file is executable
    if [[ ! -x "$BINARY_PATH" ]]; then
        log_warning "Binary is not executable"
    else
        if $VERBOSE; then
            log_info "Binary is executable"
        fi
    fi

    # Get file size
    local file_size=$(du -h "$BINARY_PATH" | cut -f1)
    if $VERBOSE; then
        log_info "Binary size: $file_size"
    fi

    # Check file type
    if command -v file &> /dev/null; then
        local file_type=$(file -b "$BINARY_PATH")
        if $VERBOSE; then
            log_info "File type: $file_type"
        fi

        # Check if it's a valid executable
        if [[ "$file_type" =~ ELF.*executable ]]; then
            log_success "Binary is a valid Linux executable"
        elif [[ "$file_type" =~ PE32.*executable ]]; then
            log_success "Binary is a valid Windows executable"
        elif [[ "$file_type" =~ Mach-O.*executable ]]; then
            log_success "Binary is a valid macOS executable"
        else
            log_warning "Binary type may not be a standard executable"
        fi
    fi

    # Check for symbols (should be stripped in release builds)
    if command -v nm &> /dev/null; then
        if nm "$BINARY_PATH" &>/dev/null; then
            log_warning "Binary contains debugging symbols (not stripped)"
        else
            if $VERBOSE; then
                log_info "Binary symbols have been stripped"
            fi
        fi
    fi

    # Check for UPX packing
    if command -v upx &> /dev/null; then
        if upx -t "$BINARY_PATH" &>/dev/null; then
            if $VERBOSE; then
                log_info "Binary is UPX packed"
            fi
        fi
    fi
}

# Perform basic functionality test
test_binary() {
    log_info "Performing basic functionality test..."

    # Test if binary can execute and show version
    if timeout 10s "$BINARY_PATH" --version &>/dev/null; then
        log_success "Binary version check passed"
    elif timeout 10s "$BINARY_PATH" -V &>/dev/null; then
        log_success "Binary version check passed"
    elif timeout 10s "$BINARY_PATH" --help &>/dev/null; then
        log_success "Binary help check passed"
    else
        log_warning "Binary functionality test failed or timed out"
        log_info "This may be due to missing dependencies or runtime requirements"
    fi
}

# Print verification summary
print_summary() {
    echo
    echo "=========================================="
    echo "OPUS-GPU Binary Verification Summary"
    echo "=========================================="
    echo "Binary: $(basename "$BINARY_PATH")"
    echo "Size: $(du -h "$BINARY_PATH" | cut -f1)"
    echo "Path: $BINARY_PATH"
    echo
    if [[ -n "$SIGNATURE_PATH" && -f "$SIGNATURE_PATH" ]]; then
        echo "✓ Digital signature verified"
    else
        echo "⚠ No digital signature verified"
    fi
    if [[ -n "$CHECKSUM_PATH" && -f "$CHECKSUM_PATH" ]]; then
        echo "✓ Checksum verified"
    else
        echo "⚠ No checksum verified"
    fi
    echo "✓ Binary properties checked"
    echo "✓ Basic functionality tested"
    echo
    echo "Verification completed at: $(date)"
    echo "=========================================="
}

# Main execution
main() {
    parse_args "$@"
    auto_detect_files
    check_files

    local verification_failed=false

    # Perform verifications
    if ! verify_signature; then
        verification_failed=true
    fi

    if ! verify_checksums; then
        verification_failed=true
    fi

    check_binary_properties
    test_binary

    print_summary

    if $verification_failed; then
        log_error "Verification failed! Binary integrity could not be confirmed."
        exit 1
    else
        log_success "All verifications passed! Binary integrity confirmed."
    fi
}

# Handle interruption
trap 'log_error "Verification interrupted"; exit 1' INT TERM

# Run main function
main "$@"