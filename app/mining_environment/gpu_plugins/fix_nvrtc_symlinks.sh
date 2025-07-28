#!/bin/bash
# fix_nvrtc_symlinks.sh - Script tự động sửa NVRTC symbolic links
# Tích hợp vào GPU plugins system cho automatic runtime fix
# Sử dụng: ./fix_nvrtc_symlinks.sh [--check-only] [--verbose] [--silent]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
CHECK_ONLY=false
VERBOSE=false
SILENT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --check-only)
            CHECK_ONLY=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --silent)
            SILENT=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--check-only] [--verbose] [--silent]"
            echo "  --check-only    Only check links, don't create them"
            echo "  --verbose       Show detailed output"
            echo "  --silent        Suppress all output except errors"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log() {
    if [[ "$VERBOSE" == "true" && "$SILENT" == "false" ]]; then
        echo -e "${BLUE}[NVRTC-FIX]${NC} $1"
    fi
}

success() {
    if [[ "$SILENT" == "false" ]]; then
        echo -e "${GREEN}[NVRTC-FIX]${NC} $1"
    fi
}

warning() {
    if [[ "$SILENT" == "false" ]]; then
        echo -e "${YELLOW}[NVRTC-FIX]${NC} $1"
    fi
}

error() {
    echo -e "${RED}[NVRTC-FIX ERROR]${NC} $1" >&2
}

check_nvrtc_libraries() {
    # Tìm đường dẫn thực tế của NVRTC library
    local actual_target="/usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140"
    local fallback_target="/usr/local/cuda/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140"
    local target_lib=""
    
    # Xác định đường dẫn chính xác
    if [[ -f "$actual_target" ]]; then
        target_lib="$actual_target"
    elif [[ -f "$fallback_target" ]]; then
        target_lib="$fallback_target"
    else
        error "NVRTC library not found in expected locations"
        error "  Checked: $actual_target"
        error "  Checked: $fallback_target"
        return 1
    fi
    
    local base_path="/usr/local/cuda/lib64"
    local required_link="$base_path/libnvrtc-builtins.so.12.0"
    local system_link="/usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0"
    
    log "Checking NVRTC libraries..."
    log "Using target library: $target_lib"
    
    success "Found target library: $target_lib"
    
    # Check required symbolic link
    if [[ -L "$required_link" ]]; then
        local link_target=$(readlink "$required_link")
        if [[ "$link_target" == "$target_lib" ]]; then
            success "Required symbolic link exists and is correct: $required_link"
        else
            warning "Required symbolic link exists but points to wrong target: $required_link -> $link_target"
            warning "Expected target: $target_lib"
            return 2
        fi
    elif [[ -f "$required_link" ]]; then
        warning "Required file exists but is not a symbolic link: $required_link"
        return 2
    else
        warning "Required symbolic link missing: $required_link"
        return 2
    fi
    
    # Check system-wide symbolic link
    if [[ -L "$system_link" ]]; then
        local system_target=$(readlink "$system_link")
        if [[ "$system_target" == "$target_lib" ]]; then
            success "System-wide symbolic link exists and is correct: $system_link"
        else
            warning "System-wide symbolic link exists but points to wrong target: $system_link -> $system_target"
            return 3
        fi
    else
        warning "System-wide symbolic link missing: $system_link"
        return 3
    fi
    
    return 0
}

create_nvrtc_symlinks() {
    # Tìm đường dẫn thực tế của NVRTC library (giống check_nvrtc_libraries)
    local actual_target="/usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140"
    local fallback_target="/usr/local/cuda/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0.140"
    local target_lib=""
    
    # Xác định đường dẫn chính xác
    if [[ -f "$actual_target" ]]; then
        target_lib="$actual_target"
    elif [[ -f "$fallback_target" ]]; then
        target_lib="$fallback_target"
    else
        error "NVRTC library not found in expected locations during fix"
        return 1
    fi
    
    local base_path="/usr/local/cuda/lib64"
    local required_link="$base_path/libnvrtc-builtins.so.12.0"
    local system_link="/usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.0"
    
    log "Creating NVRTC symbolic links..."
    log "Source library: $target_lib"
    
    # Tạo thư mục CUDA lib64 nếu chưa có
    mkdir -p "$base_path"
    
    # Create CUDA lib64 symbolic link trỏ đến file thực tế
    if [[ ! -L "$required_link" ]] || [[ "$(readlink "$required_link")" != "$target_lib" ]]; then
        log "Creating CUDA lib64 symbolic link..."
        ln -sf "$target_lib" "$required_link"
        success "Created: $required_link -> $target_lib"
    fi
    
    # Create system-wide symbolic link
    if [[ ! -L "$system_link" ]] || [[ "$(readlink "$system_link")" != "$target_lib" ]]; then
        log "Creating system-wide symbolic link..."
        mkdir -p /usr/lib/x86_64-linux-gnu
        ln -sf "$target_lib" "$system_link"
        success "Created: $system_link -> $target_lib"
    fi
    
    # Update ldconfig cache
    log "Updating ldconfig cache..."
    ldconfig 2>/dev/null || {
        warning "ldconfig update failed, but symbolic links were created"
    }
    success "NVRTC symbolic link fix completed"
}

verify_fix() {
    log "Verifying fix..."
    
    # Check with ldconfig
    if ldconfig -p | grep -q "libnvrtc-builtins.so.12.0"; then
        success "libnvrtc-builtins.so.12.0 found in ldconfig cache"
    else
        error "libnvrtc-builtins.so.12.0 NOT found in ldconfig cache"
        return 1
    fi
    
    # Show ldconfig output for nvrtc libraries
    echo
    echo "NVRTC libraries in ldconfig cache:"
    ldconfig -p | grep nvrtc || echo "  (none found)"
    
    # Show symbolic links
    echo
    echo "NVRTC symbolic links:"
    ls -la /usr/local/cuda/lib64/libnvrtc-builtins.so.12.* 2>/dev/null || echo "  (none found in CUDA lib64)"
    ls -la /usr/lib/x86_64-linux-gnu/libnvrtc-builtins.so.12.* 2>/dev/null || echo "  (none found in system lib)"
    
    return 0
}

main() {
    if [[ "$SILENT" == "false" ]]; then
        echo "🔧 NVRTC Symbolic Link Auto-Fix"
    fi
    
    # Check current state
    check_result=0
    check_nvrtc_libraries || check_result=$?
    
    case $check_result in
        0)
            success "All NVRTC symbolic links are correct!"
            if [[ "$CHECK_ONLY" == "false" ]]; then
                verify_fix
            fi
            exit 0
            ;;
        1)
            error "Target library missing. Cannot proceed."
            exit 1
            ;;
        2|3)
            if [[ "$CHECK_ONLY" == "true" ]]; then
                warning "Issues found. Re-run without --check-only to fix."
                exit $check_result
            else
                warning "Issues found. Attempting to fix..."
                create_nvrtc_symlinks
                
                # Verify fix
                if verify_fix; then
                    success "Fix completed successfully!"
                    exit 0
                else
                    error "Fix verification failed!"
                    exit 1
                fi
            fi
            ;;
    esac
}

# Run main function
main "$@"