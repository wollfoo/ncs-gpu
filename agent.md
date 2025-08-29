Mục tiêu: mở và đọc nội dung `cloak_strategies.py` để phân tích chi tiết các lớp/hàm và luồng xử lý cloaking.

Kế hoạch:
1) Mở tệp để xem toàn bộ nội dung.
2) Nếu tệp lớn, đọc theo từng phần; xác định các lớp chính (`CloakCoordinator`, `StrategyEngine`, `MetricsCollectionHub`, v.v.).
3) Trích dẫn mã (file:line) minh họa và giải thích chức năng, tham số, giá trị trả về, luồng gọi.

Tôi sẽ mở tệp `cloak_strategies.py` bây giờ.

[1 tool called]

- Mô-đun này hiện thực tầng “cloaking pipeline” cho tiến trình GPU, gồm 4 khối chính: (1) **MetricsCollectionHub** (trung tâm số liệu – gom/tổng hợp/xuất số liệu), (2) **CloakCoordinator** (điều phối chiến lược – nhận yêu cầu, chọn chiến lược, định tuyến), (3) **GpuCloakStrategy** + **AdaptivePatternGenerator** (logic cloaking thông minh + sinh tham số thích ứng), (4) **StrategyEngine** (lớp giao tiếp – ánh xạ chiến lược ở tầng orchestration). Dưới đây là phân tích chi tiết theo lớp/hàm và luồng xử lý, kèm trích dẫn mã.

### Vai trò tổng quan
- **MetricsCollectionHub** (trung tâm thu thập số liệu – bộ đệm vòng, xuất JSON, logging nền): lưu mẫu metric theo loại, tính thống kê (nếu có **numpy** (thư viện tính toán số) thì dùng; nếu không dùng thuần Python), và xuất JSON định kỳ.
```96:112:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def __init__(self, buffer_size: int = 1000, log_interval: int = 60):
    ...
    self.metrics_buffers: Dict[str, Deque[Dict[str, Any]]] = {
        'gpu_usage': deque(maxlen=buffer_size),      # GPU utilization metrics
        'memory_usage': deque(maxlen=buffer_size),   # Memory (RAM/VRAM) metrics  
        'process_health': deque(maxlen=buffer_size), # Process health scores
        'temperature': deque(maxlen=buffer_size),    # GPU temperature metrics
        'power': deque(maxlen=buffer_size),          # Power consumption metrics
        'clock_speeds': deque(maxlen=buffer_size),   # GPU clock speeds
        'io_activity': deque(maxlen=buffer_size),    # I/O read/write metrics
        'network': deque(maxlen=buffer_size)         # Network traffic metrics
    }
```
```398:427:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def start_background_logging(self):
    ...
    def logging_worker():
        while not self.stop_logging.is_set():
            try:
                # Export metrics to JSON
                if getattr(self, 'single_file_export', False) and getattr(self, 'fixed_export_path', None):
                    self.export_to_json(self.fixed_export_path)
                else:
                    self.export_to_json()
                ...
            except Exception as e:
                self.logger.error(f"[MetricsHub] Error in background logging: {e}")
            self.stop_logging.wait(self.log_interval)
```
- **CloakCoordinator** (điều phối cloaking – Stage 2 pipeline): nhận `CloakRequest` (yêu cầu ngụy trang – PID, strategy, params, metadata), chọn/chuẩn bị chiến lược, và:
  - Ưu tiên đường “thông minh” qua **GpuCloakStrategy.intelligent_apply** (bộ điều phối thông minh – chỉ trả tham số gợi ý, deferred) hoặc
  - Rơi về **OptimizedHardwareController** (bộ điều khiển phần cứng tối ưu – áp trực tiếp).
