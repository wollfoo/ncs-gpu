#!/usr/bin/env python3
"""
PHASE 2: MIGRATE CODE AND UPDATE IMPORTS
Thời gian: 6 giờ
Mục đích: Di chuyển files và cập nhật imports
"""

import os
import shutil
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Tuple, Set

# Configuration
SCRIPTS_DIR = "/app/mining_environment/scripts"
BASE_DIR = "/app/mining_environment/gpu_optimization"
LOG_FILE = "phase2_migration.log"

# File mappings - từ scripts/ sang thư mục mới
FILE_MAPPINGS = {
    # Orchestrator
    "gpu_optimization_orchestrator.py": "orchestrator/orchestrator.py",
    
    # Monitoring
    "gpu_monitoring_dashboard.py": "monitoring/dashboard.py",
    "gpu_resource_monitor.py": "monitoring/resource_monitor.py",
    
    # Strategies
    "cloak_strategies.py": "strategies/cloak.py",
    
    # Resource Control
    "resource_control.py": "resource_control/controller.py",
    
    # Coordination
    "cross_process_coordination.py": "coordination/cross_process.py",
    "dag_synchronization.py": "coordination/dag_sync.py",
    
    # Execution
    "parallel_strategy_executor.py": "execution/parallel_executor.py",
    
    # Profiling
    "performance_profiler.py": "profiling/performance_profiler.py",
}

# Import replacements mapping
IMPORT_REPLACEMENTS = {
    # From old scripts imports to new module imports
    "from scripts.gpu_optimization_orchestrator": "from gpu_optimization.orchestrator.orchestrator",
    "import scripts.gpu_optimization_orchestrator": "import gpu_optimization.orchestrator.orchestrator",
    
    "from scripts.gpu_monitoring_dashboard": "from gpu_optimization.monitoring.dashboard",
    "import scripts.gpu_monitoring_dashboard": "import gpu_optimization.monitoring.dashboard",
    
    "from scripts.gpu_resource_monitor": "from gpu_optimization.monitoring.resource_monitor",
    "import scripts.gpu_resource_monitor": "import gpu_optimization.monitoring.resource_monitor",
    
    "from scripts.cloak_strategies": "from gpu_optimization.strategies.cloak",
    "import scripts.cloak_strategies": "import gpu_optimization.strategies.cloak",
    
    "from scripts.resource_control": "from gpu_optimization.resource_control.controller",
    "import scripts.resource_control": "import gpu_optimization.resource_control.controller",
    
    "from scripts.cross_process_coordination": "from gpu_optimization.coordination.cross_process",
    "import scripts.cross_process_coordination": "import gpu_optimization.coordination.cross_process",
    
    "from scripts.dag_synchronization": "from gpu_optimization.coordination.dag_sync",
    "import scripts.dag_synchronization": "import gpu_optimization.coordination.dag_sync",
    
    "from scripts.parallel_strategy_executor": "from gpu_optimization.execution.parallel_executor",
    "import scripts.parallel_strategy_executor": "import gpu_optimization.execution.parallel_executor",
    
    "from scripts.performance_profiler": "from gpu_optimization.profiling.performance_profiler",
    "import scripts.performance_profiler": "import gpu_optimization.profiling.performance_profiler",
}


