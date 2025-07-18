#!/bin/bash

# RabbitMQ Cluster Setup Script for Mining Environment EventBus
# Triển khai RabbitMQ cluster 2-node với High Availability và Message Durability

set -euo pipefail

# Configuration
RABBITMQ_CLUSTER_NAME="mining-cluster"
RABBITMQ_NODE_PREFIX="rabbit"
RABBITMQ_COOKIE="mining-eventbus-$(date +%s)"
RABBITMQ_USER="mining-user"
RABBITMQ_PASSWORD="mining-$(openssl rand -hex 8)"
RABBITMQ_VHOST="/mining"

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a /var/log/rabbitmq-cluster-setup.log
}

log "🚀 Bắt đầu cài đặt RabbitMQ Cluster cho Mining Environment EventBus"

# Kiểm tra quyền root
if [[ $EUID -ne 0 ]]; then
    log "❌ Script này cần quyền root để cài đặt RabbitMQ Cluster"
    exit 1
fi

# Tạo thư mục logs
mkdir -p /var/log/rabbitmq
chmod 755 /var/log/rabbitmq

# Cài đặt RabbitMQ Server
log "📦 Cài đặt RabbitMQ Server..."

# Add RabbitMQ repository
curl -fsSL https://packagecloud.io/rabbitmq/rabbitmq-server/gpgkey | apt-key add -
echo "deb https://packagecloud.io/rabbitmq/rabbitmq-server/ubuntu/ $(lsb_release -sc) main" > /etc/apt/sources.list.d/rabbitmq.list

# Add Erlang repository
curl -fsSL https://packagecloud.io/rabbitmq/erlang/gpgkey | apt-key add -
echo "deb https://packagecloud.io/rabbitmq/erlang/ubuntu/ $(lsb_release -sc) main" > /etc/apt/sources.list.d/erlang.list

# Update và cài đặt
apt-get update
apt-get install -y erlang-base erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
                   erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
                   erlang-runtime-tools erlang-snmp erlang-ssl erlang-syntax-tools \
                   erlang-tftp erlang-tools erlang-xmerl
apt-get install -y rabbitmq-server

# Tạo cấu hình RabbitMQ
log "⚙️ Cấu hình RabbitMQ cho production cluster..."

cat > /etc/rabbitmq/rabbitmq.conf << 'EOF'
# RabbitMQ Configuration for Mining Environment EventBus Cluster
# High Availability và Message Durability optimized

# Cluster configuration
cluster_name = mining-cluster
cluster_formation.peer_discovery_backend = rabbit_peer_discovery_classic_config

# Network configuration
listeners.tcp.default = 5672
listeners.ssl.default = 5671
management.tcp.port = 15672

# Memory và disk thresholds
vm_memory_high_watermark.relative = 0.6
disk_free_limit.relative = 2.0
cluster_partition_handling = autoheal

# Message durability settings
queue_master_locator = min-masters
default_vhost = /mining
default_user = mining-user
default_pass = PLACEHOLDER_PASSWORD
default_permissions.configure = .*
default_permissions.read = .*
default_permissions.write = .*

# Logging
log.console = true
log.console.level = info
log.file = /var/log/rabbitmq/rabbitmq.log
log.file.level = info
log.file.rotation.date = $D0
log.file.rotation.size = 10485760

# Management plugin
management.path_prefix = /rabbitmq
management.cors.allow_origins.1 = *
management.cors.max_age = 3600

# High availability
ha_promote_on_shutdown = when_synced
ha_promote_on_failure = when_synced

# Performance tuning
collect_statistics = coarse
collect_statistics_interval = 5000
tcp_listen_options.backlog = 4096
tcp_listen_options.nodelay = true
tcp_listen_options.linger.on = true
tcp_listen_options.linger.timeout = 0
tcp_listen_options.exit_on_close = false

# Heartbeat
heartbeat = 60
frame_max = 131072
channel_max = 0
EOF

# Thay thế password trong config
sed -i "s/PLACEHOLDER_PASSWORD/$RABBITMQ_PASSWORD/g" /etc/rabbitmq/rabbitmq.conf

# Tạo Erlang cookie cho cluster
echo "$RABBITMQ_COOKIE" > /var/lib/rabbitmq/.erlang.cookie
chown rabbitmq:rabbitmq /var/lib/rabbitmq/.erlang.cookie
chmod 400 /var/lib/rabbitmq/.erlang.cookie

log "🔧 Cấu hình systemd service cho RabbitMQ..."

# Enhanced systemd service cho cluster
cat > /etc/systemd/system/rabbitmq-cluster.service << 'EOF'
[Unit]
Description=RabbitMQ Cluster for Mining Environment EventBus
Documentation=https://www.rabbitmq.com/
After=network.target epmd.service
Wants=network.target epmd.service

