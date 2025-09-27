// Package loadbalancer implements work stealing and load distribution
package loadbalancer

import (
	"context"
	"fmt"
	"math/rand"
	"sync"
	"sync/atomic"
	"time"

	"github.com/opus-gpu/scheduler/pkg/task"
	"go.uber.org/zap"
)

// LoadBalancer distributes tasks across GPU workers
type LoadBalancer struct {
	workers    []*Worker
	strategy   BalancingStrategy
	stealing   *WorkStealer
	backoff    *BackpressureController
	logger     *zap.Logger
	metrics    *Metrics
	stopCh     chan struct{}
	wg         sync.WaitGroup
}

// Worker represents a GPU worker
type Worker struct {
	ID          string
	DeviceID    int
	Queue       *WorkQueue
	Load        atomic.Float64
	TaskCount   atomic.Int32
	IsAvailable atomic.Bool
	LastSteal   time.Time
	mu          sync.RWMutex
}

// WorkQueue is a thread-safe task queue
type WorkQueue struct {
	tasks  []*task.Task
	mu     sync.RWMutex
	notify chan struct{}
}

// BalancingStrategy định nghĩa chiến lược load balancing
type BalancingStrategy interface {
	SelectWorker(workers []*Worker, t *task.Task) *Worker
	Rebalance(workers []*Worker) []*BalanceAction
}

// BalanceAction represents a rebalancing action
type BalanceAction struct {
	From   *Worker
	To     *Worker
	Task   *task.Task
	Reason string
}

// Metrics tracks load balancer performance
type Metrics struct {
	TasksDistributed  atomic.Uint64
	TasksStolen       atomic.Uint64
	RebalanceAttempts atomic.Uint64
	BackpressureHits  atomic.Uint64
}

// NewLoadBalancer creates a new load balancer
func NewLoadBalancer(numWorkers int, strategy BalancingStrategy, logger *zap.Logger) *LoadBalancer {
	workers := make([]*Worker, numWorkers)
	for i := 0; i < numWorkers; i++ {
		workers[i] = &Worker{
			ID:       fmt.Sprintf("worker-%d", i),
			DeviceID: i,
			Queue:    NewWorkQueue(),
		}
		workers[i].IsAvailable.Store(true)
	}
	
	return &LoadBalancer{
		workers:  workers,
		strategy: strategy,
		stealing: NewWorkStealer(logger),
		backoff:  NewBackpressureController(),
		logger:   logger,
		metrics:  &Metrics{},
		stopCh:   make(chan struct{}),
	}
}

// Start begins load balancing operations
func (lb *LoadBalancer) Start(ctx context.Context) error {
	lb.logger.Info("Starting load balancer")
	
	// Start work stealing goroutine
	lb.wg.Add(1)
	go lb.workStealingLoop(ctx)
	
	// Start rebalancing goroutine
	lb.wg.Add(1)
	go lb.rebalancingLoop(ctx)
	
	// Start backpressure monitoring
	lb.wg.Add(1)
	go lb.backpressureLoop(ctx)
	
	return nil
}

// Stop stops the load balancer
func (lb *LoadBalancer) Stop() {
	lb.logger.Info("Stopping load balancer")
	close(lb.stopCh)
	lb.wg.Wait()
}

// Distribute assigns a task to a worker
func (lb *LoadBalancer) Distribute(t *task.Task) error {
	// Check backpressure
	if lb.backoff.ShouldThrottle() {
		lb.metrics.BackpressureHits.Add(1)
		return fmt.Errorf("system under backpressure")
	}
	
	// Select worker based on strategy
	worker := lb.strategy.SelectWorker(lb.workers, t)
	if worker == nil {
		return fmt.Errorf("no available workers")
	}
	
	// Assign task to worker
	if err := worker.Queue.Push(t); err != nil {
		return err
	}
	
	worker.TaskCount.Add(1)
	lb.metrics.TasksDistributed.Add(1)
	
	lb.logger.Debug("Task distributed",
		zap.String("taskID", t.ID),
		zap.String("workerID", worker.ID))
	
	return nil
}

// workStealingLoop implements work stealing
func (lb *LoadBalancer) workStealingLoop(ctx context.Context) {
	defer lb.wg.Done()
	
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-lb.stopCh:
			return
		case <-ticker.C:
			lb.performWorkStealing()
		}
	}
}