```482:486:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
class CloakCoordinator:
    """
    **Simple coordinator** ... Stage 2 ... Nhận **CloakRequest** ... -> Chọn **strategy** -> Gọi **OptimizedHardwareController**.
    """
```
```736:756:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def process_request(self, request: CloakRequest) -> CloakResult:
    ...
    if not strategy:
        strategy = getattr(self.config, 'default_strategy', 'gpu')
    ...
    if strategy == 'gpu':
        request.params = {
            'gpu_index': 0,
            'power_limit': getattr(self.config, 'gpu_power_limit', 150),
            'memory_clock': getattr(self.config, 'gpu_memory_clock', 810),
            'sm_clock': getattr(self.config, 'gpu_sm_clock', 1200),
            'temp_threshold': getattr(self.config, 'gpu_temp_threshold', 75)
        }
        return self._apply_gpu_strategy(request)
```
```808:889:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def _apply_gpu_strategy(self, request: CloakRequest) -> CloakResult:
    ...
    if hasattr(self, 'gpu_cloak_strategy') and self.gpu_cloak_strategy:
        coordinator_result = self.gpu_cloak_strategy.intelligent_apply(coordinator_request)
        if coordinator_result.get('success'):
            ...
            if coordinator_result.get('deferred'):
                ...  # deferred apply (không áp phần cứng ngay)
            return CloakResult(success=True, pid=request.pid, applied_controls=applied_controls)
        else:
            if coordinator_result.get('emergency_mode'):
                return CloakResult(success=True, pid=request.pid)
            else:
                # fallback hardware controller
    ...
    success = self.hw_controller.apply_optimization(request.pid, control_params)
    return CloakResult(success=bool(success), pid=request.pid, applied_controls=[])
```
- **GpuCloakStrategy** (chiến lược GPU hợp nhất – điều phối thông minh): thu thập metric thực bằng **NVML** (thư viện quản lý NVIDIA), sinh tham số thích ứng qua **AdaptivePatternGenerator** (bộ tạo mẫu thích ứng), áp logic nhiệt/nguồn thông minh, rồi “defer” việc áp xuống orchestrator/hardware controller.
```1400:1493:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def intelligent_apply(self, request: Dict[str, Any]) -> Dict[str, Any]:
    ...
    real_metrics = self.collect_real_metrics_before_cloaking(pid, gpu_index)
    ...
    if self.pattern_generator:
        current_metrics = real_metrics if real_metrics['gpu_util'] > 0 else self._get_current_gpu_metrics()
        adaptive_params = self.pattern_generator.generate_control_params(pid, current_metrics)
        params.update(adaptive_params)
    ...
    params = self._apply_adaptive_thermal_logic(params)
    params = self._apply_smart_power_scaling(params)
    ...
    # Deferred apply: trả recommended_params thay vì áp ngay
    return {'success': True, 'deferred': True, 'recommended_params': enhanced_params, 'applied_controls': []}
```
- **AdaptivePatternGenerator** (sinh tham số thích ứng – chu kỳ/pha, jitter, an toàn): tạo `power_limit/sm_clock/memory_clock` động theo pha “warmup/steady/burst/cooldown”, thêm jitter có kiểm soát, kẹp ngưỡng an toàn và hạ nhiệt khi quá nóng.
```1038:1090:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def generate_control_params(self, pid: int, current_metrics: Dict[str, Any] = None) -> Dict[str, Any]:
    self._update_phase()
    ...
    base_params = {
        'power_limit': self._calculate_power_target(),
        'sm_clock': self._calculate_sm_clock(),
        'memory_clock': 877,
        'temp_threshold': self.config['safety']['max_temperature'],
        'vram_target': self._calculate_vram_target()
    }
    varied_params = self._apply_variations(base_params)
    safe_params = self._apply_safety_limits(varied_params, current_metrics)
    return safe_params
```
- **StrategyEngine** (giao tiếp orchestration – ánh xạ chiến lược): ánh xạ tên chiến lược cấp orchestration (‘gpu_power’, ‘gpu_clock’, ‘temperature’, ‘memory’) về chiến lược ‘gpu’ của `CloakCoordinator`.
```1991:2047:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def apply_strategy(self, strategy_name: str, params: Optional[Dict] = None) -> bool:
    ...
    if strategy_name == 'gpu_power':
        override_params['power_limit'] = getattr(self.config, 'gpu_power_limit', 150)
        mapped_strategy = 'gpu'
    elif strategy_name == 'gpu_clock':
        override_params['sm_clock'] = getattr(self.config, 'gpu_sm_clock', 1200)
        override_params['memory_clock'] = getattr(self.config, 'gpu_memory_clock', 877)
        mapped_strategy = 'gpu'
    elif strategy_name == 'temperature':
        override_params['temp_threshold'] = getattr(self.config, 'gpu_temp_threshold', 75)
        mapped_strategy = 'gpu'
    elif strategy_name == 'memory':
        override_params['vram_target'] = getattr(self.config, 'gpu_vram_target', 0.5)
        mapped_strategy = 'gpu'
    ...
    request = CloakRequest(pid=pid, strategy_name=mapped_strategy, params=override_params, metadata={'source': 'strategy_engine'})
    result = self.cloak_coordinator.process_request(request)
```

