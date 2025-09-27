// Package scheduler implements various scheduling algorithms
package scheduler

import (
	"container/heap"
	"fmt"
	"math"
	"sort"
	"sync"
	"time"

	"github.com/opus-gpu/scheduler/pkg/task"
	"go.uber.org/zap"
)

// Algorithm định nghĩa interface cho scheduling algorithms
type Algorithm interface {
	// Schedule chọn task tiếp theo từ queue
	Schedule(tasks []*task.Task, resources ResourceState) (*task.Task, error)
	// Name trả về tên của algorithm
	Name() string
}

// ResourceState represents available GPU resources
type ResourceState struct {
	TotalGPUs      int
	AvailableGPUs  int
	GPUUtilization map[int]float64 // GPU ID -> utilization %
	MemoryUsage    map[int]int     // GPU ID -> memory MB used
	Temperature    map[int]float32 // GPU ID -> temperature C
}

// FIFOScheduler implements First-In-First-Out scheduling
type FIFOScheduler struct {
	logger *zap.Logger
}

func NewFIFOScheduler(logger *zap.Logger) *FIFOScheduler {
	return &FIFOScheduler{logger: logger}
}

func (s *FIFOScheduler) Name() string {
	return "FIFO"
}

func (s *FIFOScheduler) Schedule(tasks []*task.Task, resources ResourceState) (*task.Task, error) {
	if len(tasks) == 0 {
		return nil, fmt.Errorf("no tasks available")
	}
	
	// Sort by creation time
	sort.Slice(tasks, func(i, j int) bool {
		return tasks[i].CreatedAt.Before(tasks[j].CreatedAt)
	})
	
	// Return first task that fits resources
	for _, t := range tasks {
		if s.canSchedule(t, resources) {
			s.logger.Debug("FIFO scheduled task", zap.String("taskID", t.ID))
			return t, nil
		}
	}
	
	return nil, fmt.Errorf("no schedulable tasks")
}

func (s *FIFOScheduler) canSchedule(t *task.Task, resources ResourceState) bool {
	return t.Resources.GPUs <= resources.AvailableGPUs
}

// PriorityScheduler implements priority-based scheduling
type PriorityScheduler struct {
	logger *zap.Logger
	queue  PriorityQueue
	mu     sync.Mutex
}

func NewPriorityScheduler(logger *zap.Logger) *PriorityScheduler {
	pq := make(PriorityQueue, 0)
	heap.Init(&pq)
	return &PriorityScheduler{
		logger: logger,
		queue:  pq,
	}
}

func (s *PriorityScheduler) Name() string {
	return "Priority"
}

func (s *PriorityScheduler) Schedule(tasks []*task.Task, resources ResourceState) (*task.Task, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	
	// Build priority queue
	s.queue = make(PriorityQueue, 0, len(tasks))
	for _, t := range tasks {
		item := &PriorityItem{
			task:     t,
			priority: int(t.Priority),
		}
		heap.Push(&s.queue, item)
	}
	
	// Pop tasks until we find one that fits
	for s.queue.Len() > 0 {
		item := heap.Pop(&s.queue).(*PriorityItem)
		if s.canSchedule(item.task, resources) {
			s.logger.Debug("Priority scheduled task",
				zap.String("taskID", item.task.ID),
				zap.Uint8("priority", item.task.Priority))
			return item.task, nil
		}
	}
	
	return nil, fmt.Errorf("no schedulable tasks")
}

func (s *PriorityScheduler) canSchedule(t *task.Task, resources ResourceState) bool {
	return t.Resources.GPUs <= resources.AvailableGPUs
}

// PriorityItem for priority queue
type PriorityItem struct {
	task     *task.Task
	priority int
	index    int
}

// PriorityQueue implements heap.Interface
type PriorityQueue []*PriorityItem

func (pq PriorityQueue) Len() int { return len(pq) }

func (pq PriorityQueue) Less(i, j int) bool {
	// Higher priority first
	return pq[i].priority > pq[j].priority
}

func (pq PriorityQueue) Swap(i, j int) {
	pq[i], pq[j] = pq[j], pq[i]
	pq[i].index = i
	pq[j].index = j
}

func (pq *PriorityQueue) Push(x interface{}) {
	n := len(*pq)
	item := x.(*PriorityItem)
	item.index = n
	*pq = append(*pq, item)
}

