// Package client - gRPC client implementation
// GRPCClient: gRPC client để giao tiếp với miner
package client

import (
	"context"
	"fmt"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

// GRPCClient - gRPC client structure (client struct – cấu trúc client)
type GRPCClient struct {
	conn   *grpc.ClientConn
	client MinerServiceClient // Generated từ protobuf
}

// MinerStatus - Miner status structure (status data – dữ liệu trạng thái)
type MinerStatus struct {
	Running         bool
	Ready           bool
	PID             int
	Uptime          time.Duration
	TotalHashrate   float64
	SharesAccepted  int64
	SharesRejected  int64
	GPUs            []GPUStatus
}

// GPUStatus - GPU status structure (GPU data – dữ liệu GPU)
type GPUStatus struct {
	ID          int
	Name        string
	Hashrate    float64
	Temperature int
	PowerDraw   int
	MemoryUsed  int
}

// StartRequest - Start miner request (start params – tham số khởi động)
type StartRequest struct {
	ConfigPath string
	Wallet     string
	Pool       string
}

// StopRequest - Stop miner request (stop params – tham số dừng)
type StopRequest struct {
	Timeout time.Duration
	Force   bool
}

// GPUInfo - GPU information (GPU metadata – thông tin GPU)
type GPUInfo struct {
	ID                string
	Name              string
	ComputeCapability string
	TotalMemory       int64
	BusID             string
	Status            string
}

// GPUStats - Detailed GPU statistics (GPU metrics – metrics GPU chi tiết)
type GPUStats struct {
	ID                  int
	Name                string
	Status              string
	Hashrate            float64
	Temperature         int
	FanSpeed            int
	PowerDraw           int
	PowerLimit          int
	ClockSpeed          int
	MemoryUsed          int
	MemoryTotal         int
	Utilization         int
	MemoryUtilization   int
}

// NewGRPCClient - Create gRPC client (client creation – tạo client mới)
func NewGRPCClient(addr string) (*GRPCClient, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	// Kết nối đến gRPC server với insecure credentials (local development)
	conn, err := grpc.DialContext(ctx, addr,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithBlock(),
	)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to gRPC server: %w", err)
	}

	return &GRPCClient{
		conn:   conn,
		client: NewMinerServiceClient(conn), // Generated protobuf client
	}, nil
}

// Close - Đóng gRPC connection (connection cleanup – đóng kết nối)
func (c *GRPCClient) Close() error {
	return c.conn.Close()
}

// GetStatus - Lấy miner status (status query – truy vấn trạng thái)
func (c *GRPCClient) GetStatus(ctx context.Context) (*MinerStatus, error) {
	req := &GetStatusRequest{}
	resp, err := c.client.GetStatus(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("gRPC GetStatus failed: %w", err)
	}

	// Convert protobuf response to internal struct
	status := &MinerStatus{
		Running:        resp.Running,
		Ready:          resp.Ready,
		PID:            int(resp.Pid),
		Uptime:         time.Duration(resp.UptimeSeconds) * time.Second,
		TotalHashrate:  resp.TotalHashrate,
		SharesAccepted: resp.SharesAccepted,
		SharesRejected: resp.SharesRejected,
		GPUs:           make([]GPUStatus, len(resp.Gpus)),
	}

	for i, gpu := range resp.Gpus {
		status.GPUs[i] = GPUStatus{
			ID:          int(gpu.Id),
			Name:        gpu.Name,
			Hashrate:    gpu.Hashrate,
			Temperature: int(gpu.Temperature),
			PowerDraw:   int(gpu.PowerDraw),
			MemoryUsed:  int(gpu.MemoryUsed),
		}
	}

	return status, nil
}

// Start - Khởi động miner (miner startup – khởi chạy)
func (c *GRPCClient) Start(ctx context.Context, req *StartRequest) error {
	startReq := &StartMinerRequest{
		ConfigPath: req.ConfigPath,
		Wallet:     req.Wallet,
		Pool:       req.Pool,
	}

	_, err := c.client.StartMiner(ctx, startReq)
	if err != nil {
		return fmt.Errorf("gRPC StartMiner failed: %w", err)
	}

	return nil
}

// Stop - Dừng miner (miner shutdown – dừng hoạt động)
func (c *GRPCClient) Stop(ctx context.Context, req *StopRequest) error {
	stopReq := &StopMinerRequest{
		TimeoutSeconds: int32(req.Timeout.Seconds()),
		Force:          req.Force,
	}

	_, err := c.client.StopMiner(ctx, stopReq)
	if err != nil {
		return fmt.Errorf("gRPC StopMiner failed: %w", err)
	}

	return nil
}

// EnableStealth - Bật stealth mode (stealth activation – kích hoạt ẩn danh)
func (c *GRPCClient) EnableStealth(ctx context.Context) error {
	req := &SetStealthRequest{Enabled: true}
	_, err := c.client.SetStealth(ctx, req)
	return err
}

// DisableStealth - Tắt stealth mode (stealth deactivation – vô hiệu hóa ẩn danh)
func (c *GRPCClient) DisableStealth(ctx context.Context) error {
	req := &SetStealthRequest{Enabled: false}
	_, err := c.client.SetStealth(ctx, req)
	return err
}

// GetStealthStatus - Lấy stealth status (stealth query – truy vấn trạng thái ẩn danh)
func (c *GRPCClient) GetStealthStatus(ctx context.Context) (bool, error) {
	req := &GetStealthStatusRequest{}
	resp, err := c.client.GetStealthStatus(ctx, req)
	if err != nil {
		return false, err
	}
	return resp.Enabled, nil
}

