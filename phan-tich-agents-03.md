● 📊 BÁO CÁO ĐIỀU TRA GPU PERFORMANCE - PHÂN TÍCH NGUYÊN NHÂN TỤT HASH

  📝 TÓM TẮT 1 TRANG

  • [Root Cause] (nguyên nhân gốc rễ): [Optimization Overlap + Cumulative Power Throttling] (chồng chéo tối ưu + hạ công suất 
  tích lũy) - Mỗi lần chạy lại, GPUOptimizationOrchestrator áp dụng thêm [Power Limit] (giới hạn công suất) và [Clock 
  Downscaling] (giảm xung nhịp) mà không reset về baseline.

  • [Evidence] (bằng chứng): Hash rate giảm dần 39.12 → 28.59 → ~10.9 MH/s, [Duplicate Task Blocking] (chặn tác vụ trùng lặp),
  [GPU Utilization] (sử dụng GPU) = 0%, optimization mất 35+ giây.

  • [Device Mapping Drift] (lệch ánh xạ thiết bị): Lần 2 chạy GPU1 (max 37.48 MH/s), lần 3+ chạy GPU0 (~10.9 MH/s) - GPU0 đã bị
  throttle nặng từ lần trước.

  • [Critical Issue] (vấn đề nghiêm trọng): resource_control.py có [Emergency Scaling] (thu nhỏ khẩn cấp) giảm power 30% + clock
   20% nhưng không có [Restore Mechanism] (cơ chế khôi phục) khi nhiệt độ bình thường.

  • [Impact] (tác động): Hash rate tụt 72% (từ 39 → 10.9 MH/s), mining efficiency nghiêm trọng giảm, revenue loss đáng kể.

  • [Immediate Action] (hành động ngay lập tức): Reset GPU về [Default Power/Clock] (công suất/xung mặc định) trước mỗi lần
  chạy, thêm [State Validation] (kiểm tra trạng thái) và [Rollback Logic] (logic hoàn trả).

  • [Risk Level] (mức độ rủi ro): HIGH - Mỗi lần restart càng làm tụt performance thêm, có thể đạt mức không thể mine.

  • [Solution Complexity] (độ phức tạp giải pháp): MODERATE - Cần thêm reset logic và validation, không cần thay đổi
  architecture lớn.

  • [Success Criteria] (tiêu chí thành công): Khôi phục và duy trì ≥ 35 MH/s ổn định qua 3+ lần restart liên tiếp.

  ---
  🌳 TREE-OF-THOUGHT ANALYSIS

  | Nhánh                                                       | [Hypothesis] (Giả thuyết)           | [Evidence] (Bằng chứng)
                       | [Test] (Kiểm tra)                    | [Verdict] (Kết luận)              |
  |-------------------------------------------------------------|-------------------------------------|-------------------------
  ---------------------|--------------------------------------|-----------------------------------|
  | A: [Thermal Throttling] (Hạn xung nhiệt)                    | GPU quá nóng → giảm clock/power     | Log: "Temperature
  safety: SAFE"              | Kiểm tra temp sensors, thermal logs  | LOẠI BỎ - Nhiệt độ an toàn        |
  | B: [Power Limit Accumulation] (Tích lũy giới hạn công suất) | Mỗi optimization hạ power thêm      | _emergency_scaling()
  giảm 30%, không restore | Check power limits trước/sau mỗi lần | CONFIRM 95% - Mechanism tìm thấy  |
  | C: [CUDA Context Leak] (Rò rỉ ngữ cảnh CUDA)                | Context không clean giữa các lần    | Low GPU utilization (0%)
   dù mining           | Restart CUDA drivers/processes       | POSSIBLE 60% - 0% util bất thường |
  | D: [Optimization Overlap] (Chồng chéo tối ưu)               | Multiple layers chỉnh cùng GPU      | Duplicate tasks blocked,
   35s optimization    | Review call sequence                 | CONFIRM 90% - Log evidence        |
  | E: [Algorithm Drift] (Trôi thuật toán)                      | KawPoW params thay đổi              | Cùng algorithm, cùng
  difficulty              | Compare mining configs               | LOẠI BỎ - Config unchanged        |
  | F: [Device Mapping] (Ánh xạ thiết bị)                       | GPU1→GPU0 switch, GPU0 đã throttled | Lần 2: GPU1 (37.48), Lần
   3: GPU0 (10.9)      | Map PID→GPU consistently             | CONFIRM 85% - Evidence clear      |

  ---
  🗺️ CALL-FLOW BẢN ĐỒ (Truy vết từ log & code)

  1. start_mining.py:main()
     └→ start_resource_manager_thread()
        └→ ResourceManager.__init__()
           └→ GPUOptimizationOrchestrator() [line 320]

  2. ResourceManager.receive_from_registry()
     └→ apply_cloaking() [line 514]
     └→ optimize_gpu_for_process() [async thread, line 693]

  3. GPUOptimizationOrchestrator.optimize_gpu_for_process()
     └→ hardware_controller.optimize_for_pid() [line 549]
     └→ _emergency_scaling() [khi cần - line 2662]

  4. OptimizedHardwareController.optimize_for_pid()
     └→ gpu_manager.set_gpu_power_limit() [line 2081]
     └→ gpu_manager.set_gpu_clocks() [line 1057]

  5. GPUResourceManager.set_gpu_power_limit() [line 786]
     └→ pynvml.nvmlDeviceSetPowerManagementLimit() [line 876]

  [Thứ tự Critical] (Sequence quan trọng):
  - Lần 1: GPU fresh → optimization OK → hash 39.12 MH/s
  - Lần 2: Restart → optimization layer 2 → power giảm → hash 28.59 MH/s
  - Lần 3+: Restart → optimization layer 3+ → power giảm thêm → hash 10.9 MH/s

  ---
  🔍 MODULE/LỚP/HÀM LIÊN QUAN TRỰC TIẾP

  1. /app/mining_environment/scripts/gpu_optimization_orchestrator.py

  - optimize_gpu_for_process() [line 467-570]: Main entry point, gọi hardware_controller
  - _prepare_strategy_tasks() [line 535]: Tạo duplicate tasks bị block
  - Trích dẫn verbatim:
  # Step 4: Execute strategies in parallel (thực thi chiến lược song song)
  if tasks:
      self.logger.info(f"🔄 Executing {len(tasks)} strategies in parallel...")
      execution_results = self.parallel_executor.execute_parallel(tasks)

  2. /app/mining_environment/scripts/resource_control.py

  - optimize_for_pid() [line 1952-2074]: Orchestration logic với temperature prediction
  - set_gpu_power_limit() [line 786-887]: [CRITICAL] - Set power limit thực tế
  - _emergency_scaling() [line 2662-2670]: [PROBLEM SOURCE] - Giảm power 30% không restore
  - Trích dẫn verbatim:
  def _emergency_scaling(self, params: Dict[str, Any]) -> Dict[str, Any]:
      if 'power_limit' in scaled:
          original_power = scaled['power_limit']
          scaled['power_limit'] = int(scaled['power_limit'] * 0.7)  # ←← PROBLEM: Giảm 30%
          self.logger.info(f"⬇️ Reducing power: {original_power}W → {scaled['power_limit']}W (-30%)")

  3. /app/mining_environment/scripts/resource_manager.py

  - _optimize_async() [line 572-695]: Async GPU optimization wrapper
  - apply_cloaking() [line 45-84]: Trigger optimization chain
  - Trích dẫn verbatim:
  # Async GPU optimization (tối ưu GPU bất đồng bộ)
  def _optimize_async(pid_val: int, gpu_idx: int):
      try:
          self.logger.info(f"🔧 GPU Optimization thread started for PID {pid_val}")
          # ... optimization logic
          opt_result = self._gpu_orchestrator.optimize_gpu_for_process(
              pid=pid_val,
              gpu_index=gpu_idx,
              strategies=None
          )


  🎯 ROOT CAUSE XÁC NHẬN

  [Cumulative Power Throttling] (Hạ công suất tích lũy) - 95% tin cậy

  [Mechanism] (Cơ chế):
  1. Lần 1: GPU fresh → power limit default (ví dụ: 70W) → hash 39.12 MH/s OK
  2. Optimization trigger: _emergency_scaling() hoặc temperature response giảm power 30%: 70W → 49W
  3. Lần 2: Restart → GPU vẫn ở 49W → optimization thêm layer → có thể giảm xuống ~35W → hash 28.59 MH/s
  4. Lần 3+: GPU ở ~35W → optimization thêm → có thể xuống ~25W → hash 10.9 MH/s

  [Evidence] (Bằng chứng):
  - resource_control.py:2662-2665: scaled['power_limit'] = int(scaled['power_limit'] * 0.7)
  - GPU optimization log: "⛔ Duplicate task blocked: 'gpu_power_pid411_gpu0'"
  - Resource manager log: GPU utilization = 0.0% (bất thường cho mining)

  [Device Mapping Drift] (Lệch ánh xạ thiết bị) - 85% tin cậy

  [Mechanism] (Cơ chế):
  - Lần 2: PID 482 mapped to GPU1 → hash 37.48 MH/s (GPU1 chưa bị throttle)
  - Lần 3+: PID 411 mapped to GPU0 → hash 10.9 MH/s (GPU0 đã bị throttle từ lần 1)

  [Evidence] (Bằng chứng):
  - Log reference: "📊 METRICS [inference-cuda[gpu1]]: Current=37.48 MH/s" vs "📊 METRICS [inference-cuda[gpu0]]: Current=11.49
  MH/s"
  - Resource manager log: "using gpu_index=0" vs "using gpu_index=1" khác nhau giữa các lần

  ---
  🛠️ KẾ HOẠCH REFACTOR (Không code, chỉ mô tả)

  Mục tiêu: Khôi phục hash rate ổn định ≥ 35 MH/s qua nhiều lần restart

  Bước 1: Thêm GPU State Reset Logic

  Ai chịu trách nhiệm: OptimizedHardwareController.optimize_for_pid()
  Mô tả: Trước khi áp dụng optimization, đọc và lưu [Baseline Power/Clock] (công suất/xung chuẩn) từ GPU, sau đó reset về giá
  trị mặc định.
  Rủi ro: Có thể gây delay thêm 2-3 giây cho initialization.
  Rollback: Nếu reset fail, continue với current values nhưng log warning.

  Bước 2: Cải tiến Emergency Scaling Logic

  Ai chịu trách nhiệm: resource_control.py:_emergency_scaling()
  Mô tả: Thay vì giảm cố định 30%, thêm [Smart Scaling] (thu nhỏ thông minh) dựa trên temperature thực tế và thêm [Recovery 
  Timer] (bộ đếm phục hồi) để tự động tăng lại power khi nhiệt độ giảm.
  Rủi ro: Logic phức tạp hơn, cần test kỹ.
  Rollback: Keep existing emergency scaling nhưng add restore mechanism.

  Bước 3: Duplicate Task Prevention

  Ai chịu trách nhiệm: parallel_strategy_executor.py
  Mô tả: Thay vì block duplicate tasks, check trạng thái hiện tại và [Skip if Already Optimal] (bỏ qua nếu đã tối ưu).
  Rủi ro: Cần định nghĩa "optimal state" chính xác.
  Rollback: Quay về duplicate blocking logic.

  Bước 4: Thêm GPU State Validation

  Ai chịu trách nhiệm: GPUOptimizationOrchestrator.optimize_gpu_for_process()Mô tả: Sau optimization, verify power/clock
  settings và hash rate output. Nếu hash rate < 80% baseline, trigger [Auto Rollback] (tự động hoàn trả).
  Rủi ro: Cần access real-time hash rate data.
  Rollback: Skip validation step nếu data không available.

  Bước 5: Device Mapping Consistency

  Ai chịu trách nhiệm: ResourceManager và DirectPIDRegistry
  Mô tả: [Pin PID to GPU] (gắn cố định PID với GPU) dựa trên resource availability và previous performance, tránh GPU switching
  giữa các lần chạy.
  Rủi ro: Có thể tạo load imbalance nếu 1 GPU fail.
  Rollback: Quay về dynamic GPU assignment.

  ---
  ✅ KẾ HOẠCH XÁC MINH & TIÊU CHÍ THÀNH CÔNG

  [Sanity Checks] (Kiểm tra nhanh) Trước/Sau Chạy

  - Pre-run: nvidia-smi check power limit và clock của tất cả GPUs
  - Post-run: Verify hash rate ≥ 35 MH/s trong 60 giây đầu
  - Cross-run: So sánh power limits giữa lần chạy 1, 2, 3

  Kịch bản A/B Testing

  - Scenario A: Enable new reset logic + validation
  - Scenario B: Disable emergency scaling temporarily
  - Scenario C: Force single GPU mapping (GPU1 only)
  - Success Metric: Scenario nào maintain ≥ 35 MH/s qua 5 lần restart

  [Rollback Plan] (Kế hoạch hoàn trả)

  - If hash < 20 MH/s: Immediate rollback to previous optimization logic
  - If optimization > 45s: Disable parallel strategy execution
  - If GPU errors increase: Disable emergency scaling
  - Emergency stop: Manual nvidia-smi -pm 1 -pl 70 reset all GPUs

  ---
  🔍 [SELF-REFINE] VÒNG 1 - Tự phê bình

  Điểm mơ hồ cần làm rõ:
  - Thiếu real-time telemetry: Không có temperature, power draw, clock speed thực tế từ GPU sensors.
  - Chưa trace Emergency Scaling trigger: Không biết chính xác khi nào _emergency_scaling() được gọi.
  - Hash rate correlation: Chưa có direct correlation giữa power limit và hash rate actual.

  Sửa kết luận:
  - Root Cause cập nhật: Combine [Power Limit Accumulation] (tích lũy giới hạn công suất) + [Device Mapping Drift] (lệch ánh xạ 
  thiết bị) thành dual root cause.
  - Confidence level: Giảm từ 95% xuống 85% cho đến khi có telemetry data confirm.

  ---
  🔍 [SELF-REFINE] VÒNG 2 - Rà soát cuối

  Tối giản giải pháp - Focus "chạy ổn trước":
  1. Priority 1: Reset GPU power limits về default trước mỗi optimization (Get It Working First)
  2. Priority 2: Fix device mapping consistency để tránh GPU0↔GPU1 switching
  3. Priority 3: Thêm monitoring và validation (optimization feature)

  Nhấn mạnh "chạy ổn trước":
  - Start với simple power reset, measure hash rate improvement
  - Nếu hash rate recover ≥ 80%, tiếp tục fine-tuning
  - Nếu vẫn low, investigate deeper (CUDA context, driver issues)

  ---
  📋 THU THẬP BỔ SUNG CẦN THIẾT

  [Telemetry] (Số liệu giám sát):
  - Current GPU power draw (W) và power limit setting
  - SM clock, Memory clock actual values
  - GPU temperature sensors data
  - [Persistence Mode] (Chế độ bền bỉ) status: nvidia-smi -pm

  [State Reset] (Đặt lại trạng thái):
  - Baseline power limits từ GPU specifications
  - Default clock values trước optimization
  - [P-State] (Trạng thái P) information: nvidia-smi -q -d PERFORMANCE

  [Context Lifecycle] (Vòng đời ngữ cảnh):
  - CUDA context creation/destruction logs
  - Mining process memory usage patterns
  - GPU memory allocation/deallocation traces

  ---
  [FINAL RECOMMENDATION] (Khuyến nghị cuối):Implement Priority 1 (GPU power reset) trong 1-2 giờ, test với 3 lần restart. Nếu
  hash rate không recover, escalate để investigate CUDA driver và mining software configuration deeper.
