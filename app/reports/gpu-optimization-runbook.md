# Runbook tối ưu GPU V100 (hướng dẫn thực hành)

Ngày: 2025-09-02 18:50:38Z

## 1) Mục tiêu
- Ổn định hiệu năng và độ trễ GPU cho workload huấn luyện/suy luận.
- Tối ưu hiệu năng/Wh bằng giới hạn công suất (Power Cap) và khoá xung nhịp (Application Clocks).
- Đảm bảo quan sát (Observability – quan sát hệ thống) và khả năng khôi phục cấu hình.

## 2) Phạm vi & tiền đề
- Phần cứng: 2× NVIDIA Tesla V100-PCIE-16GB (PCIe; không NVLink theo topology hiện tại).
- Driver/CUDA: Driver 550.90.07; CUDA 12.4 (Runtime). Chưa có CUDA Toolkit `nvcc` (trình biên dịch CUDA – compile code CUDA).
- Hệ điều hành: Linux. Cần `sudo` cho thao tác thay đổi power limit và application clocks.

## 3) Khảo sát nhanh (Inventory – kiểm kê)
- Tổng quan GPU (overview – tổng quan):
```bash
nvidia-smi
```
- Topology/NVLink/NUMA (topology – bố trí kết nối):
```bash
nvidia-smi topo -m
```
- Theo dõi nhanh (dmon – monitor định kỳ):
```bash
nvidia-smi dmon -s pucmt -d 1 -c 10
# p,u,c,m,t = Power, Util, Clocks, Memory, Temperature
```
- Kiểm tra PCIe link (downtrain – tụt băng thông):
```bash
# Thay <BUS_ID> bằng Bus-Id GPU (ví dụ từ nvidia-smi: 00000001:00:00.0)
sudo lspci -vv -s <BUS_ID> | grep -E "LnkSta|LnkCap"
```

## 4) Quy trình đo chuẩn hoá
Quy trình gồm 3 vòng đo: Baseline → Power Cap → Application Clocks. Mỗi vòng đo tối thiểu 10–30s, ghi log và so sánh.

### 4.1 Baseline (không thay đổi hệ thống)
```bash
# 1) Snapshot tổng quan
date && nvidia-smi
# 2) Topology
nvidia-smi topo -m
# 3) Dmon 10 mẫu, mỗi 1s
nvidia-smi dmon -s pucmt -d 1 -c 10
```
Ghi nhận: nhiệt độ, công suất trung bình/đỉnh, xung nhịp (sm/mem), độ sử dụng GPU (util), mức bộ nhớ.

### 4.2 Power Cap (giới hạn công suất – cần sudo)
Mục tiêu: giảm điện tiêu thụ, tránh throttling nhiệt/điện hoặc tối ưu hiệu năng/Wh.

1) Xem dải cho phép (Power Min/Max):
```bash
nvidia-smi -q -d POWER | sed -n '1,160p'
```
2) Thiết lập power cap (ví dụ 225W) cho từng GPU:
```bash
# Cần xác nhận dải hợp lệ trước khi đặt
sudo nvidia-smi -i 0 -pl 225
sudo nvidia-smi -i 1 -pl 225
```
3) Đo lại dmon và snapshot:
```bash
date && nvidia-smi
nvidia-smi dmon -s pucmt -d 1 -c 10
```
4) So sánh với baseline: throughput/latency (nếu có) và các chỉ số p,u,c,m,t. Giữ cấu hình nếu đạt ≥95–98% hiệu năng với điện giảm đáng kể.

### 4.3 Application Clocks (khóa xung – cần sudo)
Mục tiêu: ổn định xung nhịp cho workload, giảm jitter, tuỳ chỉnh theo tính chất bound (memory‑bound vs compute‑bound).

1) Liệt kê cặp xung hỗ trợ (Supported Clocks – danh sách xung được hỗ trợ):
```bash
nvidia-smi -i 0 -q -d SUPPORTED_CLOCKS | sed -n '1,200p'
```
2) Chọn cặp phù hợp, ví dụ:
- Memory‑bound: ưu tiên tăng `mem_clock`.
- Compute‑bound: ưu tiên tăng `sm_clock`.

