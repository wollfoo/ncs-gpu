// Package main implements the GPU scheduler service
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"github.com/opus-gpu/scheduler/internal/cgo"
	"github.com/opus-gpu/scheduler/internal/fault"
	"github.com/opus-gpu/scheduler/internal/loadbalancer"
	"github.com/opus-gpu/scheduler/internal/resource"
	"github.com/opus-gpu/scheduler/internal/scheduler"
	"github.com/opus-gpu/scheduler/pkg/task"
	"github.com/spf13/viper"
	"go.uber.org/zap"
)

// Scheduler orchestrates GPU task scheduling
type Scheduler struct {
	config         *Config
	runtime        *cgo.RuntimeHandle
	taskQueue      *TaskQueue
	taskGraph      *task.TaskGraph
	algorithms     map[string]scheduler.Algorithm
	loadBalancer   *loadbalancer.LoadBalancer
	resourcePool   *resource.ResourcePool
	recoveryMgr    *fault.RecoveryManager
	logger         *zap.Logger
	metrics        *Metrics
	stopCh         chan struct{}
	wg             sync.WaitGroup
}

// Config holds scheduler configuration
type Config struct {
	// Scheduler settings
	Algorithm       string        `mapstructure:"algorithm"`
	MaxConcurrent   int           `mapstructure:"max_concurrent"`
	ScheduleInterval time.Duration `mapstructure:"schedule_interval"`
	
	// Resource settings
	GPUCount        int     `mapstructure:"gpu_count"`
	MemoryFraction  float64 `mapstructure:"memory_fraction"`
	
	// Load balancing
	LoadBalanceStrategy string `mapstructure:"load_balance_strategy"`
	EnableWorkStealing  bool   `mapstructure:"enable_work_stealing"`
	
	// Fault tolerance
	EnableCheckpointing bool          `mapstructure:"enable_checkpointing"`
	CheckpointInterval  time.Duration `mapstructure:"checkpoint_interval"`
	MaxRetries          int           `mapstructure:"max_retries"`
	
	// Runtime
	RuntimeConfigPath string `mapstructure:"runtime_config_path"`
	LogLevel          string `mapstructure:"log_level"`
}

// TaskQueue manages pending tasks
type TaskQueue struct {
	pending  []*task.Task
	running  map[string]*task.Task
	complete map[string]*task.Task
	mu       sync.RWMutex
}

// Metrics tracks scheduler performance
type Metrics struct {
	TasksScheduled   uint64
	TasksCompleted   uint64
	TasksFailed      uint64
	AverageWaitTime  time.Duration
	AverageExecTime  time.Duration
	ResourceUtilization float64
}

func main() {
	// Parse command line flags
	configPath := flag.String("config", "config.yaml", "Path to configuration file")
	flag.Parse()
	
	// Load configuration
	config, err := loadConfig(*configPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to load config: %v\n", err)
		os.Exit(1)
	}
	
	// Initialize logger
	logger, err := initLogger(config.LogLevel)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Failed to init logger: %v\n", err)
		os.Exit(1)
	}
	defer logger.Sync()
	
	// Create scheduler
	sched, err := NewScheduler(config, logger)
	if err != nil {
		logger.Fatal("Failed to create scheduler", zap.Error(err))
	}
	
	// Start scheduler
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	
	if err := sched.Start(ctx); err != nil {
		logger.Fatal("Failed to start scheduler", zap.Error(err))
	}
	
	// Wait for shutdown signal
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, os.Interrupt, syscall.SIGTERM)
	
	<-sigCh
	logger.Info("Shutting down scheduler...")
	
	// Graceful shutdown
	sched.Stop()
	logger.Info("Scheduler stopped")
}

