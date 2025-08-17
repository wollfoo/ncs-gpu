Tiến hành refactor code để khắc phục lỗi , đảm bảo refactor xong thì hãy dọn dẹp mã nguồn theo chuẩn clean code 
### Đề xuất hành động nhanh 
- Gắn `metrics_hub` dùng chung vào `CloakCoordinator/GpuCloakStrategy` mà `ResourceManager` sử dụng.  
- Đẩy metrics baseline vào hub trước khi Orchestrator return sớm (kể cả khi coordination fail).  
- Tăng khả năng chịu lỗi NVML bằng fallback dữ liệu từ log `stealth_inference_cuda`.  
- Giảm timeout/tăng retry trong coordinator để giảm return sớm, đảm bảo gọi OHC.  
- Đồng bộ log OHC sang `gpu_optimization.log` ở các sự kiện chính để dễ theo dõi.

- Bằng chứng log và code đã trích dẫn ở trên. Nếu cần, tôi có thể áp dụng các edits nhỏ theo hướng dẫn trên để bạn review.

- Tóm tắt tác động:
  - metrics bắt đầu có mẫu → `metrics.json` có nội dung.  
  - OHC chạy được sau coordination ổn định → `optimizedhardwarecontroller.log` có các log “Starting optimization…”, “Applied …”.  
  - Dễ quan sát hơn nhờ hợp nhất log sự kiện chính.