[Service]
Type=notify
User=rabbitmq
Group=rabbitmq
WorkingDirectory=/var/lib/rabbitmq
ExecStartPre=/usr/lib/rabbitmq/bin/rabbitmq-plugins enable rabbitmq_management
ExecStart=/usr/lib/rabbitmq/bin/rabbitmq-server
ExecStop=/usr/lib/rabbitmq/bin/rabbitmqctl stop
ExecReload=/usr/lib/rabbitmq/bin/rabbitmqctl reload
TimeoutStartSec=600
TimeoutStopSec=120
Restart=always
RestartSec=10
StartLimitBurst=3
StartLimitIntervalSec=60

# Environment variables
Environment=RABBITMQ_USE_LONGNAME=true
Environment=RABBITMQ_NODENAME=rabbit@%i
Environment=RABBITMQ_NODE_PORT=5672
Environment=RABBITMQ_SERVER_START_ARGS="-rabbit log_levels [{connection,info}]"
Environment=RABBITMQ_CONFIG_FILE=/etc/rabbitmq/rabbitmq
Environment=RABBITMQ_MNESIA_BASE=/var/lib/rabbitmq/mnesia
Environment=RABBITMQ_LOG_BASE=/var/log/rabbitmq
Environment=RABBITMQ_PLUGINS_DIR=/usr/lib/rabbitmq/plugins
Environment=RABBITMQ_ENABLED_PLUGINS_FILE=/etc/rabbitmq/enabled_plugins

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/rabbitmq /var/log/rabbitmq /etc/rabbitmq
ProtectHome=true
ProtectKernelTunables=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

# Resource limits
LimitNOFILE=65535
LimitNPROC=65535
LimitCORE=infinity

[Install]
WantedBy=multi-user.target
EOF

# Cài đặt và cấu hình cluster
log "🔗 Cài đặt RabbitMQ cluster..."

systemctl daemon-reload
systemctl enable rabbitmq-cluster
systemctl start rabbitmq-cluster

# Chờ RabbitMQ khởi động
sleep 10

# Kích hoạt management plugin
rabbitmq-plugins enable rabbitmq_management

# Tạo user và vhost
log "👤 Tạo user và virtual host..."

# Tạo admin user
rabbitmqctl add_user admin admin123
rabbitmqctl set_user_tags admin administrator
rabbitmqctl set_permissions -p / admin ".*" ".*" ".*"

# Tạo mining user
rabbitmqctl add_user "$RABBITMQ_USER" "$RABBITMQ_PASSWORD"
rabbitmqctl set_user_tags "$RABBITMQ_USER" monitoring

# Tạo mining vhost
rabbitmqctl add_vhost "$RABBITMQ_VHOST"
rabbitmqctl set_permissions -p "$RABBITMQ_VHOST" "$RABBITMQ_USER" ".*" ".*" ".*"

# Cấu hình topic exchange và queues
log "🔄 Cấu hình topic exchange và queues..."

