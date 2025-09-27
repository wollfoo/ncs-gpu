// Package task defines the task model and dependency graph
package task

import (
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
)

// TaskType định nghĩa loại task
type TaskType string

const (
	TaskTypeCompute   TaskType = "compute"
	TaskTypeBenchmark TaskType = "benchmark"
	TaskTypeInference TaskType = "inference"
	TaskTypeTraining  TaskType = "training"
)

// TaskStatus trạng thái của task
type TaskStatus string

const (
	TaskStatusPending    TaskStatus = "pending"
	TaskStatusScheduled  TaskStatus = "scheduled"
	TaskStatusRunning    TaskStatus = "running"
	TaskStatusCompleted  TaskStatus = "completed"
	TaskStatusFailed     TaskStatus = "failed"
	TaskStatusCancelled  TaskStatus = "cancelled"
)

// Priority levels
const (
	PriorityLow      uint8 = 0
	PriorityNormal   uint8 = 100
	PriorityHigh     uint8 = 150
	PriorityCritical uint8 = 200
)

// Task represents a GPU computation task
type Task struct {
	// Basic info
	ID          string    `json:"id"`
	Type        TaskType  `json:"type"`
	Name        string    `json:"name"`
	Description string    `json:"description,omitempty"`
	
	// Scheduling
	Priority    uint8      `json:"priority"`
	Deadline    *time.Time `json:"deadline,omitempty"`
	Affinity    *Affinity  `json:"affinity,omitempty"`
	
	// Dependencies
	Dependencies []string  `json:"dependencies,omitempty"`
	DependsOn    []*Task   `json:"-"` // Internal use
	Dependents   []*Task   `json:"-"` // Tasks that depend on this
	
	// Execution
	Payload     []byte        `json:"payload"`
	Params      TaskParams    `json:"params,omitempty"`
	Resources   ResourceReq   `json:"resources"`
	Constraints []Constraint  `json:"constraints,omitempty"`
	
	// State
	Status      TaskStatus    `json:"status"`
	Result      *TaskResult   `json:"result,omitempty"`
	Error       string        `json:"error,omitempty"`
	Retries     int          `json:"retries"`
	MaxRetries  int          `json:"max_retries"`
	
	// Timing
	CreatedAt   time.Time     `json:"created_at"`
	ScheduledAt *time.Time    `json:"scheduled_at,omitempty"`
	StartedAt   *time.Time    `json:"started_at,omitempty"`
	CompletedAt *time.Time    `json:"completed_at,omitempty"`
	
	// Metadata
	Labels      map[string]string `json:"labels,omitempty"`
	Annotations map[string]string `json:"annotations,omitempty"`
	
	// Internal
	mu          sync.RWMutex      `json:"-"`
}

// TaskParams contains task-specific parameters
type TaskParams struct {
	BatchSize        int    `json:"batch_size,omitempty"`
	Iterations       int    `json:"iterations,omitempty"`
	Precision        string `json:"precision,omitempty"` // fp16, fp32, fp64
	OptimizationLevel int    `json:"optimization_level,omitempty"`
	CustomParams     map[string]interface{} `json:"custom,omitempty"`
}

// ResourceReq specifies resource requirements
type ResourceReq struct {
	GPUs       int     `json:"gpus"`
	MemoryMB   int     `json:"memory_mb"`
	ComputeCap float32 `json:"compute_capability,omitempty"` // Min compute capability
	CUDACores  int     `json:"cuda_cores,omitempty"`
}

// Affinity định nghĩa GPU affinity
type Affinity struct {
	PreferredGPUs []int    `json:"preferred_gpus,omitempty"`
	RequiredGPUs  []int    `json:"required_gpus,omitempty"`
	AntiAffinity  []string `json:"anti_affinity,omitempty"` // Task IDs to avoid co-location
}

// Constraint định nghĩa ràng buộc scheduling
type Constraint struct {
	Type  string `json:"type"`
	Value string `json:"value"`
}

// TaskResult contains task execution result
type TaskResult struct {
	Output    []byte            `json:"output"`
	Metrics   map[string]float64 `json:"metrics"`
	Artifacts []string          `json:"artifacts,omitempty"`
	Duration  time.Duration     `json:"duration"`
}

// NewTask creates a new task
func NewTask(taskType TaskType, payload []byte) *Task {
	return &Task{
		ID:         uuid.New().String(),
		Type:       taskType,
		Priority:   PriorityNormal,
		Payload:    payload,
		Status:     TaskStatusPending,
		CreatedAt:  time.Now(),
		MaxRetries: 3,
		Labels:     make(map[string]string),
		Resources: ResourceReq{
			GPUs:     1,
			MemoryMB: 1024,
		},
	}
}

// SetPriority sets task priority
func (t *Task) SetPriority(priority uint8) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.Priority = priority
}

// SetDeadline sets task deadline
func (t *Task) SetDeadline(deadline time.Time) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.Deadline = &deadline
}

// AddDependency adds a dependency
func (t *Task) AddDependency(taskID string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.Dependencies = append(t.Dependencies, taskID)
}