func (pq *PriorityQueue) Pop() interface{} {
	old := *pq
	n := len(old)
	item := old[n-1]
	old[n-1] = nil
	item.index = -1
	*pq = old[0 : n-1]
	return item
}

// FairQueueScheduler implements fair queuing with weighted shares
type FairQueueScheduler struct {
	logger  *zap.Logger
	shares  map[string]float64 // user/label -> share
	usage   map[string]float64 // user/label -> usage
	mu      sync.RWMutex
}

func NewFairQueueScheduler(logger *zap.Logger) *FairQueueScheduler {
	return &FairQueueScheduler{
		logger: logger,
		shares: make(map[string]float64),
		usage:  make(map[string]float64),
	}
}

func (s *FairQueueScheduler) Name() string {
	return "FairQueue"
}

func (s *FairQueueScheduler) Schedule(tasks []*task.Task, resources ResourceState) (*task.Task, error) {
	if len(tasks) == 0 {
		return nil, fmt.Errorf("no tasks available")
	}
	
	// Calculate dominant resource share for each user
	userTasks := s.groupByUser(tasks)
	minDRS := math.MaxFloat64
	var selectedTask *task.Task
	
	for user, userTaskList := range userTasks {
		drs := s.getDominantResourceShare(user)
		
		for _, t := range userTaskList {
			if s.canSchedule(t, resources) && drs < minDRS {
				minDRS = drs
				selectedTask = t
			}
		}
	}
	
	if selectedTask != nil {
		s.updateUsage(s.getUserLabel(selectedTask), float64(selectedTask.Resources.GPUs))
		s.logger.Debug("FairQueue scheduled task",
			zap.String("taskID", selectedTask.ID),
			zap.Float64("DRS", minDRS))
		return selectedTask, nil
	}
	
	return nil, fmt.Errorf("no schedulable tasks")
}

func (s *FairQueueScheduler) canSchedule(t *task.Task, resources ResourceState) bool {
	return t.Resources.GPUs <= resources.AvailableGPUs
}

func (s *FairQueueScheduler) groupByUser(tasks []*task.Task) map[string][]*task.Task {
	groups := make(map[string][]*task.Task)
	for _, t := range tasks {
		user := s.getUserLabel(t)
		groups[user] = append(groups[user], t)
	}
	return groups
}

func (s *FairQueueScheduler) getUserLabel(t *task.Task) string {
	if user, ok := t.Labels["user"]; ok {
		return user
	}
	return "default"
}

func (s *FairQueueScheduler) getDominantResourceShare(user string) float64 {
	s.mu.RLock()
	defer s.mu.RUnlock()
	
	usage := s.usage[user]
	share := s.shares[user]
	if share == 0 {
		share = 1.0 // Default share
	}
	
	return usage / share
}

func (s *FairQueueScheduler) updateUsage(user string, amount float64) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.usage[user] += amount
}

// DeadlineScheduler implements Earliest Deadline First scheduling
type DeadlineScheduler struct {
	logger *zap.Logger
}

func NewDeadlineScheduler(logger *zap.Logger) *DeadlineScheduler {
	return &DeadlineScheduler{logger: logger}
}

func (s *DeadlineScheduler) Name() string {
	return "EDF"
}

func (s *DeadlineScheduler) Schedule(tasks []*task.Task, resources ResourceState) (*task.Task, error) {
	if len(tasks) == 0 {
		return nil, fmt.Errorf("no tasks available")
	}
	
	// Filter tasks with deadlines
	tasksWithDeadline := make([]*task.Task, 0)
	for _, t := range tasks {
		if t.Deadline != nil {
			tasksWithDeadline = append(tasksWithDeadline, t)
		}
	}
	
	if len(tasksWithDeadline) == 0 {
		// Fall back to priority if no deadlines
		return NewPriorityScheduler(s.logger).Schedule(tasks, resources)
	}
	
	// Sort by deadline
	sort.Slice(tasksWithDeadline, func(i, j int) bool {
		return tasksWithDeadline[i].Deadline.Before(*tasksWithDeadline[j].Deadline)
	})
	
	// Return first task that fits
	for _, t := range tasksWithDeadline {
		if s.canSchedule(t, resources) {
			s.logger.Debug("EDF scheduled task",
				zap.String("taskID", t.ID),
				zap.Time("deadline", *t.Deadline))
			return t, nil
		}
	}
	
	return nil, fmt.Errorf("no schedulable tasks")
}

