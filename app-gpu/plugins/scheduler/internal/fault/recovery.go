// Package fault implements fault tolerance and recovery mechanisms
package fault

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/opus-gpu/scheduler/pkg/task"
	"go.uber.org/zap"
)

// RecoveryManager handles task failures and recovery
type RecoveryManager struct {
	retryPolicy    RetryPolicy
	checkpointer   *Checkpointer
	failover       *FailoverHandler
	healthChecker  *HealthChecker
	logger         *zap.Logger
	metrics        *RecoveryMetrics
	failureHistory map[string]*FailureRecord
	mu             sync.RWMutex
}

// RetryPolicy defines retry behavior
type RetryPolicy struct {
	MaxRetries       int
	BaseDelay        time.Duration
	MaxDelay         time.Duration
	BackoffFactor    float64
	RetryableErrors  map[string]bool
}

// FailureRecord tracks failure history
type FailureRecord struct {
	TaskID      string
	Failures    []FailureInfo
	RetryCount  int
	LastFailure time.Time
}

// FailureInfo contains failure details
type FailureInfo struct {
	Timestamp   time.Time
	Error       string
	ErrorCode   string
	WorkerID    string
	Recoverable bool
}

// Checkpoint represents a task checkpoint
type Checkpoint struct {
	TaskID      string
	State       []byte
	Progress    float64
	CreatedAt   time.Time
	Version     int
}

// RecoveryMetrics tracks recovery statistics
type RecoveryMetrics struct {
	TotalFailures     atomic.Uint64
	RecoveredTasks    atomic.Uint64
	UnrecoverableTasks atomic.Uint64
	CheckpointsSaved  atomic.Uint64
	CheckpointsLoaded atomic.Uint64
	FailoversExecuted atomic.Uint64
}

// NewRecoveryManager creates a new recovery manager
func NewRecoveryManager(logger *zap.Logger) *RecoveryManager {
	return &RecoveryManager{
		retryPolicy: DefaultRetryPolicy(),
		checkpointer: NewCheckpointer(),
		failover: NewFailoverHandler(logger),
		healthChecker: NewHealthChecker(logger),
		logger: logger,
		metrics: &RecoveryMetrics{},
		failureHistory: make(map[string]*FailureRecord),
	}
}

// DefaultRetryPolicy returns default retry policy
func DefaultRetryPolicy() RetryPolicy {
	return RetryPolicy{
		MaxRetries:    3,
		BaseDelay:     1 * time.Second,
		MaxDelay:      30 * time.Second,
		BackoffFactor: 2.0,
		RetryableErrors: map[string]bool{
			"RESOURCE_UNAVAILABLE": true,
			"TIMEOUT":             true,
			"NETWORK_ERROR":       true,
			"GPU_OOM":            true,
		},
	}
}

// HandleTaskFailure handles a task failure
func (rm *RecoveryManager) HandleTaskFailure(ctx context.Context, t *task.Task, err error) (RecoveryAction, error) {
	rm.mu.Lock()
	defer rm.mu.Unlock()
	
	rm.metrics.TotalFailures.Add(1)
	
	// Record failure
	failure := FailureInfo{
		Timestamp:   time.Now(),
		Error:       err.Error(),
		ErrorCode:   rm.classifyError(err),
		Recoverable: rm.isRecoverable(err),
	}
	
	record, exists := rm.failureHistory[t.ID]
	if !exists {
		record = &FailureRecord{
			TaskID:   t.ID,
			Failures: []FailureInfo{},
		}
		rm.failureHistory[t.ID] = record
	}
	
	record.Failures = append(record.Failures, failure)
	record.LastFailure = time.Now()
	
	// Determine recovery action
	action := rm.determineAction(t, record, failure)
	
	rm.logger.Info("Task failure handled",
		zap.String("taskID", t.ID),
		zap.String("error", err.Error()),
		zap.String("action", string(action)))
	
	// Execute recovery action
	switch action {
	case RecoveryActionRetry:
		return rm.executeRetry(ctx, t, record)
	case RecoveryActionCheckpoint:
		return rm.executeCheckpointRecovery(ctx, t)
	case RecoveryActionFailover:
		return rm.executeFailover(ctx, t)
	case RecoveryActionAbort:
		rm.metrics.UnrecoverableTasks.Add(1)
		return action, fmt.Errorf("task %s aborted after %d failures", t.ID, record.RetryCount)
	default:
		return RecoveryActionAbort, fmt.Errorf("unknown recovery action")
	}
}

// determineAction determines the recovery action
func (rm *RecoveryManager) determineAction(t *task.Task, record *FailureRecord, failure FailureInfo) RecoveryAction {
	// Check if error is recoverable
	if !failure.Recoverable {
		return RecoveryActionAbort
	}
	
	// Check retry count
	if record.RetryCount >= rm.retryPolicy.MaxRetries {
		return RecoveryActionAbort
	}
	
	// Check if checkpoint exists
	if rm.checkpointer.HasCheckpoint(t.ID) {
		return RecoveryActionCheckpoint
	}
	
	// Check failover conditions
	if rm.shouldFailover(record) {
		return RecoveryActionFailover
	}
	
	return RecoveryActionRetry
}