// NewScheduler creates a new scheduler instance
func NewScheduler(config *Config, logger *zap.Logger) (*Scheduler, error) {
	// Initialize Rust runtime
	runtime, err := cgo.NewRuntime(config.RuntimeConfigPath)
	if err != nil {
		return nil, fmt.Errorf("failed to init runtime: %w", err)
	}
	
	// Initialize scheduling algorithms
	algorithms := map[string]scheduler.Algorithm{
		"fifo":     scheduler.NewFIFOScheduler(logger),
		"priority": scheduler.NewPriorityScheduler(logger),
		"fair":     scheduler.NewFairQueueScheduler(logger),
		"deadline": scheduler.NewDeadlineScheduler(logger),
		"affinity": scheduler.NewAffinityScheduler(logger, scheduler.NewPriorityScheduler(logger)),
	}
	
	// Initialize load balancer
	var strategy loadbalancer.BalancingStrategy
	switch config.LoadBalanceStrategy {
		case "round-robin":
			strategy = loadbalancer.NewRoundRobinStrategy()
		case "least-loaded":
			strategy = loadbalancer.NewLeastLoadedStrategy()
		default:
			strategy = loadbalancer.NewLeastLoadedStrategy()
	}
	
	lb := loadbalancer.NewLoadBalancer(config.GPUCount, strategy, logger)
	
	// Initialize resource pool
	allocStrategy := resource.NewBestFitStrategy(logger)
	resourcePool := resource.NewResourcePool(config.GPUCount, allocStrategy, logger)
	
	// Initialize recovery manager
	recoveryMgr := fault.NewRecoveryManager(logger)
	
	return &Scheduler{
		config:       config,
		runtime:      runtime,
		taskQueue:    NewTaskQueue(),
		taskGraph:    task.NewTaskGraph(),
		algorithms:   algorithms,
		loadBalancer: lb,
		resourcePool: resourcePool,
		recoveryMgr:  recoveryMgr,
		logger:       logger,
		metrics:      &Metrics{},
		stopCh:       make(chan struct{}),
	}, nil
}

// Start starts the scheduler
func (s *Scheduler) Start(ctx context.Context) error {
	s.logger.Info("Starting scheduler",
		zap.String("algorithm", s.config.Algorithm),
		zap.Int("gpus", s.config.GPUCount))
	
	// Start load balancer
	if err := s.loadBalancer.Start(ctx); err != nil {
		return fmt.Errorf("failed to start load balancer: %w", err)
	}
	
	// Start scheduling loop
	s.wg.Add(1)
	go s.schedulingLoop(ctx)
	
	// Start task execution loop
	s.wg.Add(1)
	go s.executionLoop(ctx)
	
	// Start monitoring loop
	s.wg.Add(1)
	go s.monitoringLoop(ctx)
	
	// Start checkpoint loop if enabled
	if s.config.EnableCheckpointing {
		s.wg.Add(1)
		go s.checkpointLoop(ctx)
	}
	
	return nil
}

// Stop stops the scheduler
func (s *Scheduler) Stop() {
	close(s.stopCh)
	s.wg.Wait()
	
	// Cleanup
	s.loadBalancer.Stop()
	s.runtime.Shutdown()
}

// schedulingLoop is the main scheduling loop
func (s *Scheduler) schedulingLoop(ctx context.Context) {
	defer s.wg.Done()
	
	ticker := time.NewTicker(s.config.ScheduleInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-s.stopCh:
			return
		case <-ticker.C:
			s.scheduleNext()
		}
	}
}

// scheduleNext schedules the next task
func (s *Scheduler) scheduleNext() {
	// Get ready tasks
	readyTasks := s.taskQueue.GetReadyTasks()
	if len(readyTasks) == 0 {
		return
	}
	
	// Get resource status
	resourceStatus := s.resourcePool.GetResourceStatus()
	resourceState := scheduler.ResourceState{
		TotalGPUs:     resourceStatus.TotalGPUs,
		AvailableGPUs: resourceStatus.AvailableGPUs,
		GPUUtilization: make(map[int]float64),
		MemoryUsage:    make(map[int]int),
		Temperature:    make(map[int]float32),
	}
	
	for _, gpu := range resourceStatus.GPUStatuses {
		resourceState.GPUUtilization[gpu.ID] = gpu.Load
		resourceState.MemoryUsage[gpu.ID] = gpu.MemoryUsed
		resourceState.Temperature[gpu.ID] = float32(gpu.Temperature)
	}
	
	// Select algorithm
	algo, exists := s.algorithms[s.config.Algorithm]
	if !exists {
		algo = s.algorithms["priority"]
	}
	
	// Schedule task
	selectedTask, err := algo.Schedule(readyTasks, resourceState)
	if err != nil {
		s.logger.Debug("No task scheduled", zap.Error(err))
		return
	}
	
	// Allocate resources
	req := resource.ResourceRequest{
		GPUCount:    selectedTask.Resources.GPUs,
		MinMemoryMB: selectedTask.Resources.MemoryMB,
	}
	
	allocation, err := s.resourcePool.Allocate(selectedTask.ID, req)
	if err != nil {
		s.logger.Error("Failed to allocate resources",
			zap.String("taskID", selectedTask.ID),
			zap.Error(err))
		return
	}
	
	// Distribute to load balancer
	if err := s.loadBalancer.Distribute(selectedTask); err != nil {
		s.logger.Error("Failed to distribute task",
			zap.String("taskID", selectedTask.ID),
			zap.Error(err))
		
		// Release resources
		s.resourcePool.Deallocate(selectedTask.ID)
		return
	}
	
	// Update task status
	selectedTask.UpdateStatus(task.TaskStatusScheduled)
	s.taskQueue.MarkRunning(selectedTask)
	
	s.metrics.TasksScheduled++
	
	s.logger.Info("Task scheduled",
		zap.String("taskID", selectedTask.ID),
		zap.String("type", string(selectedTask.Type)),
		zap.Int("gpus", len(allocation.Resources)))
}

