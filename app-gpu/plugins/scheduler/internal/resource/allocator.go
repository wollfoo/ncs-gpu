// Package resource implements GPU resource allocation and management
package resource

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"time"

	"github.com/opus-gpu/scheduler/pkg/task"
	"go.uber.org/zap"
)

// GPUResource represents a single GPU resource
type GPUResource struct {
	ID             int
	Name           string
	TotalMemoryMB  int
	UsedMemoryMB   atomic.Int32
	ComputeCapacity float32
	CurrentLoad    atomic.Float64
	Temperature    atomic.Float64
	PowerUsage     atomic.Float64
	IsAvailable    atomic.Bool
	ReservedBy     atomic.Value // stores task ID
	LastUpdated    time.Time
	mu             sync.RWMutex
}

// ResourcePool manages GPU resources
type ResourcePool struct {
	resources      []*GPUResource
	allocations    map[string]*Allocation // taskID -> allocation
	reservations   map[string]*Reservation // taskID -> reservation
	strategy       AllocationStrategy
	logger         *zap.Logger
	metrics        *AllocationMetrics
	mu             sync.RWMutex
}

// Allocation represents an allocated resource
type Allocation struct {
	TaskID      string
	Resources   []*GPUResource
	MemoryMB    int
	AllocatedAt time.Time
	ExpiresAt   *time.Time
}

// Reservation represents a resource reservation
type Reservation struct {
	TaskID      string
	Resources   ResourceRequest
	Priority    int
	CreatedAt   time.Time
	ValidUntil  time.Time
	Fulfilled   bool
}

// ResourceRequest specifies resource requirements
type ResourceRequest struct {
	GPUCount        int
	MinMemoryMB     int
	MinComputeCap   float32
	PreferredGPUs   []int
	ExclusiveAccess bool
	Duration        time.Duration
}

// AllocationStrategy defines how resources are allocated
type AllocationStrategy interface {
	Allocate(pool []*GPUResource, req ResourceRequest) ([]*GPUResource, error)
	Score(resource *GPUResource, req ResourceRequest) float64
}

// AllocationMetrics tracks allocation performance
type AllocationMetrics struct {
	TotalAllocations   atomic.Uint64
	FailedAllocations  atomic.Uint64
	TotalDeallocations atomic.Uint64
	AverageWaitTime    atomic.Float64
	ResourceUtilization atomic.Float64
}

// NewResourcePool creates a new resource pool
func NewResourcePool(gpuCount int, strategy AllocationStrategy, logger *zap.Logger) *ResourcePool {
	resources := make([]*GPUResource, gpuCount)
	for i := 0; i < gpuCount; i++ {
		resources[i] = &GPUResource{
			ID:              i,
			Name:            fmt.Sprintf("GPU-%d", i),
			TotalMemoryMB:   24576, // 24GB default
			ComputeCapacity: 8.6,   // Compute capability
		}
		resources[i].IsAvailable.Store(true)
	}
	
	return &ResourcePool{
		resources:    resources,
		allocations:  make(map[string]*Allocation),
		reservations: make(map[string]*Reservation),
		strategy:     strategy,
		logger:       logger,
		metrics:      &AllocationMetrics{},
	}
}

// Allocate allocates resources for a task
func (rp *ResourcePool) Allocate(taskID string, req ResourceRequest) (*Allocation, error) {
	rp.mu.Lock()
	defer rp.mu.Unlock()
	
	// Check if already allocated
	if alloc, exists := rp.allocations[taskID]; exists {
		return alloc, nil
	}
	
	// Find available resources
	available := rp.getAvailableResources(req)
	if len(available) < req.GPUCount {
		rp.metrics.FailedAllocations.Add(1)
		return nil, fmt.Errorf("insufficient resources: need %d GPUs, have %d available",
			req.GPUCount, len(available))
	}
	
	// Use strategy to select resources
	selected, err := rp.strategy.Allocate(available, req)
	if err != nil {
		rp.metrics.FailedAllocations.Add(1)
		return nil, err
	}
	
	// Create allocation
	allocation := &Allocation{
		TaskID:      taskID,
		Resources:   selected,
		MemoryMB:    req.MinMemoryMB,
		AllocatedAt: time.Now(),
	}
	
	if req.Duration > 0 {
		expiresAt := time.Now().Add(req.Duration)
		allocation.ExpiresAt = &expiresAt
	}
	
	// Mark resources as allocated
	for _, res := range selected {
		res.IsAvailable.Store(false)
		res.ReservedBy.Store(taskID)
		res.UsedMemoryMB.Add(int32(req.MinMemoryMB))
	}
	
	rp.allocations[taskID] = allocation
	rp.metrics.TotalAllocations.Add(1)
	rp.updateUtilization()
	
	rp.logger.Info("Resources allocated",
		zap.String("taskID", taskID),
		zap.Int("gpuCount", len(selected)))
	
	return allocation, nil
}