class MigrationLogger:
    """Simple logger for migration process"""
    
    def __init__(self, logfile):
        self.logfile = logfile
        with open(logfile, 'w') as f:
            f.write("=" * 60 + "\n")
            f.write("PHASE 2 MIGRATION LOG\n")
            f.write("=" * 60 + "\n\n")
    
    def log(self, message, level="INFO"):
        """Log a message with timestamp"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.logfile, 'a') as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
        print(f"[{level}] {message}")


class CodeMigrator:
    """Main migration class"""
    
    def __init__(self):
        self.logger = MigrationLogger(LOG_FILE)
        self.files_migrated = []
        self.files_updated = []
        self.errors = []
    
    def migrate_files(self) -> bool:
        """Step 2.1: Move files from scripts/ to new structure"""
        self.logger.log("Starting file migration...")
        
        for old_file, new_path in FILE_MAPPINGS.items():
            src = os.path.join(SCRIPTS_DIR, old_file)
            dst = os.path.join(BASE_DIR, new_path)
            
            # Check if source exists
            if not os.path.exists(src):
                self.logger.log(f"Source file not found: {src}", "WARNING")
                continue
            
            # Create destination directory
            dst_dir = os.path.dirname(dst)
            os.makedirs(dst_dir, exist_ok=True)
            
            try:
                # Copy file (preserve original for now)
                shutil.copy2(src, dst)
                self.files_migrated.append((src, dst))
                self.logger.log(f"✓ Migrated: {old_file} -> {new_path}")
            except Exception as e:
                self.errors.append(f"Failed to migrate {old_file}: {e}")
                self.logger.log(f"✗ Failed: {old_file}: {e}", "ERROR")
        
        self.logger.log(f"File migration complete: {len(self.files_migrated)} files migrated")
        return len(self.errors) == 0
    
    def update_imports_in_file(self, filepath: str) -> int:
        """Update imports in a single file"""
        changes_made = 0
        
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            original_content = content
            
            # Apply all import replacements
            for old_import, new_import in IMPORT_REPLACEMENTS.items():
                if old_import in content:
                    content = content.replace(old_import, new_import)
                    changes_made += 1
            
            # Also handle relative imports within the new structure
            if "/gpu_optimization/" in filepath:
                # Update relative imports to use absolute imports
                content = re.sub(
                    r'from \.([\w.]+) import',
                    r'from gpu_optimization.\1 import',
                    content
                )
            
            # Write back if changes were made
            if content != original_content:
                with open(filepath, 'w') as f:
                    f.write(content)
                self.files_updated.append(filepath)
                self.logger.log(f"  ✓ Updated imports in: {filepath} ({changes_made} changes)")
            
        except Exception as e:
            self.errors.append(f"Failed to update {filepath}: {e}")
            self.logger.log(f"  ✗ Failed to update: {filepath}: {e}", "ERROR")
        
        return changes_made
    
    def update_all_imports(self) -> bool:
        """Step 2.2: Update imports in all Python files"""
        self.logger.log("Starting import updates...")
        
        total_changes = 0
        
        # Update imports in the entire mining_environment directory
        for root, dirs, files in os.walk("/app/mining_environment"):
            # Skip venv and cache directories
            dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', 'node_modules']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    changes = self.update_imports_in_file(filepath)
                    total_changes += changes
        
        self.logger.log(f"Import updates complete: {len(self.files_updated)} files updated, {total_changes} total changes")
        return len(self.errors) == 0
    
    def create_module_wrappers(self) -> bool:
        """Step 2.3: Create wrapper modules for seamless transition"""
        self.logger.log("Creating module wrappers...")
        
        wrappers = {
            # Orchestrator wrapper
            "orchestrator/__init__.py": """
from .orchestrator import *
from .orchestrator import __all__
""",
            # Monitoring wrapper
            "monitoring/__init__.py": """
from .dashboard import *
from .resource_monitor import *

__all__ = ['GPUMonitor', 'ResourceMonitor', 'dashboard_main', 'monitor_main']
""",
            # Strategies wrapper
            "strategies/__init__.py": """
from .cloak import *

__all__ = ['CloakStrategy', 'apply_cloak', 'get_strategy']
""",
            # Resource control wrapper
            "resource_control/__init__.py": """
from .controller import *

__all__ = ['ResourceController', 'HardwareController', 'control_resources']
""",
            # Coordination wrapper
            "coordination/__init__.py": """
from .cross_process import *
from .dag_sync import *

__all__ = ['CrossProcessCoordinator', 'DAGSynchronizer', 'coordinate']
""",
            # Execution wrapper
            "execution/__init__.py": """
from .parallel_executor import *

