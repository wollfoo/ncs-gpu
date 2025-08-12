root@e477c94e9576:/app# python start_mining.py --debug 2>&1 | tee mining_debug.log
✅ [EnhancedLogging] Event-driven aggregation started: /app/mining_environment/logs/unified.log
✅ [**EnhancedLogging** (ghi log nâng cao)] **Initialized** (đã khởi tạo) 7 **loggers** (bộ ghi nhật ký) với **event-driven aggregation** (tổng hợp theo sự kiện – gom nhật ký kích hoạt)
2025-08-12 05:40:28,410 - gpu_plugin - INFO - unknown - ===== GPU PLUGIN LOGGING SYSTEM STARTED =====
2025-08-12 05:40:28,411 - gpu_plugin - INFO - unknown - GPU Plugin Logger initialized and ready
2025-08-12 05:40:28,411 - gpu_plugin - INFO - unknown - Available for logging GPU plugin operations
2025-08-12 05:40:28,411 - gpu_plugin - INFO - unknown - ============================================
2025-08-12 05:40:28,411 - gpu_cloaking - INFO - unknown - ===== GPU CLOAKING LOGGING SYSTEM STARTED =====
2025-08-12 05:40:28,411 - gpu_cloaking - INFO - unknown - GPU Cloaking Logger initialized and ready
2025-08-12 05:40:28,411 - gpu_cloaking - INFO - unknown - Available for logging GPU cloaking operations
2025-08-12 05:40:28,411 - gpu_optimization - INFO - unknown - ===== GPU OPTIMIZATION LOGGING SYSTEM STARTED =====
2025-08-12 05:40:28,411 - gpu_optimization - INFO - unknown - GPU Optimization Logger initialized and ready
2025-08-12 05:40:28,411 - gpu_optimization - INFO - unknown - Available for logging GPU optimization operations
2025-08-12 05:40:28,411 - mining_performance - INFO - unknown - ===== MINING PERFORMANCE LOGGING SYSTEM STARTED =====
2025-08-12 05:40:28,411 - mining_performance - INFO - unknown - Mining Performance Logger initialized and ready
2025-08-12 05:40:28,411 - mining_performance - INFO - unknown - Available for logging mining performance operations
2025-08-12 05:40:28,412 - audit_integration - INFO - unknown - ===== AUDIT INTEGRATION LOGGING SYSTEM STARTED =====
2025-08-12 05:40:28,412 - audit_integration - INFO - unknown - Audit Integration Logger initialized and ready
2025-08-12 05:40:28,412 - audit_integration - INFO - unknown - Available for logging audit integration operations
2025-08-12 05:40:28,412 - gpu_monitoring - INFO - unknown - ===== GPU MONITORING LOGGING SYSTEM STARTED =====
2025-08-12 05:40:28,412 - gpu_monitoring - INFO - unknown - GPU Monitoring Logger initialized and ready
2025-08-12 05:40:28,412 - gpu_monitoring - INFO - unknown - Available for logging GPU monitoring operations
✅ [PHASE-2-VALIDATION] Phase 2 refactoring validation PASSED
2025-08-12 05:40:28,456 - error_management - INFO - unknown - ✅ [ErrorReporter] **Centralized error reporter initialized** (Trình báo cáo lỗi tập trung đã khởi tạo – hệ thống báo lỗi trung tâm đã thiết lập)
2025-08-12 05:40:28,510 - error_management - INFO - unknown - ✅ [Recovery] Registered handler for 3001
2025-08-12 05:40:28,510 - error_management - INFO - unknown - ✅ [Recovery] Registered handler for 1004
2025-08-12 05:40:28,511 - error_management - INFO - unknown - ✅ [Recovery] Registered handler for 2002
2025-08-12 05:40:28,511 - gpu_cloaking - INFO - unknown - ✅ [Recovery] Strategy recovery handlers registered successfully
2025-08-12 05:40:28,534 - mining_performance - INFO - unknown - ============================================ [Repeated 10x in last 30s]
✅ [PHASE-2-VALIDATION] Phase 2 refactoring validation PASSED
2025-08-12 05:40:28,548 - start_mining - INFO - unknown - ===== Bắt đầu hoạt động khai thác tiền điện tử (Simplified Sequential Architecture) =====
2025-08-12 05:40:28,548 - start_mining - INFO - unknown - 🔧 Đang thiết lập môi trường (sequential direct)...
2025-08-12 05:40:28,548 - start_mining - INFO - unknown - Bắt đầu thiết lập môi trường khai thác (Thread-Safe Mode).
2025-08-12 05:40:28,548 - start_mining - INFO - unknown - 🔐 Khởi tạo **Environment** (môi trường – hệ thống hoạt động) đã được khởi tạo thành công **privileged manager** (trình quản lý đặc quyền – quản lý hoạt động cần quyền cao)...
2025-08-12 05:40:28,549 - start_mining - INFO - unknown - 🔑 Running as root - all privileged operations available
2025-08-12 05:40:28,549 - start_mining - INFO - unknown - 🔒 Xác thực **security context** (bối cảnh bảo mật – thông tin quyền hạn và bảo mật)...
2025-08-12 05:40:28,551 - start_mining - INFO - unknown - ✅ Bối cảnh bảo mật: User=root, Root=True
2025-08-12 05:40:28,551 - start_mining - INFO - unknown - 🎮 Kiểm tra **GPU access** (truy cập GPU – quyền sử dụng card đồ họa)...
2025-08-12 05:40:28,552 - start_mining - DEBUG - unknown - [ROOT] Running: nvidia-smi -L
2025-08-12 05:40:28,571 - start_mining - DEBUG - unknown - [ROOT] Success: GPU 0: Tesla T4 (UUID: GPU-e0a08df4-b073-fee0-210b-318510ddca67)...
2025-08-12 05:40:28,572 - start_mining - DEBUG - unknown - [ROOT] Running: nvidia-smi --query-gpu=driver_version --format=csv,noheader
2025-08-12 05:40:28,589 - start_mining - DEBUG - unknown - [ROOT] Success: 550.90.07...
2025-08-12 05:40:28,590 - start_mining - INFO - unknown - ✅ Truy cập GPU: Available=True, Count=1
2025-08-12 05:40:28,590 - start_mining - INFO - unknown - ℹ️ **eBPF GPU telemetry** (giám sát GPU qua eBPF – theo dõi hiệu suất GPU) đã được DISABLE để tránh **memory conflicts** (xung đột bộ nhớ – lỗi tranh chấp RAM)
2025-08-12 05:40:28,590 - start_mining - INFO - unknown - 🌍 Chạy **centralized environment setup** (thiết lập môi trường tập trung – cấu hình chung cho hệ thống)...
2025-08-12 05:40:28,590 - setup_env - INFO - unknown - 🚀 **Starting cryptocurrency mining environment setup** (bắt đầu thiết lập môi trường khai thác tiền điện tử – starting crypto mining env setup).
2025-08-12 05:40:28,590 - setup_env - INFO - unknown - ✅ **Configuration loaded** (đã tải cấu hình – config đã được load) từ /app/mining_environment/config/system_params.json
2025-08-12 05:40:28,591 - setup_env - INFO - unknown - ✅ **Configuration loaded** (đã tải cấu hình – config đã được load) từ /app/mining_environment/config/environmental_limits.json
2025-08-12 05:40:28,591 - setup_env - INFO - unknown - ✅ **Configuration loaded** (đã tải cấu hình – config đã được load) từ /app/mining_environment/config/resource_config.json
2025-08-12 05:40:28,591 - setup_env - INFO - unknown - 🔍 **[SETUP] Starting memory configuration validation** (bắt đầu xác thực cấu hình bộ nhớ – starting memory config validation)...
2025-08-12 05:40:28,591 - setup_env - INFO - unknown - 🔍 [MEMORY VALIDATION] System RAM detected: 27.4GB
2025-08-12 05:40:28,591 - setup_env - INFO - unknown - 🔍 [MEMORY VALIDATION] Configured allocation: 96.0GB
2025-08-12 05:40:28,591 - setup_env - ERROR - unknown - 💀 [CRITICAL] Memory allocation (96.0GB) exceeds system capacity (27.4GB)
2025-08-12 05:40:28,591 - setup_env - ERROR - unknown - ❌ [MEMORY VALIDATION] Validation failed: Memory allocation overflow: 96.0GB > 27.4GB
2025-08-12 05:40:28,591 - setup_env - ERROR - unknown - ❌ **[SETUP] Memory configuration validation failed** (xác thực cấu hình bộ nhớ thất bại – memory config validation failed): Memory allocation overflow: 96.0GB > 27.4GB
2025-08-12 05:40:28,591 - setup_env - ERROR - unknown - 🚨 **[CRITICAL] System cannot start with invalid memory configuration** (hệ thống không thể khởi động với cấu hình bộ nhớ không hợp lệ – system can't start với memory config sai)
2025-08-12 05:40:28,591 - setup_env - ERROR - unknown - 💡 **[SOLUTION] Please fix memory settings in resource_config.json** (vui lòng sửa cài đặt bộ nhớ trong resource_config.json – fix memory settings trong file config)
root@e477c94e9576:/app#