// Deallocate releases allocated resources
func (rp *ResourcePool) Deallocate(taskID string) error {
	rp.mu.Lock()
	defer rp.mu.Unlock()
	
	allocation, exists := rp.allocations[taskID]
	if !exists {
		return fmt.Errorf("allocation not found for task %s", taskID)
	}
	
	// Release resources
	for _, res := range allocation.Resources {
		res.IsAvailable.Store(true)
		res.ReservedBy.Store("")
		res.UsedMemoryMB.Add(-int32(allocation.MemoryMB))
		res.CurrentLoad.Store(0)
	}
	
	delete(rp.allocations, taskID)
	rp.metrics.TotalDeallocations.Add(1)
	rp.updateUtilization()
	
	rp.logger.Info("Resources deallocated",
		zap.String("taskID", taskID),
		zap.Int("gpuCount", len(allocation.Resources)))
	
	return nil
}

// Reserve reserves resources for future allocation
func (rp *ResourcePool) Reserve(taskID string, req ResourceRequest, priority int) (*Reservation, error) {
	rp.mu.Lock()
	defer rp.mu.Unlock()
	
	// Check if already reserved
	if res, exists := rp.reservations[taskID]; exists {
		return res, nil
	}
	
	// Create reservation
	reservation := &Reservation{
		TaskID:     taskID,
		Resources:  req,
		Priority:   priority,
		CreatedAt:  time.Now(),
		ValidUntil: time.Now().Add(5 * time.Minute), // Default 5 min reservation
	}
	
	rp.reservations[taskID] = reservation
	
	rp.logger.Info("Resources reserved",
		zap.String("taskID", taskID),
		zap.Int("priority", priority))
	
	return reservation, nil
}

// CancelReservation cancels a resource reservation
func (rp *ResourcePool) CancelReservation(taskID string) error {
	rp.mu.Lock()
	defer rp.mu.Unlock()
	
	if _, exists := rp.reservations[taskID]; !exists {
		return fmt.Errorf("reservation not found for task %s", taskID)
	}
	
	delete(rp.reservations, taskID)
	rp.logger.Info("Reservation cancelled", zap.String("taskID", taskID))
	
	return nil
}

// FulfillReservations attempts to fulfill pending reservations
func (rp *ResourcePool) FulfillReservations() {
	rp.mu.Lock()
	defer rp.mu.Unlock()
	
	// Sort reservations by priority
	var pending []*Reservation
	for _, res := range rp.reservations {
		if !res.Fulfilled && time.Now().Before(res.ValidUntil) {
			pending = append(pending, res)
		}
	}
	
	// Try to fulfill each reservation
	for _, res := range pending {
		available := rp.getAvailableResources(res.Resources)
		if len(available) >= res.Resources.GPUCount {
			// Can fulfill this reservation
			if alloc, err := rp.strategy.Allocate(available, res.Resources); err == nil {
				allocation := &Allocation{
					TaskID:      res.TaskID,
					Resources:   alloc,
					MemoryMB:    res.Resources.MinMemoryMB,
					AllocatedAt: time.Now(),
				}
				
				// Mark as allocated
				for _, r := range alloc {
					r.IsAvailable.Store(false)
					r.ReservedBy.Store(res.TaskID)
				}
				
				rp.allocations[res.TaskID] = allocation
				res.Fulfilled = true
				
				rp.logger.Info("Reservation fulfilled",
					zap.String("taskID", res.TaskID))
			}
		}
	}
	
	// Clean up expired reservations
	for taskID, res := range rp.reservations {
		if time.Now().After(res.ValidUntil) {
			delete(rp.reservations, taskID)
		}
	}
}

// GetAllocation returns the allocation for a task
func (rp *ResourcePool) GetAllocation(taskID string) (*Allocation, bool) {
	rp.mu.RLock()
	defer rp.mu.RUnlock()
	
	alloc, exists := rp.allocations[taskID]
	return alloc, exists
}

// GetResourceStatus returns current resource status
func (rp *ResourcePool) GetResourceStatus() ResourceStatus {
	rp.mu.RLock()
	defer rp.mu.RUnlock()
	
	status := ResourceStatus{
		TotalGPUs:     len(rp.resources),
		AllocatedGPUs: 0,
		AvailableGPUs: 0,
		TotalMemoryMB: 0,
		UsedMemoryMB:  0,
		GPUStatuses:   make([]GPUStatus, 0, len(rp.resources)),
	}
	
	for _, res := range rp.resources {
		if res.IsAvailable.Load() {
			status.AvailableGPUs++
		} else {
			status.AllocatedGPUs++
		}
		
		status.TotalMemoryMB += res.TotalMemoryMB
		status.UsedMemoryMB += int(res.UsedMemoryMB.Load())
		
		gpuStatus := GPUStatus{
			ID:          res.ID,
			Name:        res.Name,
			IsAvailable: res.IsAvailable.Load(),
			Load:        res.CurrentLoad.Load(),
			MemoryUsed:  int(res.UsedMemoryMB.Load()),
			Temperature: res.Temperature.Load(),
			PowerUsage:  res.PowerUsage.Load(),
		}
		
		if taskID, ok := res.ReservedBy.Load().(string); ok && taskID != "" {
			gpuStatus.AllocatedTo = taskID
		}
		
		status.GPUStatuses = append(status.GPUStatuses, gpuStatus)
	}
	
	status.Utilization = float64(status.AllocatedGPUs) / float64(status.TotalGPUs)
	
	return status
}