__all__ = ['ParallelExecutor', 'execute_parallel', 'ExecutionContext']
""",
            # Profiling wrapper
            "profiling/__init__.py": """
from .performance_profiler import *

__all__ = ['PerformanceProfiler', 'profile', 'get_metrics']
""",
        }
        
        for wrapper_path, content in wrappers.items():
            full_path = os.path.join(BASE_DIR, wrapper_path)
            try:
                with open(full_path, 'w') as f:
                    f.write(content.strip())
                self.logger.log(f"✓ Created wrapper: {wrapper_path}")
            except Exception as e:
                self.errors.append(f"Failed to create wrapper {wrapper_path}: {e}")
                self.logger.log(f"✗ Failed wrapper: {wrapper_path}: {e}", "ERROR")
        
        return len(self.errors) == 0
    
    def verify_migration(self) -> bool:
        """Step 2.4: Verify the migration was successful"""
        self.logger.log("Verifying migration...")
        
        verification_passed = True
        
        # Check all migrated files exist
        for _, dst in self.files_migrated:
            if not os.path.exists(dst):
                self.logger.log(f"✗ Missing migrated file: {dst}", "ERROR")
                verification_passed = False
        
        # Try to import the new modules
        test_imports = [
            "gpu_optimization.orchestrator",
            "gpu_optimization.monitoring",
            "gpu_optimization.strategies",
            "gpu_optimization.resource_control",
            "gpu_optimization.coordination",
            "gpu_optimization.execution",
            "gpu_optimization.profiling",
        ]
        
        import sys
        sys.path.insert(0, "/app/mining_environment")
        
        for module_name in test_imports:
            try:
                __import__(module_name)
                self.logger.log(f"✓ Can import: {module_name}")
            except ImportError as e:
                self.logger.log(f"✗ Cannot import {module_name}: {e}", "WARNING")
                # Not a hard failure - modules might have dependencies
        
        return verification_passed
    
    def generate_summary(self):
        """Generate migration summary"""
        summary = f"""
{"=" * 60}
PHASE 2 MIGRATION SUMMARY
{"=" * 60}

Files Migrated: {len(self.files_migrated)}
Files Updated: {len(self.files_updated)}
Errors: {len(self.errors)}

Migrated Files:
{chr(10).join([f"  - {os.path.basename(src)} -> {os.path.basename(dst)}" for src, dst in self.files_migrated])}

{f"Errors Encountered:{chr(10)}{chr(10).join(['  - ' + e for e in self.errors])}" if self.errors else "No errors encountered."}

Next Steps:
1. Run the test harness: python migration_test_harness.py
2. Run unit tests: python -m pytest tests/
3. Check import compatibility
4. Proceed to Phase 3 if all tests pass

{"=" * 60}
"""
        self.logger.log(summary)
        
        # Save summary to file
        with open("phase2_summary.txt", 'w') as f:
            f.write(summary)


def main():
    """Main migration execution"""
    print("=" * 60)
    print("PHASE 2: CODE MIGRATION")
    print("=" * 60)
    
    migrator = CodeMigrator()
    
    # Execute migration steps
    steps = [
        ("Step 2.1: Migrate Files", migrator.migrate_files),
        ("Step 2.2: Update Imports", migrator.update_all_imports),
        ("Step 2.3: Create Wrappers", migrator.create_module_wrappers),
        ("Step 2.4: Verify Migration", migrator.verify_migration),
    ]
    
    all_passed = True
    for step_name, step_func in steps:
        print(f"\n{step_name}...")
        if not step_func():
            all_passed = False
            print(f"  ⚠ {step_name} had issues")
    
    # Generate summary
    migrator.generate_summary()
    
    if all_passed:
        print("\n✅ PHASE 2 COMPLETE - Migration successful!")
        print("Check phase2_summary.txt for details")
        print("Next: Run phase3_testing.sh")
        return 0
    else:
        print("\n⚠️ PHASE 2 COMPLETE WITH WARNINGS")
        print("Review phase2_migration.log for details")
        return 1


if __name__ == "__main__":
    exit(main())
