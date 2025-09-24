"""Cấu hình tập trung cho toàn bộ nền tảng GPU."""

from __future__ import annotations

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Định nghĩa thông số vận hành với kiểm soát qua biến môi trường."""

    environment: str = Field("dev", description="Môi trường triển khai hiện hành")
    batch_size: int = Field(32, ge=1, description="Kích thước batch cho inference")
    max_pipeline_concurrency: int = Field(4, ge=1, description="Số stage song song")
    orchestrator_host: str = Field("0.0.0.0", description="Địa chỉ bind orchestrator")
    orchestrator_port: int = Field(9000, description="Cổng expose orchestrator")
    control_plane_url: str = Field(
        "http://localhost:8080", description="Điểm điều khiển để đăng ký SLO"
    )
    telemetry_endpoint: str = Field(
        "http://localhost:9464/metrics", description="Prometheus scrape endpoint"
    )
    inference_endpoint: str = Field(
        "http://localhost:7070", description="Rust inference service endpoint"
    )
    enable_feature_flags: bool = Field(True, description="Bật/tắt hệ flag bảo vệ")

    class Config:
        env_prefix = "APPGPU_"
        case_sensitive = False


@lru_cache
def load_config() -> AppConfig:
    """Giữ config singleton cho toàn bộ tiến trình."""

    return AppConfig()