// executionLoop handles task execution
func (s *Scheduler) executionLoop(ctx context.Context) {
	defer s.wg.Done()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-s.stopCh:
			return
		default:
			s.processRunningTasks()
			time.Sleep(100 * time.Millisecond)
		}
	}
}

// processRunningTasks processes running tasks
func (s *Scheduler) processRunningTasks() {
	runningTasks := s.taskQueue.GetRunningTasks()
	
	for _, t := range runningTasks {
		// Check task status via runtime
		result, err := s.runtime.GetTaskResult(t.ID)
		if err != nil {
			// Task still running or not found
			continue
		}
		
		// Task completed
		t.UpdateStatus(task.TaskStatusCompleted)
		t.Result = &task.TaskResult{
			Output:   result,
			Duration: t.GetExecutionTime(),
		}
		
		// Release resources
		if err := s.resourcePool.Deallocate(t.ID); err != nil {
			s.logger.Error("Failed to deallocate resources",
				zap.String("taskID", t.ID),
				zap.Error(err))
		}
		
		// Move to completed
		s.taskQueue.MarkComplete(t)
		s.metrics.TasksCompleted++
		
		s.logger.Info("Task completed",
			zap.String("taskID", t.ID),
			zap.Duration("duration", t.GetExecutionTime()))
		
		// Process dependent tasks
		for _, dep := range t.Dependents {
			if dep.IsReady() {
				dep.UpdateStatus(task.TaskStatusPending)
			}
		}
	}
}

// monitoringLoop monitors system health
func (s *Scheduler) monitoringLoop(ctx context.Context) {
	defer s.wg.Done()
	
	ticker := time.NewTicker(10 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-s.stopCh:
			return
		case <-ticker.C:
			s.logMetrics()
		}
	}
}

// checkpointLoop saves checkpoints periodically
func (s *Scheduler) checkpointLoop(ctx context.Context) {
	defer s.wg.Done()
	
	ticker := time.NewTicker(s.config.CheckpointInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-s.stopCh:
			return
		case <-ticker.C:
			s.saveCheckpoints()
		}
	}
}

// saveCheckpoints saves task checkpoints
func (s *Scheduler) saveCheckpoints() {
	runningTasks := s.taskQueue.GetRunningTasks()
	
	for _, t := range runningTasks {
		// In real implementation, would get actual state
		state := []byte(fmt.Sprintf("checkpoint-%s", t.ID))
		progress := 0.5 // Dummy progress
		
		if err := s.recoveryMgr.SaveCheckpoint(t, state, progress); err != nil {
			s.logger.Error("Failed to save checkpoint",
				zap.String("taskID", t.ID),
				zap.Error(err))
		}
	}
}

// logMetrics logs scheduler metrics
func (s *Scheduler) logMetrics() {
	resourceStatus := s.resourcePool.GetResourceStatus()
	
	s.logger.Info("Scheduler metrics",
		zap.Uint64("scheduled", s.metrics.TasksScheduled),
		zap.Uint64("completed", s.metrics.TasksCompleted),
		zap.Uint64("failed", s.metrics.TasksFailed),
		zap.Float64("utilization", resourceStatus.Utilization),
		zap.Int("pending", s.taskQueue.PendingCount()),
		zap.Int("running", s.taskQueue.RunningCount()))
}

