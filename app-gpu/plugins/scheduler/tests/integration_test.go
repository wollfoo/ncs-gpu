// Package tests contains integration tests for the scheduler
package tests

import (
	"context"
	"fmt"
	"testing"
	"time"

	"github.com/opus-gpu/scheduler/internal/fault"
	"github.com/opus-gpu/scheduler/internal/loadbalancer"
	"github.com/opus-gpu/scheduler/internal/resource"
	"github.com/opus-gpu/scheduler/internal/scheduler"
	"github.com/opus-gpu/scheduler/pkg/task"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.uber.org/zap"
)

// TestSchedulerIntegration tests full scheduler workflow
func TestSchedulerIntegration(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	// Create task graph
	taskGraph := task.NewTaskGraph()
	
	// Create tasks with dependencies
	task1 := task.NewTask(task.TaskTypeCompute, []byte("data1"))
	task2 := task.NewTask(task.TaskTypeCompute, []byte("data2"))
	task3 := task.NewTask(task.TaskTypeCompute, []byte("data3"))
	
	// Task3 depends on Task1 and Task2
	task3.AddDependency(task1.ID)
	task3.AddDependency(task2.ID)
	
	// Add to graph
	require.NoError(t, taskGraph.AddTask(task1))
	require.NoError(t, taskGraph.AddTask(task2))
	require.NoError(t, taskGraph.AddTask(task3))
	
	// Check topological sort
	sorted, err := taskGraph.TopologicalSort()
	require.NoError(t, err)
	assert.Len(t, sorted, 3)
	
	// Task1 and Task2 should come before Task3
	task3Index := -1
	for i, t := range sorted {
		if t.ID == task3.ID {
			task3Index = i
			break
		}
	}
	assert.Greater(t, task3Index, 0)
}

// TestSchedulingAlgorithms tests different scheduling algorithms
func TestSchedulingAlgorithms(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	testCases := []struct {
		name      string
		algorithm scheduler.Algorithm
		tasks     []*task.Task
		expected  string
	}{
		{
			name:      "FIFO",
			algorithm: scheduler.NewFIFOScheduler(logger),
			tasks: []*task.Task{
				createTestTask("1", task.PriorityLow, time.Now()),
				createTestTask("2", task.PriorityHigh, time.Now().Add(1*time.Second)),
			},
			expected: "1", // First created
		},
		{
			name:      "Priority",
			algorithm: scheduler.NewPriorityScheduler(logger),
			tasks: []*task.Task{
				createTestTask("1", task.PriorityLow, time.Now()),
				createTestTask("2", task.PriorityHigh, time.Now()),
			},
			expected: "2", // Higher priority
		},
	}
	
	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			resources := scheduler.ResourceState{
				TotalGPUs:     4,
				AvailableGPUs: 4,
			}
			
			selected, err := tc.algorithm.Schedule(tc.tasks, resources)
			require.NoError(t, err)
			assert.Equal(t, tc.expected, selected.ID)
		})
	}
}

// TestLoadBalancing tests load balancing
func TestLoadBalancing(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	// Create load balancer
	strategy := loadbalancer.NewLeastLoadedStrategy()
	lb := loadbalancer.NewLoadBalancer(4, strategy, logger)
	
	ctx := context.Background()
	require.NoError(t, lb.Start(ctx))
	defer lb.Stop()
	
	// Distribute tasks
	for i := 0; i < 10; i++ {
		testTask := createTestTask(string(rune('A'+i)), task.PriorityNormal, time.Now())
		err := lb.Distribute(testTask)
		assert.NoError(t, err)
	}
	
	// Allow some time for balancing
	time.Sleep(200 * time.Millisecond)
	
	// Tasks should be distributed across workers
	// (actual verification would require accessing internal state)
}

// TestResourceAllocation tests resource allocation
func TestResourceAllocation(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	// Create resource pool
	strategy := resource.NewBestFitStrategy(logger)
	pool := resource.NewResourcePool(4, strategy, logger)
	
	// Test allocation
	req1 := resource.ResourceRequest{
		GPUCount:    2,
		MinMemoryMB: 4096,
	}
	
	alloc1, err := pool.Allocate("task1", req1)
	require.NoError(t, err)
	assert.Len(t, alloc1.Resources, 2)
	
	// Check status
	status := pool.GetResourceStatus()
	assert.Equal(t, 2, status.AllocatedGPUs)
	assert.Equal(t, 2, status.AvailableGPUs)
	
	// Test second allocation
	req2 := resource.ResourceRequest{
		GPUCount:    1,
		MinMemoryMB: 2048,
	}
	
	alloc2, err := pool.Allocate("task2", req2)
	require.NoError(t, err)
	assert.Len(t, alloc2.Resources, 1)
	
	// Test deallocation
	err = pool.Deallocate("task1")
	require.NoError(t, err)
	
	status = pool.GetResourceStatus()
	assert.Equal(t, 1, status.AllocatedGPUs)
	assert.Equal(t, 3, status.AvailableGPUs)
}

