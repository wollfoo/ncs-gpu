### 3.2 AI Training

#### 🤖 Giới Thiệu
**AI Training** (huấn luyện AI) là quá trình dạy máy học từ dữ liệu để tạo ra **model** (mô hình – bộ não nhân tạo) có khả năng dự đoán hoặc phân loại.

#### 📚 Các Framework Hỗ Trợ
- **PyTorch**: Framework linh hoạt cho nghiên cứu
- **TensorFlow**: Framework mạnh mẽ của Google
- **JAX**: Framework tối ưu cho tính toán khoa học
- **ONNX**: Format chung cho các models

#### 🎯 Ví Dụ Training Model Đơn Giản

```python
# train_simple.py - Training model AI đơn giản

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset

# 1. Tạo dataset mẫu
X = torch.randn(1000, 10)  # 1000 samples, 10 features
y = torch.randint(0, 2, (1000,))  # Binary classification

dataset = TensorDataset(X, y)
dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

# 2. Định nghĩa model đơn giản
class SimpleNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(10, 64)
        self.fc2 = nn.Linear(64, 32)
        self.fc3 = nn.Linear(32, 2)
        
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        x = torch.relu(self.fc2(x))
        x = self.fc3(x)
        return x

# 3. Setup training
model = SimpleNet().cuda()
criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# 4. Training loop
for epoch in range(10):
    for batch_x, batch_y in dataloader:
        batch_x, batch_y = batch_x.cuda(), batch_y.cuda()
        
        optimizer.zero_grad()
        outputs = model(batch_x)
        loss = criterion(outputs, batch_y)
        loss.backward()
        optimizer.step()
    
    print(f"Epoch {epoch+1}, Loss: {loss.item():.4f}")

print("✅ Training hoàn tất!")
```

### 3.3 Image Processing

#### 🎨 Giới Thiệu
**Image Processing** (xử lý ảnh) sử dụng GPU để thực hiện các phép biến đổi ảnh/video với tốc độ cao.

#### 🖼️ Ví Dụ Xử Lý Ảnh Cơ Bản

```python
# image_basic.py - Xử lý ảnh cơ bản với GPU

import cv2
import numpy as np
from PIL import Image
import torch
import torchvision.transforms as T

def enhance_image(image_path):
    """Cải thiện chất lượng ảnh"""
    
    # Load ảnh
    img = Image.open(image_path)
    
    # Chuyển sang tensor và GPU
    transform = T.Compose([
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], 
                   std=[0.229, 0.224, 0.225])
    ])
    
    img_tensor = transform(img).unsqueeze(0).cuda()
    
    # Xử lý trên GPU
    # Ví dụ: Tăng độ sáng và contrast
    enhanced = img_tensor * 1.2 + 0.1
    enhanced = torch.clamp(enhanced, 0, 1)
    
    # Chuyển về CPU và save
    result = enhanced.squeeze(0).cpu()
    
    # Denormalize và save
    denorm = T.Compose([
        T.Normalize(mean=[-0.485/0.229, -0.456/0.224, -0.406/0.225],
                   std=[1/0.229, 1/0.224, 1/0.225]),
        T.ToPILImage()
    ])
    
    output_img = denorm(result)
    output_img.save("enhanced_output.jpg")
    print("✅ Đã lưu ảnh enhanced!")
    
    return output_img

# Sử dụng
enhance_image("input.jpg")
```

### 3.4 Scientific Computing

#### 🔬 Giới Thiệu
**Scientific Computing** (tính toán khoa học) sử dụng GPU để giải các bài toán phức tạp trong khoa học và kỹ thuật.

#### 🧮 Ví Dụ Tính Toán Ma Trận

```python
# matrix_calc.py - Tính toán ma trận với GPU

import torch
import time

def gpu_matrix_operations(size=5000):
    """Các phép tính ma trận trên GPU"""
    
    print(f"📊 Ma trận {size}x{size}")
    
    # Tạo ma trận trên GPU
    A = torch.randn(size, size).cuda()
    B = torch.randn(size, size).cuda()
    
    # 1. Nhân ma trận
    start = time.time()
    C = torch.matmul(A, B)
    torch.cuda.synchronize()
    print(f"Nhân ma trận: {time.time()-start:.3f}s")
    
    # 2. Nghịch đảo ma trận
    start = time.time()
    A_inv = torch.inverse(A)
    torch.cuda.synchronize()
    print(f"Nghịch đảo: {time.time()-start:.3f}s")
    
    # 3. Eigenvalues
    start = time.time()
    eigenvalues = torch.linalg.eigvals(A[:1000, :1000])
    torch.cuda.synchronize()
    print(f"Eigenvalues: {time.time()-start:.3f}s")
    
    return C

# Test
gpu_matrix_operations(3000)
```

---

## 4. Ví Dụ Minh Họa

### 4.1 Script Mining Tự Động