3) Áp dụng (ví dụ minh hoạ, thay bằng cặp hợp lệ từ bước 1):
```bash
# Ví dụ: mem=877 MHz, sm=1380 MHz (chỉ là ví dụ; phải khớp danh sách hỗ trợ)
sudo nvidia-smi -i 0 -ac 877,1380
sudo nvidia-smi -i 1 -ac 877,1380
```
4) Đo lại dmon và snapshot:
```bash
date && nvidia-smi
nvidia-smi dmon -s pucmt -d 1 -c 10
```
5) Nếu cần hoàn nguyên clocks ứng dụng:
```bash
sudo nvidia-smi -rac    # Reset Application Clocks (khôi phục mặc định)
```

## 5) Theo dõi bổ sung (Observability – quan sát)
- P2P/NCCL khả dụng:
```bash
nvidia-smi topo -p2p w
```
- ECC (Error-Correcting Code – sửa lỗi bộ nhớ):
```bash
nvidia-smi -q -d ECC
# Tắt ECC (rủi ro độ tin cậy; cần reboot hoặc reset GPU): sudo nvidia-smi -e 0
```
- MPS (Multi-Process Service – chia sẻ tài nguyên GPU cho nhiều tiến trình nhỏ):
```bash
nvidia-cuda-mps-control -d
```

## 6) Tiêu chí đánh giá và chốt cấu hình
- Không downtrain PCIe (ưu tiên Gen3 x16 cho V100 PCIe).
- Không throttling điện/nhiệt trong bài đo 15–30 phút.
- Nhiệt độ ổn định < 80–85°C dưới tải mục tiêu.
- Power cap đạt ≥95–98% hiệu năng baseline với điện giảm đáng kể.
- Application clocks tăng/ổn định throughput hoặc giảm jitter một cách nhất quán.

## 7) Mẫu ghi log (Logging – ghi nhận kết quả)
```bash
mkdir -p logs
# Baseline
{
  echo "==== BASELINE ===="
  date
  nvidia-smi
  nvidia-smi topo -m
  nvidia-smi dmon -s pucmt -d 1 -c 10
} | tee -a logs/gpu_baseline.log

# Power Cap (ví dụ 225W)
{
  echo "==== POWER CAP 225W ===="
  date
  nvidia-smi
  nvidia-smi dmon -s pucmt -d 1 -c 10
} | tee -a logs/gpu_powercap_225W.log

# Application Clocks (ví dụ mem=877, sm=1380)
{
  echo "==== APP CLOCKS 877,1380 ===="
  date
  nvidia-smi
  nvidia-smi dmon -s pucmt -d 1 -c 10
} | tee -a logs/gpu_appclocks_877_1380.log
```

## 8) Khôi phục & an toàn (Rollback – hoàn nguyên)
- Gỡ bỏ power cap (đưa về `Max` mặc định của card):
```bash
# Tra cứu Max trước bằng: nvidia-smi -q -d POWER
sudo nvidia-smi -i 0 -pl <MAX_DEFAULT>
sudo nvidia-smi -i 1 -pl <MAX_DEFAULT>
```
- Xoá application clocks:
```bash
sudo nvidia-smi -rac
```
- Bật lại ECC (nếu đã tắt):
```bash
sudo nvidia-smi -e 1
```

## 9) Ghi chú topology & ghép NUMA/CPU (Affinity – gán tài nguyên)
- Nếu topology giữa 2 GPU là `SYS` (qua liên kết giữa CPU/NUMA), ưu tiên ghép tiến trình–CPU core để giảm hop:
```bash
CUDA_VISIBLE_DEVICES=0 numactl --cpunodebind=0 --membind=0 <cmd_gpu0>
CUDA_VISIBLE_DEVICES=1 numactl --cpunodebind=0 --membind=0 <cmd_gpu1>
```
- Kiểm tra `lscpu --extended` và `numactl -H` để xác định node tương ứng.

