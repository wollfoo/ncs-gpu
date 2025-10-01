package orchestrator

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/sirupsen/logrus"
)

// Config holds orchestrator configuration
type Config struct {
	MaxWorkersPerGPU  int
	RestartDelay      time.Duration
	PoolURL          string
	WalletAddress    string
	WorkerNamePrefix string
	GPUPowerLimit    int
	GPUTargetTemp    int
	MonitorInterval  time.Duration
}

// Orchestrator manages GPU mining workers
type Orchestrator struct {
	config   Config
	logger   *logrus.Logger
	workers  map[string]*Worker
	mu       sync.RWMutex
	stopChan chan struct{}
}

// Worker represents a mining worker
type Worker struct {
	ID        string
	GPUIndex  int
	Status    string
	Hashrate  float64
	StartTime time.Time
	Errors    int
}

// New creates a new orchestrator instance
func New(config Config, logger *logrus.Logger) *Orchestrator {
	return &Orchestrator{
		config:   config,
		logger:   logger,
		workers:  make(map[string]*Worker),
		stopChan: make(chan struct{}),
	}
}

// Start begins orchestrator operation
func (o *Orchestrator) Start(ctx context.Context) error {
	o.logger.Info("Starting orchestrator...")
	
	// Validate configuration
	if err := o.validateConfig(); err != nil {
		return fmt.Errorf("config validation failed: %w", err)
	}
	
	// Start worker management loop
	go o.manageWorkers(ctx)
	
	// Start monitoring loop
	go o.monitorWorkers(ctx)
	
	// Wait for context cancellation
	<-ctx.Done()
	o.logger.Info("Orchestrator context cancelled, stopping...")
	
	// Cleanup
	o.stopAllWorkers()
	
	return nil
}

func (o *Orchestrator) validateConfig() error {
	if o.config.WalletAddress == "" {
		return fmt.Errorf("wallet address is required")
	}
	
	if o.config.PoolURL == "" {
		return fmt.Errorf("pool URL is required")
	}
	
	if o.config.MaxWorkersPerGPU <= 0 {
		o.config.MaxWorkersPerGPU = 1
	}
	
	return nil
}

func (o *Orchestrator) manageWorkers(ctx context.Context) {
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			o.checkAndRestartWorkers()
		}
	}
}

func (o *Orchestrator) monitorWorkers(ctx context.Context) {
	ticker := time.NewTicker(o.config.MonitorInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			o.collectMetrics()
			o.reportStatus()
		}
	}
}

func (o *Orchestrator) checkAndRestartWorkers() {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	for id, worker := range o.workers {
		if worker.Status == "error" || worker.Status == "stopped" {
			o.logger.Warnf("Worker %s is not running, scheduling restart...", id)
			
			// Schedule restart after delay
			go func(w *Worker) {
				time.Sleep(o.config.RestartDelay)
				o.restartWorker(w)
			}(worker)
		}
	}
}

func (o *Orchestrator) restartWorker(worker *Worker) {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	o.logger.Infof("Restarting worker %s...", worker.ID)
	
	// Reset worker state
	worker.Status = "starting"
	worker.StartTime = time.Now()
	worker.Errors = 0
	
	// TODO: Implement actual worker restart logic
	
	// Simulate successful restart
	worker.Status = "running"
	o.logger.Infof("Worker %s restarted successfully", worker.ID)
}

func (o *Orchestrator) collectMetrics() {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	totalHashrate := 0.0
	runningWorkers := 0
	
	for _, worker := range o.workers {
		if worker.Status == "running" {
			runningWorkers++
			totalHashrate += worker.Hashrate
		}
	}
	
	o.logger.WithFields(logrus.Fields{
		"total_workers":   len(o.workers),
		"running_workers": runningWorkers,
		"total_hashrate":  totalHashrate,
	}).Info("Orchestrator metrics")
}

func (o *Orchestrator) reportStatus() {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	for _, worker := range o.workers {
		uptime := time.Since(worker.StartTime)
		o.logger.WithFields(logrus.Fields{
			"worker_id": worker.ID,
			"gpu_index": worker.GPUIndex,
			"status":    worker.Status,
			"hashrate":  worker.Hashrate,
			"uptime":    uptime.String(),
			"errors":    worker.Errors,
		}).Debug("Worker status")
	}
}

func (o *Orchestrator) stopAllWorkers() {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	o.logger.Info("Stopping all workers...")
	
	for id, worker := range o.workers {
		worker.Status = "stopping"
		// TODO: Implement actual worker stop logic
		worker.Status = "stopped"
		o.logger.Infof("Worker %s stopped", id)
	}
}

// AddWorker adds a new worker to orchestrator management
func (o *Orchestrator) AddWorker(gpuIndex int) string {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	workerID := fmt.Sprintf("%s-gpu%d-%d", 
		o.config.WorkerNamePrefix, 
		gpuIndex, 
		time.Now().Unix())
	
	worker := &Worker{
		ID:        workerID,
		GPUIndex:  gpuIndex,
		Status:    "starting",
		StartTime: time.Now(),
		Errors:    0,
	}
	
	o.workers[workerID] = worker
	o.logger.Infof("Added worker %s for GPU %d", workerID, gpuIndex)
	
	// TODO: Actually start the worker process
	worker.Status = "running"
	
	return workerID
}

// RemoveWorker removes a worker from orchestrator management
func (o *Orchestrator) RemoveWorker(workerID string) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	
	worker, exists := o.workers[workerID]
	if !exists {
		return fmt.Errorf("worker %s not found", workerID)
	}
	
	// Stop the worker
	worker.Status = "stopping"
	// TODO: Actually stop the worker process
	
	delete(o.workers, workerID)
	o.logger.Infof("Removed worker %s", workerID)
	
	return nil
}

// GetWorkerStatus returns status of a specific worker
func (o *Orchestrator) GetWorkerStatus(workerID string) (*Worker, error) {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	worker, exists := o.workers[workerID]
	if !exists {
		return nil, fmt.Errorf("worker %s not found", workerID)
	}
	
	return worker, nil
}

// GetAllWorkers returns all workers
func (o *Orchestrator) GetAllWorkers() map[string]*Worker {
	o.mu.RLock()
	defer o.mu.RUnlock()
	
	// Return a copy to avoid race conditions
	workers := make(map[string]*Worker)
	for k, v := range o.workers {
		workers[k] = v
	}
	
	return workers
}