// executeRetry executes retry recovery
func (rm *RecoveryManager) executeRetry(ctx context.Context, t *task.Task, record *FailureRecord) (RecoveryAction, error) {
	record.RetryCount++
	
	// Calculate backoff delay
	delay := rm.calculateBackoff(record.RetryCount)
	
	rm.logger.Info("Scheduling task retry",
		zap.String("taskID", t.ID),
		zap.Int("attempt", record.RetryCount),
		zap.Duration("delay", delay))
	
	// Wait before retry
	select {
	case <-time.After(delay):
	case <-ctx.Done():
		return RecoveryActionAbort, ctx.Err()
	}
	
	// Reset task status for retry
	t.UpdateStatus(task.TaskStatusPending)
	t.IncrementRetries()
	
	rm.metrics.RecoveredTasks.Add(1)
	
	return RecoveryActionRetry, nil
}

// executeCheckpointRecovery recovers from checkpoint
func (rm *RecoveryManager) executeCheckpointRecovery(ctx context.Context, t *task.Task) (RecoveryAction, error) {
	checkpoint, err := rm.checkpointer.LoadCheckpoint(t.ID)
	if err != nil {
		return RecoveryActionAbort, fmt.Errorf("failed to load checkpoint: %w", err)
	}
	
	// Restore task state from checkpoint
	if err := rm.restoreTaskState(t, checkpoint); err != nil {
		return RecoveryActionAbort, fmt.Errorf("failed to restore state: %w", err)
	}
	
	rm.metrics.CheckpointsLoaded.Add(1)
	
	rm.logger.Info("Task recovered from checkpoint",
		zap.String("taskID", t.ID),
		zap.Float64("progress", checkpoint.Progress))
	
	return RecoveryActionCheckpoint, nil
}

// executeFailover executes failover recovery
func (rm *RecoveryManager) executeFailover(ctx context.Context, t *task.Task) (RecoveryAction, error) {
	if err := rm.failover.Execute(ctx, t); err != nil {
		return RecoveryActionAbort, fmt.Errorf("failover failed: %w", err)
	}
	
	rm.metrics.FailoversExecuted.Add(1)
	
	rm.logger.Info("Task failover executed",
		zap.String("taskID", t.ID))
	
	return RecoveryActionFailover, nil
}

// classifyError classifies the error type
func (rm *RecoveryManager) classifyError(err error) string {
	// Simplified error classification
	errStr := err.Error()
	
	switch {
	case contains(errStr, "OOM", "out of memory"):
		return "GPU_OOM"
	case contains(errStr, "timeout", "deadline exceeded"):
		return "TIMEOUT"
	case contains(errStr, "network", "connection"):
		return "NETWORK_ERROR"
	case contains(errStr, "resource", "unavailable"):
		return "RESOURCE_UNAVAILABLE"
	default:
		return "UNKNOWN"
	}
}

// isRecoverable checks if error is recoverable
func (rm *RecoveryManager) isRecoverable(err error) bool {
	errorCode := rm.classifyError(err)
	return rm.retryPolicy.RetryableErrors[errorCode]
}

// shouldFailover determines if failover is needed
func (rm *RecoveryManager) shouldFailover(record *FailureRecord) bool {
	// Failover if multiple failures in short time
	if len(record.Failures) >= 2 {
		recentFailures := 0
		threshold := time.Now().Add(-1 * time.Minute)
		
		for _, f := range record.Failures {
			if f.Timestamp.After(threshold) {
				recentFailures++
			}
		}
		
		return recentFailures >= 2
	}
	
	return false
}

// calculateBackoff calculates backoff delay
func (rm *RecoveryManager) calculateBackoff(attempt int) time.Duration {
	delay := rm.retryPolicy.BaseDelay
	
	for i := 1; i < attempt; i++ {
		delay = time.Duration(float64(delay) * rm.retryPolicy.BackoffFactor)
		if delay > rm.retryPolicy.MaxDelay {
			delay = rm.retryPolicy.MaxDelay
			break
		}
	}
	
	return delay
}

// restoreTaskState restores task state from checkpoint
func (rm *RecoveryManager) restoreTaskState(t *task.Task, checkpoint *Checkpoint) error {
	// In real implementation, would deserialize and restore state
	t.UpdateStatus(task.TaskStatusPending)
	return nil
}

// SaveCheckpoint saves a task checkpoint
func (rm *RecoveryManager) SaveCheckpoint(t *task.Task, state []byte, progress float64) error {
	checkpoint := &Checkpoint{
		TaskID:    t.ID,
		State:     state,
		Progress:  progress,
		CreatedAt: time.Now(),
	}
	
	if err := rm.checkpointer.SaveCheckpoint(checkpoint); err != nil {
		return err
	}
	
	rm.metrics.CheckpointsSaved.Add(1)
	return nil
}

// RecoveryAction defines recovery actions
type RecoveryAction string

