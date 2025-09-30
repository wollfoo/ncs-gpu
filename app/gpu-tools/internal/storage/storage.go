// Package storage - Metrics storage backends
// Storage: Interface và implementations cho time-series databases
package storage

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/influxdata/influxdb-client-go/v2"
	"github.com/opus-gpu/gpu-tools/internal/client"
)

// MetricsStorage - Storage interface (storage abstraction – trừu tượng lưu trữ)
type MetricsStorage interface {
	Write(ctx context.Context, name string, value client.MetricValue) error
	Query(ctx context.Context, query string) ([]client.MetricValue, error)
	Close() error
}

// ============================================================================
// In-Memory Storage (for testing)
// ============================================================================

// MemoryStorage - In-memory storage implementation (memory backend – backend bộ nhớ)
type MemoryStorage struct {
	data map[string][]client.MetricValue
	mu   sync.RWMutex
}

// NewMemoryStorage - Create memory storage (memory storage creation – tạo bộ nhớ)
func NewMemoryStorage() *MemoryStorage {
	return &MemoryStorage{
		data: make(map[string][]client.MetricValue),
	}
}

// Write - Write metric to memory (memory write – ghi vào bộ nhớ)
func (s *MemoryStorage) Write(ctx context.Context, name string, value client.MetricValue) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	s.data[name] = append(s.data[name], value)

	// Keep last 1000 values per metric
	if len(s.data[name]) > 1000 {
		s.data[name] = s.data[name][len(s.data[name])-1000:]
	}

	return nil
}

// Query - Query metrics từ memory (memory query – truy vấn bộ nhớ)
func (s *MemoryStorage) Query(ctx context.Context, query string) ([]client.MetricValue, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// Simplified query - production cần proper query parser
	if values, ok := s.data[query]; ok {
		return values, nil
	}

	return nil, fmt.Errorf("metric not found: %s", query)
}

// Close - Close storage (cleanup – dọn dẹp)
func (s *MemoryStorage) Close() error {
	return nil
}

// ============================================================================
// InfluxDB Storage
// ============================================================================

// InfluxDBStorage - InfluxDB storage implementation (InfluxDB backend – backend InfluxDB)
type InfluxDBStorage struct {
	client   influxdb2.Client
	writeAPI influxdb2.WriteAPI
	org      string
	bucket   string
}

// NewInfluxDBStorage - Create InfluxDB storage (InfluxDB storage creation – tạo InfluxDB storage)
func NewInfluxDBStorage(url string) (*InfluxDBStorage, error) {
	// Parse connection string: influxdb://host:port?org=myorg&bucket=metrics&token=xxx
	// Simplified - production cần proper URL parsing

	client := influxdb2.NewClient(url, "your-token")

	org := "myorg"
	bucket := "metrics"

	writeAPI := client.WriteAPI(org, bucket)

	return &InfluxDBStorage{
		client:   client,
		writeAPI: writeAPI,
		org:      org,
		bucket:   bucket,
	}, nil
}

// Write - Write metric to InfluxDB (InfluxDB write – ghi vào InfluxDB)
func (s *InfluxDBStorage) Write(ctx context.Context, name string, value client.MetricValue) error {
	// Create InfluxDB point
	point := influxdb2.NewPoint(
		name,
		value.Labels,
		map[string]interface{}{"value": value.Value},
		value.Timestamp,
	)

	// Write point
	s.writeAPI.WritePoint(point)

	return nil
}

// Query - Query metrics từ InfluxDB (InfluxDB query – truy vấn InfluxDB)
func (s *InfluxDBStorage) Query(ctx context.Context, query string) ([]client.MetricValue, error) {
	queryAPI := s.client.QueryAPI(s.org)

	result, err := queryAPI.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("InfluxDB query failed: %w", err)
	}

	var metrics []client.MetricValue
	for result.Next() {
		record := result.Record()

		value, ok := record.Value().(float64)
		if !ok {
			continue
		}

		metrics = append(metrics, client.MetricValue{
			Value:     value,
			Labels:    record.Values(),
			Timestamp: record.Time(),
		})
	}

	if result.Err() != nil {
		return nil, fmt.Errorf("InfluxDB query error: %w", result.Err())
	}

	return metrics, nil
}

// Close - Close InfluxDB connection (InfluxDB cleanup – đóng InfluxDB)
func (s *InfluxDBStorage) Close() error {
	s.writeAPI.Flush()
	s.client.Close()
	return nil
}

// ============================================================================
// VictoriaMetrics Storage
// ============================================================================

// VictoriaMetricsStorage - VictoriaMetrics storage implementation (VictoriaMetrics backend – backend VictoriaMetrics)
type VictoriaMetricsStorage struct {
	url    string
	client *client.HTTPClient
}

// NewVictoriaMetricsStorage - Create VictoriaMetrics storage (VictoriaMetrics creation – tạo VictoriaMetrics)
func NewVictoriaMetricsStorage(url string) (*VictoriaMetricsStorage, error) {
	return &VictoriaMetricsStorage{
		url:    url,
		client: client.NewHTTPClient(url),
	}, nil
}

// Write - Write metric to VictoriaMetrics (VictoriaMetrics write – ghi vào VictoriaMetrics)
func (s *VictoriaMetricsStorage) Write(ctx context.Context, name string, value client.MetricValue) error {
	// TODO: Implement VictoriaMetrics write API
	// Use Prometheus remote write protocol
	return nil
}

// Query - Query metrics từ VictoriaMetrics (VictoriaMetrics query – truy vấn VictoriaMetrics)
func (s *VictoriaMetricsStorage) Query(ctx context.Context, query string) ([]client.MetricValue, error) {
	// TODO: Implement VictoriaMetrics query API (PromQL)
	return nil, fmt.Errorf("not implemented")
}

// Close - Close VictoriaMetrics connection (cleanup – dọn dẹp)
func (s *VictoriaMetricsStorage) Close() error {
	return nil
}

// ============================================================================
// Config helper
// ============================================================================

// LoadAggregatorConfig - Load aggregator config từ file (config loading – tải cấu hình)
func LoadAggregatorConfig(path string) (*AggregatorConfig, error) {
	// Simplified - production cần proper config loading
	return &AggregatorConfig{
		MinerURL:        "http://localhost:8080",
		CollectInterval: 5 * time.Second,
		StorageType:     "memory",
		MetricsPort:     9091,
		AlertRules: []AlertRule{
			{
				Name:      "gpu_temperature",
				Condition: ">",
				Threshold: 85.0,
				Action:    "webhook",
				URL:       "https://alerts.example.com/gpu-overheat",
			},
		},
	}, nil
}

// AggregatorConfig - Aggregator configuration (aggregator config – cấu hình aggregator)
type AggregatorConfig struct {
	MinerURL        string
	CollectInterval time.Duration
	StorageType     string
	StorageURL      string
	MetricsPort     int
	AlertRules      []AlertRule
}

// AlertRule - Alert rule definition (alert rule – quy tắc cảnh báo)
type AlertRule struct {
	Name      string
	Condition string
	Threshold float64
	Action    string
	URL       string
}
