// Package aggregator - Metrics aggregation service
// Aggregator: Thu thập metrics từ miner và export sang time-series DB
package aggregator

import (
	"context"
	"fmt"
	"net/http"
	"time"

	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/opus-gpu/gpu-tools/internal/storage"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
	"github.com/prometheus/client_golang/prometheus/promhttp"
	"go.uber.org/zap"
)

// Config - Aggregator configuration (aggregator config – cấu hình thu thập)
type Config struct {
	MinerURL        string
	CollectInterval time.Duration
	StorageType     string // influxdb, victoria, prometheus
	StorageURL      string
	AlertRules      []AlertRule
	MetricsPort     int
}

// AlertRule - Alert rule definition (alert rule – quy tắc cảnh báo)
type AlertRule struct {
	Name      string
	Condition string  // e.g., "gpu_temperature > 85"
	Threshold float64
	Action    string
	URL       string
}

// Aggregator - Metrics aggregator (metrics collector – bộ thu thập)
type Aggregator struct {
	config     *Config
	logger     *zap.Logger
	httpClient *client.HTTPClient
	storage    storage.MetricsStorage
	alertMgr   *AlertManager

	// Prometheus metrics
	gpuHashrate         *prometheus.GaugeVec
	gpuTemperature      *prometheus.GaugeVec
	gpuPowerDraw        *prometheus.GaugeVec
	gpuMemoryUsed       *prometheus.GaugeVec
	processUptime       prometheus.Gauge
	sharesAccepted      prometheus.Counter
	collectionDuration  prometheus.Histogram
	collectionErrors    prometheus.Counter
}

// New - Create metrics aggregator (aggregator creation – tạo bộ thu thập)
func New(cfg *Config, logger *zap.Logger) (*Aggregator, error) {
	// Validate config
	if cfg.MinerURL == "" {
		return nil, fmt.Errorf("miner_url is required")
	}
	if cfg.CollectInterval == 0 {
		cfg.CollectInterval = 5 * time.Second
	}
	if cfg.MetricsPort == 0 {
		cfg.MetricsPort = 9091
	}

	// Create HTTP client
	httpClient := client.NewHTTPClient(cfg.MinerURL)

	// Create storage backend
	var store storage.MetricsStorage
	var err error
	switch cfg.StorageType {
	case "influxdb":
		store, err = storage.NewInfluxDBStorage(cfg.StorageURL)
	case "victoria":
		store, err = storage.NewVictoriaMetricsStorage(cfg.StorageURL)
	default:
		store = storage.NewMemoryStorage() // In-memory for testing
	}
	if err != nil {
		return nil, fmt.Errorf("failed to create storage: %w", err)
	}

	// Create alert manager
	alertMgr := NewAlertManager(cfg.AlertRules, logger)

	// Initialize Prometheus metrics
	agg := &Aggregator{
		config:     cfg,
		logger:     logger,
		httpClient: httpClient,
		storage:    store,
		alertMgr:   alertMgr,

		gpuHashrate: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_hashrate_mhs",
				Help: "GPU hashrate in MH/s",
			},
			[]string{"gpu_id", "gpu_name"},
		),

		gpuTemperature: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_temperature_celsius",
				Help: "GPU temperature in Celsius",
			},
			[]string{"gpu_id", "gpu_name"},
		),

		gpuPowerDraw: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_power_draw_watts",
				Help: "GPU power draw in watts",
			},
			[]string{"gpu_id", "gpu_name"},
		),

		gpuMemoryUsed: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_memory_used_mb",
				Help: "GPU memory used in MB",
			},
			[]string{"gpu_id", "gpu_name"},
		),

		processUptime: promauto.NewGauge(
			prometheus.GaugeOpts{
				Name: "mining_process_uptime_seconds",
				Help: "Mining process uptime in seconds",
			},
		),

		sharesAccepted: promauto.NewCounter(
			prometheus.CounterOpts{
				Name: "mining_shares_accepted_total",
				Help: "Total number of accepted mining shares",
			},
		),

		collectionDuration: promauto.NewHistogram(
			prometheus.HistogramOpts{
				Name:    "metrics_collection_duration_seconds",
				Help:    "Duration of metrics collection",
				Buckets: prometheus.DefBuckets,
			},
		),

		collectionErrors: promauto.NewCounter(
			prometheus.CounterOpts{
				Name: "metrics_collection_errors_total",
				Help: "Total number of metrics collection errors",
			},
		),
	}

	return agg, nil
}

// Run - Start aggregator (aggregator main loop – vòng lặp chính)
func (a *Aggregator) Run(ctx context.Context) error {
	// Start Prometheus metrics HTTP server
	go a.startMetricsServer()

	ticker := time.NewTicker(a.config.CollectInterval)
	defer ticker.Stop()

	a.logger.Info("Metrics aggregator started")

	for {
		select {
		case <-ctx.Done():
			a.logger.Info("Shutting down metrics aggregator")
			return a.storage.Close()

		case <-ticker.C:
			if err := a.collect(ctx); err != nil {
				a.logger.Error("Collection failed", zap.Error(err))
				a.collectionErrors.Inc()
			}
		}
	}
}