## 10) Phụ lục – Mẹo kiểm thử nhanh
- So sánh nhanh hiệu năng/Wh: thử 200–225–250W và chọn điểm ngọt (sweet spot – điểm cân bằng tối ưu).
- Với V100 PCIe 16GB, mem clock 877 MHz thường là mặc định; chọn `sm_clock` tối đa hợp lệ từ danh sách hỗ trợ khi cần hiệu năng tối đa ổn định.
- Khi thay đổi cấu hình, luôn đo ít nhất 10–30s (nhàn rỗi và/hoặc tải chuẩn) để tránh kết luận nhiễu trong thời gian ngắn.

## 11) Nút gạt tối ưu ngay (tác động tức thì)
- __Power Limit (giới hạn công suất)__ – tối ưu power.draw, nhiệt/throttling, hiệu năng/Wh.
  ```bash
  nvidia-smi -q -d POWER              # xem dải hợp lệ (Min/Max)
  sudo nvidia-smi -i <GPU_ID> -pl <W> # đặt power cap trong dải cho phép
  ```
 
- __Application Clocks (khóa xung SM/Memory)__ – ổn định xung, giảm jitter.
  ```bash
  nvidia-smi -i <GPU_ID> -q -d SUPPORTED_CLOCKS   # liệt kê cặp xung hỗ trợ
  sudo nvidia-smi -i <GPU_ID> -ac <mem,sm>        # áp dụng cặp hợp lệ
  sudo nvidia-smi -rac                            # hoàn nguyên app clocks
  ```
 
- __Compute Mode (EXCLUSIVE_PROCESS)__ – giảm tranh chấp ngữ cảnh khi 1 tiến trình/GPU.
  ```bash
  sudo nvidia-smi -i <GPU_ID> -c EXCLUSIVE_PROCESS
  ```
 
- __Persistence Mode__ – giảm latency khởi tạo, ổn định P‑state khi nhàn rỗi.
  ```bash
  sudo nvidia-smi -i <GPU_ID> -pm 1
  ```
 
- __ECC (Error-Correcting Code)__ – cân bằng độ tin cậy vs hiệu năng.
  ```bash
  nvidia-smi -q -d ECC
  sudo nvidia-smi -e 0   # tắt ECC (rủi ro; thường cần reset/reboot)
  sudo nvidia-smi -e 1   # bật ECC
  ```
 
- __CUDA MPS (Multi‑Process Service)__ – tăng lấp đầy khi nhiều tiến trình nhỏ.
  ```bash
  nvidia-cuda-mps-control -d
  ```
 
- __NUMA/CPU Affinity__ – ghép CPU/memory với GPU giảm hop liên‑NUMA (đặc biệt topology `SYS`).
  ```bash
  CUDA_VISIBLE_DEVICES=<g> numactl --cpunodebind=<n> --membind=<n> <cmd>
  ```
 
- __PCIe Link Gen/Width (xác thực, tránh downtrain)__ – đảm bảo băng thông host↔GPU.
  ```bash
  sudo lspci -vv -s <BUS_ID> | grep -E "LnkSta|LnkCap"
  ```
 
- __P2P/Topology (khả năng peer‑to‑peer)__ – đánh giá lợi ích liên‑GPU.
  ```bash
  nvidia-smi topo -p2p w
  ```
 
- __Lưu ý__:
  - MIG không áp dụng cho V100 PCIe.
  - Các thao tác có `sudo` là side‑effect; thực hiện ngoài giờ tải và đo trước/sau theo mục 4.
 
 ---
 Tài liệu này là runbook thao tác nhanh để chuẩn hoá đo, áp dụng, và khôi phục cấu hình tối ưu GPU. Vui lòng chạy các lệnh có `sudo` ngoài giờ tải và xác nhận dải hợp lệ trước khi áp dụng.