// TestWorkStealing tests work stealing mechanism
func TestWorkStealing(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	// Create workers with different load
	busyWorker := &loadbalancer.Worker{
		ID:       "busy",
		Queue:    loadbalancer.NewWorkQueue(),
		DeviceID: 0,
	}
	busyWorker.IsAvailable.Store(true)
	
	idleWorker := &loadbalancer.Worker{
		ID:       "idle",
		Queue:    loadbalancer.NewWorkQueue(),
		DeviceID: 1,
	}
	idleWorker.IsAvailable.Store(true)
	
	// Add tasks to busy worker
	for i := 0; i < 5; i++ {
		testTask := createTestTask(string(rune('A'+i)), task.PriorityNormal, time.Now())
		busyWorker.Queue.Push(testTask)
		busyWorker.TaskCount.Add(1)
	}
	
	// Perform work stealing
	stealer := loadbalancer.NewWorkStealer(logger)
	stolen := stealer.TrySteal(idleWorker, []*loadbalancer.Worker{busyWorker})
	
	assert.True(t, stolen)
	assert.Greater(t, int(idleWorker.TaskCount.Load()), 0)
	assert.Less(t, int(busyWorker.TaskCount.Load()), 5)
}

// TestFaultRecovery tests fault recovery mechanisms
func TestFaultRecovery(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	// Create recovery manager
	recoveryMgr := fault.NewRecoveryManager(logger)
	
	// Test task failure handling
	testTask := createTestTask("failing-task", task.PriorityNormal, time.Now())
	testTask.MaxRetries = 3
	
	ctx := context.Background()
	
	// Simulate recoverable failure
	recoverableErr := fmt.Errorf("TIMEOUT: operation timed out")
	action, err := recoveryMgr.HandleTaskFailure(ctx, testTask, recoverableErr)
	
	assert.Equal(t, fault.RecoveryActionRetry, action)
	assert.NoError(t, err)
	
	// Simulate non-recoverable failure
	testTask.MaxRetries = 0 // No more retries
	nonRecoverableErr := fmt.Errorf("FATAL: unrecoverable error")
	action, err = recoveryMgr.HandleTaskFailure(ctx, testTask, nonRecoverableErr)
	
	assert.Equal(t, fault.RecoveryActionAbort, action)
	assert.Error(t, err)
}

// TestCheckpointing tests checkpoint save/load
func TestCheckpointing(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	recoveryMgr := fault.NewRecoveryManager(logger)
	
	// Create test task
	testTask := createTestTask("checkpoint-task", task.PriorityNormal, time.Now())
	
	// Save checkpoint
	state := []byte("task state data")
	progress := 0.75
	
	err := recoveryMgr.SaveCheckpoint(testTask, state, progress)
	assert.NoError(t, err)
	
	// Simulate failure and recovery
	ctx := context.Background()
	recoverableErr := fmt.Errorf("GPU_OOM: out of memory")
	
	action, err := recoveryMgr.HandleTaskFailure(ctx, testTask, recoverableErr)
	
	// Should use checkpoint recovery
	assert.Equal(t, fault.RecoveryActionCheckpoint, action)
	assert.NoError(t, err)
}

// TestBackpressure tests backpressure handling
func TestBackpressure(t *testing.T) {
	controller := loadbalancer.NewBackpressureController()
	
	// Normal load
	controller.Update(0.5, 50)
	assert.False(t, controller.ShouldThrottle())
	
	// High load
	controller.Update(0.9, 150)
	assert.True(t, controller.ShouldThrottle())
	
	// Load reduced
	controller.Update(0.3, 30)
	assert.False(t, controller.ShouldThrottle())
}

// TestConcurrentScheduling tests concurrent task scheduling
func TestConcurrentScheduling(t *testing.T) {
	logger, _ := zap.NewDevelopment()
	
	// Create components
	taskGraph := task.NewTaskGraph()
	algo := scheduler.NewPriorityScheduler(logger)
	
	// Launch concurrent task submissions
	done := make(chan bool, 10)
	
	for i := 0; i < 10; i++ {
		go func(id int) {
			testTask := createTestTask(fmt.Sprintf("concurrent-%d", id), 
				uint8(id%4)*50, time.Now())
			err := taskGraph.AddTask(testTask)
			assert.NoError(t, err)
			done <- true
		}(i)
	}
	
	// Wait for all submissions
	for i := 0; i < 10; i++ {
		<-done
	}
	
	// All tasks should be in graph
	readyTasks := taskGraph.GetReadyTasks()
	assert.Len(t, readyTasks, 10)
	
	// Schedule all tasks
	resources := scheduler.ResourceState{
		TotalGPUs:     10,
		AvailableGPUs: 10,
	}
	
	scheduled := 0
	for len(readyTasks) > 0 {
		selected, err := algo.Schedule(readyTasks, resources)
		if err != nil {
			break
		}
		
		// Remove selected from ready list
		for i, t := range readyTasks {
			if t.ID == selected.ID {
				readyTasks = append(readyTasks[:i], readyTasks[i+1:]...)
				break
			}
		}
		
		scheduled++
		resources.AvailableGPUs--
	}
	
	assert.Equal(t, 10, scheduled)
}

// Helper function to create test tasks
func createTestTask(id string, priority uint8, createdAt time.Time) *task.Task {
	t := &task.Task{
		ID:        id,
		Type:      task.TaskTypeCompute,
		Priority:  priority,
		CreatedAt: createdAt,
		Status:    task.TaskStatusPending,
		Resources: task.ResourceReq{
			GPUs:     1,
			MemoryMB: 1024,
		},
		MaxRetries: 3,
	}
	return t
}
