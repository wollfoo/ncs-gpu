# coordination/ – Điều phối & dòng công việc

- `coordinator.py`: trung tâm điều phối (coordinator – sắp xếp) tác vụ/DAG.

Hướng dẫn:
- Tách biệt lớp điều phối (sắp xếp luồng) khỏi lớp tác vụ (chiến lược/monitor) để giảm phụ thuộc vòng.
- Ghi log theo task-id/job-id để dễ theo dõi.
