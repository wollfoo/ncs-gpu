#!/bin/bash
# GPU OPTIMIZATION MIGRATION - MASTER RUN SCRIPT
# Chạy toàn bộ migration process với validation và rollback

set -e
set -u

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
MASTER_LOG="${LOG_DIR}/migration_master_$(date +%Y%m%d_%H%M%S).log"

# Create log directory
mkdir -p "$LOG_DIR"

# Logging function
log() {
    echo -e "${2:-}$1${NC}" | tee -a "$MASTER_LOG"
}

# Header
clear
log "╔══════════════════════════════════════════════════════════╗" "$BLUE"
log "║         GPU OPTIMIZATION MIGRATION MASTER SCRIPT         ║" "$BLUE"
log "║                     Version 2.0.0                        ║" "$BLUE"
log "╚══════════════════════════════════════════════════════════╝" "$BLUE"
log ""

# Check prerequisites
log "🔍 Checking prerequisites..." "$YELLOW"

# Check if scripts exist
REQUIRED_SCRIPTS=(
    "phase0_preparation.sh"
    "phase1_structure.sh"
    "phase2_migration.py"
    "phase3_testing.sh"
    "phase4_cleanup.sh"
)

for script in "${REQUIRED_SCRIPTS[@]}"; do
    if [ ! -f "${SCRIPT_DIR}/${script}" ]; then
        log "✗ Missing script: ${script}" "$RED"
        exit 1
    fi
done

