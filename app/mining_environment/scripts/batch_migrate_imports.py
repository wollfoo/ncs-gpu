#!/usr/bin/env python3
"""
**Batch Import Migration Script** (script migration import hàng loạt)

Tự động cập nhật import statements từ unified_logging sang module_loggers
cho tất cả các files trong codebase.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Module mapping cho migration
MODULE_MIGRATION_MAP = {
    # Legacy -> New mapping
    'get_unified_logger': {
        'start_mining.py': 'get_start_mining_logger',
        'gpu_monitoring_dashboard.py': 'get_gpu_monitoring_dashboard_logger', 
        'error_management.py': 'get_error_management_logger',
        'gpu_resource_monitor.py': 'get_gpu_monitoring_logger',
        'resource_manager.py': 'get_resource_manager_logger',
        'error_recovery_coordinator.py': 'get_coordination_logger',
        'strategy_cache.py': 'get_cloak_strategies_logger',
        'cloak_strategies.py': 'get_cloak_strategies_logger',
        'stealth_inference_cuda.py': 'get_stealth_inference_logger',
        'stealth_activation_manager.py': 'get_stealth_inference_logger',
        'coordinator.py': 'get_coordination_logger'
    }
}

def get_files_to_migrate() -> List[Path]:
    """**Get Files to Migrate** (lấy danh sách files cần migrate)"""
    base_path = Path('/home/azureuser/ncs-gpu/app')
    files_to_check = []
    
    # Tìm tất cả files Python
    for root, dirs, files in os.walk(base_path):
        # Skip __pycache__ và các thư mục ẩn
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for file in files:
            if file.endswith('.py'):
                file_path = Path(root) / file
                files_to_check.append(file_path)
    
    return files_to_check

def check_import_usage(file_path: Path) -> Dict:
    """**Check Import Usage** (kiểm tra usage của import)"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Tìm import statements
        unified_logging_imports = []
        
        # Pattern 1: from .unified_logging import get_unified_logger
        pattern1 = re.findall(r'from\s+\.unified_logging\s+import\s+(\w+)', content)
        if pattern1:
            unified_logging_imports.extend(pattern1)
        
        # Pattern 2: from unified_logging import get_unified_logger  
        pattern2 = re.findall(r'from\s+unified_logging\s+import\s+(\w+)', content)
        if pattern2:
            unified_logging_imports.extend(pattern2)
            
        # Pattern 3: from mining_environment.scripts.unified_logging import get_unified_logger
        pattern3 = re.findall(r'from\s+mining_environment\.scripts\.unified_logging\s+import\s+(\w+)', content)
        if pattern3:
            unified_logging_imports.extend(pattern3)
        
        return {
            'file': file_path,
            'has_unified_logging': len(unified_logging_imports) > 0,
            'imports': unified_logging_imports,
            'content': content
        }
        
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return {'file': file_path, 'has_unified_logging': False, 'imports': [], 'content': ''}

def migrate_file_imports(file_info: Dict) -> bool:
    """**Migrate File Imports** (migrate imports cho từng file)"""
    if not file_info['has_unified_logging']:
        return True
    
    file_path = file_info['file']
    content = file_info['content']
    filename = file_path.name
    
    print(f"🔄 Migrating {filename}...")
    
    # Backup original content
    backup_content = content
    
    try:
        # Replace import statements
        # Pattern 1: from .unified_logging import get_unified_logger
        if 'from .unified_logging import get_unified_logger' in content:
            if filename in MODULE_MIGRATION_MAP['get_unified_logger']:
                new_logger = MODULE_MIGRATION_MAP['get_unified_logger'][filename]
                content = content.replace(
                    'from .unified_logging import get_unified_logger',
                    f'from .module_loggers import {new_logger}'
                )
                print(f"  ✅ Updated relative import to {new_logger}")
        
        # Pattern 2: from unified_logging import get_unified_logger
        if 'from unified_logging import get_unified_logger' in content:
            if filename in MODULE_MIGRATION_MAP['get_unified_logger']:
                new_logger = MODULE_MIGRATION_MAP['get_unified_logger'][filename]
                content = content.replace(
                    'from unified_logging import get_unified_logger',
                    f'from module_loggers import {new_logger}'
                )
                print(f"  ✅ Updated standalone import to {new_logger}")
        
        # Pattern 3: from mining_environment.scripts.unified_logging import get_unified_logger
        if 'from mining_environment.scripts.unified_logging import get_unified_logger' in content:
            if filename in MODULE_MIGRATION_MAP['get_unified_logger']:
                new_logger = MODULE_MIGRATION_MAP['get_unified_logger'][filename]
                content = content.replace(
                    'from mining_environment.scripts.unified_logging import get_unified_logger',
                    f'from mining_environment.scripts.module_loggers import {new_logger}'
                )
                print(f"  ✅ Updated full path import to {new_logger}")
        
        # Update logger initialization calls
        if filename in MODULE_MIGRATION_MAP['get_unified_logger']:
            new_logger = MODULE_MIGRATION_MAP['get_unified_logger'][filename]
            # Replace get_unified_logger('name') calls
            content = re.sub(
                r'get_unified_logger\([^)]*\)',
                f'{new_logger}()',
                content
            )
            print(f"  ✅ Updated logger function calls to {new_logger}()")
        
        # Ghi file đã cập nhật
        if content != backup_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  💾 File {filename} updated successfully")
            return True
        else:
            print(f"  ⚠️ No changes needed for {filename}")
            return True
            
    except Exception as e:
        print(f"  ❌ Error migrating {filename}: {e}")
        # Restore backup if error
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(backup_content)
        except:
            pass
        return False

def main():
    """**Main Migration Process** (quy trình migration chính)"""
    print("🚀 Starting Batch Import Migration...")
    print("=" * 60)
    
    # Step 1: Get files to migrate
    files = get_files_to_migrate()
    print(f"📁 Found {len(files)} Python files to check")
    
    # Step 2: Check which files have unified_logging imports
    files_needing_migration = []
    for file_path in files:
        file_info = check_import_usage(file_path)
        if file_info['has_unified_logging']:
            files_needing_migration.append(file_info)
            print(f"📝 {file_path.name}: {', '.join(file_info['imports'])}")
    
    print(f"\n🎯 Found {len(files_needing_migration)} files needing migration")
    
    if not files_needing_migration:
        print("✅ No files need migration!")
        return
    
    # Step 3: Migrate each file
    print("\n🔄 Starting migration process...")
    successful_migrations = 0
    failed_migrations = 0
    
    for file_info in files_needing_migration:
        if migrate_file_imports(file_info):
            successful_migrations += 1
        else:
            failed_migrations += 1
    
    # Step 4: Report results
    print("\n" + "=" * 60)
    print("📊 MIGRATION RESULTS:")
    print(f"  ✅ Successful migrations: {successful_migrations}")
    print(f"  ❌ Failed migrations: {failed_migrations}")
    print(f"  📁 Total files processed: {len(files_needing_migration)}")
    
    if failed_migrations == 0:
        print("\n🎉 ALL MIGRATIONS COMPLETED SUCCESSFULLY!")
        print("📋 Ready to proceed with legacy file cleanup")
    else:
        print(f"\n⚠️ {failed_migrations} migrations failed - please check manually")

if __name__ == "__main__":
    main()