// SubmitTask submits a new task
func (s *Scheduler) SubmitTask(t *task.Task) error {
	// Add to task graph
	if err := s.taskGraph.AddTask(t); err != nil {
		return fmt.Errorf("failed to add task to graph: %w", err)
	}
	
	// Add to queue
	s.taskQueue.AddTask(t)
	
	s.logger.Info("Task submitted",
		zap.String("taskID", t.ID),
		zap.String("type", string(t.Type)))
	
	return nil
}

// TaskQueue implementation
func NewTaskQueue() *TaskQueue {
	return &TaskQueue{
		pending:  make([]*task.Task, 0),
		running:  make(map[string]*task.Task),
		complete: make(map[string]*task.Task),
	}
}

func (tq *TaskQueue) AddTask(t *task.Task) {
	tq.mu.Lock()
	defer tq.mu.Unlock()
	tq.pending = append(tq.pending, t)
}

func (tq *TaskQueue) GetReadyTasks() []*task.Task {
	tq.mu.RLock()
	defer tq.mu.RUnlock()
	
	ready := make([]*task.Task, 0)
	for _, t := range tq.pending {
		if t.IsReady() {
			ready = append(ready, t)
		}
	}
	return ready
}

func (tq *TaskQueue) GetRunningTasks() []*task.Task {
	tq.mu.RLock()
	defer tq.mu.RUnlock()
	
	tasks := make([]*task.Task, 0, len(tq.running))
	for _, t := range tq.running {
		tasks = append(tasks, t)
	}
	return tasks
}

func (tq *TaskQueue) MarkRunning(t *task.Task) {
	tq.mu.Lock()
	defer tq.mu.Unlock()
	
	// Remove from pending
	for i, pt := range tq.pending {
		if pt.ID == t.ID {
			tq.pending = append(tq.pending[:i], tq.pending[i+1:]...)
			break
		}
	}
	
	// Add to running
	tq.running[t.ID] = t
}

func (tq *TaskQueue) MarkComplete(t *task.Task) {
	tq.mu.Lock()
	defer tq.mu.Unlock()
	
	delete(tq.running, t.ID)
	tq.complete[t.ID] = t
}

func (tq *TaskQueue) PendingCount() int {
	tq.mu.RLock()
	defer tq.mu.RUnlock()
	return len(tq.pending)
}

func (tq *TaskQueue) RunningCount() int {
	tq.mu.RLock()
	defer tq.mu.RUnlock()
	return len(tq.running)
}

// Helper functions
func loadConfig(path string) (*Config, error) {
	viper.SetConfigFile(path)
	viper.SetDefault("algorithm", "priority")
	viper.SetDefault("max_concurrent", 10)
	viper.SetDefault("schedule_interval", "1s")
	viper.SetDefault("gpu_count", 4)
	viper.SetDefault("memory_fraction", 0.9)
	viper.SetDefault("load_balance_strategy", "least-loaded")
	viper.SetDefault("enable_work_stealing", true)
	viper.SetDefault("enable_checkpointing", true)
	viper.SetDefault("checkpoint_interval", "5m")
	viper.SetDefault("max_retries", 3)
	viper.SetDefault("log_level", "info")
	
	if err := viper.ReadInConfig(); err != nil {
		// Use defaults if config not found
		if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
			return nil, err
		}
	}
	
	var config Config
	if err := viper.Unmarshal(&config); err != nil {
		return nil, err
	}
	
	return &config, nil
}

func initLogger(level string) (*zap.Logger, error) {
	config := zap.NewProductionConfig()
	
	switch level {
	case "debug":
		config.Level = zap.NewAtomicLevelAt(zap.DebugLevel)
	case "info":
		config.Level = zap.NewAtomicLevelAt(zap.InfoLevel)
	case "warn":
		config.Level = zap.NewAtomicLevelAt(zap.WarnLevel)
	case "error":
		config.Level = zap.NewAtomicLevelAt(zap.ErrorLevel)
	default:
		config.Level = zap.NewAtomicLevelAt(zap.InfoLevel)
	}
	
	return config.Build()
}