# Make scripts executable
chmod +x "${SCRIPT_DIR}"/*.sh
log "✓ All required scripts found" "$GREEN"

# Check Python
if ! command -v python3 &> /dev/null; then
    log "✗ Python 3 is required but not installed" "$RED"
    exit 1
fi
log "✓ Python 3 available" "$GREEN"

# Check git
if ! command -v git &> /dev/null; then
    log "✗ Git is required but not installed" "$RED"
    exit 1
fi
log "✓ Git available" "$GREEN"

# Interactive mode check
log ""
log "🎯 Migration Mode Selection" "$YELLOW"
log "1) Full Auto - Run all phases automatically"
log "2) Interactive - Confirm before each phase"
log "3) Dry Run - Test without making changes"
log "4) Custom - Select specific phases"

read -p "Select mode (1-4): " MODE

# Dry run flag
DRY_RUN=false
if [ "$MODE" = "3" ]; then
    DRY_RUN=true
    log "🔄 DRY RUN MODE - No actual changes will be made" "$YELLOW"
fi

# Function to run a phase
run_phase() {
    local phase_num=$1
    local phase_script=$2
    local phase_name=$3
    local estimated_time=$4
    
    log ""
    log "═══════════════════════════════════════════════════════════" "$BLUE"
    log "PHASE ${phase_num}: ${phase_name}" "$BLUE"
    log "Estimated time: ${estimated_time}" "$BLUE"
    log "═══════════════════════════════════════════════════════════" "$BLUE"
    
    if [ "$MODE" = "2" ]; then
        read -p "Run Phase ${phase_num}? (y/n): " confirm
        if [ "$confirm" != "y" ]; then
            log "⏭ Skipping Phase ${phase_num}" "$YELLOW"
            return 0
        fi
    fi
    
    if [ "$DRY_RUN" = true ]; then
        log "🔄 DRY RUN: Would execute ${phase_script}" "$YELLOW"
        sleep 2
        return 0
    fi
    
    log "▶ Starting Phase ${phase_num}..." "$GREEN"
    
    # Run the phase script
    START_TIME=$(date +%s)
    
    if [[ "$phase_script" == *.py ]]; then
        python3 "${SCRIPT_DIR}/${phase_script}" 2>&1 | tee -a "$MASTER_LOG"
    else
        bash "${SCRIPT_DIR}/${phase_script}" 2>&1 | tee -a "$MASTER_LOG"
    fi
    
    PHASE_RESULT=$?
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    
    if [ $PHASE_RESULT -eq 0 ]; then
        log "✅ Phase ${phase_num} completed successfully (${DURATION}s)" "$GREEN"
    else
        log "❌ Phase ${phase_num} failed with error code ${PHASE_RESULT}" "$RED"
        
        # Ask for rollback
        read -p "Do you want to rollback? (y/n): " rollback
        if [ "$rollback" = "y" ]; then
            perform_rollback
        fi
        exit $PHASE_RESULT
    fi
    
    return 0
}

# Rollback function
perform_rollback() {
    log ""
    log "🔄 PERFORMING ROLLBACK..." "$YELLOW"
    
    # Check if backup exists
    if [ -f "migration.env" ]; then
        BACKUP_PATH=$(grep BACKUP_PATH migration.env | cut -d= -f2)
        if [ -f "$BACKUP_PATH" ]; then
            log "Restoring from backup: $BACKUP_PATH" "$YELLOW"
            tar -xzf "$BACKUP_PATH" -C / 2>&1 | tee -a "$MASTER_LOG"
            log "✓ Backup restored" "$GREEN"
        fi
    fi
    
    # Reset git
    cd /app/mining_environment
    git checkout main 2>/dev/null || true
    git branch -D feature/gpu-optimization-refactor 2>/dev/null || true
    
    log "✓ Rollback completed" "$GREEN"
    log "Please review the system state before continuing" "$YELLOW"
}

# Main execution based on mode
if [ "$MODE" = "4" ]; then
    # Custom mode - select phases
    log ""
    log "Select phases to run (comma-separated, e.g., 0,1,2):" "$YELLOW"
    log "0 - Preparation"
    log "1 - Structure Creation"
    log "2 - Code Migration"
    log "3 - Testing & Validation"
    log "4 - Cleanup & Finalization"
    
    read -p "Enter phases: " PHASES
    IFS=',' read -ra PHASE_ARRAY <<< "$PHASES"
    
    for phase in "${PHASE_ARRAY[@]}"; do
        case $phase in
            0) run_phase 0 "phase0_preparation.sh" "Preparation" "4 hours" ;;
            1) run_phase 1 "phase1_structure.sh" "Structure Creation" "2 hours" ;;
            2) run_phase 2 "phase2_migration.py" "Code Migration" "6 hours" ;;
            3) run_phase 3 "phase3_testing.sh" "Testing & Validation" "4 hours" ;;
            4) run_phase 4 "phase4_cleanup.sh" "Cleanup & Finalization" "2 hours" ;;
            *) log "Invalid phase: $phase" "$RED" ;;
        esac
    done
else
    # Run all phases in sequence
    run_phase 0 "phase0_preparation.sh" "Preparation" "4 hours"
    run_phase 1 "phase1_structure.sh" "Structure Creation" "2 hours"
    run_phase 2 "phase2_migration.py" "Code Migration" "6 hours"
    run_phase 3 "phase3_testing.sh" "Testing & Validation" "4 hours"
    run_phase 4 "phase4_cleanup.sh" "Cleanup & Finalization" "2 hours"
fi

# Final summary
log ""
log "═══════════════════════════════════════════════════════════" "$BLUE"
log "                    MIGRATION SUMMARY                       " "$BLUE"
log "═══════════════════════════════════════════════════════════" "$BLUE"

if [ "$DRY_RUN" = true ]; then
    log "🔄 DRY RUN COMPLETED - No actual changes were made" "$YELLOW"
else
    # Check final status
    if [ -f "migration_final_report.md" ]; then
        log "✅ MIGRATION COMPLETED SUCCESSFULLY!" "$GREEN"
        log ""
        log "📊 Key Outputs:" "$BLUE"
        log "  • Final Report: migration_final_report.md"
        log "  • Test Results: phase3_test_results.log"
        log "  • Master Log: $MASTER_LOG"
        log ""
        log "📅 Important Dates:" "$BLUE"
        log "  • Migration Date: $(date +%Y-%m-%d)"
        log "  • Deprecation End: $(date -d "+30 days" +%Y-%m-%d)"
        log ""
        log "🎯 Next Steps:" "$BLUE"
        log "  1. Review migration_final_report.md"
        log "  2. Notify team of completion"
        log "  3. Monitor for 24-48 hours"
        log "  4. Update team documentation"
        log ""
        log "🎉 Congratulations! The GPU Optimization module has been" "$GREEN"
        log "   successfully migrated to version 2.0.0!" "$GREEN"
    else
        log "⚠️ Migration may be incomplete - check logs" "$YELLOW"
        log "Log file: $MASTER_LOG"
    fi
fi

log ""
log "╔══════════════════════════════════════════════════════════╗" "$BLUE"
log "║                  END OF MIGRATION SCRIPT                 ║" "$BLUE"
log "╚══════════════════════════════════════════════════════════╝" "$BLUE"

# Create completion marker
if [ "$DRY_RUN" = false ] && [ -f "migration_final_report.md" ]; then
    echo "COMPLETED: $(date)" > "${SCRIPT_DIR}/.migration_complete"
fi

exit 0
