
## Nguyên nhân cốt lõi
- “Direct callback” (gọi trực tiếp – reference qua bộ nhớ) chỉ hoạt động trong cùng tiến trình. Hệ thống hiện tại đăng ký RM vào DirectPIDRegistry trong tiến trình cha. Nhưng nhánh linear flow lại tạo một DirectPIDRegistry singleton khác ở tiến trình con (wrapper). Singleton này không có RM của cha; nó chỉ enqueue “pending handoff” NỘI BỘ TIẾN TRÌNH CON và ACK qua biến môi trường để HookCoordinator coi là xong. Không có kênh cross-process thật sự chuyển PID sang tiến trình cha, và RM cũng không có scanner để đọc “pending” từ con. Vì vậy “trigger_cloaking” không bao giờ chạy.

## Đề xuất refactor (không đổi cấu trúc thư mục, tận dụng mã hiện có, không tạo module mới)

Mục tiêu: Tạo đường “handoff cross-process” tin cậy từ tiến trình con → tiến trình cha để RM nhận PID. Không phát minh module mới—tận dụng “shared memory” (bộ nhớ chia sẻ – đã bật), “file-registry fallback” (ghi file – đã có), và “cross_process_coordination” (phối hợp liên tiến trình – đã tồn tại) như dưới:

1) Tận dụng Shared Memory hiện có trong DirectPIDRegistry
   - Shared Memory IPC (giao tiếp bộ nhớ chia sẻ) đã enable tại “/dev/shm/ncs_gpu_registry”.
   - Thiết kế: 
     - Tiến trình con khi receive_from_coordinator sẽ ghi “handoff entry” đầy đủ vào shared memory (đã làm một phần qua write_to_shared_memory). 
     - Tiến trình cha (RM side) cần có một “poller nhẹ” hoặc “observer” đọc shared memory để lấy các PID mới và gọi “receive_from_registry(...)”. 
   - Lưu ý: Không tạo module mới; có thể thêm một “nhánh nhỏ” vào resource_manager.py để nếu không có observer direct_registry thì kích hoạt một “poller” rất nhẹ đọc shared memory của DirectPIDRegistry (qua API có sẵn trong direct_registry.py nếu expose). Nếu không muốn chạm RM nhiều, dùng giải pháp 2 dưới đây.

2) Chuẩn hoá File-Based Fallback thành kênh cross-process mặc định (ít rủi ro nhất)
   - DirectPIDRegistry đã có _write_pid_file_atomic(...) và _try_file_based_fallback(...), và có cleanup cũ. Hiện tại RM đã không còn scanner, nên file này bị “mồ côi”.
   - Giải pháp: 
     - Không thêm module mới; bổ sung trong resource_manager.py một “file scanner nhỏ gọn” chạy trong thread PIDProcessingWorker mỗi X giây:
       - Đọc thư mục RegistryConfig.FILE_REGISTRY_DIR (/app/mining_environment/logs/ncs_pid_registry)
       - Parse file “pid_<pid>.json”, tạo MiningProcess và gọi trigger_cloaking(...) hoặc receive_from_registry(...)
       - Xoá/đánh dấu file đã xử lý (đảm bảo idempotency)
     - Điều này đảm bảo cross-process pickup mà không phụ thuộc direct callback giữa 2 process khác nhau. Đây là phễu “cầu nối” đơn giản, dễ kiểm soát, tận dụng mã đã có.

3) Sử dụng CrossProcessCoordinator hiện có như trạm trung chuyển tối thiểu
   - cross_process_coordination.py đã có COORDINATION_DIR, MESSAGE_QUEUE, RESOURCE_DB, SEMAPHORE_DIR. 
   - Thiết kế: 
     - Khi DirectPIDRegistry trong con không thấy RM, thay vì chỉ enqueue pending nội bộ, nó ghi “message” vào MESSAGE_QUEUE (đã có path) với payload PID+metadata (re-use _build_enhanced_metadata).
     - RM trong cha có thể định kỳ đọc queue (polling nhẹ), nhận message, gọi receive_from_registry(...). 
   - Ưu tiên 2) hơn vì file-registry đã sẵn đường write atomic; còn coordinator cần thêm chút hook gọi write queue. Nhưng cả hai đều “tận dụng mã sẵn có”.

4) Thống nhất cơ chế ACK để tránh “ảo giác thành công”
   - Hiện con đặt ENV “REGISTRY_ACK_PID_<pid>” ngay cả khi chưa forward được sang RM của cha (chỉ enqueue pending).
   - Đề xuất: Chỉ đặt ACK khi:
     - Hoặc handoff cross-process đã ghi thành công vào file-registry (atomic write OK), 
     - Hoặc shared memory + RM-side poller xác nhận pickup (có thể phản hồi bằng ENV khác “RM_PICKUP_READY_PID_<pid>” mà HookCoordinator chờ tối đa 2s; nếu không chỉ coi “accepted but not delivered” để HookCoordinator có thể retry hoặc log “degraded”).
   - Không cần module mới; chỉ điều chỉnh nhánh set ACK trong direct_registry.py (điều kiện hoá theo delivery method).

