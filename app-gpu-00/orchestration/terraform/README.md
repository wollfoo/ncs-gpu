# Terraform Stack

- `modules/network`: VNet/Subnet, NLB internal với mTLS.
- `modules/compute`: GPU node pool (AKS/EKS) kèm autoscaling.
- `envs/dev`: cấu hình baseline cho môi trường dev, bao gồm secret store và biến môi trường mẫu.

> Module Terraform sẽ được áp dụng đầu tiên cho môi trường dev theo Phase 4; các môi trường khác kế thừa cùng cấu trúc.
