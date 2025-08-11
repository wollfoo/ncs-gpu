#!/bin/bash
# PHASE 0: PREPARATION SCRIPTS
# Thời gian: 4 giờ
# Mục đích: Chuẩn bị môi trường và backup

set -e  # Exit on error
set -u  # Exit on undefined variable

echo "=========================================="
echo "PHASE 0: PREPARATION"
echo "=========================================="

# 0.1 BACKUP CURRENT CODE
echo "[1/4] Creating backup..."
BACKUP_DIR="/tmp/gpu_optimization_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup directories
cp -r /app/mining_environment/gpu_optimization "$BACKUP_DIR/" 2>/dev/null || true
cp -r /app/mining_environment/scripts "$BACKUP_DIR/" 2>/dev/null || true

# Create tarball
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
echo "✓ Backup created at: $BACKUP_DIR.tar.gz"

# Log backup info
echo "BACKUP_PATH=$BACKUP_DIR.tar.gz" > migration.env
echo "MIGRATION_START=$(date +%Y-%m-%d\ %H:%M:%S)" >> migration.env

# 0.2 CREATE GIT BRANCH
echo "[2/4] Creating git branch..."
cd /app/mining_environment
git checkout -b feature/gpu-optimization-refactor 2>/dev/null || {
    echo "Branch already exists, switching to it..."
    git checkout feature/gpu-optimization-refactor
}
git status > pre_migration_status.txt
echo "✓ Git branch created/switched"

# 0.3 CAPTURE BASELINE METRICS
echo "[3/4] Capturing baseline metrics..."

# Run existing tests
echo "Running baseline tests..."
python -m pytest tests/ --cov=gpu_optimization --cov-report=html > baseline_tests.txt 2>&1 || true

# Capture current imports
cat > capture_imports.py << 'EOF'
import ast
import os
import json

def find_gpu_imports(directory):
    """Find all GPU-related imports in the codebase"""
    imports = {}
    
    for root, dirs, files in os.walk(directory):
        # Skip virtual environments and cache
        dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', 'node_modules']]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r') as f:
                        tree = ast.parse(f.read())
                        
                    file_imports = []
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                if 'gpu' in alias.name.lower() or 'scripts' in alias.name:
                                    file_imports.append(alias.name)
                        elif isinstance(node, ast.ImportFrom):
                            if node.module and ('gpu' in node.module.lower() or 'scripts' in node.module):
                                file_imports.append(node.module)
                    
                    if file_imports:
                        imports[filepath] = file_imports
                except Exception as e:
                    print(f"Error parsing {filepath}: {e}")
    
    return imports

# Main execution
imports = find_gpu_imports('/app/mining_environment')
with open('baseline_imports.json', 'w') as f:
    json.dump(imports, f, indent=2)

print(f"✓ Found {len(imports)} files with GPU-related imports")
EOF

python capture_imports.py
echo "✓ Baseline metrics captured"

# 0.4 CREATE TEST HARNESS
echo "[4/4] Creating test harness..."
cat > /app/mining_environment/migration_test_harness.py << 'EOF'
#!/usr/bin/env python3
"""
Migration Test Harness
Verifies that migration doesn't break functionality
"""

import unittest
import importlib
import sys
import warnings

class MigrationTestHarness(unittest.TestCase):
    """Test harness for migration verification"""
    
    def setUp(self):
        """Setup for each test"""
        warnings.filterwarnings('ignore', category=DeprecationWarning)
    
    def test_old_imports_compatibility(self):
        """Verify backward compatibility for old imports"""
        old_imports = [
            'scripts.gpu_optimization_orchestrator',
            'scripts.gpu_monitoring_dashboard',
            'scripts.gpu_resource_monitor',
            'scripts.resource_control',
            'scripts.cloak_strategies',
            'scripts.cross_process_coordination',
            'scripts.dag_synchronization',
            'scripts.parallel_strategy_executor',
            'scripts.performance_profiler',
        ]
        
        failed = []
        for module_path in old_imports:
            try:
                importlib.import_module(module_path)
            except ImportError as e:
                failed.append((module_path, str(e)))
        
        if failed:
            msg = "\n".join([f"  - {m}: {e}" for m, e in failed])
            self.fail(f"Failed to import old modules:\n{msg}")
    
    def test_new_imports(self):
        """Verify new structure imports work"""
        new_imports = [
            'gpu_optimization.orchestrator.orchestrator',
            'gpu_optimization.monitoring.dashboard',
            'gpu_optimization.monitoring.resource_monitor',
            'gpu_optimization.resource_control.controller',
            'gpu_optimization.strategies.cloak',
            'gpu_optimization.coordination.cross_process',
            'gpu_optimization.coordination.dag_sync',
            'gpu_optimization.execution.parallel_executor',
            'gpu_optimization.profiling.performance_profiler',
        ]
        
        failed = []
        for module_path in new_imports:
            try:
                importlib.import_module(module_path)
            except ImportError as e:
                failed.append((module_path, str(e)))
        
        if failed:
            msg = "\n".join([f"  - {m}: {e}" for m, e in failed])
            self.fail(f"Failed to import new modules:\n{msg}")
    
    def test_module_functionality(self):
        """Test basic functionality of migrated modules"""
        try:
            from gpu_optimization import GPUOrchestrator, GPUMonitor
            # Basic instantiation test
            self.assertIsNotNone(GPUOrchestrator)
            self.assertIsNotNone(GPUMonitor)
        except Exception as e:
            self.fail(f"Failed to use main API: {e}")

if __name__ == '__main__':
    # Run tests with verbosity
    unittest.main(verbosity=2)
EOF

echo "✓ Test harness created"

echo ""
echo "=========================================="
echo "PHASE 0 COMPLETE!"
echo "=========================================="
echo "Backup location: $(cat migration.env | grep BACKUP_PATH | cut -d= -f2)"
echo "Next step: Run phase1_structure.sh"
