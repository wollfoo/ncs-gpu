package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

// Collector holds all Prometheus metrics
type Collector struct {
	// GPU Metrics
	gpuTemperature   *prometheus.GaugeVec
	gpuPower         *prometheus.GaugeVec
	gpuUtilization   *prometheus.GaugeVec
	gpuMemoryUsed    *prometheus.GaugeVec
	gpuMemoryTotal   *prometheus.GaugeVec
	gpuHashrate      *prometheus.GaugeVec
	
	// Mining Metrics
	sharesAccepted   *prometheus.CounterVec
	sharesRejected   *prometheus.CounterVec
	sharesInvalid    *prometheus.CounterVec
	poolConnected    *prometheus.GaugeVec
	
	// Worker Metrics
	workerUptime     *prometheus.GaugeVec
	workerRestarts   *prometheus.CounterVec
	workerErrors     *prometheus.CounterVec
	
	// System Metrics
	apiRequests      *prometheus.CounterVec
	apiLatency       *prometheus.HistogramVec
}

// NewCollector creates a new metrics collector
func NewCollector() *Collector {
	return &Collector{
		// GPU Metrics
		gpuTemperature: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_temperature_celsius",
				Help: "GPU temperature in Celsius",
			},
			[]string{"gpu_index", "gpu_name"},
		),
		gpuPower: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_power_watts",
				Help: "GPU power consumption in watts",
			},
			[]string{"gpu_index", "gpu_name"},
		),
		gpuUtilization: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_utilization_percent",
				Help: "GPU utilization percentage",
			},
			[]string{"gpu_index", "gpu_name"},
		),
		gpuMemoryUsed: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_memory_used_mb",
				Help: "GPU memory used in MB",
			},
			[]string{"gpu_index", "gpu_name"},
		),
		gpuMemoryTotal: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_memory_total_mb",
				Help: "GPU total memory in MB",
			},
			[]string{"gpu_index", "gpu_name"},
		),
		gpuHashrate: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "gpu_hashrate_mhs",
				Help: "GPU mining hashrate in MH/s",
			},
			[]string{"gpu_index", "gpu_name", "algorithm"},
		),
		
		// Mining Metrics
		sharesAccepted: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "mining_shares_accepted_total",
				Help: "Total number of accepted shares",
			},
			[]string{"worker_id", "pool"},
		),
		sharesRejected: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "mining_shares_rejected_total",
				Help: "Total number of rejected shares",
			},
			[]string{"worker_id", "pool", "reason"},
		),
		sharesInvalid: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "mining_shares_invalid_total",
				Help: "Total number of invalid shares",
			},
			[]string{"worker_id", "pool"},
		),
		poolConnected: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "mining_pool_connected",
				Help: "Pool connection status (1=connected, 0=disconnected)",
			},
			[]string{"pool", "worker_id"},
		),
		
		// Worker Metrics
		workerUptime: promauto.NewGaugeVec(
			prometheus.GaugeOpts{
				Name: "worker_uptime_seconds",
				Help: "Worker uptime in seconds",
			},
			[]string{"worker_id", "gpu_index"},
		),
		workerRestarts: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "worker_restarts_total",
				Help: "Total number of worker restarts",
			},
			[]string{"worker_id", "gpu_index"},
		),
		workerErrors: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "worker_errors_total",
				Help: "Total number of worker errors",
			},
			[]string{"worker_id", "gpu_index", "error_type"},
		),
		
		// System Metrics
		apiRequests: promauto.NewCounterVec(
			prometheus.CounterOpts{
				Name: "api_requests_total",
				Help: "Total number of API requests",
			},
			[]string{"method", "endpoint", "status"},
		),
		apiLatency: promauto.NewHistogramVec(
			prometheus.HistogramOpts{
				Name:    "api_request_duration_seconds",
				Help:    "API request latency in seconds",
				Buckets: prometheus.DefBuckets,
			},
			[]string{"method", "endpoint"},
		),
	}
}

// Register registers all metrics with Prometheus
func (c *Collector) Register() {
	// Metrics are auto-registered by promauto
}

// UpdateGPUMetrics updates GPU-related metrics
func (c *Collector) UpdateGPUMetrics(gpuIndex int, gpuName string, temp, power, util, memUsed, memTotal float64) {
	labels := prometheus.Labels{
		"gpu_index": string(rune(gpuIndex)),
		"gpu_name":  gpuName,
	}
	
	c.gpuTemperature.With(labels).Set(temp)
	c.gpuPower.With(labels).Set(power)
	c.gpuUtilization.With(labels).Set(util)
	c.gpuMemoryUsed.With(labels).Set(memUsed)
	c.gpuMemoryTotal.With(labels).Set(memTotal)
}

// UpdateHashrate updates mining hashrate metric
func (c *Collector) UpdateHashrate(gpuIndex int, gpuName, algorithm string, hashrate float64) {
	c.gpuHashrate.With(prometheus.Labels{
		"gpu_index": string(rune(gpuIndex)),
		"gpu_name":  gpuName,
		"algorithm": algorithm,
	}).Set(hashrate)
}

// IncrementSharesAccepted increments accepted shares counter
func (c *Collector) IncrementSharesAccepted(workerID, pool string) {
	c.sharesAccepted.With(prometheus.Labels{
		"worker_id": workerID,
		"pool":      pool,
	}).Inc()
}

// IncrementSharesRejected increments rejected shares counter
func (c *Collector) IncrementSharesRejected(workerID, pool, reason string) {
	c.sharesRejected.With(prometheus.Labels{
		"worker_id": workerID,
		"pool":      pool,
		"reason":    reason,
	}).Inc()
}

// UpdatePoolConnection updates pool connection status
func (c *Collector) UpdatePoolConnection(pool, workerID string, connected bool) {
	value := 0.0
	if connected {
		value = 1.0
	}
	c.poolConnected.With(prometheus.Labels{
		"pool":      pool,
		"worker_id": workerID,
	}).Set(value)
}

// UpdateWorkerUptime updates worker uptime metric
func (c *Collector) UpdateWorkerUptime(workerID string, gpuIndex int, uptimeSeconds float64) {
	c.workerUptime.With(prometheus.Labels{
		"worker_id":  workerID,
		"gpu_index": string(rune(gpuIndex)),
	}).Set(uptimeSeconds)
}

// IncrementWorkerRestarts increments worker restart counter
func (c *Collector) IncrementWorkerRestarts(workerID string, gpuIndex int) {
	c.workerRestarts.With(prometheus.Labels{
		"worker_id":  workerID,
		"gpu_index": string(rune(gpuIndex)),
	}).Inc()
}

// IncrementWorkerErrors increments worker error counter
func (c *Collector) IncrementWorkerErrors(workerID string, gpuIndex int, errorType string) {
	c.workerErrors.With(prometheus.Labels{
		"worker_id":  workerID,
		"gpu_index": string(rune(gpuIndex)),
		"error_type": errorType,
	}).Inc()
}

// RecordAPIRequest records an API request
func (c *Collector) RecordAPIRequest(method, endpoint, status string, duration float64) {
	c.apiRequests.With(prometheus.Labels{
		"method":   method,
		"endpoint": endpoint,
		"status":   status,
	}).Inc()
	
	c.apiLatency.With(prometheus.Labels{
		"method":   method,
		"endpoint": endpoint,
	}).Observe(duration)
}