// getAvailableResources returns available resources matching requirements
func (rp *ResourcePool) getAvailableResources(req ResourceRequest) []*GPUResource {
	var available []*GPUResource
	
	for _, res := range rp.resources {
		if !res.IsAvailable.Load() {
			continue
		}
		
		// Check memory requirement
		availMem := res.TotalMemoryMB - int(res.UsedMemoryMB.Load())
		if availMem < req.MinMemoryMB {
			continue
		}
		
		// Check compute capability
		if res.ComputeCapacity < req.MinComputeCap {
			continue
		}
		
		available = append(available, res)
	}
	
	return available
}

// updateUtilization updates resource utilization metrics
func (rp *ResourcePool) updateUtilization() {
	totalGPUs := float64(len(rp.resources))
	allocatedGPUs := float64(len(rp.allocations))
	
	utilization := allocatedGPUs / totalGPUs
	rp.metrics.ResourceUtilization.Store(utilization)
}

// ResourceStatus represents current resource status
type ResourceStatus struct {
	TotalGPUs     int
	AllocatedGPUs int
	AvailableGPUs int
	TotalMemoryMB int
	UsedMemoryMB  int
	Utilization   float64
	GPUStatuses   []GPUStatus
}

// GPUStatus represents status of a single GPU
type GPUStatus struct {
	ID          int
	Name        string
	IsAvailable bool
	AllocatedTo string
	Load        float64
	MemoryUsed  int
	Temperature float64
	PowerUsage  float64
}

// BestFitStrategy allocates resources using best-fit algorithm
type BestFitStrategy struct {
	logger *zap.Logger
}

func NewBestFitStrategy(logger *zap.Logger) *BestFitStrategy {
	return &BestFitStrategy{logger: logger}
}

func (s *BestFitStrategy) Allocate(pool []*GPUResource, req ResourceRequest) ([]*GPUResource, error) {
	if len(pool) < req.GPUCount {
		return nil, fmt.Errorf("not enough resources")
	}
	
	// Score and sort resources
	type scoredResource struct {
		resource *GPUResource
		score    float64
	}
	
	scored := make([]scoredResource, 0, len(pool))
	for _, res := range pool {
		score := s.Score(res, req)
		scored = append(scored, scoredResource{res, score})
	}
	
	// Sort by score (higher is better)
	for i := 0; i < len(scored); i++ {
		for j := i + 1; j < len(scored); j++ {
			if scored[j].score > scored[i].score {
				scored[i], scored[j] = scored[j], scored[i]
			}
		}
	}
	
	// Select top N resources
	selected := make([]*GPUResource, 0, req.GPUCount)
	for i := 0; i < req.GPUCount && i < len(scored); i++ {
		selected = append(selected, scored[i].resource)
	}
	
	return selected, nil
}

func (s *BestFitStrategy) Score(resource *GPUResource, req ResourceRequest) float64 {
	score := 100.0
	
	// Prefer lower temperature GPUs
	temp := resource.Temperature.Load()
	if temp > 0 {
		score -= (temp - 30) * 0.5 // Penalty for high temp
	}
	
	// Prefer lower load GPUs
	load := resource.CurrentLoad.Load()
	score -= load * 0.3
	
	// Prefer GPUs with matching memory
	memDiff := float64(resource.TotalMemoryMB-req.MinMemoryMB) / float64(resource.TotalMemoryMB)
	score += memDiff * 10 // Bonus for close memory match
	
	// Check preferred GPUs
	for _, prefID := range req.PreferredGPUs {
		if resource.ID == prefID {
			score += 50 // Large bonus for preferred GPU
		}
	}
	
	return score
}

// FirstFitStrategy allocates resources using first-fit algorithm
type FirstFitStrategy struct{}

func NewFirstFitStrategy() *FirstFitStrategy {
	return &FirstFitStrategy{}
}

func (s *FirstFitStrategy) Allocate(pool []*GPUResource, req ResourceRequest) ([]*GPUResource, error) {
	if len(pool) < req.GPUCount {
		return nil, fmt.Errorf("not enough resources")
	}
	
	// Simply take the first N available resources
	selected := make([]*GPUResource, 0, req.GPUCount)
	for _, res := range pool {
		if len(selected) >= req.GPUCount {
			break
		}
		selected = append(selected, res)
	}
	
	return selected, nil
}

func (s *FirstFitStrategy) Score(resource *GPUResource, req ResourceRequest) float64 {
	// First-fit doesn't use scoring
	return 1.0
}