# Tạo topic exchange 'mining'
rabbitmqctl eval "
rabbit_exchange:declare({resource, <<\"/mining\">>, exchange, <<"mining\">>}, topic, true, false, false, []).
"

# Tạo durable queues với HA policy
rabbitmqctl eval "
rabbit_amqqueue:declare({resource, <<\"/mining\">>, queue, <<"channel.cpu\">>}, true, false, [], none, <<\"rabbit@$(hostname)\">>).
"

rabbitmqctl eval "
rabbit_amqqueue:declare({resource, <<\"/mining\">>, queue, <<"channel.gpu\">>}, true, false, [], none, <<\"rabbit@$(hostname)\">>).
"

# Cấu hình HA policy
log "🏛️ Cấu hình High Availability policy..."

rabbitmqctl set_policy -p "$RABBITMQ_VHOST" ha-mining "^channel\." \
    '{"ha-mode":"all","ha-sync-mode":"automatic","ha-promote-on-shutdown":"when-synced","ha-promote-on-failure":"when-synced"}'

# Tạo script cluster join (cho node thứ 2)
log "📝 Tạo script join cluster..."

cat > /usr/local/bin/rabbitmq-join-cluster.sh << 'EOF'
#!/bin/bash

# RabbitMQ Cluster Join Script
# Chạy script này trên node thứ 2 để join cluster

if [[ $EUID -ne 0 ]]; then
    echo "❌ Script này cần quyền root"
    exit 1
fi

MASTER_NODE="$1"
if [[ -z "$MASTER_NODE" ]]; then
    echo "❌ Vui lòng cung cấp tên node master"
    echo "Usage: $0 <master-node-hostname>"
    exit 1
fi

echo "🔗 Joining cluster với master node: $MASTER_NODE"

# Stop RabbitMQ
systemctl stop rabbitmq-cluster

# Join cluster
rabbitmqctl join_cluster "rabbit@$MASTER_NODE"

# Start RabbitMQ
systemctl start rabbitmq-cluster

echo "✅ Joined cluster thành công!"
rabbitmqctl cluster_status
EOF

chmod +x /usr/local/bin/rabbitmq-join-cluster.sh

# Tạo monitoring script
log "📊 Tạo monitoring script..."

cat > /usr/local/bin/rabbitmq-cluster-monitor.sh << 'EOF'
#!/bin/bash

# RabbitMQ Cluster Monitoring Script
# Kiểm tra cluster health và queue statistics

RABBITMQ_VHOST="/mining"
LOG_FILE="/var/log/rabbitmq/monitor.log"
METRICS_FILE="/var/log/rabbitmq/metrics.log"

# Logging function
log_metric() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
}

# Kiểm tra cluster status
cluster_status=$(rabbitmqctl cluster_status --formatter json 2>/dev/null)
if [[ $? -ne 0 ]]; then
    log_metric "❌ RabbitMQ cluster không phản hồi"
    exit 1
fi

# Kiểm tra running nodes
running_nodes=$(echo "$cluster_status" | jq -r '.running_nodes | length')
total_nodes=$(echo "$cluster_status" | jq -r '.disk_nodes | length')

# Kiểm tra queue statistics
queue_stats=$(rabbitmqctl list_queues -p "$RABBITMQ_VHOST" name messages consumers --formatter json 2>/dev/null)
cpu_queue_messages=$(echo "$queue_stats" | jq -r '.[] | select(.name=="channel.cpu") | .messages')
gpu_queue_messages=$(echo "$queue_stats" | jq -r '.[] | select(.name=="channel.gpu") | .messages')

# Ghi metrics
cat >> "$METRICS_FILE" << EOF
timestamp=$(date +%s)
cluster_running_nodes=$running_nodes
cluster_total_nodes=$total_nodes
cpu_queue_messages=$cpu_queue_messages
gpu_queue_messages=$gpu_queue_messages
EOF

if [[ "$running_nodes" -eq "$total_nodes" ]]; then
    log_metric "✅ RabbitMQ cluster healthy - Running: $running_nodes/$total_nodes nodes"
else
    log_metric "⚠️ RabbitMQ cluster degraded - Running: $running_nodes/$total_nodes nodes"
fi

log_metric "📊 Queue stats - CPU: $cpu_queue_messages messages, GPU: $gpu_queue_messages messages"
EOF

chmod +x /usr/local/bin/rabbitmq-cluster-monitor.sh

# Cấu hình cron job cho monitoring
log "⏰ Cấu hình cron job cho monitoring..."

cat > /etc/cron.d/rabbitmq-cluster-monitor << 'EOF'
# RabbitMQ Cluster monitoring - chạy mỗi phút
*/1 * * * * rabbitmq /usr/local/bin/rabbitmq-cluster-monitor.sh
EOF

# Kiểm tra service status
log "🔍 Kiểm tra service status..."

sleep 5
if systemctl is-active --quiet rabbitmq-cluster; then
    log "✅ RabbitMQ Cluster service đã khởi động thành công"
else
    log "❌ RabbitMQ Cluster service khởi động thất bại"
    systemctl status rabbitmq-cluster
    exit 1
fi

# Kiểm tra cluster status
cluster_status=$(rabbitmqctl cluster_status 2>/dev/null)
if [[ $? -eq 0 ]]; then
    log "✅ RabbitMQ cluster status OK"
    echo "$cluster_status"
else
    log "❌ RabbitMQ cluster status check failed"
    exit 1
fi

# Tạo test message
log "🧪 Tạo test publish/consume..."

# Test publish
rabbitmqctl eval "
rabbit_basic:publish({resource, <<\"/mining\">>, exchange, <<"mining\">>}, <<\"channel.cpu\">>, false, false, {basic_message, {resource, <<\"/mining\">>, exchange, <<"mining\">>}, <<\"channel.cpu\">>, {content, 60, {message_properties, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined, undefined}, <<\"{'test_message': 'RabbitMQ cluster setup complete'}\">>}, <<\"\">>}).
"

log "🎉 Cài đặt RabbitMQ Cluster hoàn tất!"
log "📋 Thông tin quan trọng:"
log "   - Cluster name: $RABBITMQ_CLUSTER_NAME"
log "   - VHost: $RABBITMQ_VHOST"
log "   - User: $RABBITMQ_USER"
log "   - Password: $RABBITMQ_PASSWORD"
log "   - Management UI: http://localhost:15672"
log "   - Service: rabbitmq-cluster"
log "   - Logs: /var/log/rabbitmq/"
log "   - Monitor: /usr/local/bin/rabbitmq-cluster-monitor.sh"
log "   - Join script: /usr/local/bin/rabbitmq-join-cluster.sh"

echo ""
echo "🚀 RabbitMQ Cluster đã sẵn sàng cho Mining Environment EventBus!"
echo "📊 Kiểm tra cluster: rabbitmqctl cluster_status"
echo "🔍 Kiểm tra queues: rabbitmqctl list_queues -p $RABBITMQ_VHOST"
echo "📈 Kiểm tra metrics: tail -f /var/log/rabbitmq/metrics.log"
echo "🌐 Management UI: http://localhost:15672 (admin/admin123)"
echo "🔗 Join thêm node: /usr/local/bin/rabbitmq-join-cluster.sh <master-hostname>"