// UpdateStatus updates task status
func (t *Task) UpdateStatus(status TaskStatus) {
	t.mu.Lock()
	defer t.mu.Unlock()
	
	t.Status = status
	now := time.Now()
	
	switch status {
	case TaskStatusScheduled:
		t.ScheduledAt = &now
	case TaskStatusRunning:
		t.StartedAt = &now
	case TaskStatusCompleted, TaskStatusFailed, TaskStatusCancelled:
		t.CompletedAt = &now
	}
}

// IsReady checks if task is ready to run
func (t *Task) IsReady() bool {
	t.mu.RLock()
	defer t.mu.RUnlock()
	
	if t.Status != TaskStatusPending {
		return false
	}
	
	// Check dependencies
	for _, dep := range t.DependsOn {
		if dep.Status != TaskStatusCompleted {
			return false
		}
	}
	
	return true
}

// CanRetry checks if task can be retried
func (t *Task) CanRetry() bool {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return t.Retries < t.MaxRetries
}

// IncrementRetries increments retry counter
func (t *Task) IncrementRetries() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.Retries++
}

// GetExecutionTime returns task execution time
func (t *Task) GetExecutionTime() time.Duration {
	t.mu.RLock()
	defer t.mu.RUnlock()
	
	if t.StartedAt == nil || t.CompletedAt == nil {
		return 0
	}
	
	return t.CompletedAt.Sub(*t.StartedAt)
}

// Serialize serializes task to JSON
func (t *Task) Serialize() ([]byte, error) {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return json.Marshal(t)
}

// Deserialize deserializes task from JSON
func Deserialize(data []byte) (*Task, error) {
	var task Task
	if err := json.Unmarshal(data, &task); err != nil {
		return nil, err
	}
	return &task, nil
}

// TaskGraph represents a dependency graph of tasks
type TaskGraph struct {
	tasks map[string]*Task
	mu    sync.RWMutex
}

// NewTaskGraph creates a new task graph
func NewTaskGraph() *TaskGraph {
	return &TaskGraph{
		tasks: make(map[string]*Task),
	}
}

// AddTask adds a task to the graph
func (g *TaskGraph) AddTask(task *Task) error {
	g.mu.Lock()
	defer g.mu.Unlock()
	
	if _, exists := g.tasks[task.ID]; exists {
		return fmt.Errorf("task %s already exists", task.ID)
	}
	
	// Resolve dependencies
	for _, depID := range task.Dependencies {
		dep, ok := g.tasks[depID]
		if !ok {
			return fmt.Errorf("dependency %s not found", depID)
		}
		task.DependsOn = append(task.DependsOn, dep)
		dep.Dependents = append(dep.Dependents, task)
	}
	
	g.tasks[task.ID] = task
	return nil
}

// GetTask retrieves a task by ID
func (g *TaskGraph) GetTask(id string) (*Task, bool) {
	g.mu.RLock()
	defer g.mu.RUnlock()
	task, ok := g.tasks[id]
	return task, ok
}

// GetReadyTasks returns all tasks ready to execute
func (g *TaskGraph) GetReadyTasks() []*Task {
	g.mu.RLock()
	defer g.mu.RUnlock()
	
	var ready []*Task
	for _, task := range g.tasks {
		if task.IsReady() {
			ready = append(ready, task)
		}
	}
	return ready
}

// TopologicalSort returns tasks in topological order
func (g *TaskGraph) TopologicalSort() ([]*Task, error) {
	g.mu.RLock()
	defer g.mu.RUnlock()
	
	visited := make(map[string]bool)
	stack := make([]*Task, 0, len(g.tasks))
	
	var visit func(*Task) error
	visit = func(task *Task) error {
		if visited[task.ID] {
			return nil
		}
		visited[task.ID] = true
		
		for _, dep := range task.DependsOn {
			if err := visit(dep); err != nil {
				return err
			}
		}
		
		stack = append(stack, task)
		return nil
	}
	
	for _, task := range g.tasks {
		if err := visit(task); err != nil {
			return nil, err
		}
	}
	
	// Reverse the stack
	for i := len(stack)/2 - 1; i >= 0; i-- {
		opp := len(stack) - 1 - i
		stack[i], stack[opp] = stack[opp], stack[i]
	}
	
	return stack, nil
}

// HasCycle checks if the graph has a cycle
func (g *TaskGraph) HasCycle() bool {
	g.mu.RLock()
	defer g.mu.RUnlock()
	
	visited := make(map[string]bool)
	recStack := make(map[string]bool)
	
	var hasCycleDFS func(*Task) bool
	hasCycleDFS = func(task *Task) bool {
		visited[task.ID] = true
		recStack[task.ID] = true
		
		for _, dep := range task.Dependents {
			if !visited[dep.ID] {
				if hasCycleDFS(dep) {
					return true
				}
			} else if recStack[dep.ID] {
				return true
			}
		}
		
		recStack[task.ID] = false
		return false
	}
	
	for _, task := range g.tasks {
		if !visited[task.ID] {
			if hasCycleDFS(task) {
				return true
			}
		}
	}
	
	return false
}
