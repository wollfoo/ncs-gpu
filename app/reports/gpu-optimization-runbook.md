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

## 0) Pre-flight GPU Reset (mặc định có guard)

- Mục tiêu: xử lý tình trạng kẹt P‑state/xung sau crash/điều chỉnh clocks/power lặp lại. Reset có điều kiện, __mặc định bật__.
- Kích hoạt/Tắt bằng biến môi trường:
  - `ENABLE_GPU_RESET_ON_START=1` (mặc định). Tắt bằng `0/false/no`.
  - `GPU_RESET_COOLDOWN_MIN=<phút>` (mặc định `10`) – tránh reset lặp.
  - `GPU_RESET_STAMP_PATH=<file>` (mặc định `/tmp/.gpu_reset_stamp`).
- Guard an toàn & trình tự thực thi (được tự động hoá trong entrypoint):
  1) Dừng CUDA MPS (best effort): `echo quit | nvidia-cuda-mps-control`.
  2) Xác nhận GPU rảnh: `nvidia-smi --query-compute-apps=pid --format=csv,noheader` phải rỗng.
  3) Kiểm tra năng lực reset: có `nvidia-smi`; nếu reset không hỗ trợ (hypervisor/primary display) → __bỏ qua an toàn__.
  4) Reset tuần tự từng GPU: `nvidia-smi --gpu-reset -i <g>`; ngủ ngắn 2s giữa các GPU.
  5) Áp lại cấu hình tối thiểu: `-pm 1`, `-c EXCLUSIVE_PROCESS` (tùy chọn: `-pl`, `-ac` theo mục 11/4.3).
  6) Ghi log/xác minh: `date && nvidia-smi`, `nvidia-smi dmon -s pucmt -d 1 -c 3`.
  7) Cooldown: đóng dấu thời gian vào `GPU_RESET_STAMP_PATH`; bỏ qua nếu chưa đủ `GPU_RESET_COOLDOWN_MIN` phút.
- Vị trí tích hợp: `app/start_mining.py` – khối PRE-FLIGHT GPU hard reset được gọi ở đầu `main()` qua `perform_hard_gpu_reset(logger)` với gating bằng các event `GPU_RESET_COMPLETED`/`GPU_RESET_SUCCESS`; reset diễn ra đúng một lần khi khởi động.
- Ví dụ cấu hình ENV:
  ```bash
  # Mặc định bật
  ENABLE_GPU_RESET_ON_START=1
  # Tắt nhanh
  ENABLE_GPU_RESET_ON_START=0
  # Tuỳ chọn
  GPU_RESET_COOLDOWN_MIN=10
  GPU_RESET_STAMP_PATH=/tmp/.gpu_reset_stamp
  ```
