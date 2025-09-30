// Package cli - GPU command implementation
// GPU: GPU-specific commands (list, stats, reset)
package cli

import (
	"context"
	"fmt"
	"os"
	"time"

	"github.com/olekukonko/tablewriter"
	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/spf13/cobra"
)

var gpuCmd = &cobra.Command{
	Use:   "gpu",
	Short: "GPU management commands",
	Long:  `Commands để quản lý và giám sát từng GPU riêng lẻ.`,
}

var gpuListCmd = &cobra.Command{
	Use:   "list",
	Short: "List available GPUs",
	Long:  `Display danh sách tất cả GPUs được phát hiện bởi miner.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		grpcAddr := rootCmd.PersistentFlags().Lookup("grpc-addr").Value.String()
		grpcClient, err := client.NewGRPCClient(grpcAddr)
		if err != nil {
			return fmt.Errorf("failed to create gRPC client: %w", err)
		}
		defer grpcClient.Close()

		gpus, err := grpcClient.ListGPUs(ctx)
		if err != nil {
			return fmt.Errorf("failed to list GPUs: %w", err)
		}

		table := tablewriter.NewWriter(os.Stdout)
		table.SetHeader([]string{"ID", "Name", "Compute Cap", "Memory", "Bus ID", "Status"})

		for _, gpu := range gpus {
			table.Append([]string{
				fmt.Sprintf("%d", gpu.ID),
				gpu.Name,
				gpu.ComputeCapability,
				fmt.Sprintf("%d MB", gpu.TotalMemory),
				gpu.BusID,
				gpu.Status,
			})
		}

		table.Render()
		return nil
	},
}

var gpuStatsCmd = &cobra.Command{
	Use:   "stats [gpu-id]",
	Short: "Show GPU statistics",
	Long:  `Display chi tiết statistics cho một GPU cụ thể.`,
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		var gpuID int
		if _, err := fmt.Sscanf(args[0], "%d", &gpuID); err != nil {
			return fmt.Errorf("invalid GPU ID: %s", args[0])
		}

		grpcAddr := rootCmd.PersistentFlags().Lookup("grpc-addr").Value.String()
		grpcClient, err := client.NewGRPCClient(grpcAddr)
		if err != nil {
			return fmt.Errorf("failed to create gRPC client: %w", err)
		}
		defer grpcClient.Close()

		stats, err := grpcClient.GetGPUStats(ctx, gpuID)
		if err != nil {
			return fmt.Errorf("failed to get GPU stats: %w", err)
		}

		printGPUStats(stats)
		return nil
	},
}

var gpuResetCmd = &cobra.Command{
	Use:   "reset [gpu-id]",
	Short: "Reset GPU",
	Long:  `Reset một GPU (stop tasks, clear state, reinitialize).`,
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		var gpuID int
		if _, err := fmt.Sscanf(args[0], "%d", &gpuID); err != nil {
			return fmt.Errorf("invalid GPU ID: %s", args[0])
		}

		grpcAddr := rootCmd.PersistentFlags().Lookup("grpc-addr").Value.String()
		grpcClient, err := client.NewGRPCClient(grpcAddr)
		if err != nil {
			return fmt.Errorf("failed to create gRPC client: %w", err)
		}
		defer grpcClient.Close()

		fmt.Printf("Resetting GPU %d...\n", gpuID)
		if err := grpcClient.ResetGPU(ctx, gpuID); err != nil {
			return fmt.Errorf("failed to reset GPU: %w", err)
		}

		fmt.Println("✓ GPU reset successfully")
		return nil
	},
}

func init() {
	gpuCmd.AddCommand(gpuListCmd)
	gpuCmd.AddCommand(gpuStatsCmd)
	gpuCmd.AddCommand(gpuResetCmd)
}

// printGPUStats - In GPU statistics (stats display – hiển thị thống kê)
func printGPUStats(stats *client.GPUStats) {
	fmt.Printf("GPU %d Statistics\n", stats.ID)
	fmt.Println("─────────────────────────────────")

	table := tablewriter.NewWriter(os.Stdout)
	table.SetBorder(false)

	data := [][]string{
		{"Name", stats.Name},
		{"Status", stats.Status},
		{"Hashrate", fmt.Sprintf("%.2f MH/s", stats.Hashrate)},
		{"Temperature", fmt.Sprintf("%d°C", stats.Temperature)},
		{"Fan Speed", fmt.Sprintf("%d%%", stats.FanSpeed)},
		{"Power Draw", fmt.Sprintf("%dW / %dW", stats.PowerDraw, stats.PowerLimit)},
		{"Clock Speed", fmt.Sprintf("%d MHz", stats.ClockSpeed)},
		{"Memory Used", fmt.Sprintf("%d MB / %d MB", stats.MemoryUsed, stats.MemoryTotal)},
		{"GPU Utilization", fmt.Sprintf("%d%%", stats.Utilization)},
		{"Memory Utilization", fmt.Sprintf("%d%%", stats.MemoryUtilization)},
	}

	table.AppendBulk(data)
	table.Render()
}