// ListGPUs - Liệt kê GPUs (GPU enumeration – liệt kê thiết bị)
func (c *GRPCClient) ListGPUs(ctx context.Context) ([]GPUInfo, error) {
	req := &ListGPUsRequest{}
	resp, err := c.client.ListGPUs(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("gRPC ListGPUs failed: %w", err)
	}

	gpus := make([]GPUInfo, len(resp.Gpus))
	for i, gpu := range resp.Gpus {
		gpus[i] = GPUInfo{
			ID:                fmt.Sprintf("%d", gpu.Id),
			Name:              gpu.Name,
			ComputeCapability: gpu.ComputeCapability,
			TotalMemory:       gpu.TotalMemory,
			BusID:             gpu.BusId,
			Status:            gpu.Status,
		}
	}

	return gpus, nil
}

// GetGPUStats - Lấy GPU statistics (GPU stats query – truy vấn thống kê GPU)
func (c *GRPCClient) GetGPUStats(ctx context.Context, gpuID int) (*GPUStats, error) {
	req := &GetGPUStatsRequest{GpuId: int32(gpuID)}
	resp, err := c.client.GetGPUStats(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("gRPC GetGPUStats failed: %w", err)
	}

	stats := &GPUStats{
		ID:                int(resp.Id),
		Name:              resp.Name,
		Status:            resp.Status,
		Hashrate:          resp.Hashrate,
		Temperature:       int(resp.Temperature),
		FanSpeed:          int(resp.FanSpeed),
		PowerDraw:         int(resp.PowerDraw),
		PowerLimit:        int(resp.PowerLimit),
		ClockSpeed:        int(resp.ClockSpeed),
		MemoryUsed:        int(resp.MemoryUsed),
		MemoryTotal:       int(resp.MemoryTotal),
		Utilization:       int(resp.Utilization),
		MemoryUtilization: int(resp.MemoryUtilization),
	}

	return stats, nil
}

// ResetGPU - Reset GPU (GPU reset – khởi động lại GPU)
func (c *GRPCClient) ResetGPU(ctx context.Context, gpuID int) error {
	req := &ResetGPURequest{GpuId: int32(gpuID)}
	_, err := c.client.ResetGPU(ctx, req)
	if err != nil {
		return fmt.Errorf("gRPC ResetGPU failed: %w", err)
	}
	return nil
}

// ============================================================================
// Protobuf generated types stubs (cần generate từ .proto file)
// ============================================================================

// MinerServiceClient - Generated gRPC client interface
type MinerServiceClient interface {
	GetStatus(ctx context.Context, in *GetStatusRequest, opts ...grpc.CallOption) (*GetStatusResponse, error)
	StartMiner(ctx context.Context, in *StartMinerRequest, opts ...grpc.CallOption) (*StartMinerResponse, error)
	StopMiner(ctx context.Context, in *StopMinerRequest, opts ...grpc.CallOption) (*StopMinerResponse, error)
	SetStealth(ctx context.Context, in *SetStealthRequest, opts ...grpc.CallOption) (*SetStealthResponse, error)
	GetStealthStatus(ctx context.Context, in *GetStealthStatusRequest, opts ...grpc.CallOption) (*GetStealthStatusResponse, error)
	ListGPUs(ctx context.Context, in *ListGPUsRequest, opts ...grpc.CallOption) (*ListGPUsResponse, error)
	GetGPUStats(ctx context.Context, in *GetGPUStatsRequest, opts ...grpc.CallOption) (*GetGPUStatsResponse, error)
	ResetGPU(ctx context.Context, in *ResetGPURequest, opts ...grpc.CallOption) (*ResetGPUResponse, error)
}

// Request/Response types (generated từ protobuf)
type (
	GetStatusRequest           struct{}
	GetStatusResponse          struct {
		Running        bool
		Ready          bool
		Pid            int32
		UptimeSeconds  int64
		TotalHashrate  float64
		SharesAccepted int64
		SharesRejected int64
		Gpus           []*GPUStatusProto
	}

	GPUStatusProto struct {
		Id          int32
		Name        string
		Hashrate    float64
		Temperature int32
		PowerDraw   int32
		MemoryUsed  int32
	}

	StartMinerRequest  struct {
		ConfigPath string
		Wallet     string
		Pool       string
	}
	StartMinerResponse struct{}

	StopMinerRequest struct {
		TimeoutSeconds int32
		Force          bool
	}
	StopMinerResponse struct{}

	SetStealthRequest struct {
		Enabled bool
	}
	SetStealthResponse struct{}

	GetStealthStatusRequest  struct{}
	GetStealthStatusResponse struct {
		Enabled bool
	}

	ListGPUsRequest struct{}
	ListGPUsResponse struct {
		Gpus []*GPUInfoProto
	}

	GPUInfoProto struct {
		Id                int32
		Name              string
		ComputeCapability string
		TotalMemory       int64
		BusId             string
		Status            string
	}

	GetGPUStatsRequest struct {
		GpuId int32
	}
	GetGPUStatsResponse struct {
		Id                  int32
		Name                string
		Status              string
		Hashrate            float64
		Temperature         int32
		FanSpeed            int32
		PowerDraw           int32
		PowerLimit          int32
		ClockSpeed          int32
		MemoryUsed          int32
		MemoryTotal         int32
		Utilization         int32
		MemoryUtilization   int32
	}

	ResetGPURequest  struct {
		GpuId int32
	}
	ResetGPUResponse struct{}
)

// NewMinerServiceClient - Constructor stub (cần thay bằng generated code)
func NewMinerServiceClient(cc grpc.ClientConnInterface) MinerServiceClient {
	panic("implement với protobuf generated code")
}