// collect - Thu thập metrics một lần (single collection – thu thập một lần)
func (a *Aggregator) collect(ctx context.Context) error {
	start := time.Now()
	defer func() {
		a.collectionDuration.Observe(time.Since(start).Seconds())
	}()

	// Fetch metrics từ miner
	metrics, err := a.httpClient.GetMetrics(ctx, &client.MetricsQuery{
		GPUID:    -1, // All GPUs
		Duration: a.config.CollectInterval,
	})
	if err != nil {
		return fmt.Errorf("failed to fetch metrics: %w", err)
	}

	// Process metrics
	for name, values := range metrics {
		for _, v := range values {
			// Update Prometheus metrics
			a.updatePrometheusMetrics(name, v)

			// Store to time-series DB
			if err := a.storage.Write(ctx, name, v); err != nil {
				a.logger.Warn("Failed to write to storage",
					zap.String("metric", name),
					zap.Error(err),
				)
			}

			// Check alert rules
			a.alertMgr.CheckMetric(name, v)
		}
	}

	return nil
}

// updatePrometheusMetrics - Cập nhật Prometheus metrics (metrics update – cập nhật metrics)
func (a *Aggregator) updatePrometheusMetrics(name string, value client.MetricValue) {
	gpuID := fmt.Sprintf("%v", value.Labels["gpu_id"])
	gpuName := fmt.Sprintf("%v", value.Labels["gpu_name"])

	switch name {
	case "gpu_hashrate":
		a.gpuHashrate.WithLabelValues(gpuID, gpuName).Set(value.Value)

	case "gpu_temperature":
		a.gpuTemperature.WithLabelValues(gpuID, gpuName).Set(value.Value)

	case "gpu_power_draw":
		a.gpuPowerDraw.WithLabelValues(gpuID, gpuName).Set(value.Value)

	case "gpu_memory_used":
		a.gpuMemoryUsed.WithLabelValues(gpuID, gpuName).Set(value.Value)

	case "process_uptime":
		a.processUptime.Set(value.Value)

	case "mining_shares_accepted":
		a.sharesAccepted.Add(value.Value)
	}
}

// startMetricsServer - Start HTTP server cho Prometheus metrics (metrics HTTP server – server HTTP metrics)
func (a *Aggregator) startMetricsServer() {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.Handler())

	addr := fmt.Sprintf(":%d", a.config.MetricsPort)
	a.logger.Info("Starting metrics HTTP server", zap.String("addr", addr))

	server := &http.Server{
		Addr:    addr,
		Handler: mux,
	}

	if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		a.logger.Error("Metrics server error", zap.Error(err))
	}
}

// AlertManager - Alert rule manager (alert processor – xử lý cảnh báo)
type AlertManager struct {
	rules  []AlertRule
	logger *zap.Logger
	client *http.Client
}

// NewAlertManager - Create alert manager (alert manager creation – tạo quản lý cảnh báo)
func NewAlertManager(rules []AlertRule, logger *zap.Logger) *AlertManager {
	return &AlertManager{
		rules:  rules,
		logger: logger,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
	}
}

// CheckMetric - Kiểm tra metric với alert rules (rule evaluation – đánh giá quy tắc)
func (am *AlertManager) CheckMetric(name string, value client.MetricValue) {
	for _, rule := range am.rules {
		// Parse rule condition (simplified - production cần expression evaluator)
		if name == rule.Name {
			// Check threshold
			var triggered bool
			switch rule.Condition {
			case ">":
				triggered = value.Value > rule.Threshold
			case "<":
				triggered = value.Value < rule.Threshold
			case ">=":
				triggered = value.Value >= rule.Threshold
			case "<=":
				triggered = value.Value <= rule.Threshold
			}

			if triggered {
				am.triggerAlert(rule, name, value)
			}
		}
	}
}

// triggerAlert - Trigger alert action (alert execution – thực thi cảnh báo)
func (am *AlertManager) triggerAlert(rule AlertRule, metricName string, value client.MetricValue) {
	am.logger.Warn("Alert triggered",
		zap.String("rule", rule.Name),
		zap.String("metric", metricName),
		zap.Float64("value", value.Value),
		zap.Float64("threshold", rule.Threshold),
	)

	switch rule.Action {
	case "webhook":
		am.sendWebhook(rule.URL, rule, metricName, value)
	case "log":
		// Already logged above
	}
}

// sendWebhook - Gửi webhook alert (webhook notification – thông báo webhook)
func (am *AlertManager) sendWebhook(url string, rule AlertRule, metric string, value client.MetricValue) {
	// TODO: Implement webhook POST request
	am.logger.Info("Sending webhook",
		zap.String("url", url),
		zap.String("rule", rule.Name),
	)
}
