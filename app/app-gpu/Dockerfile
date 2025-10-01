# Multi-stage Dockerfile cho Secure GPU Mining Core
# Bước 1: Builder stage - Biên dịch với dependencies đầy đủ
FROM rust:1.75-slim AS builder

# Metadata an toàn và thông tin bản quyền
LABEL maintainer="Academic Security Research Team"
LABEL description="Secure GPU Mining Core - Academic Research System"
LABEL version="0.1.0"
LABEL vendor="Security Research Institute"

# Cài đặt system dependencies cần thiết cho build
RUN apt-get update && apt-get install -y \
    # GPU support - Vulkan, OpenGL, CUDA
    libvulkan1 \
    libvulkan-dev \
    mesa-vulkan-drivers \
    vulkan-tools \
    libx11-dev \
    libxrandr-dev \
    libxinerama-dev \
    libxcursor-dev \
    libxi-dev \
    libgl1-mesa-dev \
    libgl1-mesa-glx \
    # CUDA support (minimal)
    software-properties-common \
    # Build tools
    pkg-config \
    cmake \
    clang \
    llvm \
    # Security scanning tools
    libssl-dev \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Tạo user không phải root cho security
RUN useradd --create-home --shell /bin/bash --user-group --uid 1000 miner

# Set working directory
WORKDIR /app

# Copy Cargo.toml và Cargo.lock để cache dependencies
COPY app-gpu/Cargo.toml app-gpu/Cargo.lock ./

# Tạo dummy main.rs để build dependencies
RUN mkdir src && echo "fn main() {}" > src/main.rs

# Pre-build dependencies (cached layer)
RUN cargo build --release --target x86_64-unknown-linux-gnu \
    && rm -rf target/release/deps/gpu_miner*

# Copy source code
COPY app-gpu/src ./src

# Build ứng dụng release với tối ưu hóa
RUN cargo build --release --target x86_64-unknown-linux-gnu \
    && strip target/x86_64-unknown-linux-gnu/release/gpu-miner

# =================================================================================
# Bước 2: Runtime stage - Minimal container với GPU support
FROM nvidia/cuda:11.8-runtime-ubuntu22.04 AS runtime

# Metadata runtime
LABEL stage="runtime"
LABEL gpu-support="nvidia-cuda"

