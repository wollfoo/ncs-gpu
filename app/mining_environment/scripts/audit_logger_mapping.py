#!/usr/bin/env python3
"""
Script kiểm tra và báo cáo mapping logger trong toàn bộ codebase.
Mục đích: Tìm các module đang import sai logger so với mapping yêu cầu.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Định nghĩa mapping chuẩn theo yêu cầu
EXPECTED_MAPPING = {
    # Module/Component → Logger function → Log file
    'start_mining.py': ('get_mining_logger', 'start_mining.log'),
    'stealth_inference_cuda.py': ('get_stealth_inference_logger', 'stealth_inference_cuda.log'),
    'HookCoordinator': ('get_coordination_logger', 'coordination.log'),
    'DirectPIDRegistry': ('get_registry_logger', 'direct_registry.log'),
    'ResourceManager': ('get_resource_manager_logger', 'resource_manager.log'),
    'cloak_strategies.py': ('get_gpu_cloaking_logger', 'cloak_strategies.log'),
    'resource_control.py': ('get_resource_control_logger', 'resource_control.log'),
    'pid_logger': ('get_pid_logger', 'pid_logger.log'),
    'utils': ('get_utility_logger', 'utils.log'),
    'gpu_plugins': ('get_gpu_plugin_logger', 'gpu_plugins.log'),
    'nvml_interceptor.py': ('get_nvml_logger', 'nvml_interceptor.log'),
    'thermal_spoofer.py': ('get_thermal_logger', 'thermal_spoofer.log'),
    'time_based_manager.py': ('get_timing_logger', 'time_based_manager.log'),
    'nvml_proxy_daemon.py': ('get_proxy_daemon_logger', 'nvml_proxy_daemon.log'),
    'stealth_monitor.py': ('get_stealth_monitor_logger', 'stealth_monitor.log'),
    'gpu_resource_monitor.py': ('get_gpu_monitoring_logger', 'gpu_resource_monitor.log'),
    'gpu_monitoring_dashboard.py': ('get_dashboard_logger', 'gpu_monitoring_dashboard.log'),
    'setup_env.py': ('get_environment_logger', 'setup_env.log'),
}

def find_python_files(base_dir: Path) -> List[Path]:
    """Tìm tất cả file Python trong thư mục."""
    return list(base_dir.rglob("*.py"))

def extract_logger_imports(file_path: Path) -> List[str]:
    """Trích xuất các import logger từ file."""
    imports = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Tìm import từ module_loggers
        pattern = r'from\s+.*module_loggers\s+import\s+([^#\n]+)'
        matches = re.findall(pattern, content)
        
        for match in matches:
            # Tách các function được import
            funcs = [f.strip() for f in match.split(',')]
            imports.extend([f for f in funcs if f.startswith('get_') and f.endswith('_logger')])
            
    except Exception as e:
        print(f"❌ Lỗi đọc {file_path}: {e}")
        
    return imports

def check_log_files(logs_dir: Path) -> Dict[str, int]:
    """Kiểm tra kích thước các file log."""
    log_sizes = {}
    
    if not logs_dir.exists():
        return log_sizes
        
    for log_file in logs_dir.glob("*.log"):
        size = log_file.stat().st_size
        log_sizes[log_file.name] = size
        
    return log_sizes

def main():
    base_dir = Path("/home/azureuser/ncs-gpu/app/mining_environment")
    logs_dir = base_dir / "logs"
    
    print("=" * 80)
    print("🔍 KIỂM TRA MAPPING LOGGER TRONG CODEBASE")
    print("=" * 80)
    
    # 1. Kiểm tra file log
    print("\n📊 Trạng thái file log:")
    print("-" * 40)
    
    log_sizes = check_log_files(logs_dir)
    empty_logs = []
    
    for log_name in sorted(EXPECTED_MAPPING.values(), key=lambda x: x[1]):
        log_file = log_name[1]
        size = log_sizes.get(log_file, -1)
        
        if size == -1:
            status = "❌ Không tồn tại"
        elif size == 0:
            status = "⚠️ Rỗng (0 bytes)"
            empty_logs.append(log_file)
        else:
            status = f"✅ {size} bytes"
            
        print(f"  {log_file:30} {status}")
    
    # 2. Kiểm tra import logger trong các module
    print("\n🔎 Kiểm tra import logger trong các module:")
    print("-" * 40)
    
    issues_found = []
    
    for module_name, (expected_func, expected_log) in EXPECTED_MAPPING.items():
        # Tìm file module
        files = find_python_files(base_dir)
        matching_files = [f for f in files if f.name == module_name]
        
        if not matching_files:
            # Có thể là class name, bỏ qua
            continue
            
        for file_path in matching_files:
            imports = extract_logger_imports(file_path)
            
            if imports:
                if expected_func not in imports:
                    # Phát hiện import sai
                    relative_path = file_path.relative_to(base_dir)
                    issues_found.append({
                        'file': str(relative_path),
                        'expected': expected_func,
                        'actual': imports,
                        'log_file': expected_log
                    })
                    print(f"  ❌ {relative_path}")
                    print(f"     Cần: {expected_func}")
                    print(f"     Thực tế: {', '.join(imports)}")
                else:
                    relative_path = file_path.relative_to(base_dir)
                    print(f"  ✅ {relative_path} - Đúng logger")
    
    # 3. Báo cáo tổng hợp
    print("\n" + "=" * 80)
    print("📋 TỔNG HỢP KẾT QUẢ:")
    print("-" * 40)
    
    if empty_logs:
        print(f"\n⚠️ Có {len(empty_logs)} file log rỗng:")
        for log in empty_logs:
            print(f"   - {log}")
    
    if issues_found:
        print(f"\n❌ Có {len(issues_found)} module import sai logger:")
        for issue in issues_found:
            print(f"   - {issue['file']} → cần sửa thành {issue['expected']}")
    
    if not empty_logs and not issues_found:
        print("\n✅ Tất cả mapping logger đã đúng!")
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    main()
