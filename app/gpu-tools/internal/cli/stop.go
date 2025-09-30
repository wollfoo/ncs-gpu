// Package cli - Stop command implementation
// Stop: Graceful shutdown của GPU miner
package cli

import (
	"context"
	"fmt"
	"time"

	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/spf13/cobra"
)

var stopCmd = &cobra.Command{
	Use:   "stop [flags]",
	Short: "Stop GPU miner gracefully",
	Long: `Stop GPU mining process với graceful shutdown.
Gửi SIGTERM, đợi miner cleanup, timeout thì force kill.`,
	Example: `  gpu-ctl stop
  gpu-ctl stop --timeout 60s
  gpu-ctl stop --force`,
	RunE: func(cmd *cobra.Command, args []string) error {
		timeout, _ := cmd.Flags().GetDuration("timeout")
		force, _ := cmd.Flags().GetBool("force")

		ctx, cancel := context.WithTimeout(context.Background(), timeout+10*time.Second)
		defer cancel()

		grpcAddr, _ := cmd.Flags().GetString("grpc-addr")
		grpcClient, err := client.NewGRPCClient(grpcAddr)
		if err != nil {
			return fmt.Errorf("failed to create gRPC client: %w", err)
		}
		defer grpcClient.Close()

		// Kiểm tra miner có đang chạy không
		status, err := grpcClient.GetStatus(ctx)
		if err != nil || !status.Running {
			return fmt.Errorf("miner is not running")
		}

		fmt.Printf("Stopping miner (PID: %d)...\n", status.PID)

		req := &client.StopRequest{
			Timeout: timeout,
			Force:   force,
		}

		if err := grpcClient.Stop(ctx, req); err != nil {
			return fmt.Errorf("failed to stop miner: %w", err)
		}

		fmt.Println("✓ Miner stopped successfully")
		return nil
	},
}

func init() {
	stopCmd.Flags().Duration("timeout", 30*time.Second,
		"Graceful shutdown timeout")
	stopCmd.Flags().Bool("force", false,
		"Force kill miner immediately (SIGKILL)")
}