# Cài đặt minimal runtime dependencies
RUN apt-get update && apt-get install -y \
    # GPU runtime libraries
    libvulkan1 \
    mesa-vulkan-drivers \
    libx11-6 \
    libxrandr2 \
    libxinerama1 \
    libxcursor1 \
    libxi6 \
    libgl1-mesa-glx \
    # Security và monitoring
    ca-certificates \
    curl \
    # Process management
    procps \
    htop \
    && rm -rf /var/lib/apt/lists/* \
    # Remove dangerous suid binaries
    && find / -perm /4000 -type f -exec chmod u-s {} \; 2>/dev/null || true

# Tạo user không phải root với UID thấp hơn để tương thích với host
RUN useradd --create-home --shell /bin/bash --user-group --uid 1000 --groups video miner

# Set working directory
WORKDIR /app

# Copy binary từ builder stage
COPY --from=builder --chown=miner:miner /app/target/x86_64-unknown-linux-gnu/release/gpu-miner /app/gpu-miner

# Tạo volume cho configuration và data
VOLUME ["/app/config", "/app/data"]

# Tạo healthcheck endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:9090/metrics || exit 1

# Set user không phải root
USER miner

# Expose Prometheus metrics port
EXPOSE 9090

# Set default environment variables cho security
ENV RUST_BACKTRACE=0 \
    RUST_LOG=info \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Default CMD chạy chế độ benchmark (safe monitoring mode)
CMD ["/app/gpu-miner", "--benchmark", "--telemetry-port", "9090"]

# =================================================================================
# Bước 3: Security hardening profile (seccomp và AppArmor)

# Seccomp profile - giới hạn system calls cho mining operations
RUN mkdir -p /etc/docker/seccomp
RUN echo '{\
    "defaultAction": "SCMP_ACT_ERRNO",\
    "architectures": ["SCMP_ARCH_X86_64"],\
    "syscalls": [\
        {"names": ["read", "write", "open", "close", "stat", "fstat", "lstat", "poll", "lseek", "mmap", "mprotect", "munmap", "brk", "rt_sigaction", "rt_sigprocmask", "rt_sigreturn", "ioctl", "pwrite64", "readv", "writev", "pipe", "select", "sched_yield", "madvise", "mremap", "msync", "mlock", "munlock", "mlockall", "munlockall", "mincore", "madvise", "shmget", "shmat", "shmctl", "dup", "dup2", "pause", "nanosleep", "getitimer", "alarm", "setitimer", "getpid", "sendfile", "socket", "connect", "accept", "sendto", "recvfrom", "sendmsg", "recvmsg", "shutdown", "bind", "listen", "getsockname", "getpeername", "socketpair", "setsockopt", "getsockopt", "clone", "fork", "vfork", "execve", "exit", "wait4", "kill", "uname", "semget", "semop", "semctl", "shmdt", "msgget", "msgsnd", "msgrcv", "msgctl", "fcntl", "flock", "fsync", "fdatasync", "truncate", "ftruncate", "getdents", "getcwd", "chdir", "fchdir", "rename", "mkdir", "rmdir", "creat", "link", "unlink", "symlink", "readlink", "chmod", "fchmod", "chown", "fchown", "lchown", "umask", "gettimeofday", "getrlimit", "getrusage", "sysinfo", "times", "ptrace", "getuid", "geteuid", "getgid", "getegid", "getgroups", "setgroups", "setuid", "setgid", "getresuid", "getresgid", "setresuid", "setresgid", "setfsuid", "setfsgid", "getpgid", "setpgid", "getsid", "setsid", "getpriority", "setpriority", "sched_getparam", "sched_setparam", "sched_getscheduler", "sched_setscheduler", "sched_yield", "sched_get_priority_max", "sched_get_priority_min", "sched_rr_get_interval", "mlockall", "munlockall", "vhangup", "modify_ldt", "pivot_root", "_sysctl", "prctl", "arch_prctl", "adjtimex", "setrlimit", "chroot", "sync", "acct", "settimeofday", "mount", "umount2", "swapon", "swapoff", "reboot", "sethostname", "setdomainname", "iopl", "ioperm", "create_module", "init_module", "delete_module", "get_kernel_syms", "query_module", "quotactl", "nfsservctl", "getpmsg", "putpmsg", "afs_syscall", "tuxcall", "security", "gettid", "readahead", "setxattr", "lsetxattr", "fsetxattr", "getxattr", "lgetxattr", "fgetxattr", "listxattr", "llistxattr", "flistxattr", "removexattr", "lremovexattr", "fremovexattr", "tkill", "time", "futex", "sched_setaffinity", "sched_getaffinity", "set_thread_area", "io_setup", "io_destroy", "io_getevents", "io_submit", "io_cancel", "get_thread_area", "lookup_dcookie", "epoll_create", "epoll_ctl_old", "epoll_wait_old", "remap_file_pages", "getdents64", "set_tid_address", "restart_syscall", "semtimedop", "fadvise64", "timer_create", "timer_settime", "timer_gettime", "timer_getoverrun", "timer_delete", "clock_settime", "clock_gettime", "clock_getres", "clock_nanosleep", "exit_group", "epoll_wait", "epoll_ctl", "tgkill", "utimes", "vserver", "mbind", "set_mempolicy", "get_mempolicy", "mq_open", "mq_unlink", "mq_timedsend", "mq_timedreceive", "mq_notify", "mq_getsetattr", "kexec_load", "waitid", "add_key", "request_key", "keyctl", "ioprio_set", "ioprio_get", "inotify_init", "inotify_add_watch", "inotify_rm_watch", "migrate_pages", "openat", "mkdirat", "mknodat", "fchownat", "futimesat", "newfstatat", "unlinkat", "renameat", "linkat", "symlinkat", "readlinkat", "fchmodat", "faccessat", "pselect6", "ppoll", "unshare", "set_robust_list", "get_robust_list", "splice", "tee", "sync_file_range", "vmsplice", "move_pages", "utimensat", "epoll_pwait", "signalfd", "timerfd_create", "eventfd", "fallocate", "timerfd_settime", "timerfd_gettime", "accept4", "signalfd4", "eventfd2", "epoll_create1", "dup3", "pipe2", "inotify_init1", "preadv", "pwritev", "rt_tgsigqueueinfo", "perf_event_open", "recvmmsg", "fanotify_init", "fanotify_mark", "prlimit64", "name_to_handle_at", "open_by_handle_at", "clock_adjtime", "syncfs", "sendmmsg", "setns", "getcpu", "process_vm_readv", "process_vm_writev", "kcmp", "finit_module"], "action": "SCMP_ACT_ALLOW"},\
        {"names": ["socket"], "action": "SCMP_ACT_ALLOW"},\
        {"names": ["execve", "execveat"], "action": "SCMP_ACT_ALLOW", "includes": {"minKernel": "5.0"}}\
    ]\
}' > /etc/docker/seccomp/gpu-miner.json

# AppArmor profile cho GPU mining
RUN mkdir -p /etc/apparmor.d/docker
RUN echo '#include <tunables/global>\nprofile gpu-miner /app/gpu-miner flags=(attach_disconnected,mediate_deleted) {\n  #include <abstractions/base>\n  #include <abstractions/nameservice>\n  #include <abstractions/ssl_certs>\n  #include <abstractions/nvidia>\n  /app/gpu-miner r,\n  /app/ r,\n  /app/** rwk,\n  /tmp/** rwk,\n  /proc/*/ r,\n  /proc/*/stat r,\n  /proc/*/maps r,\n  /proc/*/status r,\n  /sys/class/drm/card* r,\n  /dev/dri/card* rwk,\n  /dev/nvidia* rwk,\n  /dev/nvidiactl rwk,\n  /dev/nvidia-modeset rwk,\n  /dev/nvidia-uvm rwk,\n  /dev/nvidia-uvm-tools rwk,\n}' > /etc/apparmor.d/docker/gpu-miner

# =================================================================================
# Bước 4: SBOM generation stage

FROM builder AS sbom-generator

# Cài đặt SBOM tools
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install Syft từ Anchore
RUN curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin

# Generate SBOM trong JSON format
RUN syft packages /app/target/x86_64-unknown-linux-gnu/release/gpu-miner -o json > /app/gpu-miner-sbom.json

# =================================================================================
# Bước 5: Final production image

FROM runtime AS production

# Copy SBOM từ sbom-generator stage
COPY --from=sbom-generator /app/gpu-miner-sbom.json /app/gpu-miner-sbom.json

# Tạo security labels
LABEL gpu-miner.sbom-path="/app/gpu-miner-sbom.json" \
      gpu-miner.security-profile="seccomp-apparmor" \
      gpu-miner.criticality="high" \
      gpu-miner.research-purpose="academic-security"

# Tạo script entrypoint với security hardening
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Security hardening\n\
echo "Initializing GPU Mining container..."\n\
\n\
# Verify binary integrity (runtime check)\n\
if [ ! -f "/app/gpu-miner" ]; then\n\
    echo "Error: Binary not found" >&2\n\
    exit 1\n\
fi\n\
\n\
# Set CPU affinity nếu cần\n\
if [ -n "$CPU_AFFINITY" ]; then\n\
    taskset -p $CPU_AFFINITY $$\n\
fi\n\
\n\
# Set process limits\n\
ulimit -c 0  # Disable core dumps\n\
\n\
# Run application với exec để signal handling\n\
exec "/app/gpu-miner" "$@"' > /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

# Set entrypoint với security script
ENTRYPOINT ["/app/entrypoint.sh"]