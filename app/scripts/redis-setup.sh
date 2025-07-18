#!/bin/bash

# Redis Setup Script for Mining Environment EventBus
# Cài đặt và cấu hình Redis cho high-availability

set -euo pipefail

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a /var/log/redis-setup.log
}

log "🚀 Bắt đầu cài đặt Redis cho EventBus Mining Environment"

# Kiểm tra quyền root
if [[ $EUID -ne 0 ]]; then
    log "❌ Script này cần quyền root để cài đặt Redis"
    exit 1
fi

# Cài đặt Redis
log "📦 Cài đặt Redis server..."
apt-get update
apt-get install -y redis-server redis-tools

# Tạo thư mục logs
mkdir -p /var/log/redis
chown redis:redis /var/log/redis

# Cấu hình Redis cho production
log "⚙️ Cấu hình Redis cho production..."

cat > /etc/redis/redis.conf << 'EOF'
# Redis configuration for Mining Environment EventBus
# Cấu hình tối ưu cho high-availability và performance

# Network
bind 127.0.0.1
port 6379
timeout 300
tcp-keepalive 60

# General
daemonize yes
supervised systemd
pidfile /var/run/redis/redis-server.pid
loglevel notice
logfile /var/log/redis/redis-server.log

# Snapshotting (persistence)
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes
dbfilename dump.rdb
dir /var/lib/redis

# Replication
# masterauth <master-password>
# requirepass <password>

# Security
protected-mode yes
# requirepass your-strong-password-here

# Clients
maxclients 10000
timeout 300

# Memory management
maxmemory 512mb
maxmemory-policy allkeys-lru
maxmemory-samples 5

# Pub/Sub optimizations
notify-keyspace-events ""

# Slow log
slowlog-log-slower-than 10000
slowlog-max-len 128

# Latency monitoring
latency-monitor-threshold 100

# Client output buffer limits
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60

# TCP backlog
tcp-backlog 511

# Disable dangerous commands
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command KEYS ""
rename-command CONFIG "CONFIG_9a4f8c3e2b1d"
rename-command SHUTDOWN "SHUTDOWN_7b8e2a9f4c1d"
rename-command DEBUG ""
rename-command EVAL ""

# Optimize for Pub/Sub
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
list-max-ziplist-size -2
list-compress-depth 0
set-max-intset-entries 512
zset-max-ziplist-entries 128
zset-max-ziplist-value 64
hll-sparse-max-bytes 3000
stream-node-max-bytes 4096
stream-node-max-entries 100
activerehashing yes
EOF

# Cấu hình systemd service
log "🔧 Cấu hình systemd service..."

cat > /etc/systemd/system/redis-eventbus.service << 'EOF'
[Unit]
Description=Redis EventBus Server for Mining Environment
Documentation=https://redis.io/documentation
After=network.target
Wants=network.target

[Service]
Type=notify
ExecStart=/usr/bin/redis-server /etc/redis/redis.conf
ExecStop=/bin/kill -s QUIT $MAINPID
ExecReload=/bin/kill -s HUP $MAINPID
TimeoutStopSec=30
Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60

# Security
User=redis
Group=redis
NoNewPrivileges=true

# Sandboxing
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/redis /var/log/redis /var/run/redis
PrivateTmp=true
PrivateDevices=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

# Resource limits
LimitNOFILE=65535
LimitNPROC=65535

# Environment
Environment=REDIS_CONF=/etc/redis/redis.conf

[Install]
WantedBy=multi-user.target
EOF

# Cấu hình log rotation
log "📋 Cấu hình log rotation..."

cat > /etc/logrotate.d/redis-eventbus << 'EOF'
/var/log/redis/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 640 redis redis
    postrotate
        /bin/kill -USR1 `cat /var/run/redis/redis-server.pid 2>/dev/null` 2>/dev/null || true
    endscript
}
EOF

# Cấu hình monitoring script
log "📊 Tạo monitoring script..."

cat > /usr/local/bin/redis-eventbus-monitor.sh << 'EOF'
#!/bin/bash

# Redis EventBus Monitoring Script
# Kiểm tra sức khỏe Redis và ghi log metrics

REDIS_CLI="/usr/bin/redis-cli"
LOG_FILE="/var/log/redis/monitor.log"
METRICS_FILE="/var/log/redis/metrics.log"

# Logging function
log_metric() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

# Kiểm tra Redis có chạy không
if ! $REDIS_CLI ping > /dev/null 2>&1; then
    log_metric "❌ Redis server không phản hồi"
    exit 1
fi

# Thu thập metrics
CONNECTED_CLIENTS=$($REDIS_CLI info clients | grep "connected_clients" | cut -d: -f2 | tr -d '\r')
USED_MEMORY=$($REDIS_CLI info memory | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
TOTAL_COMMANDS=$($REDIS_CLI info stats | grep "total_commands_processed" | cut -d: -f2 | tr -d '\r')
PUBSUB_CHANNELS=$($REDIS_CLI pubsub channels | wc -l)

# Ghi metrics
cat >> "$METRICS_FILE" << EOF
timestamp=$(date +%s)
connected_clients=$CONNECTED_CLIENTS
used_memory=$USED_MEMORY
total_commands=$TOTAL_COMMANDS
pubsub_channels=$PUBSUB_CHANNELS
EOF

log_metric "✅ Redis healthy - Clients: $CONNECTED_CLIENTS, Memory: $USED_MEMORY, Channels: $PUBSUB_CHANNELS"
EOF

chmod +x /usr/local/bin/redis-eventbus-monitor.sh

# Cấu hình cron job cho monitoring
log "⏰ Cấu hình cron job cho monitoring..."

cat > /etc/cron.d/redis-eventbus-monitor << 'EOF'
# Redis EventBus monitoring - chạy mỗi phút
*/1 * * * * redis /usr/local/bin/redis-eventbus-monitor.sh
EOF

# Tạo thư mục run
mkdir -p /var/run/redis
chown redis:redis /var/run/redis

# Khởi động services
log "🚀 Khởi động Redis services..."

systemctl daemon-reload
systemctl enable redis-eventbus
systemctl start redis-eventbus

# Kiểm tra service status
sleep 3
if systemctl is-active --quiet redis-eventbus; then
    log "✅ Redis EventBus service đã khởi động thành công"
else
    log "❌ Redis EventBus service khởi động thất bại"
    systemctl status redis-eventbus
    exit 1
fi

# Kiểm tra kết nối
log "🔍 Kiểm tra kết nối Redis..."
if redis-cli ping | grep -q "PONG"; then
    log "✅ Redis server phản hồi PONG"
else
    log "❌ Redis server không phản hồi"
    exit 1
fi

# Tạo test channel
log "🧪 Tạo test publish/subscribe..."
redis-cli publish "test:channel" '{"message": "Redis EventBus setup complete"}' > /dev/null

log "🎉 Cài đặt Redis EventBus hoàn tất!"
log "📋 Thông tin quan trọng:"
log "   - Config file: /etc/redis/redis.conf"
log "   - Service: redis-eventbus"
log "   - Logs: /var/log/redis/"
log "   - Monitor: /usr/local/bin/redis-eventbus-monitor.sh"
log "   - Systemd: systemctl status redis-eventbus"

echo ""
echo "🚀 Redis EventBus đã sẵn sàng cho Mining Environment!"
echo "📊 Kiểm tra status: systemctl status redis-eventbus"
echo "🔍 Kiểm tra logs: tail -f /var/log/redis/redis-server.log"
echo "📈 Kiểm tra metrics: tail -f /var/log/redis/metrics.log"