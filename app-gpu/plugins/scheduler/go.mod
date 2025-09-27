module github.com/opus-gpu/scheduler

go 1.21

require (
	// Logging và monitoring
	go.uber.org/zap v1.26.0
	github.com/prometheus/client_golang v1.18.0
	
	// Concurrency và sync
	golang.org/x/sync v0.5.0
	github.com/panjf2000/ants/v2 v2.9.0
	
	// Distributed coordination
	github.com/hashicorp/raft v1.6.0
	go.etcd.io/etcd/client/v3 v3.5.11
	
	// Serialization
	google.golang.org/protobuf v1.32.0
	github.com/vmihailenco/msgpack/v5 v5.4.1
	
	// Utils
	github.com/google/uuid v1.5.0
	github.com/spf13/viper v1.18.2
	github.com/stretchr/testify v1.8.4
)

require (
	go.uber.org/multierr v1.11.0 // indirect
	go.uber.org/atomic v1.11.0 // indirect
)