// performWorkStealing steals work from busy workers
func (lb *LoadBalancer) performWorkStealing() {
	// Find idle and busy workers
	var idleWorkers, busyWorkers []*Worker
	
	for _, w := range lb.workers {
		if w.IsAvailable.Load() && w.TaskCount.Load() == 0 {
			idleWorkers = append(idleWorkers, w)
		} else if w.TaskCount.Load() > 2 {
			busyWorkers = append(busyWorkers, w)
		}
	}
	
	if len(idleWorkers) == 0 || len(busyWorkers) == 0 {
		return
	}
	
	// Perform stealing
	for _, idle := range idleWorkers {
		if lb.stealing.TrySteal(idle, busyWorkers) {
			lb.metrics.TasksStolen.Add(1)
			lb.logger.Debug("Work stolen",
				zap.String("idleWorker", idle.ID))
		}
	}
}

// rebalancingLoop periodically rebalances load
func (lb *LoadBalancer) rebalancingLoop(ctx context.Context) {
	defer lb.wg.Done()
	
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-lb.stopCh:
			return
		case <-ticker.C:
			lb.performRebalancing()
		}
	}
}

// performRebalancing rebalances load across workers
func (lb *LoadBalancer) performRebalancing() {
	actions := lb.strategy.Rebalance(lb.workers)
	
	if len(actions) == 0 {
		return
	}
	
	lb.metrics.RebalanceAttempts.Add(1)
	
	for _, action := range actions {
		// Move task from one worker to another
		if t := action.From.Queue.Pop(); t != nil {
			if err := action.To.Queue.Push(t); err == nil {
				action.From.TaskCount.Add(-1)
				action.To.TaskCount.Add(1)
				
				lb.logger.Debug("Task rebalanced",
					zap.String("taskID", t.ID),
					zap.String("from", action.From.ID),
					zap.String("to", action.To.ID),
					zap.String("reason", action.Reason))
			}
		}
	}
}

// backpressureLoop monitors and handles backpressure
func (lb *LoadBalancer) backpressureLoop(ctx context.Context) {
	defer lb.wg.Done()
	
	ticker := time.NewTicker(1 * time.Second)
	defer ticker.Stop()
	
	for {
		select {
		case <-ctx.Done():
			return
		case <-lb.stopCh:
			return
		case <-ticker.C:
			lb.updateBackpressure()
		}
	}
}

// updateBackpressure updates backpressure state
func (lb *LoadBalancer) updateBackpressure() {
	totalTasks := 0
	maxQueueSize := 0
	
	for _, w := range lb.workers {
		count := int(w.TaskCount.Load())
		totalTasks += count
		if count > maxQueueSize {
			maxQueueSize = count
		}
	}
	
	avgLoad := float64(totalTasks) / float64(len(lb.workers))
	lb.backoff.Update(avgLoad, maxQueueSize)
}

// WorkQueue implementation
func NewWorkQueue() *WorkQueue {
	return &WorkQueue{
		tasks:  make([]*task.Task, 0),
		notify: make(chan struct{}, 1),
	}
}

func (q *WorkQueue) Push(t *task.Task) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	
	q.tasks = append(q.tasks, t)
	
	// Non-blocking notify
	select {
	case q.notify <- struct{}{}:
	default:
	}
	
	return nil
}

func (q *WorkQueue) Pop() *task.Task {
	q.mu.Lock()
	defer q.mu.Unlock()
	
	if len(q.tasks) == 0 {
		return nil
	}
	
	t := q.tasks[0]
	q.tasks = q.tasks[1:]
	return t
}

func (q *WorkQueue) Size() int {
	q.mu.RLock()
	defer q.mu.RUnlock()
	return len(q.tasks)
}

// WorkStealer implements work stealing logic
type WorkStealer struct {
	logger       *zap.Logger
	stealRatio   float64
	minStealSize int
}

func NewWorkStealer(logger *zap.Logger) *WorkStealer {
	return &WorkStealer{
		logger:       logger,
		stealRatio:   0.5, // Steal half of tasks
		minStealSize: 2,   // Minimum tasks to steal
	}
}

