// Package cli - Status command implementation
// Status: Hiển thị trạng thái miner và GPU health
package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/olekukonko/tablewriter"
	"github.com/opus-gpu/gpu-tools/internal/client"
	"github.com/spf13/cobra"
	"gopkg.in/yaml.v3"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show miner and GPU status",
	Long:  `Display current miner status, GPU health, hashrate, và uptime.`,
	Example: `  gpu-ctl status
  gpu-ctl status --output json
  gpu-ctl status --watch`,
	RunE: func(cmd *cobra.Command, args []string) error {
		watch, _ := cmd.Flags().GetBool("watch")
		interval, _ := cmd.Flags().GetDuration("interval")
		outputFormat, _ := cmd.Flags().GetString("output")

		if watch {
			return watchStatus(interval, outputFormat)
		}

		return printStatus(outputFormat)
	},
}

func init() {
	statusCmd.Flags().Bool("watch", false, "Watch status continuously")
	statusCmd.Flags().Duration("interval", 2*time.Second, "Watch interval")
}

// printStatus - In trạng thái một lần (status display – hiển thị trạng thái)
func printStatus(format string) error {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	grpcAddr := rootCmd.PersistentFlags().Lookup("grpc-addr").Value.String()
	grpcClient, err := client.NewGRPCClient(grpcAddr)
	if err != nil {
		return fmt.Errorf("failed to create gRPC client: %w", err)
	}
	defer grpcClient.Close()

	status, err := grpcClient.GetStatus(ctx)
	if err != nil {
		return fmt.Errorf("failed to get status: %w", err)
	}

	switch format {
	case "json":
		return printJSON(status)
	case "yaml":
		return printYAML(status)
	default:
		return printTable(status)
	}
}

// printTable - In table format (table output – định dạng bảng)
func printTable(status *client.MinerStatus) error {
	table := tablewriter.NewWriter(os.Stdout)
	table.SetHeader([]string{"Metric", "Value"})
	table.SetBorder(false)

	data := [][]string{
		{"Status", formatStatus(status.Running)},
		{"PID", fmt.Sprintf("%d", status.PID)},
		{"Uptime", formatDuration(status.Uptime)},
		{"Total Hashrate", fmt.Sprintf("%.2f MH/s", status.TotalHashrate)},
		{"Shares Accepted", fmt.Sprintf("%d", status.SharesAccepted)},
		{"Shares Rejected", fmt.Sprintf("%d", status.SharesRejected)},
		{"GPU Count", fmt.Sprintf("%d", len(status.GPUs))},
	}

	table.AppendBulk(data)
	table.Render()

	// GPU details table
	if len(status.GPUs) > 0 {
		fmt.Println("\nGPU Details:")
		gpuTable := tablewriter.NewWriter(os.Stdout)
		gpuTable.SetHeader([]string{"ID", "Name", "Hashrate", "Temp", "Power", "Mem Used"})

		for _, gpu := range status.GPUs {
			gpuTable.Append([]string{
				fmt.Sprintf("%d", gpu.ID),
				gpu.Name,
				fmt.Sprintf("%.2f MH/s", gpu.Hashrate),
				fmt.Sprintf("%d°C", gpu.Temperature),
				fmt.Sprintf("%dW", gpu.PowerDraw),
				fmt.Sprintf("%dMB", gpu.MemoryUsed),
			})
		}
		gpuTable.Render()
	}

	return nil
}

// printJSON - In JSON format
func printJSON(status *client.MinerStatus) error {
	encoder := json.NewEncoder(os.Stdout)
	encoder.SetIndent("", "  ")
	return encoder.Encode(status)
}

// printYAML - In YAML format
func printYAML(status *client.MinerStatus) error {
	encoder := yaml.NewEncoder(os.Stdout)
	defer encoder.Close()
	return encoder.Encode(status)
}

// watchStatus - Watch status liên tục (continuous monitoring – giám sát liên tục)
func watchStatus(interval time.Duration, format string) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		// Clear screen
		fmt.Print("\033[H\033[2J")
		fmt.Printf("Last update: %s\n\n", time.Now().Format(time.RFC3339))

		if err := printStatus(format); err != nil {
			fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		}

		<-ticker.C
	}
}

// Helper functions
func formatStatus(running bool) string {
	if running {
		return "✓ Running"
	}
	return "✗ Stopped"
}

func formatDuration(d time.Duration) string {
	hours := int(d.Hours())
	minutes := int(d.Minutes()) % 60
	return fmt.Sprintf("%dh %dm", hours, minutes)
}