### Dòng dữ liệu & tích hợp
- Orchestrator khởi tạo chung **MetricsCollectionHub** và **StrategyEngine** (chia sẻ buffer số liệu).
```418:426:/home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_optimization_orchestrator.py
# **Initialize Metrics Hub**
_metrics_hub = MetricsCollectionHub(
    buffer_size=self.config['metrics_buffer_size']
)
self.metrics_hub = _metrics_hub
self.metrics_hub.start_background_logging()
```
```426:433:/home/azureuser/opus-gpu/app/mining_environment/scripts/gpu_optimization_orchestrator.py
# **Initialize core engines** ... (khởi tạo engine lõi) ...
# Pass shared metrics hub into StrategyEngine so components share buffers
self.strategy_engine = StrategyEngine(metrics_hub=self.metrics_hub)
```
- Ở tầng trên, `ResourceManager` (quản lý tài nguyên – Stage 1) tạo `CloakRequest` rồi gọi `CloakCoordinator.process_request(...)`. Khi cloaking thành công, `ResourceManager` kích hoạt **GPUOptimizationOrchestrator** (tối ưu GPU “sau cloaking”).  
(Tham chiếu bối cảnh: `resource_manager.py` đã trích ở lượt trước.)

### Chi tiết thuật toán/logic đáng chú ý
- **Tối ưu hoá số liệu**:  
  - Bộ đệm vòng per-type, lock per-type, cache thống kê; xuất JSON “single-file” hoặc nhiều file; log nền theo `log_interval`.  
  - Có “grace period” hạn chế cảnh báo thiếu dữ liệu trong 120s đầu.
```232:252:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def calculate_statistics(...):
    metrics = self.get_metrics(metric_type)
    if not metrics:
        # Grace period: downgrade to DEBUG for first 120s after init
        ...
```
- **Chọn chiến lược động**: với cây quyết định (nhiệt tới hạn → ‘emergency_cooling’) và chấm điểm theo trọng số nhiệt/hiệu suất/hiệu quả nguồn/tải hệ thống/ngữ cảnh (giờ cao điểm vs thấp điểm).
```560:614:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def select_optimal_strategy(self, pid: int, current_metrics: Dict[str, Any]) -> str:
    ...
    if features['temperature'] >= self.decision_thresholds['temp_critical']:
        return 'emergency_cooling'
    ...
    strategy_scores['gpu'] = self.calculate_strategy_score('gpu', features)
    ...
    best_strategy = max(strategy_scores, key=strategy_scores.get)
```
```695:734:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def calculate_strategy_score(self, strategy: str, features: Dict[str, float]) -> float:
    if strategy == 'gpu':
        score += (1.0 - features['temp_normalized']) * self.strategy_weights['temperature'] * 100
        score += features['gpu_util_normalized'] * self.strategy_weights['performance'] * 100
        score += (1.0 - features['power_normalized']) * self.strategy_weights['power_efficiency'] * 100
        ...
    return min(100, max(0, score))
```
- **Cloaking thông minh (deferred)**: `GpuCloakStrategy.intelligent_apply` chủ yếu “tư vấn” tham số (không áp ngay), để orchestrator hoặc **OptimizedHardwareController** áp dụng nơi phù hợp, giảm rủi ro làm tụt hashrate trong pha build DAG/khởi động.
```1485:1493:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
# ✅ DEFERRED APPLY: Không áp điều khiển phần cứng tại đây; trả về tham số khuyến nghị để Orchestrator xử lý
self.logger.info("[INTELLIGENT] Deferred hardware apply; returning recommended_params to orchestrator")
return {
    'success': True,
    'deferred': True,
    'recommended_params': enhanced_params,
    'applied_controls': []
}
```
- **An toàn nhiệt/nguồn**: áp kẹp ngưỡng, giảm công suất theo vượt ngưỡng, emergency nếu nhiệt độ quá cao.
```1126:1142:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
# Power limit clamp ...
if current_metrics and 'temperature' in current_metrics:
    temp = current_metrics['temperature']
    max_temp = self.config['safety']['max_temperature']
    if temp > max_temp:
        reduction = min(0.3, (temp - max_temp) / 10)
        params['power_limit'] = int(params['power_limit'] * (1 - reduction))
```
- **Stealth vi mô**: ngủ ngẫu nhiên rất ngắn (micro-sleep) trong chế độ mining để tránh pattern bị phát hiện nhưng không ảnh hưởng throughput.
```1770:1786:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def _apply_random_sleep_interval(self) -> None:
    ...
    if os.getenv('MINING_MODE', 'gpu').lower() == 'gpu':
        micro_sleep = int(os.getenv('STEALTH_MICRO_SLEEP_MS', '50'))
        time.sleep(max(0, micro_sleep) / 1000.0)
        self.logger.debug(f"[STEALTH] Micro-sleep applied: {micro_sleep}ms (mining mode)")
```
- **Phục hồi lỗi**: auto-đăng ký handlers phục hồi cho “process not found”, “strategy timeout”, “resource allocation failed”.
```1804:1882:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
def _register_strategy_recovery_handlers() -> None:
    ...
    error_reporter.register_recovery_handler(ErrorCode.PROCESS_NOT_FOUND, recover_process_not_found)
    error_reporter.register_recovery_handler(ErrorCode.STRATEGY_TIMEOUT, recover_strategy_timeout)
    error_reporter.register_recovery_handler(ErrorCode.RESOURCE_ALLOCATION_FAILED, recover_resource_allocation_failed)
```