- Ghi chú: Cơ chế `maybe_sudo` tự động dùng `sudo` nếu có; nếu không, lệnh sẽ chạy trực tiếp. Reset có thể bị chặn bởi môi trường; pipeline vẫn tiếp tục với cảnh báo.

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
 
 ## 12) Nút gạt nâng cao (BIOS/OS/IRQ…)
 - __BIOS/Platform__ (thiết lập nền tảng – Above 4G Decoding/PCIe Native Control/tắt ASPM): đảm bảo không downtrain PCIe và hỗ trợ BAR lớn.
   ```bash
   # Kiểm tra sau khi boot (xem Gen/Width, LnkSta/LnkCap)
   sudo lspci -vv -s <BUS_ID> | grep -E "LnkSta|LnkCap"
   ```
   - Lưu ý: cấu hình trong BIOS; thao tác theo vendor, cần bảo trì ngoài giờ.
 
 - __BMC/IPMI Fan Profile__ (hồ sơ quạt – Performance/Full Speed): tăng lưu lượng gió, hạ nhiệt, giảm nguy cơ throttling.
   ```bash
   # Ví dụ (tuỳ vendor; có thể thao tác qua giao diện BMC)
   ipmitool raw ...
   ```
   - Lưu ý: V100 PCIe thường không điều khiển quạt trực tiếp qua `nvidia-smi`.
 
 - __CPU Power Governor__ (chế độ tần số CPU – performance) và __tuned-adm__ (bộ cấu hình hiệu năng – latency-performance): giảm jitter/độ trễ host↔GPU.
   ```bash
   sudo cpupower frequency-set -g performance
   # hoặc nếu có tuned-adm
   sudo tuned-adm profile latency-performance
   ```
 
 - __IRQ Affinity__ (ghim ngắt NVIDIA về core "local" – giảm jitter):
   ```bash
   grep -i nvidia /proc/interrupts
   echo <MASK_HEX> | sudo tee /proc/irq/<IRQ>/smp_affinity
   ```
   - Lưu ý: chọn mask đúng theo sơ đồ core/NUMA; thử nghiệm và rollback rõ ràng.
 
 - __IOMMU/ACS__ (cấu hình cô lập I/O – tăng P2P/độ trễ tốt hơn trong vài cấu hình):
   - Tuỳ môi trường: kernel params như `intel_iommu=off|on,pt` hoặc điều chỉnh ACS có rủi ro bảo mật; chỉ làm khi hiểu rõ topology.
 
 - __PCIe MRRS/MPS__ (Max Read Request Size/Max Payload Size – tinh chỉnh PCIe nâng cao):
   ```bash
   # Cần hiểu root port và device; ví dụ dùng setpci (advanced)
   sudo setpci -s <BUS_ID> 68.B=xx   # MRRS
   sudo setpci -s <BUS_ID> 64.B=yy   # MPS
   ```
   - Lưu ý: advanced; cần quy trình đo/rollback chặt chẽ.
 
 - __THP/HugePages__ (Transparent Huge Pages – điều khiển trang bộ nhớ để giảm jitter):
   ```bash
   # Thử cấu hình thận trọng (quan sát trước/sau)
   echo madvise | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
   # Hoàn nguyên: echo always | sudo tee /sys/kernel/mm/transparent_hugepage/enabled
   ```
 
 - __NUMA nâng cao__ (cô lập core cho tiến trình GPU; điều phối irqbalance):
   ```bash
   taskset -c <cores> numactl --cpunodebind=<n> --membind=<n> <cmd>
   # cấu hình irqbalance để không đẩy IRQ vào core của tiến trình
   ```
 
 - __DCGM Policies/Health__ (giám sát & policy – dcgmi):
   ```bash
   # Cài DCGM rồi sử dụng
   dcgmi discovery -l
   dcgmi policy --set ...
   ```
 
 - __GPU Reset__ (đặt lại GPU khi không có tiến trình sử dụng – làm sạch trạng thái lạ):
   ```bash
   sudo nvidia-smi --gpu-reset -i <GPU_ID>
   ```
 
 - __Tự động hoá sau reboot (systemd)__ (áp cấu hình đã chốt – power limit, persistence, compute mode, clocks):
   ```bash
   # /etc/systemd/system/gpu-tune.service (ví dụ)
   [Unit]
   Description=Apply GPU tuning at boot
   After=multi-user.target
   
   [Service]
   Type=oneshot
   ExecStart=/usr/bin/nvidia-smi -pm 1
   ExecStart=/usr/bin/nvidia-smi -i 0 -c EXCLUSIVE_PROCESS
   ExecStart=/usr/bin/nvidia-smi -i 1 -c EXCLUSIVE_PROCESS
   # ExecStart=/usr/bin/nvidia-smi -i 0 -pl <W>
   # ExecStart=/usr/bin/nvidia-smi -i 1 -pl <W>
   # ExecStart=/usr/bin/nvidia-smi -i 0 -ac <mem,sm>
   # ExecStart=/usr/bin/nvidia-smi -i 1 -ac <mem,sm>
   RemainAfterExit=yes
   
   [Install]
   WantedBy=multi-user.target
   ```
   - Kích hoạt: `sudo systemctl enable --now gpu-tune` (sau khi chỉnh tham số phù hợp).
 
 __Cảnh báo__: Các nút gạt nâng cao phụ thuộc vendor (BIOS/BMC) và có rủi ro; luôn đo trước/sau, có kế hoạch rollback, và thực hiện ngoài giờ tải.
 
 ---
 Tài liệu này là runbook thao tác nhanh để chuẩn hoá đo, áp dụng, và khôi phục cấu hình tối ưu GPU. Vui lòng chạy các lệnh có `sudo` ngoài giờ tải và xác nhận dải hợp lệ trước khi áp dụng.









# Cập nhật runbook: hợp nhất “nút gạt” cơ bản + nâng cao

## Nội dung chính đã hợp nhất

- __[Cơ bản]__ `## 11` (`176–229`)
  - __Power Limit__ (giới hạn công suất – tối ưu power/Wh, giảm throttling)
  - __Application Clocks__ (khóa xung SM/Memory – ổn định xung, giảm jitter)
  - __Compute Mode__ (EXCLUSIVE_PROCESS – giảm tranh chấp ngữ cảnh)
  - __Persistence Mode__ (duy trì ngữ cảnh – giảm latency khởi tạo)
  - __ECC__ (sửa lỗi bộ nhớ – cân bằng độ tin cậy vs hiệu năng)
  - __CUDA MPS__ (dịch vụ đa tiến trình – nâng lấp đầy GPU)
  - __NUMA/CPU Affinity__ (ghép CPU/memory với GPU)
  - __PCIe Link Gen/Width__ (xác thực tránh downtrain)
  - __P2P/Topology__ (đánh giá lợi ích liên‑GPU)
  - Lưu ý MIG không áp dụng cho V100

- __[Nâng cao]__ `## 12` (`231–323`)
  - __BIOS/Platform__ (Above 4G Decoding/PCIe Native Control/tắt ASPM – chống downtrain)
  - __BMC/IPMI Fan Profile__ (Performance/Full Speed – tăng airflow, hạ nhiệt)
  - __CPU Power Governor__ (performance) + __tuned-adm__ (latency-performance)
  - __IRQ Affinity__ (ghim IRQ NVIDIA về core phù hợp – giảm jitter)
  - __IOMMU/ACS__ (tinh chỉnh cô lập I/O – thận trọng về bảo mật)
  - __PCIe MRRS/MPS__ (Max Read Request Size/Max Payload Size – advanced)
  - __THP/HugePages__ (Transparent Huge Pages – giảm jitter)
  - __NUMA nâng cao__ (cô lập core, điều phối irqbalance)
  - __DCGM Policies/Health__ (giám sát/chính sách throttling)
  - __GPU Reset__ (làm sạch trạng thái lạ khi rảnh)
  - __Systemd auto-apply__ (tự động áp cấu hình sau reboot)
  - Cảnh báo an toàn, đo/rollback rõ ràng