func (ws *WorkStealer) TrySteal(idle *Worker, busyWorkers []*Worker) bool {
	// Select random busy worker
	if len(busyWorkers) == 0 {
		return false
	}
	
	victim := busyWorkers[rand.Intn(len(busyWorkers))]
	victimSize := victim.Queue.Size()
	
	if victimSize < ws.minStealSize {
		return false
	}
	
	// Calculate steal amount
	stealCount := int(float64(victimSize) * ws.stealRatio)
	if stealCount < 1 {
		stealCount = 1
	}
	
	// Perform stealing
	stolen := 0
	for i := 0; i < stealCount; i++ {
		if t := victim.Queue.Pop(); t != nil {
			if err := idle.Queue.Push(t); err == nil {
				stolen++
				victim.TaskCount.Add(-1)
				idle.TaskCount.Add(1)
			}
		}
	}
	
	idle.LastSteal = time.Now()
	
	ws.logger.Debug("Work stealing completed",
		zap.String("idle", idle.ID),
		zap.String("victim", victim.ID),
		zap.Int("stolen", stolen))
	
	return stolen > 0
}

// BackpressureController manages system backpressure
type BackpressureController struct {
	threshold      float64
	maxQueueSize   int
	currentLoad    atomic.Float64
	throttling     atomic.Bool
	lastUpdate     time.Time
	mu             sync.RWMutex
}

func NewBackpressureController() *BackpressureController {
	return &BackpressureController{
		threshold:    0.8, // 80% load threshold
		maxQueueSize: 100,
		lastUpdate:   time.Now(),
	}
}

func (bc *BackpressureController) Update(avgLoad float64, maxQueue int) {
	bc.mu.Lock()
	defer bc.mu.Unlock()
	
	bc.currentLoad.Store(avgLoad)
	bc.lastUpdate = time.Now()
	
	// Check if should throttle
	if avgLoad > bc.threshold || maxQueue > bc.maxQueueSize {
		bc.throttling.Store(true)
	} else {
		bc.throttling.Store(false)
	}
}

func (bc *BackpressureController) ShouldThrottle() bool {
	return bc.throttling.Load()
}

func (bc *BackpressureController) GetLoad() float64 {
	return bc.currentLoad.Load()
}

// RoundRobinStrategy implements round-robin load balancing
type RoundRobinStrategy struct {
	current atomic.Uint32
}

func NewRoundRobinStrategy() *RoundRobinStrategy {
	return &RoundRobinStrategy{}
}

func (s *RoundRobinStrategy) SelectWorker(workers []*Worker, t *task.Task) *Worker {
	n := uint32(len(workers))
	if n == 0 {
		return nil
	}
	
	// Find next available worker
	start := s.current.Add(1) % n
	for i := uint32(0); i < n; i++ {
		idx := (start + i) % n
		if workers[idx].IsAvailable.Load() {
			return workers[idx]
		}
	}
	
	return nil
}

func (s *RoundRobinStrategy) Rebalance(workers []*Worker) []*BalanceAction {
	// Round-robin doesn't need rebalancing
	return nil
}

// LeastLoadedStrategy selects the least loaded worker
type LeastLoadedStrategy struct{}

func NewLeastLoadedStrategy() *LeastLoadedStrategy {
	return &LeastLoadedStrategy{}
}

func (s *LeastLoadedStrategy) SelectWorker(workers []*Worker, t *task.Task) *Worker {
	var selected *Worker
	minLoad := int32(^uint32(0) >> 1) // Max int32
	
	for _, w := range workers {
		if w.IsAvailable.Load() {
			load := w.TaskCount.Load()
			if load < minLoad {
				minLoad = load
				selected = w
			}
		}
	}
	
	return selected
}

func (s *LeastLoadedStrategy) Rebalance(workers []*Worker) []*BalanceAction {
	if len(workers) < 2 {
		return nil
	}
	
	// Calculate average load
	totalTasks := int32(0)
	for _, w := range workers {
		totalTasks += w.TaskCount.Load()
	}
	avgLoad := totalTasks / int32(len(workers))
	
	var actions []*BalanceAction
	
	// Find overloaded and underloaded workers
	for _, w := range workers {
		load := w.TaskCount.Load()
		if load > avgLoad+2 {
			// Find underloaded worker
			for _, target := range workers {
				if target.TaskCount.Load() < avgLoad-1 {
					actions = append(actions, &BalanceAction{
						From:   w,
						To:     target,
						Reason: "load imbalance",
					})
					break
				}
			}
		}
	}
	
	return actions
}
