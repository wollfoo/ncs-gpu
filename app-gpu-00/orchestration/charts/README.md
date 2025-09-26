# Helm Charts

- `scheduler/`: chart triển khai service Axum kèm cấu hình secret, service monitor và autoscaling hook.
- `executor/`: chart dạng DaemonSet cho GPU node với toleration và cấu hình resource limit.
- `observability/`: chart gom Prometheus, Grafana, Tempo, Loki phục vụ monitoring.

> Các chart đang ở giai đoạn scaffold; thông số cụ thể sẽ được tùy biến cho từng môi trường trong Phase 4.
