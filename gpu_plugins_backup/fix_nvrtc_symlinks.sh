#!/bin/bash
# fix_nvrtc_symlinks.sh - Script tự động cấu hình NVRTC libraries và ldconfig
# Tích hợp vào GPU plugins system cho automatic runtime fix
# Phương pháp: ldconfig method thay vì symbolic links (an toàn và hiệu quả hơn)
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
    # Tìm thư mục chứa NVRTC libraries
    local actual_dir="/usr/local/cuda-12.0/targets/x86_64-linux/lib"
    local fallback_dir="/usr/local/cuda/targets/x86_64-linux/lib"
    local nvrtc_lib_dir=""
    
    # Xác định thư mục chứa libraries
    if [[ -d "$actual_dir" && -f "$actual_dir/libnvrtc-builtins.so.12.0.140" ]]; then
        nvrtc_lib_dir="$actual_dir"
    elif [[ -d "$fallback_dir" && -f "$fallback_dir/libnvrtc-builtins.so.12.0.140" ]]; then
        nvrtc_lib_dir="$fallback_dir"
    else
        error "NVRTC library directory not found in expected locations"
        error "  Checked: $actual_dir"
        error "  Checked: $fallback_dir"
        return 1
    fi
    
    log "Checking NVRTC libraries via ldconfig method..."
    log "Using library directory: $nvrtc_lib_dir"
    
    success "Found NVRTC library directory: $nvrtc_lib_dir"
    
    # Check if ldconfig configuration exists
    local ldconfig_file="/etc/ld.so.conf.d/cuda-nvrtc.conf"
    if [[ -f "$ldconfig_file" ]]; then
        local configured_path=$(cat "$ldconfig_file")
        if [[ "$configured_path" == "$nvrtc_lib_dir" ]]; then
            success "ldconfig configuration exists and is correct: $ldconfig_file"
        else
            warning "ldconfig configuration exists but points to wrong directory: $configured_path"
            warning "Expected directory: $nvrtc_lib_dir"
            return 2
        fi
    else
        warning "ldconfig configuration missing: $ldconfig_file"
        return 2
    fi
    
    # Check if libraries are in ldconfig cache
    if ldconfig -p | grep -q nvrtc-builtins; then
        success "NVRTC libraries found in ldconfig cache"
        local cache_entries=$(ldconfig -p | grep nvrtc-builtins | wc -l)
        log "Found $cache_entries NVRTC entries in ldconfig cache"
    else
        warning "NVRTC libraries not found in ldconfig cache"
        return 3
    fi
    
    # Verify actual library files exist
    if [[ -f "$nvrtc_lib_dir/libnvrtc-builtins.so.12.0.140" ]]; then
        success "NVRTC library file exists: $nvrtc_lib_dir/libnvrtc-builtins.so.12.0.140"
    else
        error "NVRTC library file missing: $nvrtc_lib_dir/libnvrtc-builtins.so.12.0.140"
        return 4
    fi
    
    return 0
}

create_nvrtc_ldconfig() {
    # Tìm thư mục chứa NVRTC libraries (giống check_nvrtc_libraries)
    local actual_dir="/usr/local/cuda-12.0/targets/x86_64-linux/lib"
    local fallback_dir="/usr/local/cuda/targets/x86_64-linux/lib"
    local nvrtc_lib_dir=""
    
    # Xác định thư mục chứa libraries
    if [[ -d "$actual_dir" && -f "$actual_dir/libnvrtc-builtins.so.12.0.140" ]]; then
        nvrtc_lib_dir="$actual_dir"
    elif [[ -d "$fallback_dir" && -f "$fallback_dir/libnvrtc-builtins.so.12.0.140" ]]; then
        nvrtc_lib_dir="$fallback_dir"
    else
        error "NVRTC library directory not found in expected locations during fix"
        return 1
    fi
    
    local ldconfig_file="/etc/ld.so.conf.d/cuda-nvrtc.conf"
    
    log "Configuring NVRTC libraries via ldconfig method..."
    log "Library directory: $nvrtc_lib_dir"
    
    # Tạo/cập nhật ldconfig configuration
    log "Creating ldconfig configuration: $ldconfig_file"
    echo "$nvrtc_lib_dir" > "$ldconfig_file" || {
        error "Failed to create ldconfig configuration file"
        return 1
    }
    success "Created ldconfig configuration: $ldconfig_file"
    
    # Cập nhật ldconfig cache
    log "Updating ldconfig cache..."
    ldconfig || {
        error "ldconfig update failed"
        return 1
    }
    success "ldconfig cache updated successfully"
    
    # Kiểm tra xem libraries đã được nhận diện chưa
    if ldconfig -p | grep -q nvrtc-builtins; then
        success "NVRTC libraries found in ldconfig cache"
        local cache_entries=$(ldconfig -p | grep nvrtc-builtins | wc -l)
        log "Found $cache_entries NVRTC entries in cache"
    else
        warning "NVRTC libraries not found in ldconfig cache after update"
        return 2
    fi
    
    success "NVRTC ldconfig configuration completed successfully"
}

# Keep original function name for backward compatibility
create_nvrtc_symlinks() {
    create_nvrtc_ldconfig
}

verify_fix() {
    log "Verifying ldconfig-based NVRTC fix..."
    
    # Check ldconfig configuration file
    local ldconfig_file="/etc/ld.so.conf.d/cuda-nvrtc.conf"
    if [[ -f "$ldconfig_file" ]]; then
        local configured_path=$(cat "$ldconfig_file")
        success "ldconfig configuration exists: $ldconfig_file"
        log "Configured path: $configured_path"
    else
        error "ldconfig configuration missing: $ldconfig_file"
        return 1
    fi
    
    # Check if NVRTC libraries are in ldconfig cache
    if ldconfig -p | grep -q nvrtc-builtins; then
        success "NVRTC libraries found in ldconfig cache"
        local cache_count=$(ldconfig -p | grep nvrtc-builtins | wc -l)
        log "Found $cache_count NVRTC entries in cache"
    else
        error "NVRTC libraries NOT found in ldconfig cache"
        return 1
    fi
    
    # Verify actual library files exist
    local nvrtc_dir=$(cat "$ldconfig_file")
    if [[ -f "$nvrtc_dir/libnvrtc-builtins.so.12.0.140" ]]; then
        success "NVRTC library file exists: $nvrtc_dir/libnvrtc-builtins.so.12.0.140"
    else
        error "NVRTC library file missing: $nvrtc_dir/libnvrtc-builtins.so.12.0.140"
        return 1
    fi
    
    # Show detailed ldconfig output
    echo
    echo "=== NVRTC Libraries in ldconfig cache ==="
    ldconfig -p | grep nvrtc || echo "  (none found)"
    
    # Show library directory contents
    echo
    echo "=== NVRTC Library Directory Contents ==="
    ls -la "$nvrtc_dir"/libnvrtc*.so* 2>/dev/null || echo "  (no NVRTC libraries found)"
    
    # Test environment variable as backup
    echo
    echo "=== Environment Variable Backup ==="
    if [[ "$LD_LIBRARY_PATH" == *"$nvrtc_dir"* ]]; then
        success "LD_LIBRARY_PATH includes NVRTC directory"
    else
        warning "LD_LIBRARY_PATH does not include NVRTC directory (may need manual export)"
    fi
    
    success "✅ ldconfig-based NVRTC verification completed"
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