const (
	RecoveryActionRetry      RecoveryAction = "retry"
	RecoveryActionCheckpoint RecoveryAction = "checkpoint"
	RecoveryActionFailover   RecoveryAction = "failover"
	RecoveryActionAbort      RecoveryAction = "abort"
)

// Checkpointer manages task checkpoints
type Checkpointer struct {
	checkpoints map[string]*Checkpoint
	mu          sync.RWMutex
}

func NewCheckpointer() *Checkpointer {
	return &Checkpointer{
		checkpoints: make(map[string]*Checkpoint),
	}
}

func (c *Checkpointer) SaveCheckpoint(cp *Checkpoint) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	c.checkpoints[cp.TaskID] = cp
	return nil
}

func (c *Checkpointer) LoadCheckpoint(taskID string) (*Checkpoint, error) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	
	cp, exists := c.checkpoints[taskID]
	if !exists {
		return nil, fmt.Errorf("checkpoint not found")
	}
	
	return cp, nil
}

func (c *Checkpointer) HasCheckpoint(taskID string) bool {
	c.mu.RLock()
	defer c.mu.RUnlock()
	
	_, exists := c.checkpoints[taskID]
	return exists
}

func (c *Checkpointer) DeleteCheckpoint(taskID string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	delete(c.checkpoints, taskID)
}

// FailoverHandler manages task failover
type FailoverHandler struct {
	logger *zap.Logger
	mu     sync.Mutex
}

func NewFailoverHandler(logger *zap.Logger) *FailoverHandler {
	return &FailoverHandler{
		logger: logger,
	}
}

func (fh *FailoverHandler) Execute(ctx context.Context, t *task.Task) error {
	fh.mu.Lock()
	defer fh.mu.Unlock()
	
	// In real implementation, would:
	// 1. Find alternative worker/resource
	// 2. Migrate task state
	// 3. Update routing/scheduling
	
	fh.logger.Info("Executing failover",
		zap.String("taskID", t.ID))
	
	// Reset task for rescheduling
	t.UpdateStatus(task.TaskStatusPending)
	
	return nil
}

// HealthChecker monitors worker health
type HealthChecker struct {
	workers map[string]*WorkerHealth
	logger  *zap.Logger
	mu      sync.RWMutex
}

// WorkerHealth tracks worker health status
type WorkerHealth struct {
	WorkerID       string
	IsHealthy      atomic.Bool
	LastHeartbeat  time.Time
	FailureCount   atomic.Uint32
	ResponseTimeMs atomic.Float64
}

func NewHealthChecker(logger *zap.Logger) *HealthChecker {
	return &HealthChecker{
		workers: make(map[string]*WorkerHealth),
		logger:  logger,
	}
}

func (hc *HealthChecker) RegisterWorker(workerID string) {
	hc.mu.Lock()
	defer hc.mu.Unlock()
	
	hc.workers[workerID] = &WorkerHealth{
		WorkerID:      workerID,
		LastHeartbeat: time.Now(),
	}
	hc.workers[workerID].IsHealthy.Store(true)
}

func (hc *HealthChecker) UpdateHeartbeat(workerID string) {
	hc.mu.RLock()
	worker, exists := hc.workers[workerID]
	hc.mu.RUnlock()
	
	if exists {
		worker.LastHeartbeat = time.Now()
		worker.IsHealthy.Store(true)
		worker.FailureCount.Store(0)
	}
}

func (hc *HealthChecker) ReportFailure(workerID string) {
	hc.mu.RLock()
	worker, exists := hc.workers[workerID]
	hc.mu.RUnlock()
	
	if exists {
		count := worker.FailureCount.Add(1)
		
		// Mark unhealthy after 3 failures
		if count >= 3 {
			worker.IsHealthy.Store(false)
			hc.logger.Warn("Worker marked unhealthy",
				zap.String("workerID", workerID),
				zap.Uint32("failures", count))
		}
	}
}

func (hc *HealthChecker) IsHealthy(workerID string) bool {
	hc.mu.RLock()
	worker, exists := hc.workers[workerID]
	hc.mu.RUnlock()
	
	if !exists {
		return false
	}
	
	// Check heartbeat timeout (30 seconds)
	if time.Since(worker.LastHeartbeat) > 30*time.Second {
		worker.IsHealthy.Store(false)
	}
	
	return worker.IsHealthy.Load()
}

func (hc *HealthChecker) GetHealthyWorkers() []string {
	hc.mu.RLock()
	defer hc.mu.RUnlock()
	
	var healthy []string
	for id, worker := range hc.workers {
		if worker.IsHealthy.Load() {
			healthy = append(healthy, id)
		}
	}
	
	return healthy
}

// Helper function
func contains(str string, substrs ...string) bool {
	for _, substr := range substrs {
		if len(substr) > 0 && len(str) >= len(substr) {
			for i := 0; i <= len(str)-len(substr); i++ {
				if str[i:i+len(substr)] == substr {
					return true
				}
			}
		}
	}
	return false
}
