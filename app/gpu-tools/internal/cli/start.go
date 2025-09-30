// Package cli - Start command implementation
// Start: Khởi động GPU miner process với configuration
package cli

import (
	"context"
	"fmt"
	"time"

	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/spf13/cobra"
)

var startCmd = &cobra.Command{
	Use:   "start [flags]",
	Short: "Start GPU miner",
	Long: `Start GPU mining process với configuration được chỉ định.
Kiểm tra miner đã running trước khi start, hỗ trợ wait for ready.`,
	Example: `  gpu-ctl start --config /etc/miner/config.yaml
  gpu-ctl start --wallet 0xABC123... --pool stratum+tcp://pool.com:3333`,
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		grpcAddr, _ := cmd.Flags().GetString("grpc-addr")
		grpcClient, err := client.NewGRPCClient(grpcAddr)
		if err != nil {
			return fmt.Errorf("failed to create gRPC client: %w", err)
		}
		defer grpcClient.Close()

		// Kiểm tra miner đã running chưa
		status, err := grpcClient.GetStatus(ctx)
		if err == nil && status.Running {
			return fmt.Errorf("miner is already running (PID: %d)", status.PID)
		}

		// Start miner
		configPath, _ := cmd.Flags().GetString("config")
		wait, _ := cmd.Flags().GetBool("wait")

		req := &client.StartRequest{
			ConfigPath: configPath,
		}

		if err := grpcClient.Start(ctx, req); err != nil {
			return fmt.Errorf("failed to start miner: %w", err)
		}

		fmt.Println("✓ Miner started successfully")

		if wait {
			fmt.Println("Waiting for miner to be ready...")
			if err := waitForReady(ctx, grpcClient); err != nil {
				return fmt.Errorf("miner failed to become ready: %w", err)
			}
			fmt.Println("✓ Miner is ready")
		}

		return nil
	},
}

func init() {
	startCmd.Flags().String("config", "", "Path to miner config file")
	startCmd.Flags().Bool("wait", false, "Wait for miner to be ready")
	startCmd.Flags().String("wallet", "", "Mining wallet address")
	startCmd.Flags().String("pool", "", "Mining pool URL")
}

// waitForReady - Đợi miner sẵn sàng (health check polling – kiểm tra chu kỳ)
func waitForReady(ctx context.Context, client *client.GRPCClient) error {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
			status, err := client.GetStatus(ctx)
			if err != nil {
				continue
			}
			if status.Ready {
				return nil
			}
		}
	}
}
