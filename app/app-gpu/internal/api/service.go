package api

import (
	"context"
	"fmt"

	"github.com/opus-gpu/app-gpu/pkg/protocol"
	"github.com/sirupsen/logrus"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// APIService implements the GPU Mining gRPC service
type APIService struct {
	protocol.UnimplementedGPUMiningServiceServer
	logger *logrus.Logger
}

// NewAPIService creates a new API service instance
func NewAPIService(logger *logrus.Logger) *APIService {
	return &APIService{
		logger: logger,
	}
}

// StartMining starts mining on specified GPUs
func (s *APIService) StartMining(ctx context.Context, req *protocol.StartMiningRequest) (*protocol.StartMiningResponse, error) {
	s.logger.Infof("StartMining request: GPUs=%v, Pool=%s", req.GpuIndices, req.PoolUrl)
	
	// Validate request
	if len(req.GpuIndices) == 0 {
		return nil, status.Error(codes.InvalidArgument, "no GPU indices specified")
	}
	
	if req.PoolUrl == "" {
		return nil, status.Error(codes.InvalidArgument, "pool URL is required")
	}
	
	if req.WalletAddress == "" {
		return nil, status.Error(codes.InvalidArgument, "wallet address is required")
	}
	
	// TODO: Implement actual mining start logic
	// For now, return success
	
	response := &protocol.StartMiningResponse{
		Success: true,
		Message: fmt.Sprintf("Mining started on %d GPU(s)", len(req.GpuIndices)),
		WorkerIds: generateWorkerIds(req.GpuIndices),
	}
	
	return response, nil
}

// StopMining stops mining on specified GPUs
func (s *APIService) StopMining(ctx context.Context, req *protocol.StopMiningRequest) (*protocol.StopMiningResponse, error) {
	s.logger.Infof("StopMining request: GPUs=%v", req.GpuIndices)
	
	// TODO: Implement actual mining stop logic
	
	response := &protocol.StopMiningResponse{
		Success: true,
		Message: fmt.Sprintf("Mining stopped on %d GPU(s)", len(req.GpuIndices)),
	}
	
	return response, nil
}

// GetStatus returns current mining status
func (s *APIService) GetStatus(ctx context.Context, req *protocol.GetStatusRequest) (*protocol.GetStatusResponse, error) {
	s.logger.Debug("GetStatus request")
	
	// TODO: Implement actual status retrieval
	
	// Mock response for now
	workers := []*protocol.WorkerStatus{
		{
			WorkerId:    "worker-0",
			GpuIndex:    0,
			IsRunning:   true,
			Hashrate:    25.5,
			Temperature: 65,
			PowerUsage:  180,
			Accepted:    1234,
			Rejected:    5,
			Uptime:      3600,
		},
	}
	
	response := &protocol.GetStatusResponse{
		Workers:       workers,
		TotalHashrate: 25.5,
		PoolConnected: true,
		PoolUrl:      "stratum+tcp://pool.example.com:3333",
	}
	
	return response, nil
}

// GetMetrics returns detailed metrics
func (s *APIService) GetMetrics(ctx context.Context, req *protocol.GetMetricsRequest) (*protocol.GetMetricsResponse, error) {
	s.logger.Debug("GetMetrics request")
	
	// TODO: Implement actual metrics collection
	
	metrics := []*protocol.GpuMetrics{
		{
			GpuIndex:        0,
			Name:           "NVIDIA RTX 3080",
			Temperature:    65,
			PowerUsage:     180,
			FanSpeed:       70,
			CoreClock:      1800,
			MemoryClock:    9500,
			Utilization:    98,
			MemoryUsed:     8192,
			MemoryTotal:    10240,
		},
	}
	
	response := &protocol.GetMetricsResponse{
		Metrics:   metrics,
		Timestamp: getCurrentTimestamp(),
	}
	
	return response, nil
}

// Helper functions
func generateWorkerIds(gpuIndices []int32) []string {
	workerIds := make([]string, len(gpuIndices))
	for i, idx := range gpuIndices {
		workerIds[i] = fmt.Sprintf("worker-%d", idx)
	}
	return workerIds
}

func getCurrentTimestamp() int64 {
	return 0 // TODO: Implement
}

// Interceptors for logging
func LoggingInterceptor(logger *logrus.Logger) grpc.UnaryServerInterceptor {
	return func(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
		logger.Debugf("gRPC call: %s", info.FullMethod)
		resp, err := handler(ctx, req)
		if err != nil {
			logger.Errorf("gRPC error: %s - %v", info.FullMethod, err)
		}
		return resp, err
	}
}

func StreamLoggingInterceptor(logger *logrus.Logger) grpc.StreamServerInterceptor {
	return func(srv interface{}, ss grpc.ServerStream, info *grpc.StreamServerInfo, handler grpc.StreamHandler) error {
		logger.Debugf("gRPC stream: %s", info.FullMethod)
		err := handler(srv, ss)
		if err != nil {
			logger.Errorf("gRPC stream error: %s - %v", info.FullMethod, err)
		}
		return err
	}
}