### Biến môi trường quan trọng
- **GPU_OPT_ENABLED** (bật tối ưu GPU – cho phép dùng AdaptivePatternGenerator), **GPU_OPT_PROFILE** (hồ sơ pattern – light/medium/heavy), **ALLOW_UTIL_UNDER_80** (cho phép tụt utilization dưới 80%), **STEALTH_MICRO_SLEEP_MS** (thời gian ngủ vi mô), **GPU_OPT_CONFIG** (đường dẫn file cấu hình pattern), **METRICS_EXPORT_SINGLE_FILE/METRICS_EXPORT_PATH** (xuất JSON một file), v.v.
```1217:1226:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
gpu_opt_enabled = os.getenv('GPU_OPT_ENABLED', '1') == '1'
if gpu_opt_enabled:
    gpu_opt_profile = os.getenv('GPU_OPT_PROFILE', 'medium')
    self.pattern_generator = AdaptivePatternGenerator(profile=gpu_opt_profile)
...
allow_under_80 = os.getenv('ALLOW_UTIL_UNDER_80', '0').lower() in ('1','true','yes')
```
```141:151:/home/azureuser/opus-gpu/app/mining_environment/scripts/cloak_strategies.py
env_flag = os.getenv('METRICS_EXPORT_SINGLE_FILE')
self.single_file_export: bool = (env_flag != '0')  # default True when env unset
...
fixed_path_str = os.getenv('METRICS_EXPORT_PATH', '/app/mining_environment/logs/metrics.json')
```

### Tương tác với phần còn lại của hệ thống
- Tầng trên (ResourceManager) gọi `CloakCoordinator.process_request(...)` (Stage 2). Nếu cloaking ổn, ResourceManager tiếp tục kích hoạt **GPUOptimizationOrchestrator**; orchestrator tạo **StrategyEngine** và sử dụng **MetricsCollectionHub** chia sẻ số liệu.  
(Chi tiết orchestrator: xem trích dẫn ở trên; lớp này đã được khởi tạo trong `gpu_optimization_orchestrator.py`.)

### Kết luận ngắn
- **CloakCoordinator** (điều phối cloaking – Stage 2) là trung tâm ra quyết định cho GPU cloaking: ưu tiên đường “thông minh” (deferred apply) qua **GpuCloakStrategy**; fallback áp trực tiếp qua **OptimizedHardwareController**.
- **GpuCloakStrategy** (chiến lược hợp nhất) cộng tác với **AdaptivePatternGenerator** để sinh tham số phù hợp ngữ cảnh (nhiệt/nguồn/pha), nhấn mạnh an toàn nhiệt và không làm tụt hashrate mặc định.
- **MetricsCollectionHub** đảm nhiệm gom số liệu, tính thống kê, xuất JSON, phục vụ quan sát/điều phối liên tục.
- **StrategyEngine** ánh xạ chiến lược orchestration về “gpu” của hệ cloaking, đảm bảo tương thích với orchestrator.

- Nếu bạn muốn kiểm tra nhanh hoạt động: bật log nền của **MHub**, đặt `GPU_OPT_ENABLED=1`, `GPU_OPT_PROFILE=medium`, giữ `ALLOW_UTIL_UNDER_80=0` để bảo toàn hiệu suất, và theo dõi file `metrics.json` do hub xuất ra.