```bash
#!/bin/bash
# auto_mining.sh - Script mining tự động

# Cấu hình
WALLET="kaspa:qr0xxxxxxxxxxx"
POOL="stratum+tcp://acc-pool.pw:16061"
WORKER="worker01"

# Kiểm tra GPU
echo "🔍 Checking GPU..."
nvidia-smi

# Start mining
echo "⛏️ Starting mining..."
docker run -d \
  --name auto-miner \
  --gpus all \
  --restart always \
  -e WALLET=$WALLET \
  -e POOL=$POOL \
  -e WORKER=$WORKER \
  opus-gpu:v2.0 --mode mining

# Monitor
watch -n 5 'docker logs --tail 20 auto-miner'
```

### 4.2 API Client Python

```python
# opus_client.py - Python client cho OPUS-GPU

import requests
import json

class OpusGPUClient:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def submit_task(self, task_type, payload):
        """Gửi task lên OPUS-GPU"""
        data = {
            "type": task_type,
            "payload": payload,
            "priority": 5
        }
        
        resp = requests.post(
            f"{self.api_url}/api/v2/tasks",
            headers=self.headers,
            json=data
        )
        
        if resp.status_code == 201:
            return resp.json()["task_id"]
        else:
            raise Exception(f"Error: {resp.text}")
    
    def get_result(self, task_id):
        """Lấy kết quả task"""
        resp = requests.get(
            f"{self.api_url}/api/v2/tasks/{task_id}/result",
            headers=self.headers
        )
        
        if resp.status_code == 200:
            return resp.json()
        else:
            return None

# Sử dụng
client = OpusGPUClient("http://localhost:8080", "your-api-key")
task_id = client.submit_task("compute", {"operation": "matrix_multiply"})
result = client.get_result(task_id)
```

---

## 5. Xử Lý Sự Cố

### 5.1 Lỗi GPU Thường Gặp

| Lỗi | Nguyên nhân | Giải pháp |
|-----|-------------|-----------|
| **CUDA out of memory** | GPU hết VRAM | Giảm batch size, clear cache |
| **No CUDA device** | Driver/CUDA chưa cài | Cài NVIDIA driver + CUDA |
| **GPU is lost** | GPU bị treo | Reset GPU với nvidia-smi |
| **Timeout error** | Task quá lâu | Tăng timeout, optimize code |

### 5.2 Commands Debug

```bash
# Reset GPU
sudo nvidia-smi --gpu-reset

# Clear GPU memory
sudo nvidia-smi --gpu-reset -i 0

# Monitor GPU
nvidia-smi dmon -i 0

# Check CUDA
nvcc --version
python -c "import torch; print(torch.cuda.is_available())"

# Docker GPU test
docker run --rm --gpus all nvidia/cuda:12.3.0-base nvidia-smi
```

---

## 6. Câu Hỏi Thường Gặp (FAQ)

### Q1: OPUS-GPU có miễn phí không?
**A:** Có, OPUS-GPU là open source với Apache License 2.0, miễn phí cho mọi mục đích.

### Q2: Hỗ trợ GPU nào?
**A:** Tất cả GPU NVIDIA từ GTX 1060 trở lên với CUDA 11.8+.

### Q3: Làm sao tối ưu hashrate mining?
**A:** 
- Overclock memory: +1000 MHz
- Underclock core: -200 MHz
- Power limit: 70%
- Giữ nhiệt độ < 70°C

### Q4: Có thể dùng nhiều GPU không?
**A:** Có, OPUS-GPU hỗ trợ multi-GPU với load balancing tự động.

### Q5: Training AI có cần dataset lớn không?
**A:** Tùy thuộc vào task, có thể dùng pre-trained models và fine-tuning với dataset nhỏ.

### Q6: API có giới hạn rate limit không?
**A:** Mặc định 1000 requests/hour, có thể tăng trong config.

### Q7: Backup và recovery như thế nào?
**A:** OPUS-GPU tự động checkpoint mỗi 5 phút, có thể restore từ checkpoint khi gặp lỗi.

---

## 📞 Thông Tin Hỗ Trợ

- **Email**: support@opus-gpu.io
- **Discord**: https://discord.gg/opus-gpu
- **GitHub**: https://github.com/opus-gpu/opus-gpu
- **Documentation**: https://docs.opus-gpu.io
- **Forum**: https://forum.opus-gpu.io

---

## 🎓 Tài Nguyên Học Tập

### Videos Tutorial
- [Getting Started với OPUS-GPU](https://youtube.com/opus-gpu/start)
- [Mining Cryptocurrency hiệu quả](https://youtube.com/opus-gpu/mining)
- [Training AI Models](https://youtube.com/opus-gpu/ai)

### Courses
- OPUS-GPU Fundamentals (Free)
- Advanced GPU Computing
- Mining Optimization Masterclass

### Books & Papers
- "GPU Computing với OPUS" - Tải free tại docs.opus-gpu.io/book
- Research papers về GPU optimization

---

*Phiên bản: 2.0.0*  
*Cập nhật: 27/01/2025*  
*Tác giả: OPUS Team*