func (s *DeadlineScheduler) canSchedule(t *task.Task, resources ResourceState) bool {
	return t.Resources.GPUs <= resources.AvailableGPUs
}

// AffinityScheduler considers GPU affinity preferences
type AffinityScheduler struct {
	logger    *zap.Logger
	fallback  Algorithm
}

func NewAffinityScheduler(logger *zap.Logger, fallback Algorithm) *AffinityScheduler {
	return &AffinityScheduler{
		logger:   logger,
		fallback: fallback,
	}
}

func (s *AffinityScheduler) Name() string {
	return "Affinity"
}

func (s *AffinityScheduler) Schedule(tasks []*task.Task, resources ResourceState) (*task.Task, error) {
	if len(tasks) == 0 {
		return nil, fmt.Errorf("no tasks available")
	}
	
	// Score tasks based on affinity match
	scoredTasks := make([]struct {
		task  *task.Task
		score int
	}, 0, len(tasks))
	
	for _, t := range tasks {
		if !s.canSchedule(t, resources) {
			continue
		}
		
		score := s.calculateAffinityScore(t, resources)
		scoredTasks = append(scoredTasks, struct {
			task  *task.Task
			score int
		}{t, score})
	}
	
	if len(scoredTasks) == 0 {
		return nil, fmt.Errorf("no schedulable tasks")
	}
	
	// Sort by score (higher is better)
	sort.Slice(scoredTasks, func(i, j int) bool {
		return scoredTasks[i].score > scoredTasks[j].score
	})
	
	selected := scoredTasks[0].task
	s.logger.Debug("Affinity scheduled task",
		zap.String("taskID", selected.ID),
		zap.Int("score", scoredTasks[0].score))
	
	return selected, nil
}

func (s *AffinityScheduler) canSchedule(t *task.Task, resources ResourceState) bool {
	if t.Resources.GPUs > resources.AvailableGPUs {
		return false
	}
	
	// Check required GPUs
	if t.Affinity != nil && len(t.Affinity.RequiredGPUs) > 0 {
		for _, gpu := range t.Affinity.RequiredGPUs {
			if util, ok := resources.GPUUtilization[gpu]; !ok || util > 90 {
				return false
			}
		}
	}
	
	return true
}

func (s *AffinityScheduler) calculateAffinityScore(t *task.Task, resources ResourceState) int {
	score := 0
	
	if t.Affinity == nil {
		return score
	}
	
	// Bonus for preferred GPUs being available
	for _, gpu := range t.Affinity.PreferredGPUs {
		if util, ok := resources.GPUUtilization[gpu]; ok && util < 50 {
			score += 10
		}
	}
	
	// Penalty for high temperature GPUs
	for gpu, temp := range resources.Temperature {
		if temp > 75 {
			score -= 5
		}
	}
	
	return score
}

// MultiAlgorithmScheduler combines multiple algorithms
type MultiAlgorithmScheduler struct {
	algorithms []Algorithm
	weights    []float64
	logger     *zap.Logger
}

func NewMultiAlgorithmScheduler(logger *zap.Logger, algorithms []Algorithm, weights []float64) *MultiAlgorithmScheduler {
	return &MultiAlgorithmScheduler{
		algorithms: algorithms,
		weights:    weights,
		logger:     logger,
	}
}

func (s *MultiAlgorithmScheduler) Name() string {
	return "MultiAlgorithm"
}

func (s *MultiAlgorithmScheduler) Schedule(tasks []*task.Task, resources ResourceState) (*task.Task, error) {
	// Vote-based selection from multiple algorithms
	votes := make(map[string]float64)
	
	for i, algo := range s.algorithms {
		selected, err := algo.Schedule(tasks, resources)
		if err == nil && selected != nil {
			weight := 1.0
			if i < len(s.weights) {
				weight = s.weights[i]
			}
			votes[selected.ID] += weight
		}
	}
	
	// Select task with most votes
	var bestTask *task.Task
	maxVotes := 0.0
	
	for _, t := range tasks {
		if v := votes[t.ID]; v > maxVotes {
			maxVotes = v
			bestTask = t
		}
	}
	
	if bestTask != nil {
		s.logger.Debug("MultiAlgorithm scheduled task",
			zap.String("taskID", bestTask.ID),
			zap.Float64("votes", maxVotes))
		return bestTask, nil
	}
	
	return nil, fmt.Errorf("no consensus on task selection")
}