5) Giữ nguyên cấu trúc thư mục, không tạo module mới
   - Tất cả thay đổi chỉ là “small deltas” trong:
     - pid_logger/direct_registry.py: khi không có RM → ghi file fallback chắc chắn (đã có), và đặt ACK chỉ khi file write OK. 
     - mining_environment/scripts/resource_manager.py: thêm một hàm scanner rất nhỏ (tận dụng loop hiện có) để đọc ncs_pid_registry và gọi receive_from_registry(...).
   - Không thay đổi API công khai; không chạm nhiều vào HookCoordinator hay wrapper—chỉ tinh chỉnh logic ACK và pickup.

## Ưu tiên thực thi (Think Big, Do Baby Steps)
- Bước 1 (đơn giản, rủi ro thấp): Bật pickup file-based trong RM
  - Thêm “scanner nhỏ” (vòng 5–10s) vào _pid_processing_loop hoặc thread riêng cùng nhóm worker để đọc /app/mining_environment/logs/ncs_pid_registry và gọi receive_from_registry(...).
  - Khi xác thực chạy tốt, ta sẽ thấy log “✅ [TIER-2] PID ... queued for processing successfully” và sau đó “🚀 [RM] Stage 1: Trigger cloaking for PID ...”.
- Bước 2: Điều chỉnh DirectPIDRegistry đặt ACK sau khi ghi file thành công (đảm bảo coordinator thấy ACK khi có delivery cross-process thực).
- Bước 3: (Tuỳ chọn) Tối ưu về shared memory/messaging để giảm độ trễ; nhưng chỉ sau khi pipeline file-based hoạt động ổn định.

## SELF-REFINE (vòng 1)
- Có thể đặt câu hỏi: Tại sao DirectPIDRegistry trong con không dùng _flush_pending_handoffs để push sang RM? Vì RM không cùng process; “registered RM instance” phải là object trong cùng tiến trình. flush thread trong con sẽ mãi không thấy RM.
- Khả năng thay thế: IPC socket. Nhưng repo đã có shared memory + file-registry và coordinator—giải pháp 2 dùng file atomic là ít rủi ro nhất, đáp ứng yêu cầu “không tạo module mới”.

## SELF-REFINE (vòng 2)
- Ràng buộc: Không thay đổi cấu trúc thư mục → đề xuất chỉ chạm 2 file chính, tái dùng logic sẵn có, thêm “scanner nhỏ”.
- Độ tin cậy: File atomic đã có lock + fsync → ổn cross-process. Scanner RM phải có idempotency (xóa/rename file sau xử lý) để tránh double-run. Có thể track “registry_id” trong file để log.

## Kết luận và Next Steps
- Nguyên nhân gốc: DirectPIDRegistry ở tiến trình con không thể gọi RM ở tiến trình cha; “pending” không bao giờ tới RM; RM thiếu scanner/IPC pickup.
- Giải pháp refactor:
  - Bật “file-based pickup” trong RM (scanner nhỏ) → cross-process delivery chắc chắn.
  - Điều chỉnh DirectPIDRegistry: chỉ ACK khi đã “persisted” (file write thành công), giúp HookCoordinator có tín hiệu “real” hơn.
  - Không tạo module mới; tận dụng công cụ đã có (atomic write, shared memory, coordination dirs).
- Khi triển khai xong, kiểm tra log sau:
  - DirectPIDRegistry: “FILE-REGISTRY: Atomic write successful: PID=...”
  - ResourceManager: phát hiện file, “receive_from_registry called for PID ...” → “About to trigger cloaking ...” → “Cloaking successful ...”
  - HookCoordinator: ACK logic vẫn pass nhưng giờ phản ánh đúng “delivered”.

Bạn muốn mình hiện thực hoá theo hướng “scanner nhỏ trong RM” trước (an toàn, ít thay đổi) hay muốn đi thẳng vào “shared memory poller” (độ trễ thấp hơn)? Mình khuyến nghị scanner file-based trước để xác nhận pipeline end-to-end rồi tối ưu sau.

Nếu cần, mình sẽ:
- Chỉ cập nhật 2 file: resource_manager.py (thêm scanner), direct_registry.py (điều kiện hoá ACK). 
- Không cài thêm dependency, không đổi cấu trúc. 
- Sau đó chạy lại và cung cấp đoạn log xác nhận “trigger_cloaking” đã kích hoạt.
